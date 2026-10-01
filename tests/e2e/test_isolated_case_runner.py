"""Service-free orchestration contracts for the one-case private runner."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from .run_ci import CASES
from .support import isolated_case_runner as runner
from .support.environment import SetupError
from .support.isolated_fault_result import FAULT_CASE

REVISION = "a" * 40


def report(case, when, outcome="passed"):
    return SimpleNamespace(nodeid=case, when=when, outcome=outcome)


def test_standalone_gate_requires_one_exact_case_environment():
    case = CASES[0]
    gate = runner.StandaloneCaseGate(case)
    environment = object()
    gate.pytest_collection_finish(SimpleNamespace(items=[SimpleNamespace(nodeid=case)]))
    gate.pytest_runtest_call(SimpleNamespace(funcargs={"environment": environment}))
    for when in ("setup", "call", "teardown"):
        gate.pytest_runtest_logreport(report(case, when))
    assert gate.exact_pass(0)
    gate.pytest_runtest_logreport(report(case, "call"))
    assert not gate.exact_pass(0)


@pytest.mark.parametrize("mutation", ["foreign", "collection", "missing_environment", "skip", "exit"])
def test_standalone_gate_rejects_inexact_execution(mutation):
    case = CASES[0]
    gate = runner.StandaloneCaseGate(case)
    collected = [] if mutation == "collection" else [SimpleNamespace(nodeid=case)]
    gate.pytest_collection_finish(SimpleNamespace(items=collected))
    if mutation != "missing_environment":
        gate.pytest_runtest_call(SimpleNamespace(funcargs={"environment": object()}))
    for when in ("setup", "call", "teardown"):
        gate.pytest_runtest_logreport(report(
            "tests/e2e/foreign.py::test_foreign" if mutation == "foreign" and when == "call" else case,
            when, "skipped" if mutation == "skip" and when == "call" else "passed"))
    assert not gate.exact_pass(1 if mutation == "exit" else 0)


def test_runner_rejects_unallowlisted_or_unsafe_root_before_creation(tmp_path, monkeypatch):
    repository = tmp_path / "repo"
    repository.mkdir()
    monkeypatch.setattr(runner, "REPO", repository)
    profile = tmp_path / "profile.json"
    profile.write_text("{}")
    with pytest.raises(SetupError, match="allowlisted"):
        runner.run_isolated_case(profile, tmp_path / "private", "foreign::case", REVISION)
    with pytest.raises(SetupError, match="new absolute"):
        runner.run_isolated_case(profile, "relative-private", CASES[0], REVISION)
    with pytest.raises(SetupError, match="outside"):
        runner.run_isolated_case(profile, repository / "private", CASES[0], REVISION)
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(SetupError, match="new absolute"):
        runner.run_isolated_case(profile, existing, CASES[0], REVISION)


def configure_success(monkeypatch, tmp_path, case, *, fault=False):
    repository = tmp_path / "repo"
    repository.mkdir()
    profile_source = tmp_path / "profile.json"
    profile_source.write_text("{}")
    monkeypatch.setattr(runner, "REPO", repository)
    monkeypatch.setattr(runner, "_repository_identity", lambda: (REVISION, False))
    monkeypatch.setattr(runner, "_validated_profile",
                        lambda *args, **kwargs: (b"{}", {"deadline_scale": 1}, {"inputs": "exact"}))
    monkeypatch.setattr(runner, "inputs_match",
                        lambda identities, manifest, revision, dirty, scale:
                        identities == {"inputs": "exact"} and manifest == {"fixture": "exact"}
                        and revision == REVISION and dirty is False and scale == 1)
    calls = []

    def inspect(artifact, junit, pytest_log, expected_case, revision):
        calls.append(("generic", Path(artifact), expected_case, revision))
        assert Path(junit).is_file() and "PRIVATE_MARKER" in Path(pytest_log).read_text()
        return {"version": 1, "status": "accepted", "scope": "generic-test-scope"}

    def inspect_fault(artifact, junit, pytest_log, revision):
        calls.append(("fault", Path(artifact), FAULT_CASE, revision))
        assert Path(junit).is_file() and "PRIVATE_MARKER" in Path(pytest_log).read_text()
        return {"version": 1, "status": "accepted", "scope": "fault-test-scope"}

    monkeypatch.setattr(runner, "inspect_isolated_case", inspect)
    monkeypatch.setattr(runner, "inspect_isolated_fault", inspect_fault)

    def fake_pytest(args, plugins):
        assert args[0] == case
        assert [arg for arg in args if "::" in arg] == [case]
        assert "PYTEST_ADDOPTS" not in runner.os.environ
        assert "PYTEST_PLUGINS" not in runner.os.environ
        assert runner.os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
        local_profile = Path(args[args.index("--e2e-profile") + 1])
        artifacts_root = Path(json.loads(local_profile.read_text())["artifacts"])
        artifact = artifacts_root / "sapphire-e2e-fixture"
        artifact.mkdir(parents=True)
        (artifact / "manifest.json").write_text('{"fixture":"exact"}')
        environment = SimpleNamespace(artifacts=artifact)
        gate = plugins[0]
        gate.pytest_collection_finish(SimpleNamespace(items=[SimpleNamespace(nodeid=case)]))
        gate.pytest_runtest_call(SimpleNamespace(funcargs={"environment": environment}))
        for when in ("setup", "call", "teardown"):
            gate.pytest_runtest_logreport(report(case, when))
        junit = Path(args[args.index("--junitxml") + 1])
        junit.write_text("<testsuites />")
        print("PRIVATE_MARKER")
        return 0

    monkeypatch.setattr(pytest, "main", fake_pytest)
    return profile_source, calls


@pytest.mark.parametrize("case,expected_inspector", [(CASES[0], "generic"), (FAULT_CASE, "fault")])
def test_runner_executes_one_case_binds_inputs_and_uses_required_inspector(
        tmp_path, monkeypatch, case, expected_inspector):
    profile, calls = configure_success(monkeypatch, tmp_path, case)
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k PRIVATE_MARKER")
    monkeypatch.setenv("PYTEST_PLUGINS", "PRIVATE_MARKER")
    private = tmp_path / "private"
    cwd = Path.cwd()
    assert runner.run_isolated_case(profile, private, case, REVISION) == 0
    assert Path.cwd() == cwd
    assert runner.os.environ["PYTEST_ADDOPTS"] == "-k PRIVATE_MARKER"
    assert runner.os.environ["PYTEST_PLUGINS"] == "PRIVATE_MARKER"
    result = json.loads((private / "runner-result.json").read_text())
    assert result == {
        "version": 1, "status": "accepted", "stage": "verified", "scope": runner.SCOPE,
        "case": case, "source_revision": REVISION, "source_dirty": False,
        "pytest_exit_code": 0, "exact_single_case_verified": True,
        "profile_inputs_verified": True,
        "inspection_sha256": runner._sha256(private / "inspection.json"),
        "inspection_scope": "fault-test-scope" if case == FAULT_CASE else "generic-test-scope",
        "short_feedback_only": True,
        "generic_scenario_semantics_independently_verified": False,
        "specialized_fault_inspection_applied": case == FAULT_CASE,
        "combined_gate_verified": False,
    }
    assert calls[0][0] == expected_inspector and calls[0][2:] == (case, REVISION)
    assert len(list((private / "artifacts").iterdir())) == 1


def test_runner_preserves_private_failure_without_inspection(tmp_path, monkeypatch):
    case = CASES[0]
    profile, calls = configure_success(monkeypatch, tmp_path, case)

    def fail(*args, **kwargs):
        raise ValueError("PRIVATE_FAILURE_MARKER")

    monkeypatch.setattr(pytest, "main", fail)
    private = tmp_path / "private"
    assert runner.run_isolated_case(profile, private, case, REVISION) == 1
    result = json.loads((private / "runner-result.json").read_text())
    assert result["status"] == "failed" and result["stage"] == "suite"
    assert "PRIVATE_FAILURE_MARKER" not in json.dumps(result)
    assert "PRIVATE_FAILURE_MARKER" in (private / "entry-error.log").read_text()
    assert not (private / "inspection.json").exists() and calls == []


@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_runner_attempts_captured_owned_cleanup_once_after_propagated_failure(
        tmp_path, monkeypatch, cleanup_fails):
    case = CASES[0]
    profile, _ = configure_success(monkeypatch, tmp_path, case)

    class CapturedEnvironment:
        _closed = False
        calls = 0
        def close(self):
            self.calls += 1
            if cleanup_fails:
                raise KeyboardInterrupt("PRIVATE_CLEANUP_MARKER")
            self._closed = True

    environment = CapturedEnvironment()
    def interrupt(args, plugins):
        plugins[0].environment = environment
        raise KeyboardInterrupt("PRIVATE_RUNNER_INTERRUPT")

    monkeypatch.setattr(pytest, "main", interrupt)
    private = tmp_path / "private"
    assert runner.run_isolated_case(profile, private, case, REVISION) == 1
    result = json.loads((private / "runner-result.json").read_text())
    assert environment.calls == 1
    assert result["captured_environment_cleanup_attempted"] is True
    assert result["captured_environment_cleanup_failed"] is cleanup_fails
    assert "PRIVATE_RUNNER_INTERRUPT" in (private / "entry-error.log").read_text()
    if cleanup_fails:
        assert "PRIVATE_CLEANUP_MARKER" in (private / "cleanup-error.log").read_text()
    else:
        assert not (private / "cleanup-error.log").exists()


def test_runner_rejects_captured_cleanup_that_returns_without_closure(tmp_path, monkeypatch):
    case = CASES[0]
    profile, _ = configure_success(monkeypatch, tmp_path, case)

    class IncompleteEnvironment:
        _closed = False
        calls = 0
        def close(self):
            self.calls += 1

    environment = IncompleteEnvironment()
    def interrupt(args, plugins):
        plugins[0].environment = environment
        raise RuntimeError("runner interruption")

    monkeypatch.setattr(pytest, "main", interrupt)
    private = tmp_path / "private"
    assert runner.run_isolated_case(profile, private, case, REVISION) == 1
    result = json.loads((private / "runner-result.json").read_text())
    assert environment.calls == 1 and result["captured_environment_cleanup_failed"] is True
    assert "cleanup remained incomplete" in (private / "cleanup-error.log").read_text()


def test_runner_rejects_source_change_after_private_inspection(tmp_path, monkeypatch):
    case = CASES[0]
    profile, _ = configure_success(monkeypatch, tmp_path, case)
    identities = iter(((REVISION, False), (REVISION, True)))
    monkeypatch.setattr(runner, "_repository_identity", lambda: next(identities))
    private = tmp_path / "private"
    assert runner.run_isolated_case(profile, private, case, REVISION) == 1
    result = json.loads((private / "runner-result.json").read_text())
    assert result["status"] == "failed" and result["stage"] == "inspection"
    assert not (private / "inspection.json").exists()
    assert "source changed" in (private / "entry-error.log").read_text()


def test_runner_requires_exact_clean_reviewed_revision_before_root(tmp_path, monkeypatch):
    repository = tmp_path / "repo"
    repository.mkdir()
    profile = tmp_path / "profile.json"
    profile.write_text("{}")
    monkeypatch.setattr(runner, "REPO", repository)
    monkeypatch.setattr(runner, "_validated_profile",
                        lambda *args, **kwargs: (b"{}", {"deadline_scale": 1}, {}))
    private = tmp_path / "private"
    monkeypatch.setattr(runner, "_repository_identity", lambda: ("b" * 40, False))
    with pytest.raises(SetupError, match="exact clean"):
        runner.run_isolated_case(profile, private, CASES[0], REVISION)
    assert not private.exists()
    monkeypatch.setattr(runner, "_repository_identity", lambda: (REVISION, True))
    with pytest.raises(SetupError, match="exact clean"):
        runner.run_isolated_case(profile, private, CASES[0], REVISION)
    assert not private.exists()

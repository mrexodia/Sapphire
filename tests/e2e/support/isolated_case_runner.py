"""Produce and inspect one private standalone allowlisted isolated-case run.

This is a short-feedback lane, not a substitute for the combined acceptance gate.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import traceback

from ..run_ci import CASES, inputs_match
from .ci_profile_result import _validated_profile
from .environment import REPO, SetupError
from .isolated_case_result import inspect_isolated_case
from .isolated_fault_result import FAULT_CASE, inspect_isolated_fault

SCOPE = "single-allowlisted-isolated-case-private-runner-v1"


def _hex(value, length):
    return (isinstance(value, str) and len(value) == length
            and all(char in "0123456789abcdef" for char in value))


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _repository_identity():
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    dirty = bool(subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=REPO, text=True))
    return revision, dirty


def _new_external_root(path):
    requested = Path(path)
    if (not requested.is_absolute() or requested.exists() or requested.is_symlink()
            or not requested.parent.is_dir() or requested.parent.is_symlink()):
        raise SetupError("standalone case private root must be a new absolute directory")
    resolved = requested.resolve()
    repository = Path(REPO).resolve()
    if resolved == repository or repository in resolved.parents:
        raise SetupError("standalone case private root must be outside the repository")
    return resolved


class StandaloneCaseGate:
    """Retain only exact collection/outcome and the one owned fixture reference."""
    def __init__(self, expected_case):
        if expected_case not in CASES:
            raise SetupError("standalone case is not allowlisted")
        self.expected_case = expected_case
        self.collected = []
        self.reports = {phase: [] for phase in ("setup", "call", "teardown")}
        self.unexpected = 0
        self.environment = None

    def pytest_collection_finish(self, session):
        self.collected = [item.nodeid for item in session.items]

    def pytest_runtest_logreport(self, report):
        if report.nodeid != self.expected_case or report.when not in self.reports:
            self.unexpected += 1
            return
        outcome = report.outcome if report.outcome in {"passed", "failed", "skipped"} else "invalid"
        self.reports[report.when].append(outcome)

    def pytest_runtest_call(self, item):
        environment = item.funcargs.get("environment")
        if environment is None:
            self.unexpected += 1
        elif self.environment is not None and self.environment is not environment:
            self.unexpected += 1
        else:
            self.environment = environment

    def exact_pass(self, exit_code):
        return (exit_code == 0 and self.collected == [self.expected_case]
                and not self.unexpected
                and all(values == ["passed"] for values in self.reports.values())
                and self.environment is not None)


def run_isolated_case(profile_path, private_root, expected_case, expected_revision,
                      *, worker=None, binaries=None, suffix=None):
    if expected_case not in CASES:
        raise SetupError("standalone case is not allowlisted")
    if not _hex(expected_revision, 40):
        raise SetupError("expected standalone case revision must be exact lowercase git identity")
    root = _new_external_root(private_root)
    _, profile, identities = _validated_profile(
        profile_path, worker=worker, binaries=binaries, suffix=suffix)
    revision, dirty = _repository_identity()
    if revision != expected_revision or dirty:
        raise SetupError("standalone case requires the exact clean reviewed revision")

    root.mkdir(mode=0o700)
    artifacts_root = root / "artifacts"
    local_profile = root / "profile.json"
    pytest_log = root / "pytest.log"
    junit = root / "live.xml"
    inspection_path = root / "inspection.json"
    result_path = root / "runner-result.json"
    report = {
        "version": 1, "status": "failed", "stage": "preflight", "scope": SCOPE,
        "case": expected_case, "source_revision": revision, "source_dirty": False,
    }
    gate = None

    try:
        profile["artifacts"] = str(artifacts_root)
        local_profile.write_text(json.dumps(profile), encoding="utf-8")
        report["stage"] = "suite"
        saved = {key: os.environ.get(key) for key in
                 ("PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PYTEST_DISABLE_PLUGIN_AUTOLOAD")}
        original_cwd = Path.cwd()
        try:
            os.environ.pop("PYTEST_ADDOPTS", None)
            os.environ.pop("PYTEST_PLUGINS", None)
            os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
            os.chdir(REPO)
            with pytest_log.open("x", encoding="utf-8") as log, \
                    contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                import pytest
                gate = StandaloneCaseGate(expected_case)
                code = pytest.main([
                    expected_case, "--rootdir", str(REPO),
                    "--e2e-profile", str(local_profile), "-q", "--capture=sys",
                    "-o", "addopts=", "-p", "no:cacheprovider", "--strict-markers",
                    "--junitxml", str(junit),
                ], plugins=[gate])
        finally:
            os.chdir(original_cwd)
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        report["pytest_exit_code"] = int(code)
        if not gate.exact_pass(code):
            raise SetupError("standalone case did not produce one exact passing execution")
        try:
            entries = list(artifacts_root.iterdir())
        except OSError as error:
            raise SetupError("standalone case artifact root is unavailable") from error
        if (artifacts_root.is_symlink() or len(entries) != 1 or entries[0].is_symlink()
                or not entries[0].is_dir()
                or gate.environment.artifacts.resolve() != entries[0].resolve()):
            raise SetupError("standalone case artifact ownership is ambiguous")
        artifact = entries[0]
        try:
            manifest = json.loads((artifact / "manifest.json").read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise SetupError("standalone case manifest is unreadable") from error
        if not inputs_match(identities, manifest, revision, False,
                            profile.get("deadline_scale", 1)):
            raise SetupError("standalone case inputs do not match the reviewed profile")

        report["stage"] = "inspection"
        if expected_case == FAULT_CASE:
            proof = inspect_isolated_fault(artifact, junit, pytest_log, revision)
        else:
            proof = inspect_isolated_case(
                artifact, junit, pytest_log, expected_case, revision)
        final_revision, final_dirty = _repository_identity()
        if final_revision != revision or final_dirty:
            raise SetupError("standalone case source changed during execution or inspection")
        with inspection_path.open("x", encoding="utf-8") as stream:
            json.dump(proof, stream, indent=2)
            stream.write("\n")
        report.update({
            "status": "accepted", "stage": "verified", "pytest_exit_code": 0,
            "exact_single_case_verified": True, "profile_inputs_verified": True,
            "inspection_sha256": _sha256(inspection_path),
            "inspection_scope": proof["scope"],
            "short_feedback_only": True,
            "generic_scenario_semantics_independently_verified": False,
            "specialized_fault_inspection_applied": expected_case == FAULT_CASE,
            "combined_gate_verified": False,
        })
    except BaseException:
        report["status"] = "failed"
        with (root / "entry-error.log").open("w", encoding="utf-8") as log:
            traceback.print_exc(file=log)
        environment = gate.environment if gate is not None else None
        if environment is not None and not getattr(environment, "_closed", False):
            report["captured_environment_cleanup_attempted"] = True
            try:
                environment.close()
                if not getattr(environment, "_closed", False):
                    raise SetupError("captured standalone environment cleanup remained incomplete")
                report["captured_environment_cleanup_failed"] = False
            except BaseException:
                report["captured_environment_cleanup_failed"] = True
                with (root / "cleanup-error.log").open("w", encoding="utf-8") as log:
                    traceback.print_exc(file=log)
    finally:
        try:
            with result_path.open("x", encoding="utf-8") as stream:
                json.dump(report, stream, indent=2)
                stream.write("\n")
        except OSError:
            return 1
    return 0 if report["status"] == "accepted" else 1

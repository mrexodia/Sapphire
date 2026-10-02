"""Synthetic ownership/fault contracts; none of these are gameplay evidence."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from . import run_workload as runner
from .support.workload import build_plan


class Harness:
    def __init__(self, monkeypatch, tmp_path, module=runner):
        self.module, self.events, self.faults = module, [], {}
        self.catalog = {"route": [[0, 0, 0], [0.5, 0, 0]]}
        self.plan = build_plan(self.catalog, "explore", 42, 2, 4)
        self.root, self.artifacts = tmp_path / "runtime", tmp_path / "artifacts"
        self.root.mkdir()
        self.artifacts.mkdir()
        self.profile = tmp_path / "profile.json"
        self.profile.write_text(json.dumps({"quest_catalog": "synthetic"}))
        harness = self

        class Environment:
            def __init__(self, profile):
                harness.call("allocate")
                self.root, self.artifacts = harness.root, harness.artifacts
                self.worker = "synthetic-worker"
                self.redactions = {"private-session-token"}
                self.processes = {"world": SimpleNamespace(pid=12)}

            def start(self):
                harness.call("environment.start")

            def check_alive(self):
                harness.call("environment.check_alive")

            def close(self):
                harness.call("environment.close")
                if not harness.faults.get("retain_root"):
                    self.root.rmdir()

        class Worker:
            def __init__(self, *args):
                harness.call("worker.construct")
                self.process = SimpleNamespace(pid=13)

            def __enter__(self):
                harness.call("worker.enter")
                return self

            def __exit__(self, *args):
                harness.call("worker.close")

        class Metrics:
            def __init__(self, processes):
                harness.call("metrics.construct")
                self.processes = processes
                self.samples = [{"processes": {name: {"rss_bytes": 100, "cpu_seconds": 1,
                                                      "private_commit_bytes": 200} for name in processes}}]
                if harness.faults.get("bad_resource_summary"):
                    self.samples = [{"processes": {"world": {"rss_bytes": 100}}}]
                if harness.faults.get("unserializable_samples"):
                    self.samples = [{"unserializable": object()}]

            def start(self):
                harness.call("metrics.start")

            def stop(self):
                harness.call("metrics.stop")

        class Workload:
            def __init__(self, *args):
                harness.call("workload.construct")
                self.bots = [1, 2]
                self.outcomes = [{"status": "passed", "duration_seconds": 0.2}]
                self.rounds, self.checkpoints = [], []
                if harness.faults.get("bad_action_summary"):
                    self.outcomes = [{"status": "passed"}]

            def setup(self):
                harness.call("workload.setup")

            def run(self):
                harness.call("workload.run")
                return {"actions": 1}

            def shutdown(self):
                harness.call("workload.shutdown")

        monkeypatch.setattr(module, "Environment", Environment)
        monkeypatch.setattr(module, "Worker", Worker)
        monkeypatch.setattr(module, "ProcessMetrics", Metrics)
        monkeypatch.setattr(module, "Workload", Workload)
        monkeypatch.setattr(module, "load_quest_catalog", lambda _: self.catalog)
        write_text, replace = Path.write_text, Path.replace

        def write(path, *args, **kwargs):
            if path.parent == harness.artifacts:
                harness.call("write:" + path.name)
            return write_text(path, *args, **kwargs)

        def rename(path, target):
            if path.parent == harness.artifacts:
                harness.call("replace:" + Path(target).name)
            return replace(path, target)

        monkeypatch.setattr(Path, "write_text", write)
        monkeypatch.setattr(Path, "replace", rename)

    def call(self, event):
        self.events.append(event)
        if event in self.faults:
            raise self.faults[event]

    def run(self):
        return self.module.run({}, self.catalog, self.plan, authorized=True)[0]

    def main(self):
        return self.module.main(["--profile", str(self.profile), "--bots", "2", "--steps", "4",
                                 "--authorize-disposable-environment"])


@pytest.fixture
def harness(monkeypatch, tmp_path):
    return Harness(monkeypatch, tmp_path)


def test_workload_requires_exact_authorization_before_environment(harness):
    with pytest.raises(ValueError, match="explicit disposable-environment authorization"):
        harness.module.run({}, harness.catalog, harness.plan)
    with pytest.raises(ValueError, match="explicit disposable-environment authorization"):
        harness.module.run({}, harness.catalog, harness.plan, authorized=1)
    assert not harness.events


def test_workload_cli_requires_authorization_before_profile_read(harness):
    with pytest.raises(SystemExit):
        harness.module.main(["--profile", "missing.json"])
    assert not harness.events


def test_success_closes_before_any_final_diagnostics(harness):
    result = harness.run()
    assert result["status"] == "passed" and result["runtime_removed"] is True
    assert result["execution_authorized"] is True
    assert not harness.root.exists()
    events = harness.events
    assert events.index("worker.close") < events.index("metrics.stop") < events.index("environment.close")
    assert events.index("environment.close") < events.index("write:resources.jsonl.tmp")
    assert events[-1] == "replace:result.json"
    assert json.loads((harness.artifacts / "result.json").read_text()) == result
    assert result["process_resources"]["world"] == {
        "peak_rss_bytes": 100, "cpu_seconds_delta": 0, "peak_private_commit_bytes": 200}


@pytest.mark.parametrize("point,stage", [
    ("write:plan.json", "setup"), ("environment.start", "setup"),
    ("worker.construct", "setup"), ("worker.enter", "setup"),
    ("workload.construct", "setup"), ("metrics.construct", "setup"),
    ("metrics.start", "setup"), ("workload.setup", "setup"),
    ("workload.run", "workflow"), ("workload.shutdown", "shutdown"),
    ("environment.check_alive", "shutdown"), ("worker.close", "shutdown"),
    ("metrics.stop", "sampling")])
def test_failures_cannot_skip_environment_close(harness, point, stage):
    harness.faults[point] = OSError("synthetic failure with private-session-token")
    result = harness.run()
    assert result["status"] == "failed" and result["failure_stage"] == stage
    assert harness.events.count("environment.close") == 1 and not harness.root.exists()
    assert "private-session-token" not in json.dumps(result)
    assert "private-session-token" not in (harness.artifacts / "result.json").read_text()


@pytest.mark.parametrize("point", ["workload.run", "worker.close", "metrics.stop"])
def test_interruptions_still_attempt_cleanup(harness, point):
    harness.faults[point] = KeyboardInterrupt()
    result = harness.run()
    assert result["status"] == "failed" and result["runtime_removed"] is True
    assert "interrupted" in json.dumps(result)


@pytest.mark.parametrize("name", ["resources.jsonl", "checkpoints.json", "rounds.json", "outcomes.json", "result.json"])
@pytest.mark.parametrize("operation", ["write", "replace"])
def test_each_artifact_failure_is_nonzero_after_cleanup(harness, capsys, name, operation):
    event = f"write:{name}.tmp" if operation == "write" else f"replace:{name}"
    harness.faults[event] = OSError("diagnostic disk unavailable")
    assert harness.main() == 1
    result = json.loads(capsys.readouterr().out)["result"]
    assert result["status"] == "failed" and result["runtime_removed"] is True
    assert result["artifact_errors"] == [{"artifact": name, "error": "diagnostic disk unavailable"}]
    assert harness.events.index("environment.close") < harness.events.index(event)
    assert not (harness.artifacts / name).exists()  # No partially written canonical 'passed' result.
    if name != "result.json":
        assert json.loads((harness.artifacts / "result.json").read_text())["status"] == "failed"


@pytest.mark.parametrize("fault", ["bad_resource_summary", "bad_action_summary", "unserializable_samples"])
def test_postprocessing_failures_are_explicit_and_cannot_strand_servers(harness, fault):
    harness.faults[fault] = True
    result = harness.run()
    assert result["status"] == "failed" and result["failure_stage"] == "artifacts"
    assert result["runtime_removed"] is True and not harness.root.exists()
    assert json.loads((harness.artifacts / "result.json").read_text())["status"] == "failed"


def test_complete_final_artifact_loss_still_returns_failure_after_cleanup(harness, capsys):
    names = ["resources.jsonl", "checkpoints.json", "rounds.json", "outcomes.json", "result.json"]
    harness.faults.update({f"write:{name}.tmp": OSError("disk full") for name in names})
    assert harness.main() == 1
    result = json.loads(capsys.readouterr().out)["result"]
    assert result["runtime_removed"] is True and not harness.root.exists()
    assert [row["artifact"] for row in result["artifact_errors"]] == names
    assert not (harness.artifacts / "result.json").exists()


def test_cli_success_and_plan_limits_preserved(harness, capsys):
    assert harness.main() == 0
    output = json.loads(capsys.readouterr().out)
    saved = json.loads((harness.artifacts / "plan.json").read_text())
    assert saved == harness.plan
    assert output["result"]["limits"] == harness.plan["limits"]
    assert output["result"]["runtime_removed"] is True


def test_original_failure_survives_secondary_errors(harness):
    harness.faults.update({"workload.run": RuntimeError("original action failure"),
                          "metrics.stop": RuntimeError("sampler failure"),
                          "environment.close": RuntimeError("cleanup failure"),
                          "write:outcomes.json.tmp": OSError("disk failure")})
    result = harness.run()
    assert result["failure_stage"] == "workflow" and result["error"] == "original action failure"
    assert result["sampling_error"] == "sampler failure" and result["cleanup_error"] == "cleanup failure"
    assert result["artifact_errors"][0]["artifact"] == "outcomes.json"
    assert harness.events.count("environment.close") == 1
    assert result.get("runtime_removed") is not True


@pytest.mark.parametrize("error", [RuntimeError("close failed"), KeyboardInterrupt()])
def test_cleanup_failure_overrules_success(harness, error):
    harness.faults["environment.close"] = error
    result = harness.run()
    assert result["status"] == "failed" and result["failure_stage"] == "cleanup"
    assert "cleanup_error" in result and result.get("runtime_removed") is not True


def test_returning_from_close_without_removing_root_is_not_success(harness):
    harness.faults["retain_root"] = True
    result = harness.run()
    assert result["status"] == "failed" and result["runtime_removed"] is False
    assert "runtime remains" in result["cleanup_error"]


@pytest.mark.parametrize("point", ["workload.run", "metrics.stop"])
def test_fatal_exit_still_closes_environment(harness, point):
    harness.faults[point] = SystemExit(7)
    with pytest.raises(SystemExit) as caught:
        harness.run()
    assert caught.value.code == 7
    assert "environment.close" in harness.events and not harness.root.exists()


def test_invalid_plan_has_no_environment_side_effects(harness):
    harness.plan["actions"] = [{"kind": "raw_packet", "bot": 0}]
    with pytest.raises(ValueError):
        harness.run()
    assert not harness.events

"""Synthetic host lifecycle contracts; these tests never launch Windows Sandbox."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from .support import client_disposal as policy
from .support.client_smoke import CLIENT_SHA256
from .support.development import DevelopmentError


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def prepared_root(tmp_path, monkeypatch):
    monkeypatch.setattr(policy, "REPO", tmp_path)
    root = tmp_path / ".e2e-artifacts/run"
    (root / "output").mkdir(parents=True)
    config = root / "run.wsb"; config.write_text("<Configuration />", encoding="utf-8")
    source = {"version":1,
        "scope":"committed-coordinator-source-not-native-build-attestation",
        "revision":"1" * 40,"dirty":False,
        "sha256":{"tests/e2e/synthetic.py":"a" * 64},"gitlinks":[],
        "submodule_fetch_performed":False,"remote_configured":False}
    source_path = root / "input/source.json"; write(source_path, source)
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    profile_path = root / "input/profile.json"; write(profile_path, {"synthetic":True})
    profile_hash = hashlib.sha256(profile_path.read_bytes()).hexdigest()
    write(root / "inputs.json", {"version":1,"status":"prepared_not_executed",
        "client_sha256":CLIENT_SHA256,
        "config_sha256":hashlib.sha256(config.read_bytes()).hexdigest(),
        "source_revision":"1" * 40,"source_manifest_sha256":source_hash,
        "working_tree_changes_included":False,
        "inputs":{"profile.json":profile_hash,"source.json":source_hash}})
    write(root / "output/result.json", {"run":"a"*32,"status":"passed"})
    executable = tmp_path / "WindowsSandbox.exe"; executable.write_bytes(b"synthetic")
    return root, executable


class FakeProcess:
    pid = 77
    def poll(self): return None
    def wait(self, timeout):
        assert timeout == 5
        return 0


class Clock:
    def __init__(self): self.value = 10.0
    def __call__(self):
        self.value += 0.1
        return self.value


def produce(tmp_path, monkeypatch):
    root, executable = prepared_root(tmp_path, monkeypatch)
    row = {"pid":77,"name":"windowssandbox.exe","create_time":123.5}
    states = iter([[], [row], [], []])
    launched = []
    receipt = policy.run_prepared_sandbox(
        root, 60, snapshot=lambda: copy.deepcopy(next(states)),
        launch=lambda args: launched.append(args) or FakeProcess(),
        monotonic=Clock(), wall_time=lambda:1000.0, sleep=lambda value:None,
        executable=executable)
    assert launched == [[str(executable), str(root / "run.wsb")]]
    assert receipt["status"] == "disposed" and receipt["remaining_processes"] == []
    confirmation = policy.approve_disposal(root)
    assert confirmation["confirmed"] is True
    return root


def test_exact_prepared_launch_absence_and_manual_confirmation(tmp_path, monkeypatch):
    root = produce(tmp_path, monkeypatch)
    proof = policy.require_disposal(root)
    assert proof == {"version":1,"verified":True,"scope":policy.COMPOSITE_SCOPE,
        "session":json.loads((root / "sandbox-session.json").read_text())["session"],
        "run":"a"*32,"launcher_pid":77,"launcher_returncode":0,
        "result_sha256":hashlib.sha256((root / "output/result.json").read_bytes()).hexdigest(),
        "operator_confirmation":True,"sandbox_disposal_verified":True}


@pytest.mark.parametrize("mutation", [
    lambda root: json_file(root / "inputs.json", lambda value:
        value.update(source_manifest_sha256="0" * 64)),
    lambda root: json_file(root / "inputs.json", lambda value:
        value["inputs"].update({"../source.json":"0" * 64})),
    lambda root: json_file(root / "input/source.json", lambda value:
        value.update(remote_configured=True)),
    lambda root: json_file(root / "input/source.json", lambda value:
        value["gitlinks"].append({"path":"deps/example","revision":True,
                                  "materialized":False})),
    lambda root: (root / "input/profile.json").write_bytes(b"changed"),
    lambda root: (root / "input/foreign.bin").write_bytes(b"untracked"),
])
def test_prepared_source_mismatch_fails_before_sandbox_launch(tmp_path, monkeypatch, mutation):
    root, executable = prepared_root(tmp_path, monkeypatch)
    mutation(root)
    called = []
    with pytest.raises(DevelopmentError):
        policy.run_prepared_sandbox(root, 60, snapshot=lambda:[],
            launch=lambda args:called.append(args), executable=executable)
    assert called == [] and not (root / "sandbox-session.json").exists()


def test_preexisting_sandbox_fails_before_launch_or_publication(tmp_path, monkeypatch):
    root, executable = prepared_root(tmp_path, monkeypatch)
    called = []
    with pytest.raises(DevelopmentError, match="while any Sandbox"):
        policy.run_prepared_sandbox(root, 60,
            snapshot=lambda:[{"pid":9,"name":"windowssandbox.exe","create_time":1.0}],
            launch=lambda args: called.append(args), executable=executable)
    assert called == [] and not (root / "sandbox-session.json").exists()


def test_unobserved_launcher_times_out_without_kill_or_retry(tmp_path, monkeypatch):
    root, executable = prepared_root(tmp_path, monkeypatch)
    values = iter([0.0, 0.0, 61.0])
    process = FakeProcess()
    with pytest.raises(TimeoutError, match="PID was not observed"):
        policy.run_prepared_sandbox(root, 60, snapshot=lambda:[],
            launch=lambda args:process, monotonic=lambda:next(values),
            wall_time=lambda:1.0, sleep=lambda value:None, executable=executable)
    failure = json.loads((root / "sandbox-disposal-failure.json").read_text())
    assert failure["automatic_kill_attempted"] is False
    assert failure["retry_attempted"] is False
    assert not (root / "sandbox-disposal.json").exists()


@pytest.mark.parametrize("mutation", [
    lambda root: json_file(root / "sandbox-session.json", lambda v:v.update(launcher_pid=True)),
    lambda root: json_file(root / "sandbox-disposal.json",
        lambda v:v["observed_processes"][0].update(name="foreign.exe")),
    lambda root: json_file(root / "sandbox-disposal.json",
        lambda v:v.update(observed_processes=[True])),
    lambda root: json_file(root / "sandbox-disposal-review.json",
        lambda v:v.update(confirmed=1)),
    lambda root: (root / "output/result.json").write_text("{}", encoding="utf-8"),
])
def test_strict_disposal_consumer_rejects_foreign_or_type_confused_evidence(
        tmp_path, monkeypatch, mutation):
    root = produce(tmp_path, monkeypatch)
    mutation(root)
    with pytest.raises(DevelopmentError):
        policy.require_disposal(root)


def json_file(path, mutate):
    value = json.loads(path.read_text())
    mutate(value)
    write(path, value)


def test_composite_inspector_binds_same_run_and_result_hash(tmp_path, monkeypatch):
    root = produce(tmp_path, monkeypatch)
    digest = hashlib.sha256((root / "output/result.json").read_bytes()).hexdigest()
    from .support import client_result
    monkeypatch.setattr(client_result, "inspect_client_development_result", lambda output, revision:
        {"run":"a"*32,"result_sha256":digest,"scope":"current-graphical",
         "source_revision":revision})
    proof = policy.inspect_completed_sandbox(root, "1"*40)
    assert proof["sandbox_disposal_verified"] is True
    assert proof["disposal"]["run"] == proof["run"] == "a"*32
    monkeypatch.setattr(client_result, "inspect_client_development_result", lambda output, revision:
        {"run":"b"*32,"result_sha256":digest,"scope":"current-graphical"})
    with pytest.raises(DevelopmentError, match="differ"):
        policy.inspect_completed_sandbox(root, "1"*40)

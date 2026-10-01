"""Synthetic contracts only: no real client, rendering approval or live evidence."""
import contextlib
import json
import sys
import types

import pytest

from .support.client_lifecycle import retire_witness
from .support.worker import Bot, WorkerError


class RetirementWorker:
    def __init__(self, fail=None):
        self.calls = []
        self.fail = fail

    def request(self, method, bot, **kwargs):
        assert bot == "owned-witness"
        self.calls.append(method)
        if method == self.fail:
            raise WorkerError("synthetic " + method + " failure")
        return {}

    def wait_state(self, bot, predicate, description, timeout):
        assert bot == "owned-witness" and timeout == 10
        self.calls.append(description)
        assert not predicate({"phase": "ready"})
        if description == "logout acknowledgement":
            state = {"phase": "logged_out"}
        else:
            assert description == "server logout connection close"
            # Acknowledgement or local closure must never satisfy this wait.
            assert not predicate({"phase": "logged_out"})
            assert not predicate({"phase": "closed"})
            state = {"phase": "logout_complete"}
        if self.fail == description:
            raise WorkerError("synthetic " + description + " failure")
        assert predicate(state)
        return state


def test_retirement_requires_server_closure_before_local_close_and_removal():
    worker = RetirementWorker()
    report = retire_witness(Bot(worker, "owned-witness"))
    assert worker.calls == ["logout", "logout acknowledgement", "server logout connection close", "close", "remove"]
    assert report == {"bot": "owned-witness", "server_close_observed": True, "native_bot_removed": True,
                      "scope": "normal-witness-session-retirement-not-offline-exclusion"}


@pytest.mark.parametrize("failure", ["logout", "logout acknowledgement", "server logout connection close", "close", "remove"])
def test_retirement_failure_is_not_retried_or_converted_to_success(failure):
    worker = RetirementWorker(fail=failure)
    with pytest.raises(WorkerError, match="synthetic"):
        retire_witness(Bot(worker, "owned-witness"))
    ordered = ["logout", "logout acknowledgement", "server logout connection close", "close", "remove"]
    assert worker.calls == ordered[:ordered.index(failure) + 1]


@pytest.mark.parametrize("failure", [None, "server logout connection close", "remove",
                                     "deadline_before_retirement", "deadline_during_retirement"])
def test_guest_terminal_status_depends_on_final_witness_retirement(tmp_path, monkeypatch, failure):
    # Exercise coordinator control flow with entirely synthetic setup/UI state.
    # No guest is launched, no host registry/files are changed, no review attested.
    from . import run_client_smoke as guest
    inputs, output, runtime = (tmp_path / name for name in ("input", "output", "runtime"))
    for path in (inputs, output, runtime):
        path.mkdir()
    for name, value in (("source", {}), ("profile", {}),
                        ("fixture", {"position": [0, 0, 0], "development_check": False})):
        (inputs / (name + ".json")).write_text(json.dumps(value))
    (output / "review.json").write_text("{}")  # Only the stub validator below accepts this.
    (runtime / "world.log").write_text("[2] Zone IPC : StartLogoutCountdown")
    retired = RetirementWorker(failure)
    now = [100.0]
    original_request = retired.request
    def request(method, *args, **kwargs):
        result = original_request(method, *args, **kwargs)
        if method == "remove" and failure == "deadline_during_retirement":
            now[0] = 1300.0  # Exactly the activity deadline: closure is not late success.
        return result
    retired.request = request
    monkeypatch.setattr(guest.time, "monotonic", lambda: now[0])
    cleanup = []

    class Environment:
        redactions = []
        worker = "unused"
        artifacts = tmp_path / "artifacts"
        deadline_scale = 1
        lobby_port = 0
        root = tmp_path / "removed"
        def __init__(self, profile):
            self.runtime = runtime
        def start(self):
            pass
        def check_alive(self):
            pass
        def fresh_character(self, position):
            return {"name": "synthetic", "auth": {"sId": "not-a-session"}}
        def close(self):
            cleanup.append("environment")

    class Worker:
        def __init__(self, *args):
            self.snapshots = iter([
                {"actors": {"2": {"position": [0, 0, 0]}}},
                {"actors": {"2": {"position": [2, 0, 0]}}},
                {"actors": {"2": {}}, "chat": [{"actor": 2, "message": guest.REAL_SAY}]},
                {"actors": {"2": {}}}, {"actors": {}},
            ])
        def __enter__(self):
            return self
        def __exit__(self, *args):
            cleanup.append("worker")
        def snapshot(self, bot):
            return next(self.snapshots)

    class Witness(Bot):
        def __init__(self, worker, name):
            super().__init__(retired, "owned-witness")
        def login_via_lobby(self, *args):
            return {"actors": {}}
        def say(self, message):
            assert message == guest.WITNESS_SAY

    class Client:
        pid = 123
        def poll(self):
            return None
        def kill(self):
            cleanup.append("client")
        def wait(self, timeout):
            pass

    monkeypatch.setattr(guest, "INPUT", inputs); monkeypatch.setattr(guest, "OUTPUT", output)
    monkeypatch.setattr(guest, "require_guest", lambda: "synthetic guest")
    monkeypatch.setattr(guest, "verify_source", lambda *args: "synthetic revision")
    monkeypatch.setattr(guest, "sha256", lambda *args: guest.CLIENT_SHA256)
    monkeypatch.setattr(guest, "Environment", Environment)
    monkeypatch.setattr(guest, "Worker", Worker); monkeypatch.setattr(guest, "Bot", Witness)
    monkeypatch.setattr(guest, "other_player", lambda s, *a, **k: (2, s["actors"]["2"]) if "2" in s["actors"] else None)
    monkeypatch.setattr(guest, "validate_review", lambda *args: {"synthetic_only": True})
    monkeypatch.setattr(guest.time, "sleep", lambda *args: None)
    monkeypatch.setattr(guest.shutil, "copytree", lambda *args: None)
    monkeypatch.setattr(guest.shutil, "copy2", lambda *args: None)
    monkeypatch.setattr(guest.subprocess, "run", lambda *args, **kwargs: None)
    monkeypatch.setattr(guest.subprocess, "Popen", lambda *args, **kwargs: Client())
    def save(path):
        path.write_bytes(b"synthetic")
        if path.name == "logout.png" and failure == "deadline_before_retirement":
            now[0] = 1300.0
    monkeypatch.setitem(sys.modules, "PIL", types.SimpleNamespace(ImageGrab=types.SimpleNamespace(
        grab=lambda **kwargs: types.SimpleNamespace(save=save))))
    monkeypatch.setitem(sys.modules, "winreg", types.SimpleNamespace(
        CreateKey=lambda *args: contextlib.nullcontext(), HKEY_CURRENT_USER=0, REG_DWORD=0,
        SetValueEx=lambda *args: None))
    assert guest.run() == (1 if failure else 0)
    report = json.loads((output / "result.json").read_text())
    terminal = json.loads((output / "status.json").read_text())
    assert terminal["phase"] == "finished"
    assert report["status"] == terminal["status"] == ("failed" if failure else "passed")
    assert cleanup == ["worker", "client", "environment"]
    assert report["runtime_removed"] is True
    assert report["timing"]["phases"][-2]["phase"] == "witness_retirement"
    if failure:
        assert report["failure_stage"] == "witness_retirement"
    if failure == "deadline_before_retirement":
        assert retired.calls == []
    if failure in {"server logout connection close", "remove", "deadline_before_retirement"}:
        assert report["witness_retirements"] == []
    else:
        assert report["witness_retirements"] == [{"bot": "owned-witness", "server_close_observed": True,
            "native_bot_removed": True, "scope": "normal-witness-session-retirement-not-offline-exclusion"}]

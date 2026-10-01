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
                                     "stale_real_say", "deadline_before_retirement",
                                     "deadline_during_retirement", "deadline_during_worker_exit",
                                     "observer_worker_exit",
                                     "observer_worker_exit_unknown"])
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
    said = []

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
            self.closed = False
            self.process = types.SimpleNamespace(pid=12345, poll=lambda:
                (None if failure == "observer_worker_exit_unknown"
                 else 1 if failure == "observer_worker_exit" else 0) if self.closed else None)
            baseline_chat = ([{"actor":2,"kind":10,"message":guest.REAL_SAY,"token":10}]
                             if failure == "stale_real_say" else [])
            self.snapshots = iter([
                {"actors": {"2": {"position": [0, 0, 0]}}},
                {"actors": {"2": {"position": [0, 0, 0]}}, "seq": 8, "chat": []},
                {"actors": {"2": {"position": [2, 0, 0]}}, "seq": 9, "chat": []},
                {"actors": {"2": {}}, "seq": 10, "chat": baseline_chat},
                {"actors": {"2": {}}, "seq": 11,
                 "chat": [{"actor": 2, "kind": 10, "message": guest.REAL_SAY, "token": 11}]},
                {"actors": {"2": {}}},
                {"actors": {"2": {"position": [2,0,0]}}, "seq": 12},
                {"actors": {}, "seq": 13},
            ])
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.closed = True
            if failure == "deadline_during_worker_exit":
                now[0] = 1300.0
            cleanup.append("worker")
        def snapshot(self, bot):
            return next(self.snapshots)

    class Witness(Bot):
        def __init__(self, worker, name):
            super().__init__(retired, "owned-witness")
        def login_via_lobby(self, *args):
            return {"actors": {}}
        def say(self, message):
            said.append(message)

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
    monkeypatch.setattr(guest, "real_spawn_baseline", lambda state: 0)
    monkeypatch.setattr(guest, "received_real_spawn", lambda state, name, position, baseline:
        ({"verified":True,"scope":"fresh-exact-fixture-real-client-spawn-not-client-provenance",
          "entity_id":2,"name":name,"gm_rank":0,"level":1,
          "position":state["actors"]["2"]["position"],"baseline_sequence":baseline,
          "received_sequence":1} if "2" in state["actors"] else None))
    monkeypatch.setattr(guest, "real_movement_baseline", lambda state, entity, origin:
        {"sequence":state["seq"],"position":state["actors"][str(entity)]["position"]})
    monkeypatch.setattr(guest, "received_real_movement", lambda state, entity, origin, baseline:
        ({"verified":True,
          "scope":"fresh-bounded-real-client-movement-received-by-independent-witness",
          "actor":entity,"origin":origin,"baseline_position":baseline["position"],
          "received_position":state["actors"][str(entity)]["position"],
          "baseline_sequence":baseline["sequence"],"received_sequence":state["seq"],
          "movement_metres":2.0} if state["actors"][str(entity)]["position"] == [2,0,0] else None))
    def say_baseline(state, entity):
        if state["chat"]:
            raise ValueError("synthetic stale real Say")
        return state["seq"]
    monkeypatch.setattr(guest, "real_say_baseline", say_baseline)
    monkeypatch.setattr(guest, "received_real_say", lambda state, entity, baseline:
        ({"verified":True,
          "scope":"fresh-ordinary-real-client-say-received-by-independent-witness",
          "actor":entity,"message":guest.REAL_SAY,"kind":10,
          "baseline_sequence":baseline,"message_token":state["chat"][0]["token"],
          "received_sequence":state["seq"]} if state.get("chat") else None))
    monkeypatch.setattr(guest, "real_logout_baseline", lambda state, entity, name:
        {"sequence":state["seq"],"position":state["actors"][str(entity)]["position"]})
    monkeypatch.setattr(guest, "received_real_logout", lambda state, entity, baseline:
        ({"verified":True,
          "scope":"fresh-real-client-absence-after-logout-phase-not-server-logout-proof",
          "entity_id":entity,"baseline_position":baseline["position"],
          "baseline_sequence":baseline["sequence"],"received_sequence":state["seq"]}
         if str(entity) not in state["actors"] else None))
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
    assert report["timing"]["phases"][-2]["phase"] == (
        "say" if failure == "stale_real_say" else "witness_retirement")
    if failure:
        assert report["failure_stage"] == ("observer_worker_exit"
            if failure in {"observer_worker_exit", "observer_worker_exit_unknown",
                           "deadline_during_worker_exit"}
            else "say" if failure == "stale_real_say" else "witness_retirement")
    if failure == "deadline_before_retirement":
        assert retired.calls == []
    if failure in {"server logout connection close", "remove", "deadline_before_retirement",
                   "stale_real_say"}:
        assert report["witness_retirements"] == []
    else:
        assert report["witness_retirements"] == [{"bot": "owned-witness", "server_close_observed": True,
            "native_bot_removed": True, "scope": "normal-witness-session-retirement-not-offline-exclusion"}]
    if failure == "stale_real_say":
        assert said == [] and "witness_say_challenge" not in report
    else:
        assert said == [guest.witness_say_challenge(report["run"])]
        assert report["witness_say_challenge"] == said[0]
    assert report["pre_client_state"] == {"actors":{}}
    assert report["real_spawn_receipt"] == {
        "verified":True,"scope":"fresh-exact-fixture-real-client-spawn-not-client-provenance",
        "entity_id":2,"name":"synthetic","gm_rank":0,"level":1,
        "position":[0,0,0],"baseline_sequence":0,"received_sequence":1}
    assert report["movement_baseline"]["seq"] == 8
    assert report["real_movement_receipt"] == {
        "verified":True,
        "scope":"fresh-bounded-real-client-movement-received-by-independent-witness",
        "actor":2,"origin":[0,0,0],"baseline_position":[0,0,0],
        "received_position":[2,0,0],"baseline_sequence":8,"received_sequence":9,
        "movement_metres":2.0}
    assert report["say_baseline"]["seq"] == 10
    if failure == "stale_real_say":
        assert "real_say_receipt" not in report
    else:
        assert report["real_say_receipt"] == {
            "verified":True,
            "scope":"fresh-ordinary-real-client-say-received-by-independent-witness",
            "actor":2,"message":guest.REAL_SAY,"kind":10,
            "baseline_sequence":10,"message_token":11,"received_sequence":11}
    if failure != "stale_real_say":
        assert report["logout_baseline"]["seq"] == 12
        assert report["real_logout_receipt"] == {
            "verified":True,
            "scope":"fresh-real-client-absence-after-logout-phase-not-server-logout-proof",
            "entity_id":2,"baseline_position":[2,0,0],
            "baseline_sequence":12,"received_sequence":13}
    deadline_receipt = report["activity_deadline"]
    assert deadline_receipt["enabled"] is True and deadline_receipt["limit_seconds"] == 1200
    assert deadline_receipt["scope"] == "cooperative-manual-activity-success-deadline-not-hard-cleanup-limit"
    assert deadline_receipt["environment_cleanup_may_exceed_deadline"] is True
    assert deadline_receipt["expired"] is (failure in {
        "deadline_before_retirement", "deadline_during_retirement", "deadline_during_worker_exit"})
    assert deadline_receipt["activity_and_worker_exit_completed_within_budget"] is (failure is None)
    receipt = report["observer_worker_exit"]
    assert receipt["context_exit_attempted"] and receipt["context_exit_completed"]
    assert receipt["process_id"] == 12345
    if failure == "observer_worker_exit_unknown":
        assert not receipt["process_exit_observed"] and "returncode" not in receipt
    else:
        assert receipt["process_exit_observed"]
        assert receipt["returncode"] == (1 if failure == "observer_worker_exit" else 0)

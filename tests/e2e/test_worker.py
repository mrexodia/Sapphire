"""Asset-independent worker contract tests. These do NOT establish game E2E coverage."""
import json
import socket
import subprocess

import pytest

from .support.environment import (Environment, SetupError, allocate_ports,
                                  require_process_teardowns)
from .support.worker import Bot, UnsupportedScene, Worker, WorkerError


def test_worker_rejects_unbounded_deadline_scale(tmp_path):
    with pytest.raises(WorkerError, match="deadline scale"):
        Worker(tmp_path / "unused", tmp_path / "artifacts", deadline_scale=4)


def test_bound_party_journal_records_context_not_unrelated_secrets(worker):
    context = {"id": 0, "chat_channel": 0, "count": 0, "leader_index": 0, "members": []}
    with pytest.raises(WorkerError):
        worker.request("accept_party_bound", "absent-bot", expected_party=context,
                       expected_invite={"character_id": 101, "auth_type": 1, "result": 1, "name": "Bot Leader"},
                       sId="not-for-the-journal")
    worker.close()
    text = (worker.artifacts / "actions.jsonl").read_text()
    rows = [json.loads(line) for line in text.splitlines()]
    assert rows[-1]["method"] == "accept_party_bound"
    assert rows[-1]["args"]["expected_party"] == context
    assert rows[-1]["args"]["expected_invite"]["character_id"] == 101
    assert "not-for-the-journal" not in text and "sId" not in rows[-1]["args"]


def test_administrative_journal_records_binding_not_credentials(worker):
    with pytest.raises(WorkerError):
        worker.request("development_place_registered", "absent-operator", administrative_setup=True,
                       approval_id="a" * 32, slot=0,
                       expected_operator={"name": "Tester Operator", "entity_id": 3, "character_id": 300,
                                          "password": "nested-private-password"},
                       sId="private-session-not-audit-data")
    worker.close()
    text = (worker.artifacts / "actions.jsonl").read_text()
    row = json.loads(text.splitlines()[-1])
    assert row["args"] == {"administrative_setup": True, "approval_id": "a" * 32, "slot": 0,
                           "expected_operator": {"name": "Tester Operator", "entity_id": 3, "character_id": 300}}
    assert "nested-private-password" not in text and "private-session-not-audit-data" not in text


def test_visible_tell_journal_records_peer_not_unrelated_credentials(worker):
    with pytest.raises(WorkerError):
        worker.request("tell_visible", "absent-bot", target=2, name="Tester Peer", message="Test Tell",
                       sId="private-session-not-audit-data")
    worker.close()
    text = (worker.artifacts / "actions.jsonl").read_text()
    assert json.loads(text.splitlines()[-1])["args"] == {"target":2, "name":"Tester Peer", "message":"Test Tell"}
    assert "private-session-not-audit-data" not in text


def test_capabilities(worker):
    caps = worker.request("capabilities")
    assert caps["profile"] == "sapphire-3.3"
    assert caps["scope"] == "loopback-only"
    assert "general_navigation" in caps["unsupported"]
    assert "general_combat" in caps["unsupported"]
    assert {"invite_party_bound", "accept_party_bound", "party_chat_bound", "disband_party_bound"} <= set(caps["methods"])
    assert "cast_return" in caps["methods"]
    assert "sprint" in caps["methods"]
    assert "fast_blade" in caps["methods"]
    assert "savage_blade" in caps["methods"]
    assert "bootshine" in caps["methods"]
    assert "true_strike" in caps["methods"]
    assert "blizzard" in caps["methods"]
    assert "use_shop_vfx_item" in caps["methods"]
    assert "request_shop_item_equip" in caps["methods"]
    assert "request_currency_move_rejection" in caps["methods"]
    assert "request_item_move" in caps["methods"]
    assert "request_item_swap" in caps["methods"]
    assert "request_item_split" in caps["methods"]
    assert "request_item_merge" in caps["methods"]
    assert "start_uldah_opening" in caps["methods"]
    assert "discover_central_thanalan" in caps["methods"]
    assert "sell_shop_item" in caps["methods"]
    assert "buy_shop_item" in caps["methods"]
    assert "buy_shop_equipment" in caps["methods"]
    assert "buy_shop_second_equipment" in caps["methods"]
    assert "buy_shop_third_equipment" in caps["methods"]
    assert "buy_shop_head_equipment" in caps["methods"]
    assert "buy_shop_ear_equipment" in caps["methods"]
    assert "buy_shop_neck_equipment" in caps["methods"]
    assert "buy_shop_wrist_equipment" in caps["methods"]
    assert "tell" in caps["methods"]
    assert "tell_remote" in caps["methods"]
    assert "tell_offline" in caps["methods"]
    assert "return_homepoint" in caps["methods"]
    assert all(method in caps["methods"] for method in
               ("invite_party", "accept_party", "decline_party", "leave_party", "disband_party",
                "kick_party_member", "change_party_leader", "party_chat"))


def test_unknown_bot_and_invalid_method(worker):
    with pytest.raises(WorkerError, match="unknown bot"):
        worker.snapshot("absent")
    assert worker.request("capabilities")["control_version"] == 1


def test_nonlocal_endpoint_rejected_and_secret_not_recorded(worker):
    with pytest.raises(WorkerError, match="loopback"):
        worker.request("login", "test", host="192.0.2.1", port=54994,
                       session="sensitive-session-fixture", character="Test User")
    assert worker.request("capabilities")["control_version"] == 1
    worker.close()
    assert "sensitive-session-fixture" not in (worker.artifacts / "events.jsonl").read_text()


def test_creation_rejects_nonalphabetic_character_name(worker):
    with pytest.raises(WorkerError, match="alphabetic ASCII"):
        worker.request("login", "test", host="127.0.0.1", port=1, session="test-session",
                       character="Bad_Name", create_character=True)
    assert worker.request("capabilities")["control_version"] == 1


def test_character_lobby_modes_are_bounded(worker):
    with pytest.raises(WorkerError, match="mutually exclusive"):
        worker.request("login", "test", host="127.0.0.1", port=1, session="test-session",
                       character="Test User", create_character=True, delete_character=True)
    with pytest.raises(WorkerError, match="mutually exclusive"):
        worker.request("login", "test", host="127.0.0.1", port=1, session="test-session",
                       character="Test User", create_character=True, expect_name_rejected=True)
    with pytest.raises(WorkerError, match="alphabetic ASCII"):
        worker.request("login", "test", host="127.0.0.1", port=1, session="test-session",
                       character="Bad_Name", expect_name_rejected=True)
    assert worker.request("capabilities")["control_version"] == 1


def test_failed_connect_is_observed_not_ready(worker):
    # Reserve an unlistening port so another process cannot bind it during the test.
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        worker.request("login", "test", host="127.0.0.1", port=reserved.getsockname()[1],
                       session="test-session", character="Test User")
        with pytest.raises(WorkerError, match="connection failed"):
            worker.wait_state("test", lambda s: s["phase"] == "ready", "ready", timeout=5)
    worker.request("remove", "test")
    assert "test" not in worker._versions


def test_action_before_readiness_is_rejected(worker):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        listener.settimeout(5)
        worker.request("login", "test", host="127.0.0.1", port=listener.getsockname()[1],
                       session="test-session", character="Test User")
        peer, _ = listener.accept()
        try:
            with pytest.raises(WorkerError, match="world-ready"):
                worker.request("walk_to", "test", position=[0, 0, 0])
            with pytest.raises(WorkerError, match="world-ready"):
                worker.request("request_shop_item_equip", "test", storage=0, slot=0,
                               expected_item=3286, gear_slot=6)
            with pytest.raises(WorkerError, match="world-ready"):
                worker.request("request_currency_move_rejection", "test", expected_gil=42)
            with pytest.raises(WorkerError, match="world-ready"):
                worker.request("buy_shop_equipment", "test", token=1, event_id=262468)
            with pytest.raises(WorkerError, match="world-ready"):
                worker.request("buy_shop_second_equipment", "test", token=1, event_id=262468)
            with pytest.raises(WorkerError, match="world-ready"):
                worker.request("buy_shop_third_equipment", "test", token=1, event_id=262468)
            with pytest.raises(WorkerError, match="world-ready"):
                worker.request("buy_shop_head_equipment", "test", token=1, event_id=262415)
            with pytest.raises(WorkerError, match="world-ready"):
                worker.request("buy_shop_ear_equipment", "test", token=1, event_id=262425)
            with pytest.raises(WorkerError, match="world-ready"):
                worker.request("buy_shop_neck_equipment", "test", token=1, event_id=262640)
            with pytest.raises(WorkerError, match="world-ready"):
                worker.request("buy_shop_wrist_equipment", "test", token=1, event_id=262640)
            with pytest.raises(WorkerError, match="world-ready"):
                worker.request("use_shop_vfx_item", "test", storage=0, slot=0, expected_count=3)
            with pytest.raises(WorkerError, match="world-ready"):
                worker.request("cast_return", "test")
            with pytest.raises(WorkerError, match="world-ready"):
                worker.request("sprint", "test")
            with pytest.raises(WorkerError, match="world-ready"):
                worker.request("fast_blade", "test", target=123)
            with pytest.raises(WorkerError, match="world-ready"):
                worker.request("savage_blade", "test", target=123)
            with pytest.raises(WorkerError, match="world-ready"):
                worker.request("bootshine", "test", target=123)
            with pytest.raises(WorkerError, match="world-ready"):
                worker.request("true_strike", "test", target=123)
            with pytest.raises(WorkerError, match="world-ready"):
                worker.request("blizzard", "test", target=123)
            with pytest.raises(WorkerError, match="world-ready"):
                worker.request("start_uldah_opening", "test")
            with pytest.raises(WorkerError, match="world-ready"):
                worker.request("discover_central_thanalan", "test", layout_id=3643706)
            with pytest.raises(WorkerError, match="world-ready"):
                worker.request("sell_shop_item", "test", token=1, event_id=0x40005,
                               storage=0, slot=0, expected_item=4551, expected_count=1)
            with pytest.raises(WorkerError, match="world-ready"):
                worker.request("buy_shop_item", "test", token=1, event_id=262468)
            with pytest.raises(WorkerError, match="world-ready"):
                worker.request("return_homepoint", "test")
            with pytest.raises(WorkerError, match="world-ready"):
                worker.request("invite_party", "test", target=1, name="Target")
            with pytest.raises(WorkerError, match="world-ready"):
                worker.request("party_chat", "test", message="party hello")
            with pytest.raises(WorkerError, match="world-ready"):
                worker.request("tell", "test", target=1, name="Target", message="hello")
            with pytest.raises(WorkerError, match="world-ready"):
                worker.request("tell_remote", "test", target=1, name="Target", message="hello")
            with pytest.raises(WorkerError, match="world-ready"):
                worker.request("tell_offline", "test", target=1, name="Target", message="hello")
            with pytest.raises(WorkerError, match="world-ready"):
                worker.request("request_item_move", "test", storage=0, slot=0,
                               expected_item=4555, destination_storage=3, destination_slot=24)
            with pytest.raises(WorkerError, match="world-ready"):
                worker.request("request_item_swap", "test", storage=0, slot=0, expected_item=4555,
                               destination_storage=3, destination_slot=24,
                               expected_destination_item=4551)
            move = next(row for row in worker._actions if row["method"] == "request_item_move")
            assert move["args"] == {"storage": 0, "slot": 0, "expected_item": 4555,
                                    "destination_storage": 3, "destination_slot": 24}
            swap = next(row for row in worker._actions if row["method"] == "request_item_swap")
            assert swap["args"] == {"storage": 0, "slot": 0, "expected_item": 4555,
                                    "destination_storage": 3, "destination_slot": 24,
                                    "expected_destination_item": 4551}
            worker.request("close", "test")
            assert worker.snapshot("test")["phase"] == "closed"
        finally:
            peer.close()


def test_worker_exit_wakes_waiter(worker):
    worker.process.kill()
    worker.process.wait(timeout=3)
    with pytest.raises(WorkerError):
        worker.request("capabilities", timeout=3)


def test_bad_json_does_not_echo_secret(worker_path):
    result = subprocess.run([str(worker_path)], input=b'{"pass":"do-not-echo",\n',
                            capture_output=True, timeout=5)
    assert result.returncode == 0
    assert b"do-not-echo" not in result.stdout
    assert json.loads(result.stdout)["ok"] is False


def test_oversized_request_does_not_poison_next_request(worker):
    with pytest.raises(WorkerError, match="too large"):
        worker.request("capabilities", unused="x" * 70000)
    assert worker.request("capabilities")["control_version"] == 1


def test_nonfinite_json_does_not_poison_next_request(worker):
    with pytest.raises(ValueError):
        worker.request("capabilities", unused=float("nan"))
    assert worker.request("capabilities")["control_version"] == 1


def test_missing_assets_fail_setup(tmp_path):
    with pytest.raises(SetupError, match="missing required"):
        Environment({key: str(tmp_path / "missing")
                     for key in ("binaries", "game_data", "mariadb_bin", "worker")})


def test_artifacts_are_redacted_and_runtime_removed(tmp_path):
    env = object.__new__(Environment)
    env.root = tmp_path / "private"
    env.runtime = env.root / "runtime"
    env.runtime.mkdir(parents=True)
    env.artifacts = tmp_path / "published"
    env.artifacts.mkdir()
    env.redactions = {"fixture-password", "fixture-session"}
    env.processes, env.streams, env._closed = {}, [], False
    (env.runtime / "server.log").write_text("fixture-password fixture-session diagnostic")
    env.close()
    assert not env.root.exists()
    assert (env.artifacts / "server.log").read_text() == "<redacted> <redacted> diagnostic"
    assert json.loads((env.artifacts / "process-lifecycle.json").read_text()) == {
        "version":1,
        "scope":"exact-owned-isolated-process-teardown-not-graceful-server-exit",
        "starts":[],"teardowns":[]}
    env.close()  # Cleanup is idempotent.


def test_exact_owned_process_stop_records_terminate_and_kill_fallback():
    class Process:
        pid = 44
        def __init__(self): self.calls = []
        def poll(self): return None
        def terminate(self): self.calls.append("terminate")
        def kill(self): self.calls.append("kill")
        def wait(self, timeout):
            self.calls.append(("wait", timeout))
            if timeout == 10:
                raise subprocess.TimeoutExpired("owned", timeout)
            return -9
    process = Process()
    env = object.__new__(Environment)
    env.processes = {"world":process}
    env._process_metadata = {"world":{"process":"world","generation":2,"pid":44}}
    env.process_teardowns = []
    env._stop("world")
    assert process.calls == ["terminate", ("wait",10), "kill", ("wait",5)]
    assert env.process_teardowns == [{"process":"world","generation":2,"pid":44,
        "was_running_before_cleanup":True,"terminate_requested":True,
        "kill_requested":True,"exit_observed":True,"returncode":-9,
        "scope":"exact-owned-isolated-process-teardown-not-graceful-server-exit"}]


def test_process_start_generations_bind_restarted_world(tmp_path, monkeypatch):
    from .support import environment
    pids = iter(range(100, 105))
    class Process:
        def __init__(self): self.pid = next(pids)
        def poll(self): return None
        def terminate(self): pass
        def wait(self, timeout): return -15
    monkeypatch.setattr(environment.subprocess, "Popen", lambda *args, **kwargs: Process())
    env = object.__new__(Environment)
    env.runtime = tmp_path
    env.processes, env._process_generations, env._process_metadata = {}, {}, {}
    env.process_starts, env.process_teardowns, env.streams = [], [], []
    for name in ("database","api","lobby","world"):
        env._start(name, ["synthetic"])
    env._stop("world")
    env._start("world", ["synthetic"])
    for name in reversed(list(env.processes)):
        env._stop(name)
    proof = require_process_teardowns(env.process_starts, env.process_teardowns)
    assert proof["process_count"] == 5
    assert proof["generations"] == {"api":1,"database":1,"lobby":1,"world":2}
    for stream in env.streams:
        stream.close()


def test_process_lifecycle_requires_every_running_generation_exactly_once():
    starts = [{"process":name,"generation":1,"pid":index + 20}
              for index, name in enumerate(("database","api","lobby","world"))]
    teardowns = [{**row,"was_running_before_cleanup":True,
        "terminate_requested":True,"kill_requested":False,"exit_observed":True,
        "returncode":-15,
        "scope":"exact-owned-isolated-process-teardown-not-graceful-server-exit"}
        for row in reversed(starts)]
    proof = require_process_teardowns(starts, teardowns)
    assert proof["process_count"] == 4 and proof["generations"]["world"] == 1
    mutations = [
        lambda rows: rows.pop(),
        lambda rows: rows[0].update(pid=True),
        lambda rows: rows[0].update(was_running_before_cleanup=False),
        lambda rows: rows[0].update(terminate_requested=1),
        lambda rows: rows[0].update(exit_observed=False),
        lambda rows: rows[0].update(returncode=True),
    ]
    import copy
    for mutate in mutations:
        changed = copy.deepcopy(teardowns); mutate(changed)
        with pytest.raises(SetupError):
            require_process_teardowns(starts, changed)


def test_subprocess_timeout_does_not_render_credentials(tmp_path, monkeypatch):
    import subprocess
    from .support import environment
    env = object.__new__(Environment)
    env.runtime = tmp_path
    def fail(args, **kwargs):
        raise subprocess.TimeoutExpired(args, 1)
    monkeypatch.setattr(environment.subprocess, "run", fail)
    with pytest.raises(SetupError, match="timed out") as error:
        env._run("private-setup", ["tool", "--password=fixture-secret"], timeout=1)
    assert "fixture-secret" not in str(error.value)
    assert error.value.__suppress_context__


@pytest.mark.parametrize("territory", [182, 0, "141", True])
def test_fixture_rejects_unsupported_or_private_territory(territory):
    env = object.__new__(Environment)
    with pytest.raises(SetupError, match="unsupported public"):
        env.fresh_character([0, 0, 0], territory=territory)


def test_nondefault_fixture_requires_explicit_position():
    env = object.__new__(Environment)
    with pytest.raises(SetupError, match="explicit position"):
        env.fresh_character(territory=141)


def test_ports_are_distinct_loopback_reservations():
    ports = allocate_ports(4)
    assert len(set(ports)) == 4
    assert all(0 < port <= 65535 for port in ports)


@pytest.mark.parametrize("count", [True, 0, 33])
def test_port_reservation_count_is_bounded(count):
    with pytest.raises(ValueError, match="1..32"):
        allocate_ports(count)


def test_unknown_scene_never_sends_a_result():
    class Stub:
        called = False
        def wait_state(self, *args):
            return {"scene": {"event_id": 1, "scene_id": 2, "token": 3}}
        def request(self, *args, **kwargs):
            self.called = True
    stub = Stub()
    with pytest.raises(UnsupportedScene):
        Bot(stub, "test").choose_dialogue({"profile": "sapphire-3.3", "scenes": {}}, "accept")
    assert not stub.called


def test_scene_response_preserves_observed_identity():
    class Stub:
        calls = []
        def wait_state(self, *args):
            return {"scene": {"event_id": 1, "scene_id": 2, "token": 3}}
        def request(self, *args, **kwargs):
            self.calls.append((args, kwargs))
    stub = Stub()
    Bot(stub, "test").choose_dialogue(
        {"profile": "sapphire-3.3", "scenes": {"1:2": {"choices": {"accept": [1]}}}}, "accept")
    assert stub.calls == [(("choose_scene", "test"), {"event_id": 1, "scene_id": 2, "token": 3, "results": [1]})]


@pytest.mark.parametrize("notification", ["response", "other_bot_event"])
def test_unrelated_notifications_do_not_cause_snapshot_polling(notification):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from .support.worker import Worker
    waiting = threading.Event()
    class Condition(threading.Condition):
        def wait(self, timeout=None):
            waiting.set()
            return super().wait(timeout)
    instance = object.__new__(Worker)
    instance._cv = Condition()
    instance._version, instance._failure = 0, None
    instance._versions = {}
    calls = []
    def snapshot(bot):
        calls.append(bot)
        return {"phase": "ready"}
    instance.snapshot = snapshot
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(instance.wait_state, "idle", lambda s: False, "no event", 1)
        assert waiting.wait(1)
        for _ in range(5):
            waiting.clear()
            with instance._cv:
                if notification == "other_bot_event":
                    instance._version += 1
                    instance._versions["other"] = instance._version
                instance._cv.notify_all()
            assert waiting.wait(1)
        with pytest.raises(WorkerError, match="timeout"):
            future.result(timeout=2)
    assert calls == ["idle"]


def test_matching_bot_event_wakes_state_wait():
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from .support.worker import Worker
    waiting = threading.Event()
    class Condition(threading.Condition):
        def wait(self, timeout=None):
            waiting.set()
            return super().wait(timeout)
    instance = object.__new__(Worker)
    instance._cv, instance._versions, instance._failure = Condition(), {}, None
    instance.snapshot = lambda bot: {"phase": "ready", "changed": bool(instance._versions.get(bot))}
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(instance.wait_state, "watched", lambda s: s["changed"], "matching event", 2)
        assert waiting.wait(1)
        with instance._cv:
            instance._versions["watched"] = 1
            instance._cv.notify_all()
        assert future.result(timeout=1)["changed"]


def test_transient_cleanup_failure_is_retried(tmp_path, monkeypatch):
    from .support import environment
    root = tmp_path / "runtime"
    root.mkdir()
    original = environment.shutil.rmtree
    calls = []
    def flaky(path, **kwargs):
        calls.append(path)
        if len(calls) == 1:
            raise PermissionError("temporary image handle")
        return original(path, **kwargs)
    monkeypatch.setattr(environment.shutil, "rmtree", flaky)
    environment.remove_runtime(root)
    assert len(calls) == 2 and not root.exists()


def test_permanent_cleanup_failure_is_not_hidden(tmp_path, monkeypatch):
    from .support import environment
    root = tmp_path / "runtime"
    root.mkdir()
    def fail(*args, **kwargs):
        raise PermissionError("retained handle")
    monkeypatch.setattr(environment.shutil, "rmtree", fail)
    with pytest.raises(PermissionError):
        environment.remove_runtime(root, timeout=0)
    assert root.exists()

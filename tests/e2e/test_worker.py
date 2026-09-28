"""Asset-independent worker contract tests. These do NOT establish game E2E coverage."""
import json
import socket
import subprocess

import pytest

from .support.environment import Environment, SetupError, allocate_ports
from .support.worker import Bot, UnsupportedScene, WorkerError


def test_capabilities(worker):
    caps = worker.request("capabilities")
    assert caps["profile"] == "sapphire-3.3"
    assert caps["scope"] == "loopback-only"
    assert "general_navigation" in caps["unsupported"]


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


def test_failed_connect_is_observed_not_ready(worker):
    # Reserve an unlistening port so another process cannot bind it during the test.
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        worker.request("login", "test", host="127.0.0.1", port=reserved.getsockname()[1],
                       session="test-session", character="Test User")
        with pytest.raises(WorkerError, match="connection failed"):
            worker.wait_state("test", lambda s: s["phase"] == "ready", "ready", timeout=5)
    worker.request("remove", "test")


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
    env.close()  # Cleanup is idempotent.


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


def test_ports_are_distinct():
    assert len(set(allocate_ports(4))) == 4


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


def test_unrelated_responses_do_not_cause_snapshot_polling():
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
                instance._cv.notify_all()  # An unrelated response, not a game-state event.
            assert waiting.wait(1)
        with pytest.raises(WorkerError, match="timeout"):
            future.result(timeout=2)
    assert calls == ["idle"]


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

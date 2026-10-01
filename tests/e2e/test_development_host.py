"""Warm-host lifecycle contracts; fake servers, no live game/database processes."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import time

import psutil
import pytest

from . import provision_development, run_development, serve_development
from .support.development import DevelopmentError, authenticate, check_managed_host, validate_profile
from .support.development_party import BOUND_METHODS
from .support.environment import redact_runtime_log


@pytest.fixture
def assets(tmp_path, monkeypatch):
    worker = tmp_path / "worker"
    worker.write_bytes(b"synthetic-worker")
    catalog = tmp_path / "catalog.json"
    catalog.write_text("synthetic-source-catalog")
    monkeypatch.setattr(serve_development, "load_quest_catalog",
                        lambda _: {"quest": 65686, "route": [[1, 2, 3], [2, 2, 3]]})
    return {"worker": str(worker), "quest_catalog": str(catalog)}


class FakeEnvironment:
    def __init__(self, assets, root):
        self.worker = Path(assets["worker"])
        self.root = root / "runtime"
        self.root.mkdir()
        self.artifacts = root / "artifacts"
        self.artifacts.mkdir()
        self.api_port, self.lobby_port, self.zone_port = 5000, 54994, 54992
        self.processes = {}
        self.starts = self.closes = 0
        self.fixtures = []
        self.failed = False

    def start(self):
        self.starts += 1
        self.processes = {name: SimpleNamespace(pid=index + 100) for index, name in
                          enumerate(("database", "api", "lobby", "world"))}

    def fresh_character(self, position):
        assert self.starts == 1 and position == [1, 2, 3]
        index = len(self.fixtures)
        row = {"username": f"e2e_fixture_{index}", "password": f"private-password-{index}",
               "name": f"Tester {'ABCDEFGHIJ'[index] * 10}"}
        self.fixtures.append(row)
        return row

    def check_alive(self):
        if self.failed:
            raise RuntimeError("simulated world failure")

    def close(self):
        self.closes += 1
        self.processes.clear()
        self.root.rmdir()


class Probe:
    returncode = 0
    def __init__(self, *args):
        self.closed = False
        self.process = SimpleNamespace(pid=12345,
            poll=lambda: self.returncode if self.closed else None)
    def __enter__(self): return self
    def __exit__(self, *_): self.closed = True
    def request(self, method):
        assert method == "capabilities"
        return {"methods": sorted(BOUND_METHODS)}


class Clock:
    def __init__(self): self.now = time.monotonic()
    def __call__(self): return self.now
    def sleep(self, seconds): self.now += seconds


def run_host(assets, tmp_path, *, on_ready=None, probe=Probe, maximum=60):
    env = FakeEnvironment(assets, tmp_path)
    clock = Clock()
    session = tmp_path / "session"
    def ready(status):
        if on_ready:
            on_ready(env, session, clock)
        else:
            (session / "stop").touch()
    report = serve_development.serve(assets, session, maximum_seconds=maximum,
        environment_factory=lambda _: env, worker_factory=probe,
        clock=clock, sleeper=clock.sleep, on_ready=ready)
    return report, env, session


def test_host_exports_three_distinct_accounts_and_stops_only_owned_runtime(assets, tmp_path):
    def ready(env, session, clock):
        bots = json.loads((session / "bot-profile.json").read_text())
        viewer = json.loads((session / "viewer-profile.json").read_text())
        server = json.loads((session / "server-profile.json").read_text())
        validate_profile(bots)
        check_managed_host(bots, clock=clock)
        assert "accounts" not in server
        assert len(bots["accounts"]) == 2 and viewer["account"] not in bots["accounts"]
        assert {a["username"] for a in bots["accounts"]} == {"e2e_fixture_0", "e2e_fixture_1"}
        assert viewer["account"]["username"] == "e2e_fixture_2"
        assert viewer["host_session"] == bots["host_session"]
        assert env.starts == 1 and len(env.fixtures) == 3
        (session / "stop").touch()
    report, env, session = run_host(assets, tmp_path, on_ready=ready)
    assert report["status"] == "stopped" and report["stop_reason"] == "operator_stop_file"
    assert report["cleanup_verified"] and report["private_profiles_removed"]
    assert env.starts == env.closes == 1 and not env.root.exists()
    assert not list(session.glob("*-profile.json"))
    assert "private-password" not in (session / "status.json").read_text()
    assert report["normal_lobby_creation_verified"] is False
    assert report["worker_preflight_exit"] == {
        "context_entered": True, "context_exit_attempted": True, "context_exit_completed": True,
        "process_exit_observed": True, "scope": "owned-native-worker-exit-not-server-session-closure",
        "process_id": 12345, "returncode": 0}
    assert not report["existing_database_access"] and not report["graphical_client_started"]


def test_existing_session_directory_is_never_reused(assets, tmp_path):
    session = tmp_path / "session"
    session.mkdir()
    (session / "status.json").write_text("retained evidence")
    with pytest.raises(FileExistsError):
        serve_development.serve(assets, session)
    assert (session / "status.json").read_text() == "retained evidence"


def test_bounded_host_expires_without_gameplay_sleep_masking(assets, tmp_path):
    report, env, _ = run_host(assets, tmp_path, on_ready=lambda *_: None)
    assert report["status"] == "stopped" and report["stop_reason"] == "bounded_lifetime_expired"
    assert report["elapsed_seconds"] == pytest.approx(60)
    assert env.starts == env.closes == 1


def test_process_loss_stops_host_without_restart(assets, tmp_path):
    report, env, _ = run_host(assets, tmp_path, on_ready=lambda env, *_: setattr(env, "failed", True))
    assert report["status"] == "failed" and report["cleanup_verified"]
    assert env.starts == env.closes == 1


def test_old_worker_rejected_before_server_start_or_fixtures(assets, tmp_path):
    class Old(Probe):
        def request(self, method): return {"methods": []}
    report, env, _ = run_host(assets, tmp_path, probe=Old)
    assert report["status"] == "failed" and report["failure_stage"] == "worker_preflight"
    assert env.starts == 0 and env.closes == 1 and not env.fixtures


@pytest.mark.parametrize("returncode", [1, -9, None, True])
def test_abnormal_or_unknown_preflight_worker_exit_prevents_server_start(assets, tmp_path, returncode):
    class Abnormal(Probe):
        pass
    Abnormal.returncode = returncode
    report, env, _ = run_host(assets, tmp_path, probe=Abnormal)
    assert report["status"] == "failed" and report["failure_stage"] == "worker_preflight"
    assert env.starts == 0 and env.closes == 1 and not env.fixtures
    receipt = report["worker_preflight_exit"]
    assert receipt["context_exit_completed"]
    assert receipt["process_exit_observed"] is (type(returncode) is int)


def test_preflight_worker_constructor_failure_stays_unobserved(assets, tmp_path):
    def fail(*_):
        raise RuntimeError("private constructor failure")
    report, env, _ = run_host(assets, tmp_path, probe=fail)
    assert report["status"] == "failed" and report["failure_stage"] == "worker_preflight"
    assert report["worker_preflight_exit"] == {
        "context_entered": False, "context_exit_attempted": False,
        "context_exit_completed": False, "process_exit_observed": False}
    assert env.starts == 0 and env.closes == 1 and not env.fixtures
    assert "private constructor failure" not in json.dumps(report)


def test_changed_private_file_is_not_deleted(assets, tmp_path):
    def ready(env, session, clock):
        (session / "bot-profile.json").write_text("user replacement")
        (session / "stop").touch()
    report, env, session = run_host(assets, tmp_path, on_ready=ready)
    assert report["status"] == "failed" and report["cleanup_verified"]
    assert not report["private_profiles_removed"]
    assert (session / "bot-profile.json").read_text() == "user replacement"
    assert not (session / "viewer-profile.json").exists()


def test_partial_export_is_reported_not_silently_removed(assets, tmp_path, monkeypatch):
    def broken(path, value):
        Path(path).write_text("partial private profile")
        raise OSError("disk error")
    monkeypatch.setattr(serve_development, "reserve_private_profile", broken)
    report, env, session = run_host(assets, tmp_path)
    assert report["status"] == "failed" and report["cleanup_verified"]
    assert report["profile_export_incomplete"] and not report["private_profiles_removed"]
    assert (session / "bot-profile.json").read_text() == "partial private profile"


def test_status_write_failure_does_not_skip_owned_cleanup(assets, tmp_path, monkeypatch):
    original = serve_development.publish_status
    environments = []
    def publish(path, report):
        if report["status"] in {"stopping", "stopped", "failed"}:
            raise OSError("status disk error")
        return original(path, report)
    monkeypatch.setattr(serve_development, "publish_status", publish)
    def ready(env, session, clock):
        environments.append(env)
        (session / "stop").touch()
    with pytest.raises(OSError):
        run_host(assets, tmp_path, on_ready=ready)
    assert environments[0].closes == 1 and not environments[0].root.exists()
    assert not list((tmp_path / "session").glob("*-profile.json"))


@pytest.mark.parametrize("value", [True, 59, 14401, 1.5])
def test_lifetime_invalid_before_resources(assets, tmp_path, value):
    with pytest.raises(DevelopmentError):
        serve_development.serve(assets, tmp_path / "session", maximum_seconds=value)
    assert not (tmp_path / "session").exists()


@pytest.fixture
def managed_profile(tmp_path):
    worker = tmp_path / "worker"
    worker.write_bytes(b"synthetic-worker")
    status_path = tmp_path / "status.json"
    process = psutil.Process()
    status = {"version": 1, "kind": "owned-development-host", "status": "ready", "session_id": "a" * 32,
              "owner_pid": process.pid, "owner_created": process.create_time(),
              "deadline_monotonic": time.monotonic() + 60, "api_port": 5000, "lobby_port": 54994,
              "protocol": "sapphire-3.3", "worker_sha256": hashlib.sha256(worker.read_bytes()).hexdigest(),
              "worker_preflight_exit": {
                  "scope": "owned-native-worker-exit-not-server-session-closure",
                  "context_entered": True, "context_exit_attempted": True,
                  "context_exit_completed": True, "process_exit_observed": True,
                  "process_id": 12345, "returncode": 0}}
    profile = {"version": 1, "mode": "shared-development", "protocol": "sapphire-3.3", "territory": 130,
               "worker": str(worker), "api_port": 5000, "lobby_port": 54994,
               "host_session": {"path": str(status_path), "id": "a" * 32},
               "accounts": [{"username": f"e2e_bot_{i}", "password": "private", "character": f"Bot {i}"}
                            for i in range(2)]}
    status_path.write_text(json.dumps(status))
    return profile, status, status_path


def test_managed_profile_requires_live_owner_and_exact_binding(managed_profile):
    profile, _, _ = managed_profile
    validate_profile(profile)
    check_managed_host(profile)


@pytest.mark.parametrize("patch", [{"status": "stopped"}, {"status": "failed"}, {"session_id": "b" * 32},
    {"api_port": 5001}, {"lobby_port": 1}, {"protocol": "wrong"}, {"version": True},
    {"deadline_monotonic": -1}, {"deadline_monotonic": float("nan")}, {"owner_pid": -1},
    {"owner_created": -1}, {"worker_sha256": "b" * 64}, {"worker_preflight_exit": None}])
def test_stale_or_wrong_host_rejected_before_auth_or_artifacts(managed_profile, tmp_path, patch, monkeypatch):
    profile, status, path = managed_profile
    status.update(patch)
    path.write_text(json.dumps(status))
    with pytest.raises(DevelopmentError): check_managed_host(profile)
    with pytest.raises(DevelopmentError): run_development.run(profile, tmp_path / "run", confirmed=True)
    assert not (tmp_path / "run").exists()
    server = {key: value for key, value in profile.items() if key != "accounts"}
    with pytest.raises(DevelopmentError):
        provision_development.run(server, tmp_path / "new-private.json", tmp_path / "provision", confirmed=True)
    assert not (tmp_path / "new-private.json").exists() and not (tmp_path / "provision").exists()
    monkeypatch.setattr("urllib.request.build_opener", lambda *args: pytest.fail("network attempted"))
    with pytest.raises(DevelopmentError): authenticate(profile, profile["accounts"][0])


@pytest.mark.parametrize("field,value", [
    ("context_entered", False), ("context_exit_attempted", False),
    ("context_exit_completed", False), ("process_exit_observed", False),
    ("process_id", 0), ("process_id", True), ("returncode", 1),
    ("returncode", True), ("scope", "server-session-closed")])
def test_managed_profile_rejects_malformed_or_failed_preflight_exit(managed_profile, field, value):
    profile, record, path = managed_profile
    record["worker_preflight_exit"][field] = value
    path.write_text(json.dumps(record))
    with pytest.raises(DevelopmentError):
        check_managed_host(profile)


@pytest.mark.parametrize("running,status", [(False, psutil.STATUS_RUNNING),
    (True, psutil.STATUS_ZOMBIE), (True, psutil.STATUS_DEAD)])
def test_nonlive_owner_is_rejected(managed_profile, running, status):
    profile, record, _ = managed_profile
    owner = SimpleNamespace(is_running=lambda: running, status=lambda: status,
                            create_time=lambda: record["owner_created"])
    with pytest.raises(DevelopmentError):
        check_managed_host(profile, process=lambda _: owner)


def test_stop_marker_and_missing_or_oversized_status_fail_closed(managed_profile):
    profile, _, path = managed_profile
    stop = path.with_name("stop")
    stop.touch()
    with pytest.raises(DevelopmentError): check_managed_host(profile)
    stop.unlink()
    path.write_text(" " * 16385)
    with pytest.raises(DevelopmentError): check_managed_host(profile)
    path.unlink()
    with pytest.raises(DevelopmentError): check_managed_host(profile)


def test_host_binding_schema_is_strict(managed_profile):
    profile, _, _ = managed_profile
    for binding in ({"path": "relative", "id": "a" * 32}, {"path": profile["host_session"]["path"], "id": "bad"}, None):
        bad = copy.deepcopy(profile)
        bad["host_session"] = binding
        with pytest.raises(DevelopmentError): validate_profile(bad)


def test_unknown_viewer_session_logs_are_redacted_without_registration():
    text = ("prefix Login request from session: new-session-token\r\n"
            "prefix Allowed connection with no session: other-token\n"
            "prefix Could not retrieve session: failed token with spaces\n"
            "normal line, password=known-password\n")
    redacted = redact_runtime_log(text, {"known", "known-password"})
    assert "new-session-token" not in redacted and "other-token" not in redacted
    assert "failed token" not in redacted and "known-password" not in redacted
    assert "normal line, password=<redacted>" in redacted
    assert redacted.count("<redacted>") == 4 and len(redacted.splitlines()) == 4

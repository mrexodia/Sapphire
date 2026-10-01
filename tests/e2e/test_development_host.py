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
from .inspect_development_host import main as inspect_host_main
from .inspect_managed_development_run import main as inspect_managed_main
from .inspect_managed_development_provisioning import main as inspect_provisioning_main
from .support.development import (DevelopmentError, authenticate, check_managed_host,
                                  require_managed_host_binding, validate_profile)
from .support.development_host_result import (SCOPE as HOST_RESULT_SCOPE,
                                              inspect_owned_development_host)
from .support.managed_development_result import (SCOPE as MANAGED_RESULT_SCOPE,
                                                 inspect_managed_development_run)
from .support.managed_provisioning_result import (SCOPE as MANAGED_PROVISIONING_SCOPE,
                                                  inspect_managed_provisioning)
from .support.development_binding import provisioning_binding
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
        self.process_starts = []
        self.process_teardowns = []
        self.starts = self.closes = 0
        self.fixtures = []
        self.failed = False

    def start(self):
        self.starts += 1
        self.processes = {name: SimpleNamespace(pid=index + 100) for index, name in
                          enumerate(("database", "api", "lobby", "world"))}
        self.process_starts = [{"process":name,"generation":1,"pid":process.pid}
                               for name,process in self.processes.items()]

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
        self.process_teardowns = [{**row,"was_running_before_cleanup":True,
            "terminate_requested":True,"kill_requested":False,"exit_observed":True,
            "returncode":-15,
            "scope":"exact-owned-isolated-process-teardown-not-graceful-server-exit"}
            for row in reversed(self.process_starts)]
        self.processes.clear()
        self.root.rmdir()
        (self.artifacts / "process-lifecycle.json").write_text(json.dumps({
            "version":1,
            "scope":"exact-owned-isolated-process-teardown-not-graceful-server-exit",
            "starts":self.process_starts,"teardowns":self.process_teardowns}))


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
    assert report["cleanup_verified"] and report["process_cleanup_verified"]
    assert report["private_profiles_removed"]
    assert report["environment_process_teardown"]["evidence"] == {
        "verified":True,
        "scope":"all-exact-owned-isolated-process-generations-observed-terminated",
        "process_count":4,"generations":{"api":1,"database":1,"lobby":1,"world":1}}
    assert env.starts == env.closes == 1 and not env.root.exists()
    assert not list(session.glob("*-profile.json"))
    assert "private-password" not in (session / "status.json").read_text()
    assert report["normal_lobby_creation_verified"] is False
    assert report["worker_preflight_exit"] == {
        "context_entered": True, "context_exit_attempted": True, "context_exit_completed": True,
        "process_exit_observed": True, "scope": "owned-native-worker-exit-not-server-session-closure",
        "process_id": 12345, "returncode": 0}
    assert not report["existing_database_access"] and not report["graphical_client_started"]
    proof = inspect_owned_development_host(session)
    assert proof["status"] == "accepted" and proof["scope"] == HOST_RESULT_SCOPE
    assert proof["process_teardown"]["process_count"] == 4


def managed_summary(path, receipt, worker_sha256):
    snapshot = {"version":1,
        "scope":"exact-local-account-lease-snapshot-not-server-session-or-offline-proof",
        "state":"clear","expected_lease_count":2,"present_lease_count":0,
        "records":[{"lease_index":0,"state":"absent"},{"lease_index":1,"state":"absent"}],
        "retained_run_id":None,"profile_or_account_values_disclosed":False,
        "lease_paths_or_keys_disclosed":False,"unrelated_entries_inspected":False,
        "filesystem_mutation_performed":False,"server_or_database_contacted":False,
        "active_session_checked":False,"offline_verified":False,"release_authorized":False,
        "cross_file_snapshot_atomic":False,"retained_receipts_match_run":False}
    route = [[0.0,0.0,0.0],[1.0,0.0,0.0]]
    movement = {"requested":True,"verified":True,
        "scope":"independent-witness-waypoints-not-server-authority-or-rendering",
        "cycles":1,"authored_route":route,"mover_entity_id":1,"witness_entity_id":2,
        "speed":2.0,"baseline_witness_sequence":1,
        "observations":[{"cycle":0,"step":0,"target":route[1],"received_position":route[1],"witness_sequence":2},
                        {"cycle":0,"step":1,"target":route[0],"received_position":route[0],"witness_sequence":3}]}
    report = {"version":1,"run_id":"b" * 32,"status":"passed",
        "scope":"shared-development-not-acceptance","protocol":"sapphire-3.3",
        "cycles":1,"entities":[1,2],"territory":130,"catalog_sha256":"d" * 64,
        "movement_waypoints_per_cycle":2,"movement_verification":movement,
        "party_verification":{"requested":False,"verified":False},
        "tell_verification":{"requested":False,"verified":False},
        "reconnect_verification":{"requested":False,"verified":False},
        "inventory_verification":{"requested":False,"verified":False},
        "sprint_verification":{"requested":False,"verified":False},
        "equipment_verification":{"requested":False,"verified":False},
        "decline_verification":{"requested":False,"verified":False},
        "viewer_verification":{"requested":False,"verified":False,"scope":"two-endpoint-say-and-persistent-witness-presence-not-rendering","viewer_login_or_control_performed":False},
        "server_identity_verified":False,"server_processes_owned":False,"database_access":False,
        "account_reset_performed_by_runner":False,"administrative_preparation_wait_enabled":False,
        "administrative_command_execution_attested":False,"world_restart_performed":False,
        "lease_retained":False,"worker_closed":True,"lease_snapshot_matches_run_state":True,
        "run_deadline":{"enabled":True,"limit_seconds":60,"expired":False,
            "session_work_completed_within_budget":True,
            "scope":"cooperative-success-deadline-not-hard-process-limit",
            "cleanup_may_exceed_deadline":True},
        "lease_snapshot":snapshot,"worker_sha256":worker_sha256,
        "managed_host_binding":{"requested":True,"verified":True,
            "start":receipt,"finish":copy.deepcopy(receipt),"same_binding_verified":True},
        "worker_exit":{"scope":"owned-native-worker-exit-not-server-session-closure",
            "context_entered":True,"context_exit_attempted":True,
            "context_exit_completed":True,"process_exit_observed":True,
            "process_id":999,"returncode":0}}
    path.write_text(json.dumps(report, indent=2))
    return report


def managed_provisioning_summary(path, profile, receipt, worker_sha256):
    base = managed_summary(path, receipt, worker_sha256)
    accounts = []
    for index, account in enumerate(profile["accounts"]):
        accounts.append({"slot":index,"character":account["character"],
            "account_creation":"fresh_login_verified",
            "character_creation":"refreshed_lobby_and_world_verified",
            "entity_id":100 + index,"character_id":1000 + index,"territory":130,
            "gm_rank":0,"logout_server_close_verified":True})
    report = {"version":1,"run_id":"c" * 32,"status":"provisioned",
        "scope":"shared-development-provisioning-not-gameplay",
        "ready_for_shared_checks":False,"server_identity_verified":False,
        "server_processes_owned":False,"database_access":False,
        "administrative_placement_performed":False,"credential_profile_saved":True,
        "worker_closed":True,"lease_retained":False,
        "lease_snapshot_matches_run_state":True,"lease_snapshot":base["lease_snapshot"],
        "worker_sha256":worker_sha256,"worker_exit":base["worker_exit"],
        "run_deadline":base["run_deadline"],"managed_host_binding":base["managed_host_binding"],
        "accounts":accounts,"elapsed_seconds":1.0,
        "timings":[{"phase":phase,"seconds":0.01,"outcome":"passed"} for phase in
            ("reserve_private_credential_profile","account_lease",
             "create_account_0","fresh_http_login_0","lobby_create_and_world_0","logout_0",
             "create_account_1","fresh_http_login_1","lobby_create_and_world_1","logout_1",
             "worker_session_including_close","managed_host_completion_binding",
             "provisioning_deadline_completion","release_accounts")],
        "next_step":"Opening/public-world preparation is still required before run_development. No placement or reset command was run."}
    report["provisioning_binding"] = provisioning_binding(profile, accounts)
    path.write_text(json.dumps(report, indent=2))
    return report


def test_terminal_host_inspector_is_read_only_and_cli_matches(assets, tmp_path, capsys):
    report, _, session = run_host(assets, tmp_path)
    before = {path.name:hashlib.sha256(path.read_bytes()).hexdigest()
              for path in session.iterdir() if path.is_file()}
    proof = inspect_owned_development_host(session)
    after = {path.name:hashlib.sha256(path.read_bytes()).hexdigest()
             for path in session.iterdir() if path.is_file()}
    assert before == after and proof["session_id"] == report["session_id"]
    assert inspect_host_main(["--session-dir", str(session)]) == 0
    assert json.loads(capsys.readouterr().out) == proof


def test_composite_managed_run_inspector_correlates_terminal_host_read_only(
        assets, tmp_path, capsys):
    captured = {}
    def ready(env, session, clock):
        profile = json.loads((session / "bot-profile.json").read_text())
        captured["receipt"] = check_managed_host(profile, clock=clock)
        (session / "stop").touch()
    host_report, _, session = run_host(assets, tmp_path, on_ready=ready)
    summary = tmp_path / "development-summary.json"
    managed_summary(summary, captured["receipt"], host_report["worker_sha256"])
    before = {path:hashlib.sha256(path.read_bytes()).hexdigest()
              for path in (summary, session / "status.json", session / "process-lifecycle.json")}
    proof = inspect_managed_development_run(session, summary)
    after = {path:hashlib.sha256(path.read_bytes()).hexdigest() for path in before}
    assert before == after and proof["scope"] == MANAGED_RESULT_SCOPE
    assert proof["host_session_id"] == host_report["session_id"]
    assert inspect_managed_main(["--session-dir",str(session),"--summary",str(summary)]) == 0
    assert json.loads(capsys.readouterr().out) == proof


@pytest.mark.parametrize("mutate", [
    lambda report:report.update(status="failed"),
    lambda report:report.update(server_processes_owned=True),
    lambda report:report["managed_host_binding"]["finish"].update(owner_pid=True),
    lambda report:report.update(worker_sha256="0" * 64),
    lambda report:report["worker_exit"].update(returncode=1),
    lambda report:report.update(lease_snapshot_matches_run_state=1),
    lambda report:report["run_deadline"].update(expired=True),
    lambda report:report["movement_verification"]["observations"][0].update(witness_sequence=1),
    lambda report:report.update(party_verification={"requested":False,"verified":True}),
    lambda report:report["viewer_verification"].update(viewer_login_or_control_performed=True),
])
def test_composite_managed_run_inspector_rejects_foreign_or_type_confused_run(
        assets, tmp_path, mutate):
    captured = {}
    def ready(env, session, clock):
        profile = json.loads((session / "bot-profile.json").read_text())
        captured["receipt"] = check_managed_host(profile, clock=clock)
        (session / "stop").touch()
    host_report, _, session = run_host(assets, tmp_path, on_ready=ready)
    summary = tmp_path / "development-summary.json"
    report = managed_summary(summary, captured["receipt"], host_report["worker_sha256"])
    mutate(report); summary.write_text(json.dumps(report))
    with pytest.raises(DevelopmentError):
        inspect_managed_development_run(session, summary)


def test_composite_managed_provisioning_inspector_is_read_only_and_redacted(
        assets, tmp_path, capsys):
    captured = {}
    def ready(env, session, clock):
        profile = json.loads((session / "bot-profile.json").read_text())
        captured["profile"] = profile
        captured["receipt"] = check_managed_host(profile, clock=clock)
        (session / "stop").touch()
    host_report, _, session = run_host(assets, tmp_path, on_ready=ready)
    profile_path = session / "retained-private-profile.json"
    profile = captured["profile"]
    profile_path.write_text(json.dumps(profile))
    summary = tmp_path / "provisioning-summary.json"
    managed_provisioning_summary(summary, profile, captured["receipt"], host_report["worker_sha256"])
    before = {path:hashlib.sha256(path.read_bytes()).hexdigest()
              for path in (profile_path, summary, session / "status.json",
                           session / "process-lifecycle.json")}
    proof = inspect_managed_provisioning(session, summary, profile_path)
    assert before == {path:hashlib.sha256(path.read_bytes()).hexdigest() for path in before}
    assert proof["scope"] == MANAGED_PROVISIONING_SCOPE
    text = json.dumps(proof)
    for account in profile["accounts"]:
        assert account["username"] not in text and account["password"] not in text
    assert inspect_provisioning_main(["--session-dir",str(session),"--summary",str(summary),
                                      "--profile",str(profile_path)]) == 0
    assert json.loads(capsys.readouterr().out) == proof


@pytest.mark.parametrize("mutate", [
    lambda report, profile:report.update(status="failed"),
    lambda report, profile:report.update(ready_for_shared_checks=True),
    lambda report, profile:report["accounts"][0].update(gm_rank=True),
    lambda report, profile:report["accounts"][1].update(character_id=report["accounts"][0]["character_id"]),
    lambda report, profile:report["provisioning_binding"].update(sha256="0" * 64),
    lambda report, profile:profile.update(host_session="0" * 32),
    lambda report, profile:report["run_deadline"].update(expired=True),
    lambda report, profile:report["managed_host_binding"]["finish"].update(api_port=True),
    lambda report, profile:report.update(recovery="retry"),
    lambda report, profile:report["timings"].reverse(),
])
def test_composite_managed_provisioning_rejects_partial_foreign_or_type_confused(
        assets, tmp_path, mutate):
    captured = {}
    def ready(env, session, clock):
        profile = json.loads((session / "bot-profile.json").read_text())
        captured["profile"] = profile
        captured["receipt"] = check_managed_host(profile, clock=clock)
        (session / "stop").touch()
    host_report, _, session = run_host(assets, tmp_path, on_ready=ready)
    profile = captured["profile"]
    summary = tmp_path / "provisioning-summary.json"
    report = managed_provisioning_summary(
        summary, profile, captured["receipt"], host_report["worker_sha256"])
    mutate(report, profile)
    summary.write_text(json.dumps(report))
    profile_path = session / "retained-private-profile.json"
    profile_path.write_text(json.dumps(profile))
    with pytest.raises(DevelopmentError):
        inspect_managed_provisioning(session, summary, profile_path)


def test_composite_managed_run_inspector_rejects_terminal_identity_mismatch(
        assets, tmp_path):
    captured = {}
    def ready(env, session, clock):
        profile = json.loads((session / "bot-profile.json").read_text())
        captured["receipt"] = check_managed_host(profile, clock=clock)
        (session / "stop").touch()
    host_report, _, session = run_host(assets, tmp_path, on_ready=ready)
    summary = tmp_path / "development-summary.json"
    managed_summary(summary, captured["receipt"], host_report["worker_sha256"])
    status_path = session / "status.json"
    status = json.loads(status_path.read_text()); status["owner_pid"] += 1
    status_path.write_text(json.dumps(status))
    with pytest.raises(DevelopmentError, match="identities differ"):
        inspect_managed_development_run(session, summary)


@pytest.mark.parametrize("mutate", [
    lambda status:status.update(status="failed"),
    lambda status:status.update(process_cleanup_verified=1),
    lambda status:status.update(private_profiles_removed=False),
    lambda status:status["owned_pids"].update(world=True),
    lambda status:status["owned_pids"].update(world=status["owned_pids"]["api"]),
    lambda status:status["environment_process_teardown"].update(sha256="0" * 64),
    lambda status:status["environment_process_teardown"]["evidence"].update(process_count=True),
    lambda status:status["timings"][0].update(seconds=float("nan")),
    lambda status:status.update(extra=True),
])
def test_terminal_host_inspector_rejects_partial_or_type_confused_status(
        assets, tmp_path, mutate):
    _, _, session = run_host(assets, tmp_path)
    path = session / "status.json"
    status = json.loads(path.read_text()); mutate(status)
    path.write_text(json.dumps(status))
    with pytest.raises(DevelopmentError):
        inspect_owned_development_host(session)


def test_terminal_host_inspector_rejects_nested_renamed_cleanup_marker(assets, tmp_path):
    _, _, session = run_host(assets, tmp_path)
    retained = session / "retained"; retained.mkdir()
    (retained / "Cleanup-Failure.JSON").write_text("{}")
    with pytest.raises(DevelopmentError, match="terminal cleanup failure"):
        inspect_owned_development_host(session)


def test_terminal_host_inspector_rejects_session_as_environment_artifact(assets, tmp_path):
    _, _, session = run_host(assets, tmp_path)
    status_path = session / "status.json"
    status = json.loads(status_path.read_text()); status["artifacts"] = str(session)
    status_path.write_text(json.dumps(status))
    with pytest.raises(DevelopmentError, match="artifact directory is unsafe"):
        inspect_owned_development_host(session)


def test_terminal_host_inspector_rejects_environment_cleanup_marker(assets, tmp_path):
    _, _, session = run_host(assets, tmp_path)
    status = json.loads((session / "status.json").read_text())
    retained = Path(status["artifacts"]) / "retained"; retained.mkdir()
    (retained / "Cleanup-Failure.JSON").write_text("{}")
    with pytest.raises(DevelopmentError, match="environment records terminal cleanup failure"):
        inspect_owned_development_host(session)


def test_terminal_host_inspector_rejects_environment_lifecycle_divergence(assets, tmp_path):
    _, _, session = run_host(assets, tmp_path)
    status = json.loads((session / "status.json").read_text())
    path = Path(status["artifacts"]) / "process-lifecycle.json"
    lifecycle = json.loads(path.read_text())
    lifecycle["teardowns"][0]["returncode"] = -9
    path.write_text(json.dumps(lifecycle))
    with pytest.raises(DevelopmentError, match="differs from environment artifact"):
        inspect_owned_development_host(session)


def test_terminal_host_inspector_rejects_changed_lifecycle_record(assets, tmp_path):
    _, _, session = run_host(assets, tmp_path)
    path = session / "process-lifecycle.json"
    lifecycle = json.loads(path.read_text())
    lifecycle["teardowns"][0]["returncode"] = True
    path.write_text(json.dumps(lifecycle))
    status_path = session / "status.json"
    status = json.loads(status_path.read_text())
    status["environment_process_teardown"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    status_path.write_text(json.dumps(status))
    with pytest.raises(DevelopmentError):
        inspect_owned_development_host(session)


def test_terminal_host_inspector_requires_all_four_exact_services(assets, tmp_path):
    _, _, session = run_host(assets, tmp_path)
    path = session / "process-lifecycle.json"
    lifecycle = json.loads(path.read_text())
    lifecycle["starts"] = [row for row in lifecycle["starts"] if row["process"] != "database"]
    lifecycle["teardowns"] = [row for row in lifecycle["teardowns"] if row["process"] != "database"]
    path.write_text(json.dumps(lifecycle))
    status_path = session / "status.json"
    status = json.loads(status_path.read_text())
    status["owned_pids"].pop("database")
    status["environment_process_teardown"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    status["environment_process_teardown"]["evidence"].update(
        process_count=3, generations={"api":1,"lobby":1,"world":1})
    (Path(status["artifacts"]) / "process-lifecycle.json").write_text(json.dumps(lifecycle))
    status_path.write_text(json.dumps(status))
    with pytest.raises(DevelopmentError, match="process teardown is incomplete"):
        inspect_owned_development_host(session)


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
    profile, status, path = managed_profile
    validate_profile(profile)
    receipt = check_managed_host(profile)
    assert receipt == {"managed":True,"verified":True,
        "scope":"cooperating-owned-host-ready-binding-not-server-session-lock",
        "session_id":"a" * 32,
        "status_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
        "owner_pid":status["owner_pid"],"owner_created":status["owner_created"],
        "deadline_monotonic":status["deadline_monotonic"],
        "api_port":5000,"lobby_port":54994,
        "worker_sha256":status["worker_sha256"],"preflight_worker_pid":12345}


def test_retained_managed_host_pair_rejects_type_confusion_or_changed_finish(managed_profile):
    profile, _, _ = managed_profile
    receipt = check_managed_host(profile)
    value = {"requested":True,"verified":True,"start":receipt,
             "finish":copy.deepcopy(receipt),"same_binding_verified":True}
    assert require_managed_host_binding(value, True) == value
    mutations = [
        lambda row:row.update(verified=1),
        lambda row:row["finish"].update(owner_pid=True),
        lambda row:row["finish"].update(status_sha256="0" * 64),
        lambda row:row["start"].update(preflight_worker_pid=0),
        lambda row:row.update(extra=True),
    ]
    for mutate in mutations:
        invalid = copy.deepcopy(value); mutate(invalid)
        with pytest.raises(DevelopmentError):
            require_managed_host_binding(invalid, True)


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

"""Synthetic policy/control-flow checks. No shared or disposable server is started."""
import copy
import json
from types import SimpleNamespace

import pytest

from . import run_development
from .support.development import (AccountLease, DevelopmentError, NoRedirect, Timings,
                                  authenticate, idle_state, movement_route, validate_profile, witnessed)
from .support.timing import PhaseTiming


@pytest.fixture
def profile(tmp_path):
    worker = tmp_path / "worker"
    worker.write_bytes(b"synthetic-worker-not-executable")
    return {"version": 1, "mode": "shared-development", "protocol": "sapphire-3.3",
            "worker": str(worker), "api_port": 5000, "lobby_port": 54994, "territory": 130,
            "accounts": [{"username": "e2e_mover", "password": "private-one", "character": "Bot Mover"},
                         {"username": "e2e_witness", "password": "private-two", "character": "Bot Witness"}]}


@pytest.mark.parametrize("key,value", [("api_port", True), ("lobby_port", 0),
    ("api_port", 65536), ("mode", "acceptance"), ("protocol", "unknown"),
    ("territory", 182), ("version", True), ("server_secret", "no"), ("db", {})])
def test_reject_profile_scope(profile, key, value):
    profile[key] = value
    with pytest.raises(DevelopmentError):
        validate_profile(profile)


@pytest.mark.parametrize("mutation", ["normal_account", "duplicate", "same_character", "missing_password"])
def test_dedicated_accounts_only(profile, mutation):
    if mutation == "normal_account":
        profile["accounts"][0]["username"] = "my_account"
    elif mutation == "duplicate":
        profile["accounts"][1]["username"] = "E2E_MOVER".lower()
    elif mutation == "same_character":
        profile["accounts"][1]["character"] = "bot mover"
    else:
        profile["accounts"][0].pop("password")
    with pytest.raises(DevelopmentError):
        validate_profile(profile)


def test_lease_conflict_rolls_back_only_own_locks(profile, tmp_path):
    root = tmp_path / "leases"
    first = AccountLease(profile, "first", root)
    first.acquire()
    with pytest.raises(DevelopmentError):
        AccountLease(profile, "second", root).acquire()
    assert len(list(root.glob("*.lock"))) == 2
    assert all(json.loads(p.read_text())["run_id"] == "first" for p in root.glob("*.lock"))
    first.release()
    assert not list(root.iterdir())


def test_partial_lease_acquisition_rolls_back(profile, tmp_path):
    root = tmp_path / "leases"
    lease = AccountLease(profile, "mine", root)
    root.mkdir()
    foreign = root / (lease.keys[1] + ".lock")
    foreign.write_text("foreign")
    with pytest.raises(DevelopmentError):
        lease.acquire()
    assert list(root.iterdir()) == [foreign]
    assert foreign.read_text() == "foreign"


class FakeWorker:
    """Models only normal worker semantics used by this runner."""
    def __init__(self, *args):
        self.commands = []
        self.closed = False
        # Synthetic process lifecycle for runner teardown contracts, not an OS process.
        self.process = SimpleNamespace(pid=12345, poll=lambda: 0 if self.closed else None)
        self.states = {}
        for index, name in enumerate(("mover", "witness")):
            self.states[name] = {"phase": "ready", "entity_id": index + 1, "gm_rank": 0,
                "territory": 130, "moving": False, "scene": None, "event_id": None,
                "observed_position": [0, 0, 0], "actors": {}, "chat": []}
        self.states["mover"]["actors"]["2"] = {"name": "Bot Witness", "gm_rank": 0, "position": [0, 0, 0]}
        self.states["witness"]["actors"]["1"] = {"name": "Bot Mover", "gm_rank": 0, "position": [0, 0, 0]}

    def request(self, method, bot=None, **args):
        self.commands.append(method)
        if method == "say":
            peer = "witness" if bot == "mover" else "mover"
            self.states[peer]["chat"].append({"actor": self.states[bot]["entity_id"], "message": args["message"]})
        if method == "walk_to":
            self.states["witness"]["actors"]["1"]["position"] = args["position"]
        if method == "logout":
            self.states[bot]["phase"] = "logged_out"
            if bot == "mover":
                self.states["witness"]["actors"].pop("1")
        return {}

    def snapshot(self, bot):
        return self.states[bot]

    def wait_state(self, bot, predicate, description, timeout=30):
        state = self.states[bot]
        if not predicate(state) and state["phase"] == "logged_out":
            state["phase"] = "logout_complete"
        if not predicate(state):
            raise DevelopmentError(description)
        return copy.deepcopy(state)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.closed = True


def execute(profile, tmp_path, fake=None, **kwargs):
    fake = fake or FakeWorker()
    report = run_development.run(profile, tmp_path / "run", confirmed=True,
        worker_factory=lambda *args: fake, login=lambda *_: {"lobbyHost": "127.0.0.1", "lobbyPort": 54994, "sId": "secret-session"},
        lease_root=tmp_path / "leases", **kwargs)
    return report, fake


def test_shared_smoke_lifecycle_and_timings(profile, tmp_path):
    report, fake = execute(profile, tmp_path, cycles=2)
    assert report["status"] == "passed"
    assert report["scope"] == "shared-development-not-acceptance"
    assert report["worker_closed"] and fake.closed
    assert not report["lease_retained"] and not list((tmp_path / "leases").iterdir())
    assert report["lease_snapshot"]["state"] == "clear"
    assert report["lease_snapshot_matches_run_state"] is True
    assert report["lease_snapshot"]["retained_receipts_match_run"] is False
    assert fake.commands.count("say") == 4
    assert fake.commands.count("logout") == 2
    assert set(fake.commands) == {"login", "say", "logout", "close", "remove"}
    assert report["timings"] and all(row["seconds"] >= 0 for row in report["timings"])
    text = (tmp_path / "run" / "development-summary.json").read_text()
    for secret in ("private-one", "private-two", "secret-session"):
        assert secret not in text


def test_failed_precondition_retains_leases_and_closes_worker(profile, tmp_path):
    fake = FakeWorker()
    fake.states["mover"]["territory"] = 141
    report, fake = execute(profile, tmp_path, fake)
    assert report["status"] == "failed" and report["lease_retained"]
    assert report["lease_snapshot"]["state"] == "retained"
    assert report["lease_snapshot"]["retained_run_id"] == report["run_id"]
    assert report["lease_snapshot"]["retained_receipts_match_run"] is True
    assert report["lease_snapshot_matches_run_state"] is True
    assert fake.closed and "say" not in fake.commands
    assert len(list((tmp_path / "leases").glob("*.lock"))) == 2


def test_failed_worker_close_retains_leases(profile, tmp_path):
    class BrokenClose(FakeWorker):
        def __exit__(self, *_):
            raise RuntimeError("secret-session")
    report, _ = execute(profile, tmp_path, BrokenClose())
    assert report["status"] == "failed" and report["lease_retained"]
    assert "secret-session" not in json.dumps(report)


def test_out_and_back_requires_each_independent_waypoint(profile, tmp_path, monkeypatch):
    monkeypatch.setattr(run_development, "movement_route", lambda _: ([[0, 0, 0], [1, 0, 0]], "catalog-hash"))
    report, fake = execute(profile, tmp_path)
    assert report["status"] == "passed" and fake.commands.count("walk_to") == 2
    class NoPublication(FakeWorker):
        def request(self, method, bot=None, **args):
            if method == "walk_to":
                return {}  # Acknowledgement is not independent movement proof.
            return super().request(method, bot, **args)
    other = tmp_path / "other"
    other.mkdir()
    failed, _ = execute(profile, other, NoPublication())
    assert failed["status"] == "failed" and failed["lease_retained"]


def test_opt_in_and_cycles_before_worker_or_artifacts(profile, tmp_path):
    with pytest.raises(DevelopmentError):
        run_development.run(profile, tmp_path / "run")
    for cycles in (0, 11, True, 1.5):
        with pytest.raises(DevelopmentError):
            run_development.run(profile, tmp_path / "run", confirmed=True, cycles=cycles)
    assert not (tmp_path / "run").exists()


def test_received_identity_and_positions_fail_closed():
    state = FakeWorker().states["witness"]
    assert witnessed(state, 1, "Bot Mover", [0, 0, 0])
    assert not witnessed(state, 1, "Someone Else")
    state["actors"]["1"]["position"] = [float("nan"), 0, 0]
    assert not witnessed(state, 1, "Bot Mover")
    state["observed_position"] = [float("inf"), 0, 0]
    assert not idle_state(state, 130)


@pytest.mark.parametrize("auth", [{"lobbyHost": "192.0.2.1", "lobbyPort": 54994, "sId": "secret"},
    {"lobbyHost": "127.0.0.1", "lobbyPort": 1, "sId": "secret"},
    {"lobbyHost": "127.0.0.1", "lobbyPort": 54994, "sId": ""}])
def test_http_login_rejects_wrong_handoff(profile, monkeypatch, auth):
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read(self, limit): return json.dumps(auth).encode()
    monkeypatch.setattr("urllib.request.build_opener", lambda *args: SimpleNamespace(open=lambda *a, **kw: Response()))
    with pytest.raises(DevelopmentError, match="endpoint"):
        authenticate(profile, profile["accounts"][0])
    assert NoRedirect().redirect_request(None, None, 302, "", {}, "http://example.invalid") is None


def test_http_login_uses_normal_endpoint_without_proxy(profile, monkeypatch):
    calls = []
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read(self, limit):
            assert limit == 1024 * 1024 + 1
            return json.dumps({"lobbyHost": "127.0.0.1", "lobbyPort": 54994, "sId": "token"}).encode()
    def open_request(request, timeout):
        assert request.full_url == "http://127.0.0.1:5000/sapphire-api/lobby/login"
        assert json.loads(request.data) == {"username": "e2e_mover", "pass": "private-one"}
        assert timeout == 10
        return Response()
    def opener(*handlers):
        calls.extend(handlers)
        return SimpleNamespace(open=open_request)
    monkeypatch.setattr("urllib.request.build_opener", opener)
    assert authenticate(profile, profile["accounts"][0])["sId"] == "token"
    assert calls[0].proxies == {} and isinstance(calls[1], NoRedirect)


def test_movement_prefix_is_bounded_and_source_bound(profile, tmp_path, monkeypatch):
    path = tmp_path / "catalog.json"
    path.write_text("synthetic catalog")
    profile["quest_catalog"] = str(path)
    monkeypatch.setattr("tests.e2e.support.development.load_quest_catalog",
                        lambda _: {"quest": 65686, "route": [[x, 0, 0] for x in range(20)]})
    route, identity = movement_route(profile)
    assert route == [[x, 0, 0] for x in range(6)] and len(identity) == 64
    profile["territory"] = 141
    with pytest.raises(DevelopmentError):
        movement_route(profile)
    profile["territory"] = 130
    monkeypatch.setattr("tests.e2e.support.development.load_quest_catalog",
                        lambda _: {"quest": 65687, "route": [[0, 0, 0], [1, 0, 0]]})
    with pytest.raises(DevelopmentError):
        movement_route(profile)


def test_existing_artifact_directory_never_overwritten(profile, tmp_path):
    path = tmp_path / "run"
    path.mkdir()
    (path / "evidence").write_text("retained")
    with pytest.raises(FileExistsError):
        run_development.run(profile, path, confirmed=True)
    assert (path / "evidence").read_text() == "retained"


def test_phase_timer_failure_and_pytest_report(tmp_path):
    timing = Timings()
    with pytest.raises(ValueError), timing.phase("failed"):
        raise ValueError()
    assert timing.rows[0]["outcome"] == "failed"
    path = tmp_path / "timings.json"
    plugin = PhaseTiming(path)
    for phase, duration in (("setup", 2), ("call", 3), ("teardown", 1)):
        plugin.pytest_runtest_logreport(SimpleNamespace(nodeid="example", when=phase, outcome="passed", duration=duration))
    plugin.pytest_sessionfinish(None, 0)
    report = json.loads(path.read_text())
    assert report["phase_seconds"] == {"setup": 2, "call": 3, "teardown": 1}
    with pytest.raises(FileExistsError):
        plugin.pytest_sessionfinish(None, 0)

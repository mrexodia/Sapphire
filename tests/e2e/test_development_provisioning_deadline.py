"""Cooperative provisioning-budget contracts; no server or account operations."""
import json

import pytest

from . import provision_development
from .support import development_deadline as budgets
from .support.development import DevelopmentError
from .test_development_provisioning import ProvisionWorker, server


class TimedProvisionWorker(ProvisionWorker):
    def __init__(self, now, stage=None):
        super().__init__()
        self.now, self.stage, self.deadline_scale = now, stage, 1
        self.timeouts = []

    def request(self, method, bot=None, **args):
        self.timeouts.append((method, args.get("timeout")))
        result = super().request(method, bot, **args)
        if self.stage == "request" and method == "login":
            self.now[0] = 2
        return result

    def wait_state(self, bot, predicate, description, timeout=30):
        self.timeouts.append((description, timeout))
        if ((self.stage == "world_wait" and description == "world ready") or
                (self.stage == "logout_wait" and description == "logout acknowledgement")):
            self.now[0] = 2
        result = super().wait_state(bot, predicate, description, timeout)
        if self.stage == "world_wait_result" and description == "world ready":
            self.now[0] = 2
        return result

    def __exit__(self, *args):
        result = super().__exit__(*args)
        if self.stage == "worker_cleanup":
            self.now[0] = 2
        return result


def run_timed(server, tmp_path, monkeypatch, stage):
    now = [0.0]
    monkeypatch.setattr(budgets.time, "monotonic", lambda: now[0])
    raw = TimedProvisionWorker(now, stage)
    output, artifacts = tmp_path / "private.json", tmp_path / "artifacts"
    calls = []
    original_reserve = provision_development.reserve_private_profile
    original_lease = provision_development.AccountLease

    class TimedLease(original_lease):
        def acquire(self):
            super().acquire()
            if stage == "lease":
                now[0] = 2

    def reserve(path, profile):
        original_reserve(path, profile)
        if stage == "reserve":
            now[0] = 2

    def register(profile, account):
        calls.append(("register", account["username"]))
        if stage == "register":
            now[0] = 2
        return {}

    def login(profile, account):
        calls.append(("login", account["username"]))
        if stage == "login":
            now[0] = 2
        return {"lobbyHost": "127.0.0.1", "lobbyPort": 54994, "sId": "private-session"}

    def factory(*args):
        if stage == "factory":
            now[0] = 2
        return raw

    monkeypatch.setattr(provision_development, "reserve_private_profile", reserve)
    monkeypatch.setattr(provision_development, "AccountLease", TimedLease)
    report = provision_development.run(server, output, artifacts, confirmed=True, max_seconds=1,
        worker_factory=factory, register=register, login=login, lease_root=tmp_path / "leases")
    return report, raw, calls, output


@pytest.mark.parametrize("stage", ["reserve", "lease", "factory", "register", "login", "request",
                                    "world_wait", "world_wait_result", "logout_wait",
                                    "worker_cleanup"])
def test_expiry_retains_uncertain_evidence_and_never_retries(server, tmp_path, monkeypatch, stage):
    report, raw, calls, output = run_timed(server, tmp_path, monkeypatch, stage)
    assert report["status"] == "failed"
    assert report["run_deadline"]["expired"]
    assert not report["run_deadline"]["session_work_completed_within_budget"]
    assert "provisioning_binding" not in report
    assert output.exists()  # Generated credentials survive every post-write expiry.
    assert "private-session" not in json.dumps(report)

    if stage == "reserve":
        assert report["credential_profile_saved"] and not report["lease_retained"]
        assert not raw.closed and not calls and not raw.commands
        assert not (tmp_path / "leases").exists()
        return

    assert report["credential_profile_saved"] and report["lease_retained"]
    assert len(list((tmp_path / "leases").glob("*.lock"))) == 2
    if stage == "lease":
        assert not raw.closed and not calls and not raw.commands
        return
    assert raw.closed
    if stage == "factory":
        assert not calls and not raw.commands
    elif stage == "register":
        assert len(calls) == 1 and calls[0][0] == "register" and not raw.commands
        assert report["accounts"][0]["account_creation"] == "requested_outcome_unknown"
    elif stage == "login":
        assert [kind for kind, _ in calls] == ["register", "login"] and not raw.commands
        assert report["accounts"][0]["account_creation"] == "acknowledged"
    elif stage == "request":
        assert raw.commands == ["login"]
        assert report["accounts"][0]["character_creation"] == "requested_outcome_unknown"
    if stage in {"world_wait", "world_wait_result"}:
        assert raw.commands == ["login"]
        assert report["accounts"][0]["character_creation"] == "requested_outcome_unknown"
    if stage == "logout_wait":
        assert raw.commands == ["login", "logout"]
        assert report["accounts"][0]["character_creation"] == "refreshed_lobby_and_world_verified"
        assert "logout_server_close_verified" not in report["accounts"][0]
    if stage == "worker_cleanup":
        assert report["worker_closed"] and len(report["accounts"]) == 2


def test_bounded_success_and_programmatic_disabled_default(server, tmp_path, monkeypatch):
    now = [0.0]
    monkeypatch.setattr(budgets.time, "monotonic", lambda: now[0])
    for maximum, name in ((1, "bounded"), (None, "legacy")):
        base = tmp_path / name
        raw = TimedProvisionWorker(now)
        report = provision_development.run(server, base / "private.json", base / "artifacts",
            confirmed=True, max_seconds=maximum, worker_factory=lambda *_: raw,
            register=lambda *_: {},
            login=lambda *_: {"lobbyHost":"127.0.0.1","lobbyPort":54994,"sId":"private-session"},
            lease_root=base / "leases")
        assert report["status"] == "provisioned" and not report["lease_retained"] and raw.closed
        assert report["run_deadline"]["enabled"] == (maximum is not None)
        if maximum is not None:
            assert report["run_deadline"]["session_work_completed_within_budget"]
            assert all(type(timeout) in (int, float) and 0 < timeout <= 1
                       for _, timeout in raw.timeouts)


@pytest.mark.parametrize("maximum", [True, 0, -1, 901, 1.5, "10"])
def test_invalid_budget_rejected_before_credentials_or_artifacts(server, tmp_path, maximum):
    with pytest.raises(DevelopmentError):
        provision_development.run(server, tmp_path / "private.json", tmp_path / "artifacts",
                                  confirmed=True, max_seconds=maximum)
    assert not (tmp_path / "private.json").exists() and not (tmp_path / "artifacts").exists()


@pytest.mark.parametrize("arguments,expected", [([], 300), (["--max-seconds", "45"], 45)])
def test_cli_default_and_explicit_budget(server, tmp_path, monkeypatch, arguments, expected):
    profile = tmp_path / "server.json"; profile.write_text(json.dumps(server))
    received = []
    def run(*args, **kwargs):
        received.append(kwargs["max_seconds"])
        return {"status":"provisioned", "scope":"synthetic", "elapsed_seconds":0}
    monkeypatch.setattr(provision_development, "run", run)
    assert provision_development.main(["--server-profile", str(profile),
        "--output-profile", str(tmp_path / "unused-private.json"),
        "--artifacts", str(tmp_path / "unused-artifacts"),
        "--create-new-bot-accounts", *arguments]) == 0
    assert received == [expected]

"""Provisioning control-flow/ownership contracts; never connects to a server."""
import json
import os
from pathlib import Path
import stat

import pytest

from . import provision_development
from .support.development import DevelopmentError, create_account


@pytest.fixture
def server(tmp_path):
    worker = tmp_path / "worker"
    worker.write_bytes(b"synthetic-worker")
    return {"version": 1, "mode": "shared-development", "protocol": "sapphire-3.3",
            "worker": str(worker), "api_port": 5000, "lobby_port": 54994, "territory": 130}


class ProvisionWorker:
    def __init__(self):
        self.states = {}
        self.commands = []
        self.closed = False

    def request(self, method, bot=None, **args):
        self.commands.append(method)
        if method == "login":
            assert args["create_character"] is True and args["creation_class"] == 1
            assert args["session"] == "private-session"
            self.states[bot] = {"phase": "ready", "gm_rank": 0, "territory": 182,
                                "entity_id": len(self.states) + 1, "created_via_lobby": True}
        if method == "logout":
            self.states[bot]["phase"] = "logged_out"
        return {}

    def wait_state(self, bot, predicate, description, timeout=30):
        state = self.states[bot]
        if not predicate(state) and state["phase"] == "logged_out":
            state["phase"] = "logout_complete"
        if not predicate(state):
            raise DevelopmentError(description)
        return state

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.closed = True


def execute(server, tmp_path, *, fake=None, register=None, login=None):
    fake = fake or ProvisionWorker()
    output, artifacts = tmp_path / "private.json", tmp_path / "artifacts"
    calls = []
    def creation(profile, account):
        assert output.exists()  # Credentials must survive even an uncertain request.
        saved = json.loads(output.read_text())
        assert account in saved["accounts"]
        calls.append(("create", account["username"]))
        return {}  # Deliberately only a receipt; login and world evidence are separate.
    def authentication(profile, account):
        calls.append(("login", account["username"]))
        return {"lobbyHost": "127.0.0.1", "lobbyPort": 54994, "sId": "private-session"}
    result = provision_development.run(server, output, artifacts, confirmed=True,
        worker_factory=lambda *_: fake, register=register or creation, login=login or authentication,
        lease_root=tmp_path / "leases")
    return result, fake, calls


def test_new_accounts_are_generated_and_not_adopted(server):
    first = provision_development.new_profile(server)
    second = provision_development.new_profile(server)
    assert len(first["accounts"]) == 2
    for account in first["accounts"]:
        assert account["username"].startswith("e2e_dev_") and len(account["password"]) == 48
        assert account not in second["accounts"]
        assert len(account["character"]) < 32
    with pytest.raises(DevelopmentError, match="server-only"):
        provision_development.new_profile(first)


def test_provisioning_requires_opt_in_before_any_artifacts(server, tmp_path):
    with pytest.raises(DevelopmentError):
        provision_development.run(server, tmp_path / "private.json", tmp_path / "artifacts")
    assert not (tmp_path / "private.json").exists()
    assert not (tmp_path / "artifacts").exists()


def test_success_is_provisioning_not_public_world_ready(server, tmp_path):
    result, fake, calls = execute(server, tmp_path)
    assert result["status"] == "provisioned"
    assert not result["ready_for_shared_checks"] and not result["administrative_placement_performed"]
    assert not result["database_access"] and not result["server_processes_owned"]
    assert result["credential_profile_saved"] and result["worker_closed"] and fake.closed
    assert [kind for kind, _ in calls] == ["create", "login", "create", "login"]
    assert calls[0][1] == calls[1][1] and calls[2][1] == calls[3][1] and calls[0][1] != calls[2][1]
    assert fake.commands == ["login", "logout", "close", "remove"] * 2
    assert not result["lease_retained"] and not list((tmp_path / "leases").iterdir())
    assert all(row["character_creation"] == "refreshed_lobby_and_world_verified"
               and row["account_creation"] == "fresh_login_verified"
               and row["logout_server_close_verified"] for row in result["accounts"])
    encoded = json.dumps(result)
    saved = json.loads((tmp_path / "private.json").read_text())
    assert "private-session" not in encoded
    assert all(account["password"] not in encoded for account in saved["accounts"])
    if os.name != "nt":
        assert stat.S_IMODE((tmp_path / "private.json").stat().st_mode) == 0o600


def test_uncertain_creation_never_retries_adopts_or_deletes(server, tmp_path):
    attempts = []
    def fail(profile, account):
        attempts.append(account)
        raise TimeoutError(account["password"])
    result, fake, calls = execute(server, tmp_path, register=fail)
    assert len(attempts) == 1 and not calls and not fake.commands
    assert fake.closed and result["lease_retained"]
    assert result["accounts"][0]["account_creation"] == "requested_outcome_unknown"
    assert result["accounts"][0]["character_creation"] == "not_started"
    assert result["status"] == "failed" and result["credential_profile_saved"]
    assert attempts[0]["password"] not in json.dumps(result)
    assert len(list((tmp_path / "leases").glob("*.lock"))) == 2


def test_creation_receipt_without_fresh_login_is_not_success(server, tmp_path):
    def fail(*_):
        raise DevelopmentError("login rejected")
    result, fake, calls = execute(server, tmp_path, login=fail)
    assert result["status"] == "failed" and result["lease_retained"]
    assert result["accounts"][0]["account_creation"] == "acknowledged"
    assert result["accounts"][0]["character_creation"] == "not_started"
    assert not fake.commands and [kind for kind, _ in calls] == ["create"]


@pytest.mark.parametrize("patch", [{"created_via_lobby": False}, {"gm_rank": 1}])
def test_normal_creation_and_non_gm_world_evidence_required(server, tmp_path, patch):
    class WrongState(ProvisionWorker):
        def request(self, method, bot=None, **args):
            result = super().request(method, bot, **args)
            if method == "login":
                self.states[bot].update(patch)
            return result
    result, fake, _ = execute(server, tmp_path, fake=WrongState())
    assert result["status"] == "failed" and result["lease_retained"] and fake.closed
    assert result["accounts"][0]["character_creation"] == "requested_outcome_unknown"
    assert fake.commands == ["login"]


def test_profile_conflict_stops_before_worker_or_network(server, tmp_path):
    output = tmp_path / "private.json"
    output.write_text("retained")
    result, fake, calls = execute(server, tmp_path)
    assert result["status"] == "failed" and not result["credential_profile_saved"]
    assert output.read_text() == "retained"
    assert not result["lease_retained"] and not calls and not fake.commands
    assert not (tmp_path / "leases").exists()


def test_profile_cannot_be_overwritten_by_diagnostic_artifacts(server, tmp_path):
    artifacts = tmp_path / "artifacts"
    with pytest.raises(DevelopmentError, match="outside"):
        provision_development.run(server, artifacts / "provisioning-summary.json", artifacts, confirmed=True)
    assert not artifacts.exists()


def test_profile_inside_checkout_must_be_ignored(server, tmp_path, monkeypatch):
    # Model a checkout without writing any secrets into the real checkout.
    monkeypatch.setattr(provision_development, "REPO", tmp_path)
    from types import SimpleNamespace
    monkeypatch.setattr(provision_development.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=1))
    with pytest.raises(DevelopmentError, match="git-ignored"):
        provision_development.reserve_private_profile(tmp_path / "tracked.json", server)
    assert not (tmp_path / "tracked.json").exists()


def test_create_account_uses_only_existing_normal_api(server, monkeypatch):
    from types import SimpleNamespace
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read(self, limit):
            return json.dumps({"lobbyHost": "127.0.0.1", "lobbyPort": 54994, "sId": "session"}).encode()
    def open_request(request, timeout):
        assert request.full_url == "http://127.0.0.1:5000/sapphire-api/lobby/createAccount"
        assert json.loads(request.data) == {"username": "e2e_new", "pass": "private"}
        assert timeout == 10
        return Response()
    monkeypatch.setattr("urllib.request.build_opener", lambda *args: SimpleNamespace(open=open_request))
    assert create_account(server, {"username": "e2e_new", "password": "private"})["sId"] == "session"

"""Provisioning control-flow/ownership contracts; never connects to a server."""
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
from types import SimpleNamespace

import pytest

from . import provision_development
from .inspect_development_provisioning import main as inspect_provisioning_main
from .support import development_artifact
from .support.development import DevelopmentError, create_account
from .support.environment import artifact_tree_sha256
from .support.development_provisioning_result import (
    SCOPE as DEVELOPMENT_PROVISIONING_SCOPE, inspect_development_provisioning)


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
        self.process = SimpleNamespace(pid=12345, poll=lambda: 0 if self.closed else None)

    def request(self, method, bot=None, **args):
        self.commands.append(method)
        if method == "login":
            assert args["create_character"] is True and args["creation_class"] == 1
            assert args["session"] == "private-session"
            entity = len(self.states) + 1
            self.states[bot] = {"phase": "ready", "gm_rank": 0, "territory": 182,
                                "entity_id": entity, "created_via_lobby": True,
                                "characters": [{"entity_id": entity, "character_id": 100 + entity,
                                                "name": args["character"]}]}
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


def managed_receipt(session="a"):
    return {"managed":True,"verified":True,
            "scope":"cooperating-owned-host-ready-binding-not-server-session-lock",
            "session_id":session * 32,"status_sha256":"b" * 64,
            "owner_pid":123,"owner_created":1000.0,"deadline_monotonic":2000.0,
            "api_port":5000,"lobby_port":54994,"worker_sha256":"c" * 64,
            "preflight_worker_pid":456}


def execute(server, tmp_path, *, fake=None, register=None, login=None, max_seconds=None):
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
        lease_root=tmp_path / "leases", max_seconds=max_seconds)
    return result, fake, calls


def test_external_provisioning_inspector_is_strict_sanitized_and_read_only(
        server, tmp_path, capsys):
    result, _, _ = execute(server, tmp_path, max_seconds=60)
    summary = tmp_path / "artifacts/provisioning-summary.json"
    profile_path = tmp_path / "private.json"
    before = {path:hashlib.sha256(path.read_bytes()).hexdigest()
              for path in (summary, profile_path, tmp_path / "artifacts/worker/ownership.json")}
    proof = inspect_development_provisioning(summary, profile_path)
    assert proof["scope"] == DEVELOPMENT_PROVISIONING_SCOPE
    assert proof["managed_host"] is False and proof["ready_for_shared_checks"] is False
    assert proof["worker_artifacts"]["sha256"] == result["worker_artifact_tree_sha256"]
    rendered = json.dumps(proof)
    profile = json.loads(profile_path.read_text())
    assert all(account["username"] not in rendered and account["password"] not in rendered
               for account in profile["accounts"])
    assert str(tmp_path) not in rendered
    assert before == {path:hashlib.sha256(path.read_bytes()).hexdigest() for path in before}
    assert inspect_provisioning_main(
        ["--summary",str(summary),"--profile",str(profile_path)]) == 0
    assert json.loads(capsys.readouterr().out) == proof


@pytest.mark.parametrize("mutation", ["status","managed","worker-tree","profile","duplicate"])
def test_external_provisioning_inspector_rejects_foreign_or_incomplete_evidence(
        server, tmp_path, mutation):
    execute(server, tmp_path, max_seconds=60)
    summary = tmp_path / "artifacts/provisioning-summary.json"
    profile_path = tmp_path / "private.json"
    report = json.loads(summary.read_text())
    if mutation == "status": report["status"] = "failed"
    elif mutation == "managed": report["managed_host_binding"]["requested"] = True
    elif mutation == "worker-tree":
        (tmp_path / "artifacts/worker/foreign.json").write_text("{}")
    elif mutation == "profile":
        profile = json.loads(profile_path.read_text())
        profile["accounts"][0]["character"] = "Foreign Character"
        profile_path.write_text(json.dumps(profile))
    else:
        summary.write_text(summary.read_text().replace(
            '{\n  "version": 1,', '{\n  "version": 1,\n  "version": 1,', 1))
    if mutation not in {"worker-tree","profile","duplicate"}:
        summary.write_text(json.dumps(report))
    with pytest.raises(DevelopmentError):
        inspect_development_provisioning(summary, profile_path)


def test_worker_artifact_identity_failure_never_retries_account_creation(
        server, tmp_path, monkeypatch):
    def fail(_):
        raise DevelopmentError("synthetic worker artifact identity failure")
    monkeypatch.setattr(development_artifact, "artifact_tree_sha256", fail)
    result, fake, calls = execute(server, tmp_path)
    assert result["status"] == "failed"
    assert result["failure_stage"] == "worker_artifact_identity"
    assert [kind for kind, _ in calls].count("create") == 2
    assert [kind for kind, _ in calls].count("login") == 2
    assert fake.closed and (tmp_path / "private.json").exists()


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
    assert result["worker_artifact_tree_sha256"] == artifact_tree_sha256(
        tmp_path / "artifacts/worker")
    assert result["managed_host_binding"] == {"requested":False,"verified":False,
        "start":{"managed":False,"verified":False,
                 "scope":"external-shared-server-without-owned-host-binding"},
        "finish":None,"same_binding_verified":False}
    assert result["worker_exit"] == {
        "context_entered": True, "context_exit_attempted": True, "context_exit_completed": True,
        "process_exit_observed": True, "scope": "owned-native-worker-exit-not-server-session-closure",
        "process_id": 12345, "returncode": 0}
    assert [kind for kind, _ in calls] == ["create", "login", "create", "login"]
    assert calls[0][1] == calls[1][1] and calls[2][1] == calls[3][1] and calls[0][1] != calls[2][1]
    assert fake.commands == ["login", "logout", "close", "remove"] * 2
    assert not result["lease_retained"] and not list((tmp_path / "leases").iterdir())
    assert result["lease_snapshot"]["state"] == "clear"
    assert result["lease_snapshot_matches_run_state"] is True
    assert result["lease_snapshot"]["retained_receipts_match_run"] is False
    assert all(row["character_creation"] == "refreshed_lobby_and_world_verified"
               and row["account_creation"] == "fresh_login_verified"
               and row["logout_server_close_verified"] for row in result["accounts"])
    encoded = json.dumps(result)
    saved = json.loads((tmp_path / "private.json").read_text())
    assert "private-session" not in encoded
    assert all(account["password"] not in encoded for account in saved["accounts"])
    if os.name != "nt":
        assert stat.S_IMODE((tmp_path / "private.json").stat().st_mode) == 0o600


def test_provisioning_binds_same_managed_host_at_completion(server, tmp_path, monkeypatch):
    receipt = managed_receipt()
    monkeypatch.setattr(provision_development, "check_managed_host",
                        lambda _:copy.deepcopy(receipt))
    result, _, _ = execute(server, tmp_path)
    assert result["status"] == "provisioned"
    assert result["managed_host_binding"] == {"requested":True,"verified":True,
        "start":receipt,"finish":receipt,"same_binding_verified":True}


def test_changed_managed_host_during_provisioning_retains_recovery_state(
        server, tmp_path, monkeypatch):
    calls = []
    def binding(_):
        calls.append(None)
        return managed_receipt("a" if len(calls) == 1 else "b")
    monkeypatch.setattr(provision_development, "check_managed_host", binding)
    result, fake, _ = execute(server, tmp_path)
    assert result["status"] == "failed" and result["lease_retained"] and fake.closed
    assert result["failure_stage"] == "managed_host_completion_binding"
    assert result["credential_profile_saved"]


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
    assert result["lease_snapshot"]["state"] == "retained"
    assert result["lease_snapshot"]["retained_run_id"] == result["run_id"]
    assert result["lease_snapshot"]["retained_receipts_match_run"] is True
    assert result["lease_snapshot_matches_run_state"] is True
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


@pytest.mark.parametrize("returncode", [1, -9, None, True])
def test_provisioning_never_releases_leases_without_normal_owned_worker_exit(server, tmp_path, returncode):
    fake = ProvisionWorker()
    fake.process.poll = lambda: returncode
    result, fake, calls = execute(server, tmp_path, fake=fake)
    assert result["status"] == "failed" and result["lease_retained"] and not result["worker_closed"]
    assert fake.closed and [kind for kind, _ in calls] == ["create", "login", "create", "login"]
    assert fake.commands == ["login", "logout", "close", "remove"] * 2
    assert len(list((tmp_path / "leases").glob("*.lock"))) == 2
    assert result["worker_exit"]["process_exit_observed"] is (type(returncode) is int)
    assert "provisioning_binding" not in result


def test_worker_constructor_failure_stays_unobserved_and_retains_provisioning_leases(server, tmp_path):
    output, artifacts = tmp_path / "private.json", tmp_path / "artifacts"
    def fail(*_):
        raise RuntimeError("private constructor failure")
    result = provision_development.run(server, output, artifacts, confirmed=True,
        worker_factory=fail, lease_root=tmp_path / "leases")
    assert result["status"] == "failed" and result["credential_profile_saved"]
    assert result["lease_retained"] and result["worker_exit"] == {
        "context_entered": False, "context_exit_attempted": False,
        "context_exit_completed": False, "process_exit_observed": False}
    assert len(list((tmp_path / "leases").glob("*.lock"))) == 2
    assert "private constructor failure" not in json.dumps(result)


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

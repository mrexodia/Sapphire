"""Synthetic reconnect controls; does not prove shared-server persistence."""
import copy
import json

import pytest

from . import run_development
from .support.development import DevelopmentError
from .test_development import FakeWorker, profile


class ReconnectWorker(FakeWorker):
    def __init__(self, failure=None):
        super().__init__()
        self.failure = failure
        self.requests = []
        for bot, name, entity in (("mover", "Bot Mover", 1), ("witness", "Bot Witness", 2)):
            self.states[bot]["characters"] = [{"name": name, "entity_id": entity, "character_id": entity + 100}]
        self.original = copy.deepcopy(self.states["mover"])
        self.actor_row = copy.deepcopy(self.states["witness"]["actors"]["1"])

    def request(self, method, bot=None, **args):
        self.requests.append((method, bot))
        if bot == "mover-reconnected" and method == "say":
            self.commands.append(method)
            if self.failure != "no_say":
                self.states["witness"]["chat"].append({"actor": 1, "message": args["message"]})
            return {}
        if bot == "mover-reconnected" and method == "logout":
            self.states["witness"]["actors"].pop("1", None)
        result = super().request(method, bot, **args)
        if bot == "mover" and method == "logout" and self.failure == "no_despawn":
            self.states["witness"]["actors"]["1"] = copy.deepcopy(self.actor_row)
        if bot == "mover-reconnected" and method == "login":
            state = copy.deepcopy(self.original)
            self.states[bot] = state
            self.states["witness"]["actors"]["1"] = copy.deepcopy(self.actor_row)
            if self.failure == "wrong_character_id":
                state["characters"][0]["character_id"] += 1
            elif self.failure == "wrong_entity_id":
                state["entity_id"] += 5
                state["characters"][0]["entity_id"] += 5
            elif self.failure == "wrong_name":
                state["characters"][0]["name"] = "Somebody Else"
            elif self.failure == "wrong_position":
                state["observed_position"] = [2, 0, 0]
            elif self.failure == "wrong_territory":
                state["territory"] = 141
            elif self.failure == "gm_character":
                state["gm_rank"] = 1
            elif self.failure == "no_respawn":
                self.states["witness"]["actors"].pop("1")
            elif self.failure == "wrong_witness_position":
                self.states["witness"]["actors"]["1"]["position"] = [2, 0, 0]
        return result

    def wait_state(self, bot, predicate, description, timeout=30):
        if self.failure == "no_server_close" and description == "server logout connection close":
            raise DevelopmentError("no close observed")
        return super().wait_state(bot, predicate, description, timeout)


def execute(profile, tmp_path, *, failure=None, verify=True, fake=None, await_placement=False):
    fake = fake or ReconnectWorker(failure)
    logins = []
    def login(config, account):
        logins.append(account["username"])
        if failure == "fresh_auth_failed" and len(logins) == 3:
            raise TimeoutError("private-password-or-session")
        return {"lobbyHost": "127.0.0.1", "lobbyPort": 54994, "sId": f"private-session-{len(logins)}"}
    result = run_development.run(profile, tmp_path / "run", confirmed=True,
        verify_reconnect=verify, await_placement=await_placement,
        worker_factory=lambda *_: fake, login=login, lease_root=tmp_path / "leases")
    return result, fake, logins


def test_reconnect_is_explicit_and_no_restart(profile, tmp_path):
    result, fake, logins = execute(profile, tmp_path, verify=False)
    assert result["status"] == "passed" and len(logins) == 2
    assert result["reconnect_verification"] == {"requested": False, "verified": False}
    assert all(bot != "mover-reconnected" for _, bot in fake.requests)
    assert not result["world_restart_performed"]


def test_fresh_auth_identity_position_respawn_and_liveness(profile, tmp_path):
    result, fake, logins = execute(profile, tmp_path)
    assert result["status"] == "passed" and result["worker_closed"] and fake.closed
    assert logins == ["e2e_mover", "e2e_witness", "e2e_mover"]
    proof = result["reconnect_verification"]
    assert proof["verified"] and proof["requested"]
    assert proof["scope"] == "fresh-login-position-not-world-restart"
    assert proof["identity_before"] == proof["identity_after"] == {
        "name": "Bot Mover", "entity_id": 1, "character_id": 101}
    assert proof["witness_before"] == proof["received_after"] == proof["witness_after"] == [0, 0, 0]
    assert proof["old_server_close_observed"] and proof["independent_despawn_observed"] and proof["post_login_say_observed"]
    assert not result["lease_retained"] and not list((tmp_path / "leases").iterdir())
    assert fake.requests.index(("remove", "mover")) < fake.requests.index(("login", "mover-reconnected"))
    assert fake.requests.index(("login", "mover-reconnected")) < fake.requests.index(("logout", "witness"))
    assert fake.requests.count(("login", "mover-reconnected")) == 1
    assert fake.requests.count(("logout", "mover")) == 1
    assert fake.requests.count(("logout", "mover-reconnected")) == 1
    assert set(fake.commands) == {"login", "say", "logout", "close", "remove"}
    phases = {row["phase"] for row in result["timings"]}
    assert {"reconnect_fresh_http_login", "reconnect_independent_respawn_and_say"} <= phases
    assert "private-session" not in json.dumps(result)


@pytest.mark.parametrize("failure", ["no_despawn", "no_server_close", "fresh_auth_failed",
    "wrong_character_id", "wrong_entity_id", "wrong_name", "wrong_position", "wrong_territory",
    "gm_character", "no_respawn", "wrong_witness_position", "no_say"])
def test_failed_reconnect_never_retries_or_releases_uncertain_accounts(profile, tmp_path, failure):
    result, fake, logins = execute(profile, tmp_path, failure=failure)
    assert result["status"] == "failed" and result["lease_retained"] and fake.closed
    assert result["reconnect_verification"] == {"requested": True, "verified": False}
    assert len(list((tmp_path / "leases").glob("*.lock"))) == 2
    assert fake.requests.count(("login", "mover-reconnected")) <= 1
    assert len(logins) <= 3
    if failure in {"no_despawn", "no_server_close"}:
        assert len(logins) == 2 and ("login", "mover-reconnected") not in fake.requests
    if failure == "fresh_auth_failed":
        assert ("login", "mover-reconnected") not in fake.requests
    assert "private-password-or-session" not in json.dumps(result)


def test_reconnect_flag_rejects_non_boolean_before_side_effects(profile, tmp_path):
    for value in (1, "yes", None):
        with pytest.raises(DevelopmentError):
            run_development.run(profile, tmp_path / "run", confirmed=True, verify_reconnect=value)
    assert not (tmp_path / "run").exists()


def test_placement_preparation_and_reconnect_have_separate_evidence(profile, tmp_path, monkeypatch):
    monkeypatch.setattr(run_development, "movement_route", lambda _: ([[0, 0, 0], [1, 0, 0]], "a" * 64))
    class Prepared(ReconnectWorker):
        def __init__(self):
            super().__init__()
            for state in self.states.values():
                state["territory"] = 182
        def wait_state(self, bot, predicate, description, timeout=30):
            if description.startswith("operator-prepared"):
                self.states[bot]["territory"] = 130
            return super().wait_state(bot, predicate, description, timeout)
    result, _, _ = execute(profile, tmp_path, fake=Prepared(), await_placement=True)
    assert result["status"] == "passed" and result["reconnect_verification"]["verified"]
    assert result["administrative_preparation_wait_enabled"]
    assert not result["administrative_command_execution_attested"]
    phases = [row["phase"] for row in result["timings"]]
    assert phases.index("administrative_placement_wait_not_gameplay") < phases.index("reconnect_fresh_http_login")


def test_endpoint_is_verified_after_source_bound_out_and_back(profile, tmp_path, monkeypatch):
    monkeypatch.setattr(run_development, "movement_route", lambda _: ([[0, 0, 0], [1, 0, 0]], "a" * 64))
    result, fake, _ = execute(profile, tmp_path)
    assert result["status"] == "passed"
    assert fake.commands.count("walk_to") == 2
    assert result["reconnect_verification"]["expected_position"] == [0, 0, 0]

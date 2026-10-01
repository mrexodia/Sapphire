"""Read-only reconnect inventory projection and lifecycle contracts."""
import copy

import pytest

from . import run_development
from .support.development import DevelopmentError, received_character_identity
from .support import development_inventory as inventory
from .test_development import profile
from .test_development_reconnect import ReconnectWorker


def rewards():
    return {"inventory_ready": True, "containers": {str(k): True for k in inventory.CONTAINERS},
            "inventory": {"0:2": {"storage": 0, "slot": 2, "id": 5890, "count": 3},
                          "1000:0": {"storage": 1000, "slot": 0, "id": 1601, "count": 1},
                          "2000:0": {"storage": 2000, "slot": 0, "id": 1, "count": 208}}}


class InventoryWorker(ReconnectWorker):
    def __init__(self, failure=None):
        super().__init__()
        self.inventory_failure = failure
        for state in self.states.values():
            state.update(seq=100, between_areas=False, rewards=rewards())
        if failure == "incomplete_before":
            self.states["mover"]["rewards"]["containers"].pop("1000")
        self.original = copy.deepcopy(self.states["mover"])

    def request(self, method, bot=None, **args):
        result = super().request(method, bot, **args)
        if method == "login" and bot == "mover-reconnected":
            state = self.states[bot]
            state["seq"] = 80  # Fresh sessions need not have larger sequence numbers.
            f = self.inventory_failure
            if f == "changed_count": state["rewards"]["inventory"]["0:2"]["count"] += 1
            if f == "changed_item": state["rewards"]["inventory"]["1000:0"]["id"] += 1
            if f == "changed_gil": state["rewards"]["inventory"]["2000:0"]["count"] += 1
            if f == "removed_item": state["rewards"]["inventory"].pop("0:2")
            if f == "added_item": state["rewards"]["inventory"]["0:3"] = {"storage":0,"slot":3,"id":5890,"count":1}
            if f == "incomplete_after": state["rewards"]["containers"].pop("1000")
            if f == "wrong_slot_key": state["rewards"]["inventory"]["0:2"]["slot"] = 3
        return result


def execute(profile, tmp_path, failure=None, enabled=True):
    worker = InventoryWorker(failure)
    result = run_development.run(profile, tmp_path / "run", confirmed=True,
        verify_reconnect=True, verify_inventory=enabled, worker_factory=lambda *_: worker,
        login=lambda *_: {"lobbyHost":"127.0.0.1","lobbyPort":54994,"sId":"private"},
        lease_root=tmp_path / "leases")
    return result, worker


def test_complete_received_projection_matches_after_exact_fresh_login(profile, tmp_path):
    result, worker = execute(profile, tmp_path)
    assert result["status"] == "passed" and result["worker_closed"] and not result["lease_retained"]
    proof = result["inventory_verification"]
    assert proof["verified"] and proof["changed_slots"] == []
    assert proof["before"]["inventory"] == proof["after"]["inventory"] == rewards()["inventory"]
    # The initial reciprocal Say now advances the synthetic mover sequence before capture.
    assert proof["before"]["received_sequence"] == 101 and proof["after"]["received_sequence"] == 80
    assert proof["before"]["containers"] == [0, 1, 2, 3, 1000, 2000]
    assert set(worker.commands) == {"login", "say", "logout", "close", "remove"}
    phases = [x["phase"] for x in result["timings"]]
    assert phases.index("reconnect_inventory_before_logout") < phases.index("reconnect_logout_and_despawn")
    assert phases.index("reconnect_lobby_world_identity_position") < phases.index("reconnect_inventory_after_login")


@pytest.mark.parametrize("failure", ["changed_count", "changed_item", "changed_gil", "removed_item", "added_item",
                                     "incomplete_before", "incomplete_after", "wrong_slot_key"])
def test_uncertain_inventory_retains_evidence_leases_and_never_restores_or_retries(profile, tmp_path, failure):
    result, worker = execute(profile, tmp_path, failure)
    assert result["status"] == "failed" and worker.closed and result["lease_retained"]
    assert not result["inventory_verification"]["verified"]
    assert len(list((tmp_path / "leases").glob("*.lock"))) == 2
    assert set(worker.commands) <= {"login", "say", "logout", "close", "remove"}
    assert worker.requests.count(("login", "mover-reconnected")) <= 1
    if failure == "incomplete_before":
        assert ("logout", "mover") not in worker.requests
        assert ("login", "mover-reconnected") not in worker.requests
    if failure.startswith("changed") or failure in {"removed_item", "added_item"}:
        proof = result["inventory_verification"]
        assert proof["before"] and proof["after"] and proof["changed_slots"]


def test_opt_in_and_reconnect_prerequisite(profile, tmp_path):
    result, _ = execute(profile, tmp_path, "changed_count", enabled=False)
    assert result["status"] == "passed"
    assert result["inventory_verification"] == {"requested": False, "verified": False}
    for kwargs in ({"verify_inventory": True}, {"verify_inventory": 1, "verify_reconnect": True}):
        with pytest.raises(DevelopmentError):
            run_development.run(profile, tmp_path / "invalid", confirmed=True, **kwargs)
    assert not (tmp_path / "invalid").exists()


@pytest.mark.parametrize("change", [
    lambda s: s.update(seq=True),
    lambda s: s.update(gm_rank=90),
    lambda s: s.update(between_areas=True),
    lambda s: s["characters"][0].update(character_id=999),
    lambda s: s["rewards"].update(inventory_ready=1),
    lambda s: s["rewards"]["containers"].update({"0":1}),
    lambda s: s["rewards"].update(inventory=[]),
    lambda s: s["rewards"]["inventory"].update({"00:2":s["rewards"]["inventory"].pop("0:2")}),
    lambda s: s["rewards"]["inventory"]["0:2"].update(count=True),
    lambda s: s["rewards"]["inventory"]["0:2"].update(count=0),
    lambda s: s["rewards"]["inventory"]["0:2"].update(id=-1),
    lambda s: s["rewards"]["inventory"]["0:2"].update(id=2**32),
    lambda s: s["rewards"]["inventory"].update({"0:25":{"storage":0,"slot":25,"id":5890,"count":1}}),
    lambda s: s["rewards"]["inventory"].update({"1000:14":{"storage":1000,"slot":14,"id":1601,"count":1}}),
])
def test_malformed_or_foreign_projection_is_rejected(change):
    state = InventoryWorker().snapshot("mover")
    identity = received_character_identity(state, "Bot Mover")
    change(state)
    with pytest.raises(DevelopmentError): inventory.inventory_projection(state, identity, 130)


@pytest.mark.parametrize("storage", inventory.CONTAINERS)
def test_each_selected_container_must_be_complete(storage):
    state = InventoryWorker().snapshot("mover")
    identity = received_character_identity(state, "Bot Mover")
    state["rewards"]["containers"].pop(str(storage))
    assert inventory.inventory_projection(state, identity, 130) is None


def test_projection_is_detached_and_excludes_unclaimed_fields_and_containers():
    state = InventoryWorker().snapshot("mover")
    identity = received_character_identity(state, "Bot Mover")
    state["rewards"]["inventory"]["2001:0"] = {"storage":2001,"slot":0,"id":2,"count":100}
    state["rewards"]["inventory"]["0:2"]["unclaimed_field"] = "not proof"
    proof = inventory.inventory_projection(state, identity, 130)
    assert proof["inventory"] == rewards()["inventory"]
    state["rewards"]["inventory"]["0:2"]["count"] = 99
    assert proof["inventory"]["0:2"]["count"] == 3


def test_late_complete_observation_fails(monkeypatch):
    worker = InventoryWorker(); identity = received_character_identity(worker.snapshot("mover"), "Bot Mover")
    clock = iter([100, 111])
    monkeypatch.setattr(inventory.time, "monotonic", lambda: next(clock))
    with pytest.raises(DevelopmentError, match="late"):
        inventory.capture_inventory(worker, type("Bot", (), {"name":"mover"})(), identity, 130)

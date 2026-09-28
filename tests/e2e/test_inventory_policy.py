"""Synthetic inventory contracts: acknowledgements are never mutation evidence."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from .support.worker import Bot
from .test_live_quest import move_reward_and_verify_reconnect, swap_reward_and_verify_restart


def test_move_request_waits_for_exact_ack_without_predicting_inventory():
    before = {"0:1": {"storage": 0, "slot": 1, "id": 4555, "count": 3}}
    states = [{"rewards": {"inventory": deepcopy(before), "operation_batches": [row]}}
              for row in ({"context": 123, "operation": 8, "error": 0},
                          {"context": 456, "operation": 7, "error": 0},
                          {"context": 456, "operation": 8, "error": 1},
                          {"context": 456, "operation": 8, "error": 0})]

    class Worker:
        def request(self, method, bot, **args):
            assert method == "request_item_move" and bot == "subject"
            assert args == {"storage": 0, "slot": 1, "destination_storage": 3,
                            "destination_slot": 24, "expected_item": 4555}
            return {"context": 456}

        def wait_state(self, bot, predicate, description, timeout):
            assert timeout == 17 and "not inventory mutation" in description
            assert [predicate(s) for s in states] == [False, False, False, True]
            return states[-1]

    receipt = Bot(Worker(), "subject").request_item_move(0, 1, 3, 24, 4555, timeout=17)
    assert receipt == {"context": 456, "operation": 8, "acknowledged": True, "inventory_change_verified": False}
    assert all(state["rewards"]["inventory"] == before for state in states)


def test_swap_request_waits_for_exact_ack_without_predicting_inventory():
    before = {"0:1": {"storage": 0, "slot": 1, "id": 4555, "count": 3},
              "3:24": {"storage": 3, "slot": 24, "id": 4551, "count": 2}}
    states = [{"rewards": {"inventory": deepcopy(before), "operation_batches": [row]}}
              for row in ({"context": 789, "operation": 8, "error": 0},
                          {"context": 789, "operation": 9, "error": 1},
                          {"context": 789, "operation": 9, "error": 0})]

    class Worker:
        def request(self, method, bot, **args):
            assert method == "request_item_swap" and bot == "subject"
            assert args == {"storage": 0, "slot": 1, "destination_storage": 3,
                            "destination_slot": 24, "expected_item": 4555,
                            "expected_destination_item": 4551}
            return {"context": 789}

        def wait_state(self, bot, predicate, description, timeout):
            assert timeout == 19 and "not inventory mutation" in description
            assert [predicate(s) for s in states] == [False, False, True]
            return states[-1]

    receipt = Bot(Worker(), "subject").request_item_swap(0, 1, 3, 24, 4555, 4551, timeout=19)
    assert receipt == {"context": 789, "operation": 9, "acknowledged": True,
                       "inventory_change_verified": False}
    assert all(state["rewards"]["inventory"] == before for state in states)


@pytest.mark.parametrize("method,operation,counts", [
    ("request_item_split", 10, {"expected_count": 3, "split_count": 1}),
    ("request_item_merge", 12, {"expected_count": 1, "expected_destination_count": 2}),
])
def test_split_merge_acknowledgements_never_predict_inventory(method, operation, counts):
    before = {"0:1": {"storage": 0, "slot": 1, "id": 4555, "count": 3}}

    class Worker:
        def request(self, actual, bot, **args):
            assert actual == method and bot == "subject"
            assert args == {"storage": 0, "slot": 1, "destination_storage": 3,
                            "destination_slot": 24, "expected_item": 4555, **counts}
            return {"context": 321}

        def wait_state(self, bot, predicate, description, timeout):
            states = [{"rewards": {"inventory": deepcopy(before), "operation_batches": [row]}}
                      for row in ({"context": 321, "operation": operation - 1, "error": 0},
                                  {"context": 321, "operation": operation, "error": 1},
                                  {"context": 321, "operation": operation, "error": 0})]
            assert [predicate(state) for state in states] == [False, False, True]
            return states[-1]

    bot = Bot(Worker(), "subject")
    if method.endswith("split"):
        receipt = bot.request_item_split(0, 1, 3, 24, 4555, 3, 1)
    else:
        receipt = bot.request_item_merge(0, 1, 3, 24, 4555, 1, 2)
    assert receipt == {"context": 321, "operation": operation, "acknowledged": True,
                       "inventory_change_verified": False}


class MoveFixture:
    """Exercise the actual scenario verifier with deliberately wrong fresh snapshots."""
    def __init__(self):
        self.before = {"0:0": {"storage": 0, "slot": 0, "id": 4551, "count": 2},
                       "0:1": {"storage": 0, "slot": 1, "id": 4555, "count": 3},
                       "1000:0": {"storage": 1000, "slot": 0, "id": 1601, "count": 1}}
        self.after = deepcopy(self.before)
        item = self.after.pop("0:1")
        item.update(storage=3, slot=24)
        self.after["3:24"] = item
        self.expected = {"synthetic_rewards": True}
        self.reconnected = False
        self.present = True
        self.identity = 7
        self.position = [1, 0, 2]
        self.calls = []
        self.name = "subject"

    def expect_rewards(self, expected, work_index):
        assert expected == self.expected and work_index == 1
        self.calls.append("rewards")
        return {"entity_id": 7, "rewards": {"inventory": deepcopy(self.after if self.reconnected else self.before),
                                            "containers": {"3": True}}}

    def request_item_move(self, *args, **kwargs):
        self.calls.append("move_request")
        assert args == (0, 1, 3, 24) and kwargs == {"expected_item": 4555}
        return {"context": 99, "operation": 8, "acknowledged": True, "inventory_change_verified": False}

    def logout(self):
        self.calls.append("logout")
        self.present = False

    def close(self):
        self.calls.append("remove")

    def api(self, method, payload):
        self.calls.append("http_login")
        assert method == "login" and payload == {"username": "synthetic-user", "pass": "synthetic-password"}
        return {"sId": "synthetic-session"}

    def login_via_lobby(self, auth, name):
        self.calls.append("lobby_login")
        assert auth == {"sId": "synthetic-session"} and name == "Fixture Name"
        self.reconnected = self.present = True
        return {"entity_id": self.identity, "observed_position": self.position}

    def wait_state(self, bot, predicate, description, timeout=30):
        assert bot == "observer"
        state = {"actors": {"7": {"position": [1, 0, 2]}} if self.present else {}}
        assert predicate(state)
        self.calls.append("observer")
        return state

    def expect_quest_complete(self, quest):
        self.calls.append(quest)

    def verify(self):
        fixture = {"username": "synthetic-user", "password": "synthetic-password", "name": "Fixture Name"}
        return move_reward_and_verify_reconnect(self, self, self, SimpleNamespace(name="observer"),
                                               fixture, self.expected, 1, [65686, 65687])


def test_scenario_requires_fresh_login_and_exact_slot_placement():
    fixture = MoveFixture()
    original = deepcopy(fixture.before)
    expected, evidence = fixture.verify()
    assert expected == fixture.after == evidence["after_reconnect"]
    assert evidence["before"] == fixture.before == original
    assert evidence["receipt"]["inventory_change_verified"] is False
    assert fixture.calls == ["rewards", "observer", "move_request", "logout", "observer", "remove",
                             "http_login", "lobby_login", "observer", "rewards", 65686, 65687]


@pytest.mark.parametrize("fault", ["ack_only", "duplicate", "wrong_count", "wrong_slot", "other_item_lost", "equipment_changed"])
def test_acknowledgement_or_totals_alone_cannot_satisfy_move_verifier(fault):
    fixture = MoveFixture()
    if fault == "ack_only":
        fixture.after = deepcopy(fixture.before)
    elif fault == "duplicate":
        fixture.after["0:1"] = deepcopy(fixture.before["0:1"])
    elif fault == "wrong_count":
        fixture.after["3:24"]["count"] = 2
    elif fault == "wrong_slot":
        item = fixture.after.pop("3:24")
        item["slot"] = 23
        fixture.after["3:23"] = item  # Same bag totals, wrong placement.
    elif fault == "other_item_lost":
        del fixture.after["0:0"]
    else:
        fixture.after["1000:0"]["id"] = 999
    with pytest.raises(AssertionError):
        fixture.verify()


@pytest.mark.parametrize("fault", ["identity", "position"])
def test_reconnect_must_preserve_identity_and_observed_position(fault):
    fixture = MoveFixture()
    if fault == "identity":
        fixture.identity = 8
    else:
        fixture.position = [20, 0, 2]
    with pytest.raises(AssertionError):
        fixture.verify()


class SwapFixture:
    def __init__(self):
        self.before = {"0:0": {"storage": 0, "slot": 0, "id": 4551, "count": 2},
                       "3:24": {"storage": 3, "slot": 24, "id": 4555, "count": 3},
                       "1000:0": {"storage": 1000, "slot": 0, "id": 1601, "count": 1}}
        self.after = deepcopy(self.before)
        self.after["0:0"], self.after["3:24"] = self.after["3:24"], self.after["0:0"]
        self.after["0:0"].update(storage=0, slot=0)
        self.after["3:24"].update(storage=3, slot=24)
        self.expected = {"synthetic_rewards": True}
        self.restarted = False
        self.identity = 7
        self.login_position = [1, 0, 2]
        self.calls = []
        self.name = "subject"

    def expect_rewards(self, expected, work_index):
        assert expected == self.expected and work_index == 1
        self.calls.append("rewards")
        return {"entity_id": 7, "observed_position": [1, 0, 2],
                "rewards": {"inventory": deepcopy(self.after if self.restarted else self.before)}}

    def request_item_swap(self, *args, **kwargs):
        self.calls.append("swap_request")
        assert args == (3, 24, 0, 0, 4555, 4551) and not kwargs
        return {"context": 100, "operation": 9, "acknowledged": True,
                "inventory_change_verified": False}

    def logout(self): self.calls.append("logout")
    def close(self): self.calls.append("remove")

    def restart_world(self):
        self.calls.append("restart")
        self.restarted = True

    def api(self, method, payload):
        self.calls.append("http_login")
        assert method == "login" and payload == {"username": "synthetic-user", "pass": "synthetic-password"}
        return {"sId": "synthetic-session"}

    def login_via_lobby(self, auth, name):
        self.calls.append("lobby_login")
        assert auth == {"sId": "synthetic-session"} and name == "Fixture Name"
        return {"entity_id": self.identity, "observed_position": self.login_position}

    def expect_quest_complete(self, quest): self.calls.append(quest)

    def verify(self):
        fixture = {"username": "synthetic-user", "password": "synthetic-password", "name": "Fixture Name"}
        return swap_reward_and_verify_restart(self, self, self, fixture, self.expected, 1, [65686, 65687])


def test_swap_scenario_requires_restart_and_exact_slot_exchange(tmp_path):
    fixture = SwapFixture()
    fixture.artifacts = tmp_path
    player, expected, evidence = fixture.verify()
    assert player is fixture and expected == fixture.after == evidence["after_restart"]
    assert evidence["before"] == fixture.before
    assert evidence["receipt"]["inventory_change_verified"] is False
    assert fixture.calls == ["rewards", "swap_request", "logout", "remove", "restart",
                             "http_login", "lobby_login", "rewards", 65686, 65687]
    assert (tmp_path / "inventory-swap.json").exists()


@pytest.mark.parametrize("fault", ["ack_only", "wrong_source", "wrong_destination", "count", "other_item", "identity", "position"])
def test_swap_acknowledgement_or_bag_totals_cannot_satisfy_verifier(tmp_path, fault):
    fixture = SwapFixture()
    fixture.artifacts = tmp_path
    if fault == "ack_only":
        fixture.after = deepcopy(fixture.before)
    elif fault == "wrong_source":
        fixture.after["0:0"]["id"] = 4551
    elif fault == "wrong_destination":
        fixture.after["3:24"]["id"] = 4555
    elif fault == "count":
        fixture.after["0:0"]["count"] = 2
    elif fault == "other_item":
        fixture.after["1000:0"]["id"] = 999
    elif fault == "identity":
        fixture.identity = 8
    else:
        fixture.login_position = [20, 0, 2]
    with pytest.raises(AssertionError):
        fixture.verify()

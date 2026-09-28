"""Deterministic policy, catalog and replay validation; no game/network required."""
from copy import deepcopy
import pytest

from .support.catalog import validate_quest_catalog, validate_transition_catalog
from .support.workload import build_plan, validate_plan
from .support.worker import WorkerError, reward_values


def catalog():
    return {"version": 1, "profile": "sapphire-3.3", "quest": 65686, "level": 1,
            "previous_quests": [0, 0, 0], "client": 1, "finish": 2,
            "route": [[i * 0.5, 0, 0] for i in range(9)], "route_length": 4,
            "actors": [{"base_id": 1, "layout_id": 11, "position": [0, 0, 0], "territory": 130},
                       {"base_id": 2, "layout_id": 12, "position": [4, 0, 0], "territory": 130}]}


def test_catalog_requires_complete_local_route():
    assert validate_quest_catalog(catalog())["recipient"]["layout_id"] == 12
    bad = catalog(); bad["route"] = []
    with pytest.raises(WorkerError, match="complete"):
        validate_quest_catalog(bad)
    bad = catalog(); bad["route"][-1] = [100, 0, 0]
    with pytest.raises(WorkerError, match="jump"):
        validate_quest_catalog(bad)
    bad = catalog(); bad["actors"][1]["territory"] = 131
    with pytest.raises(WorkerError, match="endpoint"):
        validate_quest_catalog(bad)


def test_follow_up_requires_observed_prerequisite():
    data = catalog()
    data["quest"] = 65687
    data["previous_quests"] = [65686, 0, 0]
    with pytest.raises(WorkerError, match="not been observed"):
        validate_quest_catalog(data)
    with pytest.raises(WorkerError, match="not been observed"):
        validate_quest_catalog(data, completed_quests={65685})
    assert validate_quest_catalog(data, completed_quests={65686})["quest"] == 65687


def test_transition_requires_physical_crossing_and_resolved_destination():
    data = {"profile": "sapphire-3.3", "version": 1, "territory": 130,
            "route": [[i * 0.5, 0, 0] for i in range(13)], "route_length": 6,
            "transition": {"id": 1, "territory": 130, "enabled": True, "shape": 1, "exit_type": 1,
                "position": [6, 0, 0], "scale": [4, 4, 4], "rotation": [0, 0, 0],
                "target_pop": 2, "target_territory": 141,
                "destinations": [{"id": 2, "territory": 141, "position": [1, 2, 3]}]}}
    assert validate_transition_catalog(data) == data
    bad = deepcopy(data); bad["transition"]["destinations"] = []
    with pytest.raises(WorkerError, match="exactly one"):
        validate_transition_catalog(bad)
    bad = deepcopy(data); bad["transition"]["position"] = [9, 0, 0]
    with pytest.raises(WorkerError, match="inside"):
        validate_transition_catalog(bad)
    bad = deepcopy(data); bad["route"] = [[5, 0, 0], [6, 0, 0]]; bad["route_length"] = 1
    with pytest.raises(WorkerError, match="outside"):
        validate_transition_catalog(bad)


def test_seed_reproduces_decisions_not_server_timing():
    a = build_plan(catalog(), "explore", 42, 2, 50)
    assert a == build_plan(catalog(), "explore", 42, 2, 50)
    assert a != build_plan(catalog(), "explore", 43, 2, 50)
    assert {p["kind"] for p in a["actions"]} == {"walk", "say", "heartbeat", "reconnect"}
    assert validate_plan(a, catalog()) == a


def test_soak_batches_have_distinct_actors():
    plan = build_plan(catalog(), "soak", 7, 4, 40)
    for offset in range(0, 40, 4):
        assert {a["bot"] for a in plan["actions"][offset:offset+4]} == {0, 1, 2, 3}
    assert all(a["kind"] != "reconnect" for a in plan["actions"])
    validate_plan(plan, catalog())


@pytest.mark.parametrize("bots,steps", [(1, 10), (33, 40), (2, 1), (2, 1001)])
def test_population_and_step_limits(bots, steps):
    with pytest.raises(ValueError):
        build_plan(catalog(), "explore", 1, bots, steps)


def test_replay_rejects_route_drift_and_unknown_commands():
    plan = build_plan(catalog(), "explore", 1, 2, 4)
    drift = catalog(); drift["route"][0][0] = 0.1
    with pytest.raises(ValueError, match="route"):
        validate_plan(plan, drift)
    bad = deepcopy(plan); bad["actions"][0] = {"kind": "raw_send", "bot": 0}
    with pytest.raises(ValueError, match="unsupported"):
        validate_plan(bad, catalog())
    bad["actions"][0] = {"kind": "say", "bot": 0, "host": "192.0.2.1"}
    with pytest.raises(ValueError, match="parameters"):
        validate_plan(bad, catalog())


def test_reward_values_never_infer_missing_inventory():
    state = {"inventory_ready": False}
    with pytest.raises(WorkerError, match="not observed"):
        reward_values(state, 1)
    state = {"inventory_ready": True, "inventory": {
        "0:0": {"storage": 0, "id": 4551, "count": 2},
        "1:0": {"storage": 1, "id": 4551, "count": 3},
        "1000:0": {"storage": 1000, "id": 4551, "count": 1}},
        "exp_by_index": [0, 50], "level_by_index": [0, 1], "class_job": 1,
        "exp_by_class": {}, "level": None}
    assert reward_values(state, 1) == {"items": {"4551": 5}, "currencies": {}, "exp": 50, "level": 1}

"""Deterministic policy, catalog and replay validation; no game/network required."""
from copy import deepcopy
import json
from pathlib import Path
import pytest

from .support.catalog import (validate_combat_catalog, validate_pursuit_catalog,
                              validate_quest_catalog, validate_respawn_catalog, validate_shop_catalog,
                              validate_transition_catalog)
from .support.combat import combat_reward_delta
from .support.workload import build_plan, validate_plan
from .support.worker import WorkerError, reward_values


@pytest.mark.parametrize("patch", [{"level": 2}, {"class_job": 2}, {"work_index": 2},
    {"base_exp": 0}, {"level": True}, {"cost": 0}, {"range": 25}, {"action": 10},
    {"cast_ms": 100}, {"target_enemy": 1}])
def test_combat_catalog_rejects_unsupported_action_metadata(patch):
    data = {"version": 1, "profile": "sapphire-3.3", "action": 9, "class_job": 1,
            "work_index": 1, "level": 1, "base_exp": 50,
            "category": 3, "cost_type": 5, "cost": 60, "range": -1,
            "cast_ms": 0, "recast_ms": 2500, "recast_group": 58, "effect_type": 1, "target_enemy": True}
    assert validate_combat_catalog(data) == data
    with pytest.raises(WorkerError, match="Fast Blade"):
        validate_combat_catalog({**data, **patch})


def test_uldah_opening_catalog_pins_all_source_defined_ring_choices():
    data = json.loads((Path(__file__).parent / "scene_catalog/opening_uldah.json").read_text())
    choices = data["scenes"]["1245187:0"]["choices"]
    assert choices == {"choose_ring_4423": [1], "choose_ring_4424": [2],
                       "choose_ring_4425": [3], "choose_ring_4426": [4]}


def test_pursuit_catalog_binds_natural_enemy_and_displaced_route():
    data = {"version": 1, "profile": "sapphire-3.3", "territory": 141,
            "enemy": {"layout_id": 3749193, "base_id": 302, "level": 14, "position": [0, 0, 0]},
            "route": [[1, 0, 0], [2.5, 0, 0], [4, 0, 0], [5.5, 0, 0], [7, 0, 0], [8, 0, 0]],
            "route_length": 7}
    assert validate_pursuit_catalog(data) == data
    for changed in ({**data, "territory": 130},
                    {**data, "enemy": {**data["enemy"], "layout_id": 1}},
                    {**data, "route": [[1, 0, 0], [3, 0, 0]], "route_length": 2}):
        with pytest.raises(WorkerError):
            validate_pursuit_catalog(changed)


def test_respawn_catalog_binds_canonical_uldah_homepoint():
    data = {"version": 1, "profile": "sapphire-3.3", "homepoint": 9, "territory": 130,
            "pop_range": {"id": 1, "position": [1, 2, 3], "rotation": [0, 1, 0]}}
    assert validate_respawn_catalog(data) == data
    for changed in ({**data, "homepoint": 8}, {**data, "territory": 141},
                    {**data, "pop_range": {**data["pop_range"], "position": [float("nan"), 2, 3]}},
                    {**data, "pop_range": {**data["pop_range"], "extra": 1}}):
        with pytest.raises(WorkerError):
            validate_respawn_catalog(changed)


def test_shop_catalog_binds_route_actor_and_exact_sale():
    data = {"version": 1, "profile": "sapphire-3.3", "territory": 130,
            "start_actor": 1001289, "route": [[0, 0, 0], [1, 0, 0]], "route_length": 1,
            "shop": {"layout_id": 3, "base_id": 4, "event_id": 262468, "position": [1, 0, 0]},
            "sale": {"item": 4551, "quantity": 1, "gil": 28},
            "purchase": {"shop_id": 262468, "index": 0, "item": 5890, "quantity": 1, "gil": 8}}
    assert validate_shop_catalog(data) == data
    for changed in ({**data, "territory": 141}, {**data, "sale": {"item": 4551, "quantity": 2, "gil": 56}},
                    {**data, "purchase": {**data["purchase"], "item": 1}},
                    {**data, "shop": {**data["shop"], "event_id": 0x10005}},
                    {**data, "route": [[0, 0, 0], [3, 0, 0]], "route_length": 3}):
        with pytest.raises(WorkerError):
            validate_shop_catalog(changed)


def test_combat_reward_delta_requires_exact_current_loot_contract():
    before = {"items": {"4551": 2}, "currencies": {"1": 10}, "exp": 0, "level": 1}
    after = {"items": {"4551": 5, "8": 5, "5016": 1, "12728": 1},
             "currencies": {"1": 10}, "exp": 50, "level": 1}
    assert combat_reward_delta(before, after, 50) == {
        "items": {"4551": 3, "8": 5, "5016": 1, "12728": 1},
        "currencies": {}, "exp": 50, "level": 0}
    alternatives = [
        ({**after, "exp": 49}, "EXP"),
        ({**after, "level": 2}, "EXP"),
        ({**after, "currencies": {"1": 11}}, "currency"),
        ({**after, "items": {**after["items"], "9": 5}}, "loot"),
        ({**after, "items": {**after["items"], "5016": 2}}, "loot"),
        ({**after, "items": {**after["items"], "4551": 6}}, "range"),
        ({**after, "items": {**after["items"], "4551": 1}}, "removed"),
    ]
    for changed, message in alternatives:
        with pytest.raises(ValueError, match=message):
            combat_reward_delta(before, changed, 50)
    with pytest.raises(ValueError, match="positive"):
        combat_reward_delta(before, after, 0)


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

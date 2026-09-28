"""Synthetic combat-policy contracts; not real gameplay or client compatibility."""
from copy import deepcopy

import pytest

from .support.combat import committed_damage, damage_value, fast_blade_ready
from .support.worker import Bot


def ready_state():
    return {"phase": "ready", "entity_id": 7, "gm_rank": 0, "moving": False,
            "event_id": None, "scene": None, "rewards": {"class_job": 1},
            "predicted_position": [0, 0, 0],
            "combat": {"fast_blade_guard_remaining_ms": 0, "effects": [], "integrities": []},
            "actors": {"7": {"kind": 1, "hp": 94, "tp": 60},
                       "8": {"kind": 2, "level": 1, "hp": 94, "position": [0, 0, 2]}}}


def test_readiness_requires_both_elapsed_local_guard_and_received_resources():
    state = ready_state()
    assert fast_blade_ready(state, 8)
    state["combat"]["fast_blade_guard_remaining_ms"] = 1
    assert not fast_blade_ready(state, 8)
    state["combat"]["fast_blade_guard_remaining_ms"] = 0
    state["actors"]["7"]["tp"] = 59
    assert not fast_blade_ready(state, 8)


@pytest.mark.parametrize("value", [None, True, -1, 0.1])
def test_missing_or_invalid_guard_does_not_default_to_ready(value):
    state = ready_state()
    state["combat"]["fast_blade_guard_remaining_ms"] = value
    with pytest.raises(ValueError, match="pacing guard"):
        fast_blade_ready(state, 8)


@pytest.mark.parametrize("target", [True, 0, -1, 0x100000000, "8"])
def test_invalid_target_rejected(target):
    with pytest.raises(ValueError, match="32-bit"):
        fast_blade_ready(ready_state(), target)


@pytest.mark.parametrize("key,value", [("phase", "zoning"), ("moving", True),
                                       ("scene", {}), ("event_id", 99)])
def test_busy_actor_never_ready(key, value):
    state = ready_state()
    state[key] = value
    assert not fast_blade_ready(state, 8)


def test_profile_death_and_estimated_range_guards():
    state = ready_state()
    assert not fast_blade_ready(state, 9)
    state["actors"]["8"]["position"][2] = 2.51
    assert not fast_blade_ready(state, 8)
    state["actors"]["8"]["position"][2] = float("nan")
    with pytest.raises(ValueError, match="position"):
        fast_blade_ready(state, 8)
    for patch in ({"kind": 1}, {"level": 2}, {"hp": 0}):
        state = ready_state()
        state["actors"]["8"].update(patch)
        assert not fast_blade_ready(state, 8)
    state = ready_state()
    state["actors"]["7"]["hp"] = 0
    with pytest.raises(ValueError, match="defeated"):
        fast_blade_ready(state, 8)
    state = ready_state()
    state["gm_rank"] = 1
    with pytest.raises(ValueError, match="non-GM"):
        fast_blade_ready(state, 8)
    state = ready_state()
    state["rewards"]["class_job"] = 2
    with pytest.raises(ValueError, match="Gladiator"):
        fast_blade_ready(state, 8)


def example_hit():
    effect = {"source": 7, "target": 8, "action": 9, "kind": 1, "request": 1, "result": 42,
              "effects": [{"type": 3, "flag": 0, "value": 9, "args": [0, 0, 0]}]}
    integrity = {"target": 8, "result": 42, "hp": 85, "hp_max": 94, "mp": 0, "tp": 1000}
    state = ready_state()
    state["combat"].update(effects=[deepcopy(effect)], integrities=[integrity])
    return state, effect, {"hp": 94, "hp_max": 94}


def test_effect_alone_or_snapshot_hp_is_not_committed_damage():
    state, effect, before = example_hit()
    assert damage_value(effect) == 9 and committed_damage(state, effect, before)
    state["combat"]["integrities"] = []
    state["actors"]["8"]["hp"] = 85
    assert not committed_damage(state, effect, before)
    state, effect, before = example_hit()
    state["combat"]["effects"] = []
    assert not committed_damage(state, effect, before)


@pytest.mark.parametrize("key,value", [("source", 10), ("target", 10), ("action", 7),
                                       ("request", 2), ("result", 43), ("kind", 2), ("effects", [])])
def test_observer_must_receive_identical_action_not_stale_or_unrelated_hit(key, value):
    state, effect, before = example_hit()
    state["combat"]["effects"][0][key] = value
    assert not committed_damage(state, effect, before)


@pytest.mark.parametrize("key,value", [("target", 7), ("result", 43), ("hp", 84), ("hp_max", 95)])
def test_integrity_must_match_target_result_and_exact_pre_hit_delta(key, value):
    state, effect, before = example_hit()
    state["combat"]["integrities"][0][key] = value
    assert not committed_damage(state, effect, before)


def test_retaliation_uses_independent_pre_hit_health():
    state, effect, before = example_hit()
    effect.update(source=8, target=7, action=7, request=0)
    state["combat"]["effects"] = [deepcopy(effect)]
    state["combat"]["integrities"][0]["target"] = 7
    assert committed_damage(state, effect, before)
    assert not committed_damage(state, effect, {"hp": 93, "hp_max": 94})
    effect["effects"][0]["flag"] = 1
    state["combat"]["effects"] = [deepcopy(effect)]
    assert damage_value(effect) == 0 and not committed_damage(state, effect, before)


def test_python_wait_uses_state_notifications_without_sending_or_retrying_actions():
    states = [ready_state() for _ in range(3)]
    states[0]["combat"]["fast_blade_guard_remaining_ms"] = 1
    states[1]["actors"]["7"]["tp"] = 59

    class FakeWorker:
        def wait_state(self, bot, predicate, description, timeout):
            assert bot == "fighter" and timeout == 17
            assert [predicate(s) for s in states] == [False, False, True]
            return states[-1]

    assert Bot(FakeWorker(), "fighter").wait_fast_blade_ready(8, timeout=17) == states[-1]

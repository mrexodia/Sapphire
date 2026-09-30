"""Natural multi-attacker high-level defeat; no enemy, EXP, resource or loot grants."""
import json
import math
import re

import pytest

from .support.catalog import load_combat_catalog
from .support.combat import combat_reward_delta, committed_damage, damage_value
from .support.worker import Bot, reward_values

pytestmark = pytest.mark.live


def test_natural_multi_attacker_high_level_defeat(environment, live_worker):
    path = environment.profile.get("combat_catalog")
    assert path, "high-level combat requires matching source-generated action metadata"
    catalog = load_combat_catalog(path)
    reward = catalog["representative_high_level_enemy"]
    assert reward == {"level": 14, "base_exp": 115}

    population = json.loads((environment.runtime / "data/bnpcs/w1f2/w1f2.json").read_text())
    matches = [row for group in population.values()
               for layout_id, row in group.get("bnpcs", {}).items()
               if layout_id == "3749193"]
    assert len(matches) == 1, "source-bound high-level population missing"
    spawn = matches[0]
    assert spawn["baseInfo"]["baseId"] == 302
    assert spawn["baseInfo"]["level"] == reward["level"]
    assert spawn["popInfo"]["nonpop"] == 0
    logs = "\n".join(p.read_text(errors="replace") for p in environment.runtime.glob("world*.log"))
    assert re.search(r"141\s+\d+\s+1\s+w1f2\s+PUBLIC\s+NAVI\s+Central Thanalan", logs)
    position = list(spawn["baseInfo"]["position"])
    position[0] += 1.0

    fixtures = [environment.fresh_character(position, 141) for _ in range(4)]
    witness_fixture = environment.fresh_character(position, 141)
    fighters = [Bot(live_worker, f"high-level-fighter-{index}") for index in range(4)]
    witness = Bot(live_worker, "high-level-witness")
    states = [bot.login_via_lobby(fixture["auth"], fixture["name"])
              for bot, fixture in zip(fighters, fixtures)]
    witness_state = witness.login_via_lobby(witness_fixture["auth"], witness_fixture["name"])
    entities = [state["entity_id"] for state in states]
    witness_entity = witness_state["entity_id"]

    def exact_target(state):
        matches = [(key, actor) for key, actor in state["actors"].items()
                   if actor["kind"] == 2 and actor["layout_id"] == 3749193
                   and actor["base_id"] == 302 and actor["level"] == 14 and actor["hp"] > 0]
        return matches[0] if len(matches) == 1 else None

    all_bots = [*fighters, witness]
    for bot in all_bots:
        live_worker.wait_state(bot.name,
            lambda s: exact_target(s) is not None
                      and all(str(entity) in s["actors"] for entity in entities)
                      and str(witness_entity) in s["actors"],
            "all ordinary clients and exact natural high-level target visible", 30)
    target, target_before = exact_target(live_worker.snapshot(witness.name))
    assert target_before["hp"] == target_before["hp_max"] == 237
    before_rewards = {bot.name: reward_values(live_worker.snapshot(bot.name)["rewards"], 1)
                      for bot in all_bots}

    effects = []
    expected_hp = target_before["hp"]
    while expected_hp > 0:
        assert len(effects) < 40, "bounded multi-attacker sequence did not defeat the target"
        for fighter, entity in zip(fighters, entities):
            if expected_hp == 0:
                break
            ready = fighter.wait_fast_blade_ready(int(target), 45)
            before = ready["actors"][target]
            assert before["hp"] == expected_hp > 0
            for observer in all_bots:
                live_worker.wait_state(observer.name,
                    lambda s, e=entity, hp=expected_hp: target in s["actors"] and str(e) in s["actors"]
                              and s["actors"][target]["hp"] == hp
                              and s["actors"][str(e)]["hp"] > 0
                              and math.dist(s["actors"][target]["position"],
                                            s["actors"][str(e)]["position"]) < 3,
                    "all clients see exact pre-hit HP and acting fighter in range", 10)
            effect = fighter.fast_blade(int(target))
            assert effect["source"] == entity and effect["action"] == 9 and damage_value(effect) > 0
            assert effect["source_effects"] == [
                {"type": 29, "value": 9, "flag": 0x80, "args": [0, 0, 0]}]
            for observer in all_bots:
                live_worker.wait_state(observer.name,
                    lambda s, e=effect, b=before: committed_damage(s, e, b),
                    "all clients receive identical high-level damage and committed HP", 10)
            effects.append({"fighter": fighter.name, "effect": effect,
                            "before_hp": before["hp"],
                            "after_hp": max(0, before["hp"] - damage_value(effect))})
            expected_hp = effects[-1]["after_hp"]

    assert {entry["fighter"] for entry in effects} == {bot.name for bot in fighters}
    def complete_reward(state, before):
        try:
            combat_reward_delta(before, reward_values(state["rewards"], 1), reward["base_exp"])
            return True
        except ValueError:
            return False

    rewards, inventories = {}, {}
    for fighter in fighters:
        rewarded = live_worker.wait_state(fighter.name,
            lambda s, before=before_rewards[fighter.name]: complete_reward(s, before),
            "exact high-level EXP and delayed loot", 20)
        after = reward_values(rewarded["rewards"], 1)
        delta = combat_reward_delta(before_rewards[fighter.name], after, reward["base_exp"])
        rewards[fighter.name] = {"before": before_rewards[fighter.name], "after": after, "delta": delta}
        inventories[fighter.name] = rewarded["rewards"]["inventory"]
    witness_after = reward_values(live_worker.snapshot(witness.name)["rewards"], 1)
    assert witness_after == before_rewards[witness.name]
    for bot in all_bots:
        live_worker.wait_state(bot.name, lambda s: target not in s["actors"],
                               "high-level target removed after natural defeat", 20)
    for bot in all_bots:
        bot.logout(wait_server_close=True)

    environment.restart_world()
    persisted = {}
    for index, (fixture, prior) in enumerate(zip(fixtures, fighters)):
        auth = environment.api("login", {"username": fixture["username"], "pass": fixture["password"]})
        bot = Bot(live_worker, f"high-level-reloaded-{index}")
        state = bot.login_via_lobby(auth, fixture["name"])
        after = reward_values(state["rewards"], 1)
        assert after == rewards[prior.name]["after"]
        assert state["rewards"]["inventory"] == inventories[prior.name]
        persisted[prior.name] = after
        bot.logout(wait_server_close=True)

    artifact = {
        "fixture": {"layout_id": 3749193, "base_id": 302, "level": 14,
                    "hp": target_before["hp_max"], "source_base_exp": reward["base_exp"]},
        "ordinary_attackers": len(fighters),
        "independent_non_attacking_witness": True,
        "effects": effects,
        "rewards": rewards,
        "witness_rewards_unchanged": witness_after,
        "persisted_rewards": persisted,
        "world_restarts": 1,
        "both_actor_and_witness_state_required": True,
        "scope": "one exact natural level-fourteen shared-hate defeat, not general scaling or capacity",
    }
    (environment.artifacts / "combat-high-level-multi-attacker.json").write_text(
        json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")

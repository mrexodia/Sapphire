"""Natural level-four progression and Fast Blade combo; no grants or timing-only proof."""
import json
import math
import re

import pytest

from .support.catalog import load_combat_catalog
from .support.combat import (approach_target, combat_reward_delta, committed_damage, damage_value,
                             wait_healthy_enemy)
from .support.worker import Bot, reward_values

pytestmark = pytest.mark.live


def test_natural_level_four_fast_blade_combo(server, live_worker):
    catalog = load_combat_catalog(server.profile["combat_catalog"])
    combo = catalog["first_fast_blade_combo"]
    reward = catalog["representative_high_level_enemy"]
    assert combo["action"] == 11 and combo["level"] == 4
    assert combo["required_cumulative_exp"] == 2000
    assert combo["minimum_level_fourteen_defeats"] == 18
    assert reward == {"level": 14, "base_exp": 115}

    population = json.loads((server.runtime / "data/bnpcs/w1f2/w1f2.json").read_text())
    server.require_navmesh(141, "w1f2")  # enemies cannot move without one
    spawns = {layout_id: row for group in population.values()
              for layout_id, row in group.get("bnpcs", {}).items()
              if row["baseInfo"]["baseId"] == 302 and row["baseInfo"]["level"] == 14
              and row["popInfo"]["nonpop"] == 0}
    # Eighteen defeats at a 60s respawn would take too long against one spawn, so
    # the fighters rotate across whichever level-14 enemy of this kind is healthy
    # nearby. They start beside this one.
    assert "3749193" in spawns and len(spawns) >= 2
    position = list(spawns["3749193"]["baseInfo"]["position"])
    position[0] += 1.0
    fixtures = [server.fresh_character(position, 141) for _ in range(4)]
    witness_fixture = server.fresh_character(position, 141)

    def authenticate(fixture):
        return server.relogin(fixture)

    def choose_and_approach(bots, witness):
        # The witness picks the nearest healthy enemy; everyone walks beside it and
        # confirms the same healthy target before the first hit.
        target, _ = wait_healthy_enemy(live_worker, witness, 302, 14, 60.0, 90)
        for bot in bots:
            approach_target(live_worker, bot, target)
        for bot in bots:
            live_worker.wait_state(bot.name,
                lambda s: s["actors"].get(target, {}).get("hp", 0) == s["actors"].get(target, {}).get("hp_max") > 0,
                "every client sees the chosen healthy target", 10)
        return target, live_worker.snapshot(witness.name)["actors"][target]

    def expected_progress(total_exp):
        level, remaining = 1, total_exp
        for threshold in combo["level_thresholds"]:
            if remaining < threshold:
                break
            remaining -= threshold
            level += 1
        return level, remaining

    def normalize_reward(after, before, expected_level, expected_exp):
        if after["level"] != expected_level or after["exp"] != expected_exp:
            raise ValueError("natural progression level/EXP mismatch")
        normalized = dict(after)
        normalized.update(level=before["level"], exp=before["exp"] + reward["base_exp"])
        return normalized

    expected_rewards = None
    expected_inventories = None
    cycles = []
    targets = []
    for kill_index in range(combo["minimum_level_fourteen_defeats"]):
        fighters = [Bot(live_worker, f"combo-fighter-{kill_index}-{index}") for index in range(4)]
        witness = Bot(live_worker, f"combo-witness-{kill_index}")
        states = [bot.login_via_lobby(authenticate(fixture), fixture["name"])
                  for bot, fixture in zip(fighters, fixtures)]
        witness_state = witness.login_via_lobby(authenticate(witness_fixture), witness_fixture["name"])
        entities = [state["entity_id"] for state in states]
        witness_entity = witness_state["entity_id"]
        if expected_rewards is not None:
            for index, state in enumerate(states):
                assert reward_values(state["rewards"], 1) == expected_rewards[index]
                assert state["rewards"]["inventory"] == expected_inventories[index]
        for bot, entity in zip(fighters, entities):
            live_worker.wait_state(bot.name,
                lambda s, e=entity: s["actors"][str(e)]["hp"] == s["actors"][str(e)]["hp_max"] > 0,
                "natural pre-cycle HP restoration", 60)
        all_bots = [*fighters, witness]
        for bot in all_bots:
            live_worker.wait_state(bot.name,
                lambda s: all(str(entity) in s["actors"] for entity in entities)
                          and str(witness_entity) in s["actors"],
                "all combo-progression clients visible", 30)
        target, target_before = choose_and_approach(all_bots, witness)
        assert target_before["hp"] == target_before["hp_max"] == 237
        targets.append({"cycle": kill_index + 1, "layout_id": target_before["layout_id"]})
        before_rewards = [reward_values(live_worker.snapshot(bot.name)["rewards"], 1)
                          for bot in fighters]
        witness_before = reward_values(live_worker.snapshot(witness.name)["rewards"], 1)

        effects = []
        expected_hp = 237
        while expected_hp > 0:
            assert len(effects) < 40
            for fighter, entity in zip(fighters, entities):
                if expected_hp == 0:
                    break
                live_worker.wait_state(fighter.name,
                    lambda s, hp=expected_hp: s["actors"].get(target, {}).get("hp") == hp,
                    "acting fighter receives exact committed high-level HP", 10)
                # Enemies roam while idle; close the gap again before each hit.
                approach_target(live_worker, fighter, target)
                ready = fighter.wait_fast_blade_ready(int(target), 45)
                before = ready["actors"][target]
                assert before["hp"] == expected_hp > 0
                for observer in all_bots:
                    # The server does not echo a player's own movement, so the acting
                    # fighter judges its range from its predicted position.
                    live_worker.wait_state(observer.name,
                        lambda s, e=entity, hp=expected_hp, own=(observer is fighter):
                                  target in s["actors"] and str(e) in s["actors"]
                                  and s["actors"][target]["hp"] == hp
                                  and s["actors"][str(e)]["hp"] > 0
                                  and math.dist(s["actors"][target]["position"],
                                                s["predicted_position"] if own else s["actors"][str(e)]["position"]) < 3,
                        "all combo-progression clients see exact pre-hit state", 10)
                effect = fighter.fast_blade(int(target))
                assert damage_value(effect) > 0
                assert effect["source_effects"] == [
                    {"type": 29, "value": 9, "flag": 0x80, "args": [0, 0, 0]}]
                for observer in all_bots:
                    live_worker.wait_state(observer.name,
                        lambda s, e=effect, b=before: committed_damage(s, e, b),
                        "identical Fast Blade and committed high-level HP", 10)
                after_hp = max(0, before["hp"] - damage_value(effect))
                effects.append({"fighter": fighter.name, "effect": effect,
                                "before_hp": before["hp"], "after_hp": after_hp})
                expected_hp = after_hp
        assert len({row["fighter"].rsplit("-", 1)[1] for row in effects}) == 4

        total_exp = reward["base_exp"] * (kill_index + 1)
        expected_level, expected_exp = expected_progress(total_exp)
        after_rewards, after_inventories, deltas = [], [], []
        for index, fighter in enumerate(fighters):
            def complete(state, before=before_rewards[index]):
                try:
                    after = reward_values(state["rewards"], 1)
                    normalized = normalize_reward(after, before, expected_level, expected_exp)
                    combat_reward_delta(before, normalized, reward["base_exp"])
                    return True
                except ValueError:
                    return False
            rewarded = live_worker.wait_state(fighter.name, complete,
                                               "exact level-four progression reward", 20)
            after = reward_values(rewarded["rewards"], 1)
            normalized = normalize_reward(after, before_rewards[index], expected_level, expected_exp)
            deltas.append(combat_reward_delta(before_rewards[index], normalized, reward["base_exp"]))
            after_rewards.append(after)
            after_inventories.append(rewarded["rewards"]["inventory"])
        assert reward_values(live_worker.snapshot(witness.name)["rewards"], 1) == witness_before
        for bot in all_bots:
            live_worker.wait_state(bot.name, lambda s: target not in s["actors"],
                                   "progression target removed", 20)
        cycles.append({"defeat": kill_index + 1, "total_exp": total_exp,
                       "level": expected_level, "exp": expected_exp,
                       "effect_count": len(effects), "first_effect": effects[0],
                       "last_effect": effects[-1], "reward_deltas": deltas})
        expected_rewards, expected_inventories = after_rewards, after_inventories
        for bot in all_bots:
            bot.logout(timeout=30, wait_server_close=True)
            bot.close()

    fighters = [Bot(live_worker, f"combo-final-fighter-{index}") for index in range(4)]
    witness = Bot(live_worker, "combo-final-witness")
    states = [bot.login_via_lobby(authenticate(fixture), fixture["name"])
              for bot, fixture in zip(fighters, fixtures)]
    witness_state = witness.login_via_lobby(authenticate(witness_fixture), witness_fixture["name"])
    entities = [state["entity_id"] for state in states]
    witness_entity = witness_state["entity_id"]
    for index, state in enumerate(states):
        assert reward_values(state["rewards"], 1) == expected_rewards[index]
        assert state["rewards"]["inventory"] == expected_inventories[index]
        assert state["rewards"]["level_by_index"][1] == 4
        assert state["rewards"]["exp_by_index"][1] == 70
    all_bots = [*fighters, witness]
    for bot in all_bots:
        live_worker.wait_state(bot.name,
            lambda s: all(str(entity) in s["actors"] for entity in entities)
                      and str(witness_entity) in s["actors"],
            "final combo clients visible", 30)
    target, final_target = choose_and_approach(all_bots, witness)
    actor, entity = fighters[0], entities[0]
    approach_target(live_worker, actor, target)
    ready = actor.wait_fast_blade_ready(int(target), 45)
    before_fast = ready["actors"][target]
    for observer in all_bots:
        live_worker.wait_state(observer.name,
            lambda s: target in s["actors"] and s["actors"][target]["hp"] == before_fast["hp"],
            "final Fast Blade pre-state", 10)
    fast_effect = actor.fast_blade(int(target))
    assert fast_effect["source_effects"] == [
        {"type": 29, "value": 9, "flag": 0x80, "args": [0, 0, 0]}]
    for observer in all_bots:
        live_worker.wait_state(observer.name,
            lambda s: committed_damage(s, fast_effect, before_fast),
            "final Fast Blade committed HP and combo readiness", 10)

    expected_savage_hp = max(0, before_fast["hp"] - damage_value(fast_effect))
    live_worker.wait_state(actor.name,
        lambda s: s["actors"].get(target, {}).get("hp") == expected_savage_hp,
        "combo actor receives committed Fast Blade HP", 10)
    ready = actor.wait_savage_blade_ready(int(target), 10)
    before_savage = ready["actors"][target]
    assert before_savage["hp"] > 0 and ready["actors"][str(entity)]["tp"] >= 60
    for observer in all_bots:
        live_worker.wait_state(observer.name,
            lambda s, own=(observer is actor): target in s["actors"] and str(entity) in s["actors"]
                      and s["actors"][target]["hp"] == before_savage["hp"]
                      and math.dist(s["actors"][target]["position"],
                                    s["predicted_position"] if own else s["actors"][str(entity)]["position"]) < 3,
            "all clients see exact Savage Blade pre-state", 10)
    savage_effect = actor.savage_blade(int(target))
    assert damage_value(savage_effect) > 0
    assert savage_effect["source_effects"] == [
        {"type": 30, "value": 0, "flag": 0, "args": [0, 0, 0]},
        {"type": 29, "value": 11, "flag": 0x80, "args": [0, 0, 0]}]
    for observer in all_bots:
        live_worker.wait_state(observer.name,
            lambda s: committed_damage(s, savage_effect, before_savage),
            "identical combo-success effect and committed Savage Blade HP", 10)
    started = live_worker.wait_state(actor.name,
        lambda s: any(row["source"] == entity and row["action"] == 11
                      and row["group"] == 58 and row["recast_centiseconds"] == 250
                      for row in s["combat"]["starts"]),
        "received Savage Blade action start", 10)

    artifact = {
        "fixture": {"base_id": 302, "level": 14, "source_base_exp": 115,
                    "start_layout_id": 3749193, "targets": targets,
                    "final_target_layout_id": final_target["layout_id"]},
        "ordinary_attackers": 4,
        "independent_witnesses_per_cycle": 1,
        "defeats": len(cycles),
        "relogins": len(cycles),
        "cycles": cycles,
        "persisted_level": started["rewards"]["level_by_index"][1],
        "persisted_exp": started["rewards"]["exp_by_index"][1],
        "combo": {"starter": fast_effect, "follow_up": savage_effect,
                  "before_hp": before_savage["hp"],
                  "after_hp": max(0, before_savage["hp"] - damage_value(savage_effect)),
                  "all_five_clients_verified": True,
                  "source_metadata": combo},
        "scope": "one exact naturally earned level-four Fast Blade to Savage Blade combo",
    }
    (server.artifacts / "combat-level-four-combo.json").write_text(
        json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")
    # The combo target is left alive and damaged; it heals itself when it retreats.
    for bot in all_bots:
        bot.logout(timeout=30)
        bot.close()

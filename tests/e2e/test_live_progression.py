"""Natural level-two progression and True Strike; no EXP, level, skill or enemy grants."""
import json
import math
import re

import pytest

from .support.catalog import load_combat_catalog
from .support.combat import combat_reward_delta, committed_damage, damage_value
from .support.worker import Bot, reward_values

pytestmark = pytest.mark.live


def test_natural_pugilist_level_two_true_strike(environment, live_worker):
    path = environment.profile.get("combat_catalog")
    assert path, "progression requires a matching source-generated combat catalog"
    catalog = load_combat_catalog(path)
    bootshine, true_strike = catalog["bootshine"], catalog["true_strike"]
    assert bootshine["class_job"] == true_strike["class_job"] == 2
    assert bootshine["work_index"] == true_strike["work_index"] == 0
    assert bootshine["level"] == 1 and true_strike["level"] == 2
    assert bootshine["base_exp"] == 50 and true_strike["cost"] == 50

    population = json.loads((environment.runtime / "data/bnpcs/w1f2/w1f2.json").read_text())
    spawn = population["LVD_BNPC_01"]["bnpcs"]["3746475"]
    assert spawn["baseInfo"]["baseId"] == 351 and spawn["baseInfo"]["level"] == 1
    logs = "\n".join(p.read_text(errors="replace") for p in environment.runtime.glob("world*.log"))
    assert re.search(r"141\s+\d+\s+1\s+w1f2\s+PUBLIC\s+NAVI\s+Central Thanalan", logs)
    position = list(spawn["baseInfo"]["position"])
    position[0] += 1.0
    fixture = environment.fresh_character(position, 141, class_job=2)

    def fresh_auth():
        return environment.api("login", {"username": fixture["username"], "pass": fixture["password"]})

    def candidates(state, maximum=20):
        return [(key, actor) for key, actor in state["actors"].items()
                if actor["kind"] == 2 and actor["base_id"] == 351 and actor["level"] == 1
                and actor["hp"] == actor["hp_max"] > 0
                and math.dist(actor["position"], state["predicted_position"]) < maximum]

    def approach(player, observer, entity):
        reached = []
        for _ in range(6):
            state = live_worker.snapshot(player.name)
            nearby = candidates(state)
            assert nearby, "no bounded observed natural target for progression"
            target, actor = min(nearby,
                key=lambda row: math.dist(row[1]["position"], state["predicted_position"]))
            if math.dist(actor["position"], state["predicted_position"]) < 2:
                return target, reached
            destination = list(actor["position"])
            player.walk_to(destination, 2.0, 15)
            live_worker.wait_state(observer.name,
                lambda s: str(entity) in s["actors"]
                          and math.dist(s["actors"][str(entity)]["position"], destination) < 0.15,
                "witness sees bounded progression approach", 15)
            reached.append(destination)
        raise AssertionError("bounded progression approach did not reach a natural target")

    def completed_reward(state, before, final_kill):
        current = reward_values(state["rewards"], 0)
        normalized = dict(current)
        if final_kill:
            if not (before["level"] == 1 and before["exp"] == 250
                    and current["level"] == 2 and current["exp"] == 0):
                return False
            normalized.update(level=1, exp=300)
        try:
            combat_reward_delta(before, normalized, 50)
            return True
        except ValueError:
            return False

    kills = []
    persisted_inventory = None
    for kill_index in range(6):
        player = Bot(live_worker, f"progression-fighter-{kill_index}")
        state = player.login_via_lobby(fresh_auth(), fixture["name"])
        entity = state["entity_id"]
        expected_level, expected_exp = (1, kill_index * 50)
        assert state["rewards"]["class_job"] == 2
        assert state["rewards"]["level_by_index"][0] == expected_level
        assert state["rewards"]["exp_by_index"][0] == expected_exp
        if persisted_inventory is not None:
            assert state["rewards"]["inventory"] == persisted_inventory
        # Recovery is natural received regeneration, not fixture mutation.
        state = live_worker.wait_state(player.name,
            lambda s: s["actors"][str(entity)]["hp"] == s["actors"][str(entity)]["hp_max"] > 0,
            "naturally restored progression fighter", 60)
        witness_fixture = environment.fresh_character(state["observed_position"], 141)
        observer = Bot(live_worker, f"progression-witness-{kill_index}")
        observer.login_via_lobby(witness_fixture["auth"], witness_fixture["name"])
        live_worker.wait_state(observer.name, lambda s: str(entity) in s["actors"],
                               "witness sees progression fighter")
        target, approached = approach(player, observer, entity)
        before_rewards = reward_values(live_worker.snapshot(player.name)["rewards"], 0)
        effects = []
        expected_hp = live_worker.snapshot(player.name)["actors"][target]["hp"]
        while expected_hp > 0:
            assert len(effects) < 16, "bounded Bootshine sequence did not defeat the natural target"
            ready = player.wait_bootshine_ready(int(target), 45)
            before = ready["actors"][target]
            assert before["hp"] == expected_hp > 0
            live_worker.wait_state(observer.name,
                lambda s: target in s["actors"] and str(entity) in s["actors"]
                          and s["actors"][target]["hp"] == before["hp"]
                          and s["actors"][str(entity)]["hp"] > 0
                          and math.dist(s["actors"][target]["position"],
                                        s["actors"][str(entity)]["position"]) < 3,
                "witness sees exact progression pre-hit state", 10)
            effect = player.bootshine(int(target))
            assert effect["action"] == 53 and damage_value(effect) > 0
            for bot in (player, observer):
                live_worker.wait_state(bot.name, lambda s, e=effect, b=before: committed_damage(s, e, b),
                                       "witnessed Bootshine effect and committed HP", 10)
            effects.append(effect)
            expected_hp = max(0, before["hp"] - damage_value(effect))

        final_kill = kill_index == 5
        rewarded = live_worker.wait_state(player.name,
            lambda s: completed_reward(s, before_rewards, final_kill),
            "exact natural progression EXP and delayed loot", 20)
        after_rewards = reward_values(rewarded["rewards"], 0)
        normalized = dict(after_rewards)
        if final_kill:
            normalized.update(level=1, exp=300)
        reward_delta = combat_reward_delta(before_rewards, normalized, 50)
        persisted_inventory = rewarded["rewards"]["inventory"]
        for bot in (player, observer):
            live_worker.wait_state(bot.name, lambda s: target not in s["actors"],
                                   "defeated progression target removed", 20)
        kills.append({"index": kill_index + 1, "target": int(target), "approach": approached,
                      "effects": effects, "before": before_rewards, "after": after_rewards,
                      "reward_delta": reward_delta})
        player.logout(wait_server_close=True)
        observer.logout(wait_server_close=True)
        environment.restart_world()

    player = Bot(live_worker, "level-two-pugilist")
    state = player.login_via_lobby(fresh_auth(), fixture["name"])
    entity = state["entity_id"]
    assert state["rewards"]["level_by_index"][0] == 2
    assert state["rewards"]["exp_by_index"][0] == 0
    assert state["rewards"]["inventory"] == persisted_inventory
    state = live_worker.wait_state(player.name,
        lambda s: s["actors"][str(entity)]["hp"] == s["actors"][str(entity)]["hp_max"] > 0,
        "naturally restored level-two Pugilist", 60)
    witness_fixture = environment.fresh_character(state["observed_position"], 141)
    observer = Bot(live_worker, "level-two-witness")
    observer.login_via_lobby(witness_fixture["auth"], witness_fixture["name"])
    live_worker.wait_state(observer.name, lambda s: str(entity) in s["actors"],
                           "witness sees level-two Pugilist")
    target, approached = approach(player, observer, entity)

    ready = player.wait_bootshine_ready(int(target), 45)
    before_bootshine = ready["actors"][target]
    live_worker.wait_state(observer.name,
        lambda s: target in s["actors"] and str(entity) in s["actors"]
                  and s["actors"][target]["hp"] == before_bootshine["hp"],
        "witness sees level-two Bootshine pre-state", 10)
    bootshine_effect = player.bootshine(int(target))
    for bot in (player, observer):
        live_worker.wait_state(bot.name,
            lambda s: committed_damage(s, bootshine_effect, before_bootshine),
            "level-two Bootshine committed HP", 10)

    ready = player.wait_true_strike_ready(int(target), 30)
    before_true_strike = ready["actors"][target]
    assert before_true_strike["hp"] > 0 and ready["actors"][str(entity)]["tp"] >= 50
    live_worker.wait_state(observer.name,
        lambda s: target in s["actors"] and str(entity) in s["actors"]
                  and s["actors"][target]["hp"] == before_true_strike["hp"]
                  and math.dist(s["actors"][target]["position"],
                                s["actors"][str(entity)]["position"]) < 3,
        "witness sees exact True Strike pre-state", 10)
    true_strike_effect = player.true_strike(int(target))
    assert true_strike_effect["action"] == 54 and damage_value(true_strike_effect) > 0
    observed = {}
    for bot in (player, observer):
        observed[bot.name] = live_worker.wait_state(bot.name,
            lambda s: committed_damage(s, true_strike_effect, before_true_strike),
            "identical True Strike effect and committed HP", 10)
    started = live_worker.wait_state(player.name,
        lambda s: any(row["source"] == entity and row["action"] == 54
                      and row["group"] == 58 and row["recast_centiseconds"] == 250
                      for row in s["combat"]["starts"]),
        "received True Strike action start", 10)

    artifact = {
        "fixture": "unchanged Central Thanalan natural level-one population",
        "progression_player_sessions": 7,
        "independent_witness_sessions": 7,
        "fresh_http_authentications": 7,
        "world_restarts": 6,
        "class_job": 2,
        "work_index": 0,
        "level_before": 1,
        "level_after": started["rewards"]["level_by_index"][0],
        "exp_after": started["rewards"]["exp_by_index"][0],
        "kills": kills,
        "persisted_inventory": persisted_inventory,
        "true_strike": {"metadata": true_strike, "approach": approached,
                        "bootshine_effect": bootshine_effect,
                        "effect": true_strike_effect,
                        "before_hp": before_true_strike["hp"],
                        "after_hp": max(0, before_true_strike["hp"] - damage_value(true_strike_effect)),
                        "both_clients_verified": True},
    }
    (environment.artifacts / "combat-level-two-true-strike.json").write_text(
        json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")
    player.logout(wait_server_close=True)
    observer.logout(wait_server_close=True)

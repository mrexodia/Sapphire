"""Natural melee, defeat and rewards; no spawned enemies or granted resources/skills."""
import json
import math
import re
import time

import pytest

from .support.worker import Bot, reward_values
from .support.catalog import load_combat_catalog
from .support.combat import combat_reward_delta, committed_damage, damage_value

pytestmark = pytest.mark.live


def test_observed_sprint_status_and_tp_debit(environment, live_worker):
    path = environment.profile.get("combat_catalog")
    assert path, "Sprint requires profile.combat_catalog generated from matching local assets"
    sprint = load_combat_catalog(path)["sprint"]
    assert sprint == {"action": 3, "base_exp": 45, "cast_ms": 0, "category": 0,
                      "class_job": 0, "cost": 0, "cost_type": 18, "effect_type": 1,
                      "level": 0, "range": 0, "recast_group": 56,
                      "recast_ms": 30000, "target_enemy": False, "work_index": -1}
    fixture, witness_fixture = environment.fresh_character(), environment.fresh_character()
    player, observer = Bot(live_worker, "sprinter"), Bot(live_worker, "sprint-observer")
    state = player.login_via_lobby(fixture["auth"], fixture["name"])
    entity = state["entity_id"]
    observer.login_via_lobby(witness_fixture["auth"], witness_fixture["name"])
    live_worker.wait_state(observer.name,
        lambda s: str(entity) in s["actors"] and s["actors"][str(entity)]["kind"] == 1,
        "observer received exact Sprint actor")
    ready = player.wait_sprint_ready()
    received_tp = ready["actors"][str(entity)]["tp"]
    assert received_tp >= 50
    acted, request = player.sprint()

    def matching_effect(s):
        return [row for row in s["combat"]["effects"]
                if row["source"] == entity and row["target"] == entity
                and row["action"] == 3 and row["kind"] == 1 and row["request"] == request]

    exact_effect = None
    for bot in (player, observer):
        observed = live_worker.wait_state(bot.name,
            lambda s: len(matching_effect(s)) == 1,
            "one exact independently received Sprint effect")
        effect = matching_effect(observed)[0]
        assert effect["effects"] == [{"type": 18, "value": 50, "flag": 128,
                                      "args": [0, 0, 30]}]
        if exact_effect is None:
            exact_effect = effect
        else:
            assert effect == exact_effect
        zero_tp = live_worker.wait_state(bot.name,
            lambda s: any(row["target"] == entity and row["tp"] == 0
                          for row in s["combat"]["hud_params"]),
            "independently received zero-TP Sprint commit")
        assert zero_tp["phase"] == "ready" and zero_tp["gm_rank"] == 0
    started = live_worker.wait_state(player.name,
        lambda s: any(row["source"] == entity and row["action"] == 3
                      for row in s["combat"]["starts"]),
        "received Sprint start metadata")
    start = next(row for row in reversed(started["combat"]["starts"])
                 if row["source"] == entity and row["action"] == 3)
    assert start["group"] == sprint["recast_group"]
    assert start["recast_centiseconds"] == sprint["recast_ms"] // 10
    assert acted["phase"] == "ready"


def test_observed_fast_blade_damage(environment, live_worker):
    path = environment.profile.get("combat_catalog")
    assert path, "combat requires profile.combat_catalog generated from matching local assets"
    catalog = load_combat_catalog(path)
    # Initial location is fixture setup, not a claim of walking here from Ul'dah.
    # Use the unchanged staged world population, not a hand-authored enemy spawn.
    population = json.loads((environment.runtime / "data/bnpcs/w1f2/w1f2.json").read_text())
    spawn = population["LVD_BNPC_01"]["bnpcs"]["3746473"]
    assert spawn["baseInfo"]["baseId"] == 351 and spawn["baseInfo"]["level"] == 1
    assert spawn["popInfo"]["nonpop"] == 0
    # NPCs must really have compatible navigation, not silently run without it.
    logs = "\n".join(p.read_text(errors="replace") for p in environment.runtime.glob("world*.log"))
    assert re.search(r"141\s+\d+\s+1\s+w1f2\s+PUBLIC\s+NAVI\s+Central Thanalan", logs)
    position = list(spawn["baseInfo"]["position"])
    # Do not overlap the enemy's exact spawn: face() has no horizontal direction
    # for coincident actors. This one-metre lateral PLAYER placement is fixture
    # setup, not a walked route, enemy relocation or navigation assertion.
    position[0] += 1.0
    fixture = environment.fresh_character(position, 141)
    witness_fixture = environment.fresh_character(position, 141)
    player, observer = Bot(live_worker, "fighter"), Bot(live_worker, "combat-observer")
    state = player.login_via_lobby(fixture["auth"], fixture["name"])
    entity = state["entity_id"]
    assert state["actors"][str(entity)]["level"] == catalog["level"]
    assert state["rewards"]["class_job"] == catalog["class_job"]
    before_rewards = player.reward_snapshot(catalog["work_index"])
    observer.login_via_lobby(witness_fixture["auth"], witness_fixture["name"])
    live_worker.wait_state(observer.name, lambda s: str(entity) in s["actors"], "fighter visible")

    def candidates(s):
        return [(key, actor) for key, actor in s["actors"].items()
                if actor["kind"] == 2 and actor["base_id"] == 351 and actor["level"] == 1
                and actor["hp"] == actor["hp_max"] > 0
                and math.dist(actor["position"], s["observed_position"]) < 2]

    # Wandering is genuine server behavior. Wait for an in-range observed NPC;
    # never force its position, issue out-of-range attacks or fabricate a route.
    state = live_worker.wait_state(player.name,
        lambda s: bool(candidates(s)) and s["actors"][str(entity)]["tp"] >= 60,
        "nearby level-one marmot and naturally regenerated TP", 30)
    target, before = candidates(state)[0]
    fighter_before = state["actors"][str(entity)]
    assert fighter_before["hp"] == fighter_before["hp_max"] > 0
    expected_hp = before["hp"]
    attempts, effects, evidence = [], [], []
    committed_states = {}
    while expected_hp > 0:
        assert len(effects) < 16, "bounded Fast Blade sequence did not defeat the level-one target"
        # No fixed sleep/retry around the action: await received natural TP and
        # the worker's conservative local guard, extended by received ActionStart.
        state = player.wait_fast_blade_ready(int(target))
        before = state["actors"][target]
        assert before["hp"] == expected_hp > 0
        live_worker.wait_state(observer.name,
            lambda s: target in s["actors"] and str(entity) in s["actors"]
                and s["actors"][target]["hp"] == before["hp"]
                and s["actors"][str(entity)]["hp"] > 0
                and math.dist(s["actors"][target]["position"], s["actors"][str(entity)]["position"]) < 3,
            "observer sees target HP and living fighter within melee range")
        attempts.append(time.monotonic())
        if len(attempts) > 1:
            assert attempts[-1] - attempts[-2] >= 2.5
        effect = player.fast_blade(int(target))
        assert effect["kind"] == 1 and damage_value(effect) > 0
        assert effect["request"] not in {old["request"] for old in effects}
        assert effect["result"] not in {old["result"] for old in effects}
        effects.append(effect)
        for bot in (player, observer):
            observed = live_worker.wait_state(bot.name,
                lambda s: committed_damage(s, effect, before),
                "identical effect and matching committed HP decrease", 10)
            assert observed["phase"] == "ready" and observed["gm_rank"] == 0 and observed["territory"] == 141
            assert observed["scene"] is None
            committed_states[bot.name] = observed
        started = live_worker.wait_state(player.name,
            lambda s: len([row for row in s["combat"]["starts"]
                           if row["source"] == entity and row["action"] == 9]) == len(effects),
            "one received Fast Blade start per request", 10)
        starts = [row for row in started["combat"]["starts"] if row["source"] == entity and row["action"] == 9]
        assert all(row["group"] == 58 and row["recast_centiseconds"] == 250 for row in starts)
        expected_hp = max(0, before["hp"] - damage_value(effect))
        evidence.append({"effect": effect, "before_hp": before["hp"], "after_hp": expected_hp,
                         "received_tp_before": state["actors"][str(entity)]["tp"],
                         "local_guard_remaining_ms": state["combat"]["starting_action_guard_remaining_ms"]})

    assert len(effects) >= 3
    for observed in committed_states.values():
        assert observed["actors"][target]["hp"] == 0

    def incoming(s):
        return [row for row in s["combat"]["effects"] if row["source"] == int(target)
                and row["target"] == entity and row["action"] == 7 and damage_value(row) > 0]

    state = live_worker.wait_state(player.name, lambda s: bool(incoming(s)), "natural marmot retaliation", 15)
    retaliation = incoming(state)[0]
    assert retaliation["kind"] == 1 and retaliation["request"] == 0
    # First positive hit against a previously full-health fighter. Later ticks
    # can regenerate HP; never infer a pre-hit value from a later desired result.
    for bot in (player, observer):
        observed = live_worker.wait_state(bot.name,
            lambda s: committed_damage(s, retaliation, fighter_before),
            "independently observed first retaliation effect and exact committed HP", 10)
        assert observed["actors"][str(entity)]["hp"] > 0
        assert observed["phase"] == "ready" and observed["territory"] == 141 and observed["gm_rank"] == 0
        assert observed["scene"] is None and observed["event_id"] is None

    def received_kill_rewards(s):
        current = reward_values(s["rewards"], catalog["work_index"])
        items = current["items"]
        first_pool = ((items.get("8", 0) - before_rewards["items"].get("8", 0) == 5)
                      != (items.get("9", 0) - before_rewards["items"].get("9", 0) == 5))
        return (current["exp"] == before_rewards["exp"] + catalog["base_exp"] and first_pool
                and items.get("5016", 0) - before_rewards["items"].get("5016", 0) == 1
                and items.get("12728", 0) - before_rewards["items"].get("12728", 0) == 1
                and 1 <= items.get("4551", 0) - before_rewards["items"].get("4551", 0) <= 3)

    rewarded = live_worker.wait_state(player.name, received_kill_rewards,
                                      "received defeat EXP and delayed loot", 15)
    after_rewards = reward_values(rewarded["rewards"], catalog["work_index"])
    after_inventory = rewarded["rewards"]["inventory"]
    reward_delta = combat_reward_delta(before_rewards, after_rewards, catalog["base_exp"])
    for bot in (player, observer):
        live_worker.wait_state(bot.name, lambda s: target not in s["actors"],
                               "defeated target removed after server fade", 20)

    # A complete fresh login supplies authoritative inventory/EXP snapshots and
    # proves persistence; the received kill-time deltas are not treated as that proof.
    player.close()
    live_worker.wait_state(observer.name, lambda s: str(entity) not in s["actors"], "fighter disconnect", 30)
    reloaded = Bot(live_worker, "fighter-reloaded")
    persisted = reloaded.login_via_lobby(fixture["auth"], fixture["name"])
    persisted = reloaded.expect_rewards(after_rewards, catalog["work_index"])
    assert persisted["rewards"]["inventory"] == after_inventory
    assert persisted["gm_rank"] == 0 and persisted["territory"] == 141
    reloaded.logout()
    observer.logout()

    # Independently exercise the other level-one melee starter action against a
    # second unchanged natural population, without granting class/resources.
    pugilist_meta = catalog["bootshine"]
    pugilist_spawn = population["LVD_BNPC_01"]["bnpcs"]["3746475"]
    assert pugilist_spawn["baseInfo"]["baseId"] == 351 and pugilist_spawn["baseInfo"]["level"] == 1
    pugilist_position = list(pugilist_spawn["baseInfo"]["position"])
    pugilist_position[0] += 1.0
    pugilist_fixture = environment.fresh_character(pugilist_position, 141, class_job=2)
    pugilist_witness_fixture = environment.fresh_character(pugilist_position, 141)
    pugilist = Bot(live_worker, "pugilist-fighter")
    pugilist_witness = Bot(live_worker, "pugilist-witness")
    pugilist_state = pugilist.login_via_lobby(pugilist_fixture["auth"], pugilist_fixture["name"])
    assert pugilist_state["rewards"]["class_job"] == pugilist_meta["class_job"]
    assert pugilist_state["actors"][str(pugilist_state["entity_id"])]["level"] == pugilist_meta["level"]
    pugilist_witness.login_via_lobby(pugilist_witness_fixture["auth"], pugilist_witness_fixture["name"])
    pugilist_entity = pugilist_state["entity_id"]

    def pugilist_candidates(s, maximum=2):
        return [(key, actor) for key, actor in s["actors"].items()
                if actor["kind"] == 2 and actor["base_id"] == 351 and actor["level"] == 1
                and actor["hp"] == actor["hp_max"] > 0
                and math.dist(actor["position"], s["predicted_position"]) < maximum]

    # Natural populations can roam while the preceding defeat scenario runs. Use
    # only received positions for a bounded ordinary approach, with the witness
    # verifying every reached point; never relocate the enemy or inject movement.
    pugilist_approach = []
    for _ in range(6):
        pugilist_state = live_worker.snapshot(pugilist.name)
        nearby = pugilist_candidates(pugilist_state, 20)
        assert nearby, "no bounded observed natural target for Pugilist approach"
        pugilist_target, approaching = min(nearby,
            key=lambda row: math.dist(row[1]["position"], pugilist_state["predicted_position"]))
        if math.dist(approaching["position"], pugilist_state["predicted_position"]) < 2:
            break
        destination = list(approaching["position"])
        pugilist.walk_to(destination, 2.0, 15)
        live_worker.wait_state(pugilist_witness.name,
            lambda s: str(pugilist_entity) in s["actors"]
                      and math.dist(s["actors"][str(pugilist_entity)]["position"], destination) < 0.15,
            "witness sees bounded Pugilist approach", 15)
        pugilist_approach.append(destination)
    else:
        raise AssertionError("bounded Pugilist approach did not reach a natural target")

    pugilist_state = live_worker.wait_state(pugilist.name,
        lambda s: bool(pugilist_candidates(s)) and s["actors"][str(pugilist_entity)]["tp"] >= 60,
        "nearby natural target and Pugilist TP", 30)
    pugilist_target, pugilist_before = pugilist_candidates(pugilist_state)[0]
    live_worker.wait_state(pugilist_witness.name,
        lambda s: pugilist_target in s["actors"] and str(pugilist_entity) in s["actors"]
                  and s["actors"][pugilist_target]["hp"] == pugilist_before["hp"],
        "witness sees Pugilist and target before Bootshine", 20)
    pugilist.wait_bootshine_ready(int(pugilist_target))
    bootshine = pugilist.bootshine(int(pugilist_target))
    assert bootshine["action"] == 53 and damage_value(bootshine) > 0
    for bot in (pugilist, pugilist_witness):
        live_worker.wait_state(bot.name, lambda s: committed_damage(s, bootshine, pugilist_before),
                               "Bootshine matching effect and committed HP", 10)
    bootshine_start = live_worker.wait_state(pugilist.name,
        lambda s: any(row["source"] == pugilist_entity and row["action"] == 53
                      and row["group"] == 58 and row["recast_centiseconds"] == 250
                      for row in s["combat"]["starts"]),
        "received Bootshine action start", 10)
    assert bootshine_start["rewards"]["class_job"] == 2
    pugilist.logout()
    pugilist_witness.logout()

    # Exercise the source-defined level-one caster action with received MP and
    # independently observed natural-target range; do not grant a spell or resource.
    blizzard_meta = catalog["blizzard"]
    caster_spawn = population["LVD_BNPC_01"]["bnpcs"]["3746477"]
    assert caster_spawn["baseInfo"]["baseId"] == 351 and caster_spawn["baseInfo"]["level"] == 1
    caster_position = list(caster_spawn["baseInfo"]["position"])
    caster_position[0] += 1.0
    caster_fixture = environment.fresh_character(caster_position, 141, class_job=7)
    caster_witness_fixture = environment.fresh_character(caster_position, 141)
    caster = Bot(live_worker, "thaumaturge-caster")
    caster_witness = Bot(live_worker, "thaumaturge-witness")
    caster_state = caster.login_via_lobby(caster_fixture["auth"], caster_fixture["name"])
    caster_entity = caster_state["entity_id"]
    assert caster_state["rewards"]["class_job"] == blizzard_meta["class_job"]
    caster_witness.login_via_lobby(caster_witness_fixture["auth"], caster_witness_fixture["name"])

    def caster_candidates(s):
        return [(key, actor) for key, actor in s["actors"].items()
                if actor["kind"] == 2 and actor["base_id"] == 351 and actor["level"] == 1
                and actor["hp"] == actor["hp_max"] > 0
                and math.dist(actor["position"], s["predicted_position"]) < 20]

    caster_state = live_worker.wait_state(caster.name,
        lambda s: bool(caster_candidates(s)) and s["actors"][str(caster_entity)]["mp"] >= 4,
        "natural target and received Thaumaturge MP", 30)
    caster_target, caster_before = min(caster_candidates(caster_state),
        key=lambda row: math.dist(row[1]["position"], caster_state["predicted_position"]))
    caster_mp_before = caster_state["actors"][str(caster_entity)]["mp"]
    live_worker.wait_state(caster_witness.name,
        lambda s: caster_target in s["actors"] and str(caster_entity) in s["actors"]
                  and s["actors"][caster_target]["hp"] == caster_before["hp"]
                  and math.dist(s["actors"][caster_target]["position"],
                                s["actors"][str(caster_entity)]["position"]) < 25,
        "witness sees Thaumaturge and natural target within spell range", 20)
    caster.wait_blizzard_ready(int(caster_target))
    blizzard = caster.blizzard(int(caster_target))
    assert blizzard["action"] == 142 and damage_value(blizzard) > 0
    for bot in (caster, caster_witness):
        live_worker.wait_state(bot.name, lambda s: committed_damage(s, blizzard, caster_before),
                               "Blizzard matching effect and committed HP", 10)
    caster_after = live_worker.wait_state(caster.name,
        lambda s: any(row["target"] == caster_entity and row["result"] == blizzard["result"]
                          and row["hp"] > 0 for row in s["combat"]["integrities"])
                  and any(row["source"] == caster_entity and row["action"] == 142
                          and row["group"] == 58 and row["recast_centiseconds"] == 250
                          for row in s["combat"]["starts"]),
        "received Blizzard source integrity and action start", 10)
    blizzard_integrity = next(row for row in caster_after["combat"]["integrities"]
                              if row["target"] == caster_entity and row["result"] == blizzard["result"])
    caster.logout()
    caster_witness.logout()

    (environment.artifacts / "combat-defeat-rewards.json").write_text(json.dumps({
        "attacks": evidence, "attempt_monotonic": attempts, "retaliation": retaliation,
        "fighter_hp_before_combat": fighter_before["hp"], "target_hp_after": 0,
        "target_removed_for_both_clients": True, "rewards_before": before_rewards,
        "rewards_after_received": after_rewards, "inventory_after_received": after_inventory,
        "reward_delta": reward_delta, "rewards_after_fresh_login": after_rewards,
        "inventory_after_fresh_login": after_inventory, "both_clients_verified": True,
        "bootshine": {"class_job": 2, "action_metadata": pugilist_meta, "effect": bootshine,
                      "target_before": pugilist_before, "observed_approach": pugilist_approach,
                      "both_clients_verified": True},
        "blizzard": {"class_job": 7, "action_metadata": blizzard_meta, "effect": blizzard,
                     "target_before": caster_before, "received_mp_before": caster_mp_before,
                     "source_integrity": blizzard_integrity, "both_clients_verified": True},
        "scope": "one natural level-one Fast Blade enemy defeat with current testTable loot/EXP plus independently observed natural-target Bootshine and Blizzard effects/resources; no combo or general combat claim"
    }, indent=2), encoding="utf-8")

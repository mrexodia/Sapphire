"""Natural-enemy player defeat without grants, relocation or injected damage."""
import json
import math
import time

import pytest

from .support.catalog import load_pursuit_catalog, load_respawn_catalog
from .support.worker import Bot, reward_values
from .support.combat import damage_value, require_unchanged_death_state

pytestmark = pytest.mark.live


def test_natural_enemy_defeats_level_one_player(server, live_worker):
    path = server.profile.get("respawn_catalog")
    pursuit_path = server.profile.get("pursuit_catalog")
    assert path and pursuit_path, "player defeat requires source-bound homepoint and pursuit catalogs"
    respawn = load_respawn_catalog(path)
    pursuit = load_pursuit_catalog(pursuit_path)
    population = json.loads((server.runtime / "data/bnpcs/w1f2/w1f2.json").read_text())
    server.require_navmesh(141, "w1f2")  # enemies cannot move without one
    candidates = []
    for group in population.values():
        for layout_id, row in group.get("bnpcs", {}).items():
            base, pop = row["baseInfo"], row["popInfo"]
            if base["baseId"] == 302 and base["level"] == 14 and pop["nonpop"] == 0:
                candidates.append((layout_id, base))
    candidates = [candidate for candidate in candidates if int(candidate[0]) == pursuit["enemy"]["layout_id"]]
    assert len(candidates) == 1, "matching source-bound Central Thanalan population missing"
    layout_id, spawn = candidates[0]
    assert spawn["position"] == pursuit["enemy"]["position"]
    fighter_position = list(spawn["position"])
    fighter_position[0] += 1.0
    observer_position = list(spawn["position"])
    observer_position[0] -= 30.0
    fighter_fixture = server.fresh_character(fighter_position, 141)
    observer_fixture = server.fresh_character(observer_position, 141)
    return_observer_fixture = server.fresh_character(respawn["pop_range"]["position"], respawn["territory"])
    observer = Bot(live_worker, "defeat-observer")
    observer.login_via_lobby(observer_fixture["auth"], observer_fixture["name"])
    return_observer = Bot(live_worker, "return-observer")
    return_observer.login_via_lobby(return_observer_fixture["auth"], return_observer_fixture["name"])
    fighter = Bot(live_worker, "defeated-fighter")
    initial = fighter.login_via_lobby(fighter_fixture["auth"], fighter_fixture["name"])
    entity = initial["entity_id"]
    before = initial["actors"][str(entity)]
    before_rewards = reward_values(initial["rewards"], 1)
    before_inventory = initial["rewards"]["inventory"]
    assert before["hp"] == before["hp_max"] > 0 and before["level"] == 1
    live_worker.wait_state(observer.name, lambda s: str(entity) in s["actors"], "fighter visible", 20)
    # The pursuit and leash routes are authored around this enemy's spawn, so the
    # scenario keeps the exact spawn. With navigation active the enemy roams and
    # may have been killed by an earlier scenario, so allow one respawn and a
    # wider search; the opening approach below follows it using received positions.
    state = live_worker.wait_state(fighter.name,
        lambda s: any(actor["kind"] == 2 and actor["base_id"] == 302 and actor["level"] == 14
                      and actor["layout_id"] == int(layout_id) and actor["hp"] == actor["hp_max"] > 0
                      and math.dist(actor["position"], s["observed_position"]) < 40
                      for actor in s["actors"].values()),
        "source-layout level-14 enemy healthy within 40m (allow one respawn)", 150)
    target = next(int(key) for key, actor in state["actors"].items()
                  if actor["kind"] == 2 and actor["base_id"] == 302 and actor["level"] == 14
                  and actor["layout_id"] == int(layout_id) and actor["hp"] == actor["hp_max"] > 0
                  and math.dist(actor["position"], state["observed_position"]) < 40)
    live_worker.wait_state(observer.name,
        lambda s: s["actors"].get(str(target), {}).get("layout_id") == int(layout_id)
                  and s["actors"][str(target)]["hp"] == s["actors"][str(target)]["hp_max"] > 0,
        "observer independently receives bounded opening target", 20)
    live_worker.wait_state(fighter.name,
        lambda s: s["actors"].get(str(entity), {}).get("tp", 0) >= 60,
        "naturally regenerated opening TP", 10)
    # This population may roam while TP regenerates. Follow only bounded received
    # positions using normal movement, with every reached point witnessed.
    opening_approach = []
    for _ in range(8):
        state = live_worker.snapshot(fighter.name)
        current_enemy = state["actors"].get(str(target))
        assert current_enemy and current_enemy["hp"] == current_enemy["hp_max"] > 0
        distance = math.dist(current_enemy["position"], state["predicted_position"])
        if distance < 2.5:
            break
        assert distance < 45, "natural opening target left bounded follow range"
        destination = list(current_enemy["position"])
        fighter.walk_to(destination, 2.0, 15)
        live_worker.wait_state(observer.name,
            lambda s: str(entity) in s["actors"]
                      and math.dist(s["actors"][str(entity)]["position"], destination) < 0.15,
            "observer sees bounded opening approach", 15)
        opening_approach.append(destination)
    else:
        raise AssertionError("bounded opening approach did not reach the natural target")
    state = fighter.wait_fast_blade_ready(target)
    enemy_start = state["actors"][str(target)]["position"]
    opening_effect = fighter.fast_blade(target)
    assert opening_effect["target"] == target and damage_value(opening_effect) > 0

    # Drive beyond the source implementation's 40m spawn-distance retreat threshold.
    leash_peak = None
    leash_peak_distance = 0
    deadline = time.monotonic() + 30
    for point in pursuit["leash_route"]:
        remaining = deadline - time.monotonic()
        assert remaining > 0, "leash route exceeded its monotonic deadline"
        current = fighter.walk_to(point, 6.0, remaining)
        enemy_position = current["actors"].get(str(target), {}).get("position", enemy_start)
        distance_from_spawn = math.dist(enemy_position, pursuit["enemy"]["position"])
        if distance_from_spawn > leash_peak_distance:
            leash_peak, leash_peak_distance = current, distance_from_spawn
    # Let pathing catch up after the fighter reaches the endpoint. Position
    # replication is coarser than the FSM tick; a received >35m pursuit followed
    # by return to spawn proves the source-defined retreat transition.
    if leash_peak_distance <= 35:
        leash_peak = live_worker.wait_state(fighter.name,
            lambda s: s["actors"].get(str(entity), {}).get("hp", 0) > 0
                      and math.dist(s["actors"].get(str(target), {}).get("position", enemy_start),
                                    pursuit["enemy"]["position"]) > 35,
            "enemy approaches source-defined leash threshold", 30)
        leash_peak_distance = math.dist(leash_peak["actors"][str(target)]["position"],
                                        pursuit["enemy"]["position"])
    live_worker.wait_state(observer.name,
        lambda s: str(entity) in s["actors"]
                  and math.dist(s["actors"][str(entity)]["position"], pursuit["leash_route"][-1]) < 0.15,
        "observer sees fighter complete leash route", 30)
    reset = live_worker.wait_state(fighter.name,
        lambda s: s["actors"].get(str(entity), {}).get("hp", 0) > 0
                  and str(target) in s["actors"]
                  and math.dist(s["actors"][str(target)]["position"], pursuit["enemy"]["position"]) < 2,
        "enemy retreats to spawn while fighter survives", 45)
    health_reset = live_worker.wait_state(fighter.name,
        lambda s: str(target) in s["actors"]
                  and s["actors"][str(target)]["hp"] == s["actors"][str(target)]["hp_max"] > 0,
        "retreated enemy health reset", 10)
    observer_health_reset = live_worker.wait_state(observer.name,
        lambda s: str(target) in s["actors"]
                  and s["actors"][str(target)]["hp"] == health_reset["actors"][str(target)]["hp"],
        "observer sees retreated enemy health reset", 10)
    assert observer_health_reset["actors"][str(target)]["hp_max"] == health_reset["actors"][str(target)]["hp_max"]
    fighter.walk_route(list(reversed(pursuit["leash_route"])), 6.0, 30)
    live_worker.wait_state(observer.name,
        lambda s: str(entity) in s["actors"]
                  and math.dist(s["actors"][str(entity)]["position"], pursuit["leash_route"][0]) < 0.15,
        "observer sees fighter return to reset enemy", 30)
    live_worker.wait_state(fighter.name,
        lambda s: str(target) in s["actors"]
                  and math.dist(s["actors"][str(target)]["position"], s["predicted_position"]) < 3,
        "returned fighter reaches reset enemy", 30)
    fighter.wait_fast_blade_ready(target)
    second_opening_effect = fighter.fast_blade(target)
    assert second_opening_effect["target"] == target and damage_value(second_opening_effect) > 0
    pursuit_enemy_start = live_worker.snapshot(fighter.name)["actors"][str(target)]["position"]

    fighter.walk_route(pursuit["route"], 6.0, 30)
    live_worker.wait_state(observer.name,
        lambda s: str(entity) in s["actors"]
                  and math.dist(s["actors"][str(entity)]["position"], pursuit["route"][-1]) < 0.15,
        "independent observer sees fighter complete pursuit route", 30)
    pursued = live_worker.wait_state(fighter.name,
        lambda s: math.dist(s["actors"].get(str(target), {}).get("position", pursuit_enemy_start),
                            pursuit_enemy_start) >= 2,
        "hostile natural enemy pursuit", 30)
    pursued_observer = live_worker.wait_state(observer.name,
        lambda s: math.dist(s["actors"].get(str(target), {}).get("position", pursuit_enemy_start),
                            pursuit_enemy_start) >= 2,
        "observer sees hostile natural enemy pursuit", 30)
    enemy_pursued_position = pursued["actors"][str(target)]["position"]
    observer_pursued_position = pursued_observer["actors"][str(target)]["position"]
    # These snapshots are independent and the enemy is still moving; requiring
    # two asynchronously received positions to be the same tick is invalid. A
    # chasing enemy may also pass the fighter's endpoint between snapshots, so
    # endpoint distance is not monotonic. Require independently received movement
    # at least 2m with a forward projection and cosine toward that endpoint instead.
    route_vector = [end - start for start, end in zip(pursuit["route"][0], pursuit["route"][-1])]
    route_length = math.sqrt(sum(value * value for value in route_vector))
    assert route_length > 5
    for position in (enemy_pursued_position, observer_pursued_position):
        displacement = [end - start for start, end in zip(pursuit_enemy_start, position)]
        displacement_length = math.sqrt(sum(value * value for value in displacement))
        projection = sum(value * direction for value, direction in zip(displacement, route_vector)) / route_length
        cosine = projection / displacement_length
        assert displacement_length >= 2 and projection >= 2 and cosine > 0.5

    defeated = live_worker.wait_state(fighter.name,
        lambda s: s["actors"].get(str(entity), {}).get("hp") == 0,
        "natural hostile-enemy player defeat", 90)
    incoming = [effect for effect in defeated["combat"]["effects"]
                if effect["target"] == entity and effect["kind"] == 1 and damage_value(effect) > 0]
    starts = [start for start in defeated["combat"]["starts"]
              if start["source"] == entity and start["action"] == 9]
    assert incoming and len(starts) == 2
    sources = {effect["source"] for effect in incoming}
    assert len(sources) == 1
    source = next(iter(sources))
    enemy = defeated["actors"][str(source)]
    assert enemy["base_id"] == 302 and enemy["level"] == 14 and 0 < enemy["hp"] < enemy["hp_max"]
    assert math.dist(enemy["position"], pursuit["route"][-1]) < 4
    require_unchanged_death_state(
        before_rewards, before_inventory,
        reward_values(defeated["rewards"], 1), defeated["rewards"]["inventory"])

    observed = live_worker.wait_state(observer.name,
        lambda s: s["actors"].get(str(entity), {}).get("hp") == 0,
        "observer sees player defeat", 20)
    observer_incoming = [effect for effect in observed["combat"]["effects"]
                         if effect["source"] == source and effect["target"] == entity
                         and effect["kind"] == 1 and damage_value(effect) > 0]
    assert observer_incoming == incoming
    for state in (defeated, observed):
        integrities = {(row["target"], row["result"]): row for row in state["combat"]["integrities"]}
        for effect in incoming:
            committed = integrities[(entity, effect["result"])]
            assert committed["hp"] == max(0, committed["previous_hp"] - damage_value(effect))
            assert committed["hp"] < committed["previous_hp"] <= before["hp_max"]
            assert committed["hp_max"] == before["hp_max"]
        assert integrities[(entity, incoming[-1]["result"])]["hp"] == 0

    incoming_integrities = [{key: row[key] for key in ("target", "result", "previous_hp", "hp", "hp_max")}
                            for row in defeated["combat"]["integrities"]
                            if row["target"] == entity and row["result"] in {effect["result"] for effect in incoming}]
    assert len(incoming_integrities) == len(incoming)

    returned = fighter.return_homepoint(respawn["territory"], respawn["pop_range"]["position"])
    live_worker.wait_state(observer.name, lambda s: str(entity) not in s["actors"],
                           "defeated fighter leaves Central Thanalan", 30)
    return_seen = live_worker.wait_state(return_observer.name,
        lambda s: str(entity) in s["actors"]
                  and s["actors"][str(entity)]["hp"] == s["actors"][str(entity)]["hp_max"]
                  and math.dist(s["actors"][str(entity)]["position"], respawn["pop_range"]["position"]) < 0.15,
        "independent observer sees living fighter at homepoint", 30)
    assert returned["homepoint"] == 9 and returned["territory"] == 130
    returned_position = returned["observed_position"]
    returned_hp = returned["actors"][str(entity)]["hp"]
    assert returned_hp == returned["actors"][str(entity)]["hp_max"] == before["hp_max"]
    require_unchanged_death_state(
        before_rewards, before_inventory,
        reward_values(returned["rewards"], 1), returned["rewards"]["inventory"])

    fighter.logout()
    live_worker.wait_state(return_observer.name, lambda s: str(entity) not in s["actors"],
                           "returned fighter session cleanup", 30)
    fighter.close()
    observer.logout()
    observer.close()
    return_observer.logout()
    return_observer.close()
    auth = server.relogin(fighter_fixture)
    reloaded = Bot(live_worker, "returned-reloaded")
    persisted = reloaded.login_via_lobby(auth, fighter_fixture["name"])
    persisted_self = persisted["actors"][str(persisted["entity_id"])]
    assert persisted["territory"] == respawn["territory"]
    assert math.dist(persisted["observed_position"], respawn["pop_range"]["position"]) < 0.15
    assert persisted_self["hp"] == persisted_self["hp_max"] == before["hp_max"]
    require_unchanged_death_state(
        before_rewards, before_inventory,
        reward_values(persisted["rewards"], 1), persisted["rewards"]["inventory"])
    reloaded.logout()
    reloaded.close()
    (server.artifacts / "combat-player-defeat.json").write_text(json.dumps({
        "population_layout": int(layout_id), "enemy_base_id": 302, "enemy_level": 14,
        "fighter_hp_before": before["hp"], "opening_effect": opening_effect,
        "observed_opening_approach": opening_approach,
        "pursuit_route_length": pursuit["route_length"],
        "enemy_position_before_first_engagement": enemy_start,
        "enemy_position_before_pursuit": pursuit_enemy_start,
        "leash_route_length": pursuit["leash_route_length"],
        "enemy_position_at_leash_peak": leash_peak["actors"][str(target)]["position"],
        "received_leash_peak_distance": leash_peak_distance,
        "enemy_position_after_reset": reset["actors"][str(target)]["position"],
        "enemy_hp_at_spawn_arrival": reset["actors"][str(target)]["hp"],
        "enemy_hp_after_reset": health_reset["actors"][str(target)]["hp"],
        "enemy_hp_max_after_reset": health_reset["actors"][str(target)]["hp_max"],
        "health_reset_observer_verified": True,
        "fighter_hp_after_reset": reset["actors"][str(entity)]["hp"],
        "second_opening_effect": second_opening_effect,
        "enemy_position_after_pursuit": enemy_pursued_position, "pursuit_observer_verified": True,
        "incoming_effects": incoming, "incoming_integrities": incoming_integrities,
        "fighter_hp_after": 0, "enemy_hp_after": enemy["hp"],
        "homepoint": respawn, "returned_position": returned_position, "returned_hp": returned_hp,
        "return_observer_hp": return_seen["actors"][str(entity)]["hp"],
        "persisted_position": persisted["observed_position"], "persisted_hp": persisted_self["hp"],
        "reward_state_before": before_rewards, "reward_state_after_defeat": before_rewards,
        "reward_state_after_return": before_rewards, "reward_state_after_restart": before_rewards,
        "inventory_unchanged_through_defeat_return_restart": before_inventory,
        "both_defeat_clients_verified": True, "return_observer_verified": True,
        "scope": "one natural level-14 enemy pursues a normally moving level-one player, retreats to spawn after the 40m leash, is re-engaged and defeats the player, followed by a source-bound homepoint return and restart persistence with exact tracked EXP, level, currency and inventory unchanged; no durability, raise or general combat claim"
    }, indent=2), encoding="utf-8")

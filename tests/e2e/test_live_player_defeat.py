"""Natural-enemy player defeat without grants, relocation or injected damage."""
import json
import math

import pytest

from .support.catalog import load_respawn_catalog
from .support.worker import Bot
from .support.combat import damage_value

pytestmark = pytest.mark.live


def test_natural_enemy_defeats_level_one_player(environment, live_worker):
    path = environment.profile.get("respawn_catalog")
    assert path, "player defeat requires a source-bound homepoint catalog"
    respawn = load_respawn_catalog(path)
    population = json.loads((environment.runtime / "data/bnpcs/w1f2/w1f2.json").read_text())
    candidates = []
    for group in population.values():
        for layout_id, row in group.get("bnpcs", {}).items():
            base, pop = row["baseInfo"], row["popInfo"]
            if base["baseId"] == 302 and base["level"] == 14 and pop["nonpop"] == 0:
                candidates.append((layout_id, base))
    assert candidates, "matching unchanged Central Thanalan level-14 population missing"
    layout_id, spawn = candidates[0]
    fighter_position = list(spawn["position"])
    fighter_position[0] += 1.0
    observer_position = list(spawn["position"])
    observer_position[0] -= 30.0
    fighter_fixture = environment.fresh_character(fighter_position, 141)
    observer_fixture = environment.fresh_character(observer_position, 141)
    return_observer_fixture = environment.fresh_character(respawn["pop_range"]["position"], respawn["territory"])
    observer = Bot(live_worker, "defeat-observer")
    observer.login_via_lobby(observer_fixture["auth"], observer_fixture["name"])
    return_observer = Bot(live_worker, "return-observer")
    return_observer.login_via_lobby(return_observer_fixture["auth"], return_observer_fixture["name"])
    fighter = Bot(live_worker, "defeated-fighter")
    initial = fighter.login_via_lobby(fighter_fixture["auth"], fighter_fixture["name"])
    entity = initial["entity_id"]
    before = initial["actors"][str(entity)]
    assert before["hp"] == before["hp_max"] > 0 and before["level"] == 1
    live_worker.wait_state(observer.name, lambda s: str(entity) in s["actors"], "fighter visible", 20)
    state = live_worker.wait_state(fighter.name,
        lambda s: any(actor["kind"] == 2 and actor["base_id"] == 302 and actor["level"] == 14
                      and actor["hp"] == actor["hp_max"] > 0
                      and math.dist(actor["position"], s["observed_position"]) < 3
                      for actor in s["actors"].values()),
        "nearby natural level-14 enemy and received state", 20)
    target = next(int(key) for key, actor in state["actors"].items()
                  if actor["kind"] == 2 and actor["base_id"] == 302 and actor["level"] == 14
                  and actor["hp"] == actor["hp_max"] > 0
                  and math.dist(actor["position"], state["observed_position"]) < 3)
    fighter.wait_fast_blade_ready(target)
    opening_effect = fighter.fast_blade(target)
    assert opening_effect["target"] == target and damage_value(opening_effect) > 0

    defeated = live_worker.wait_state(fighter.name,
        lambda s: s["actors"].get(str(entity), {}).get("hp") == 0,
        "natural hostile-enemy player defeat", 90)
    incoming = [effect for effect in defeated["combat"]["effects"]
                if effect["target"] == entity and effect["kind"] == 1 and damage_value(effect) > 0]
    starts = [start for start in defeated["combat"]["starts"]
              if start["source"] == entity and start["action"] == 9]
    assert incoming and len(starts) == 1
    sources = {effect["source"] for effect in incoming}
    assert len(sources) == 1
    source = next(iter(sources))
    enemy = defeated["actors"][str(source)]
    assert enemy["base_id"] == 302 and enemy["level"] == 14 and 0 < enemy["hp"] < enemy["hp_max"]
    assert math.dist(enemy["position"], defeated["observed_position"]) < 4

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

    fighter.logout()
    live_worker.wait_state(return_observer.name, lambda s: str(entity) not in s["actors"],
                           "returned fighter session cleanup", 30)
    fighter.close()
    observer.logout()
    observer.close()
    return_observer.logout()
    return_observer.close()
    environment.restart_world()
    auth = environment.api("login", {"username": fighter_fixture["username"], "pass": fighter_fixture["password"]})
    reloaded = Bot(live_worker, "returned-reloaded")
    persisted = reloaded.login_via_lobby(auth, fighter_fixture["name"])
    persisted_self = persisted["actors"][str(persisted["entity_id"])]
    assert persisted["territory"] == respawn["territory"]
    assert math.dist(persisted["observed_position"], respawn["pop_range"]["position"]) < 0.15
    assert persisted_self["hp"] == persisted_self["hp_max"] == before["hp_max"]
    reloaded.logout()
    reloaded.close()
    (environment.artifacts / "combat-player-defeat.json").write_text(json.dumps({
        "population_layout": int(layout_id), "enemy_base_id": 302, "enemy_level": 14,
        "fighter_hp_before": before["hp"], "opening_effect": opening_effect,
        "incoming_effects": incoming, "incoming_integrities": incoming_integrities,
        "fighter_hp_after": 0, "enemy_hp_after": enemy["hp"],
        "homepoint": respawn, "returned_position": returned_position, "returned_hp": returned_hp,
        "return_observer_hp": return_seen["actors"][str(entity)]["hp"],
        "persisted_position": persisted["observed_position"], "persisted_hp": persisted_self["hp"],
        "both_defeat_clients_verified": True, "return_observer_verified": True,
        "scope": "one natural level-14 enemy defeat followed by an ordinary source-bound homepoint return and restart persistence; no raise, pursuit or general combat claim"
    }, indent=2), encoding="utf-8")

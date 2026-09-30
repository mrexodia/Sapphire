"""One source-bound natural vision-aggro path without a player combat action."""
import json
import math

import pytest

from .support.catalog import load_pursuit_catalog, load_respawn_catalog
from .support.combat import (committed_damage, damage_value,
                             require_unchanged_death_state)
from .support.worker import Bot, reward_values

pytestmark = pytest.mark.live


def test_natural_vision_aggro_without_player_action(environment, live_worker):
    pursuit_path = environment.profile.get("pursuit_catalog")
    respawn_path = environment.profile.get("respawn_catalog")
    assert pursuit_path and respawn_path, "proximity aggro requires source-bound pursuit and respawn catalogs"
    pursuit = load_pursuit_catalog(pursuit_path)
    respawn = load_respawn_catalog(respawn_path)
    bound = pursuit["proximity_enemy"]

    population = json.loads((environment.runtime / "data/bnpcs/w1f2/w1f2.json").read_text())
    matches = []
    for group in population.values():
        row = group.get("bnpcs", {}).get(str(bound["layout_id"]))
        if row is not None:
            matches.append(row)
    assert len(matches) == 1
    source = matches[0]
    assert source["baseInfo"]["baseId"] == bound["base_id"]
    assert source["baseInfo"]["level"] == bound["level"]
    assert source["baseInfo"]["activeType"] == bound["active_type"] == 0
    assert source["baseInfo"]["position"] == bound["position"]
    assert source["SenseInfo"]["Sense"] == [bound["sense"], 0] == [1, 0]
    assert source["SenseInfo"]["SenseRange"] == [bound["sense_range"], 10]
    assert source["Behaviour"]["wanderingRange"] == bound["wandering_range"]
    assert source["popInfo"]["nonpop"] == source["popInfo"]["invalidRepop"] == 0

    fighter_fixture = environment.fresh_character(pursuit["proximity_route"][0], 141)
    witness_fixture = environment.fresh_character(pursuit["proximity_witness_position"], 141)
    witness = Bot(live_worker, "proximity-aggro-witness")
    witness.login_via_lobby(witness_fixture["auth"], witness_fixture["name"])
    fighter = Bot(live_worker, "proximity-aggro-fighter")
    initial = fighter.login_via_lobby(fighter_fixture["auth"], fighter_fixture["name"])
    entity = initial["entity_id"]
    before = initial["actors"][str(entity)]
    before_rewards = reward_values(initial["rewards"], 1)
    before_inventory = initial["rewards"]["inventory"]
    assert before["hp"] == before["hp_max"] > 0 and before["level"] == 1

    state = live_worker.wait_state(
        fighter.name,
        lambda s: any(actor["layout_id"] == bound["layout_id"]
                      and actor["base_id"] == bound["base_id"]
                      and actor["level"] == bound["level"]
                      and actor["hp"] == actor["hp_max"] > 0
                      for actor in s["actors"].values()),
        "source-bound living active-vision enemy", 20)
    target = next(int(key) for key, actor in state["actors"].items()
                  if actor["layout_id"] == bound["layout_id"]
                  and actor["base_id"] == bound["base_id"]
                  and actor["level"] == bound["level"]
                  and actor["hp"] == actor["hp_max"] > 0)
    witness_before = live_worker.wait_state(
        witness.name,
        lambda s: str(entity) in s["actors"] and str(target) in s["actors"],
        "witness independently receives fighter and active enemy", 20)
    assert math.dist(state["predicted_position"], bound["position"]) > 15
    assert not state["combat"]["effects"] and not state["combat"]["starts"]

    fighter.walk_route(pursuit["proximity_route"], 6.0, 30)
    approach_seen = live_worker.wait_state(
        witness.name,
        lambda s: str(entity) in s["actors"]
                  and math.dist(s["actors"][str(entity)]["position"],
                                pursuit["proximity_route"][-1]) < 0.15,
        "witness sees source-navmesh vision approach", 30)
    first = live_worker.wait_state(
        fighter.name,
        lambda s: any(effect["source"] == target and effect["target"] == entity
                      and effect["kind"] == 1 and damage_value(effect) > 0
                      for effect in s["combat"]["effects"]),
        "natural active enemy attacks without a player action", 30)
    effect = next(effect for effect in first["combat"]["effects"]
                  if effect["source"] == target and effect["target"] == entity
                  and effect["kind"] == 1 and damage_value(effect) > 0)
    assert not first["combat"]["starts"]
    assert not any(row["source"] == entity for row in first["combat"]["effects"])
    assert committed_damage(first, effect, before)

    witnessed = live_worker.wait_state(
        witness.name,
        lambda s: effect in s["combat"]["effects"],
        "witness receives identical unprovoked enemy action", 20)
    assert committed_damage(witnessed, effect, witness_before["actors"][str(entity)])

    defeated = live_worker.wait_state(
        fighter.name,
        lambda s: s["actors"].get(str(entity), {}).get("hp") == 0,
        "natural active enemy defeats non-attacking player", 240)
    observed_defeat = live_worker.wait_state(
        witness.name,
        lambda s: s["actors"].get(str(entity), {}).get("hp") == 0,
        "witness sees unprovoked natural player defeat", 20)
    assert observed_defeat["actors"][str(entity)]["hp"] == 0
    assert not defeated["combat"]["starts"]
    assert not any(row["source"] == entity for row in defeated["combat"]["effects"])
    require_unchanged_death_state(
        before_rewards, before_inventory,
        reward_values(defeated["rewards"], 1), defeated["rewards"]["inventory"])
    incoming = [row for row in defeated["combat"]["effects"]
                if row["source"] == target and row["target"] == entity
                and row["kind"] == 1 and damage_value(row) > 0]
    assert incoming and effect in incoming

    returned = fighter.return_homepoint(respawn["territory"], respawn["pop_range"]["position"])
    live_worker.wait_state(witness.name, lambda s: str(entity) not in s["actors"],
                           "unprovoked defeated fighter leaves source territory", 30)
    require_unchanged_death_state(
        before_rewards, before_inventory,
        reward_values(returned["rewards"], 1), returned["rewards"]["inventory"])
    fighter.logout()
    fighter.close()
    witness.logout()
    witness.close()
    environment.restart_world()

    (environment.artifacts / "combat-proximity-aggro.json").write_text(json.dumps({
        "enemy": bound,
        "approach_route_length": pursuit["proximity_route_length"],
        "approach_start": pursuit["proximity_route"][0],
        "approach_end": pursuit["proximity_route"][-1],
        "witness_position": pursuit["proximity_witness_position"],
        "fighter_position_after_route": approach_seen["actors"][str(entity)]["position"],
        "first_unprovoked_effect": effect,
        "fighter_hp_before": before["hp"],
        "fighter_hp_after_first_effect": first["actors"][str(entity)]["hp"],
        "fighter_hp_after": defeated["actors"][str(entity)]["hp"],
        "received_bound_enemy_effect_count": len(incoming),
        "return_territory": returned["territory"],
        "player_combat_effects_sent": 0,
        "player_action_starts_received": 0,
        "independent_witness_verified": True,
        "reward_state_unchanged": before_rewards,
        "scope": "one source-bound level-six active vision enemy naturally attacks and defeats a normally moving non-attacking level-one player; not general proximity, vision, line-of-sight, aggro, target-selection, pursuit or combat policy"
    }, indent=2), encoding="utf-8")

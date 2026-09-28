"""One normal learned melee action; no spawned/modified enemies or granted skills."""
import json
import math
import re

import pytest

from .support.worker import Bot
from .support.catalog import load_combat_catalog

pytestmark = pytest.mark.live


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
    position = spawn["baseInfo"]["position"]
    fixture = environment.fresh_character(position, 141)
    witness_fixture = environment.fresh_character(position, 141)
    player, observer = Bot(live_worker, "fighter"), Bot(live_worker, "combat-observer")
    state = player.login_via_lobby(fixture["auth"], fixture["name"])
    entity = state["entity_id"]
    assert state["actors"][str(entity)]["level"] == catalog["level"]
    assert state["rewards"]["class_job"] == catalog["class_job"]
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
    live_worker.wait_state(observer.name,
        lambda s: target in s["actors"] and str(entity) in s["actors"]
            and s["actors"][target]["hp"] == before["hp"]
            and math.dist(s["actors"][target]["position"], s["actors"][str(entity)]["position"]) < 3,
        "observer sees healthy target within fighter's melee range")
    effect = player.fast_blade(int(target))
    damage = sum(e["value"] for e in effect["effects"] if e["type"] in (3, 5) and e["flag"] == 0)
    assert damage > 0, f"expected positive damage, received {effect}"
    for bot in (player, observer):
        state = live_worker.wait_state(bot.name,
            lambda s: any(e["source"] == entity and e["target"] == int(target) and e["action"] == 9
                          and e["result"] == effect["result"] for e in s["combat"]["effects"])
                and any(i["target"] == int(target) and i["result"] == effect["result"]
                        and i["hp_max"] == before["hp_max"]
                        and i["hp"] == max(0, before["hp"] - damage) for i in s["combat"]["integrities"]),
            "matching action result and committed HP decrease", 10)
        assert state["phase"] == "ready" and state["gm_rank"] == 0 and state["territory"] == 141
        assert state["scene"] is None
        observed = next(e for e in state["combat"]["effects"]
                        if e["result"] == effect["result"] and e["source"] == entity and e["target"] == int(target))
        assert observed["effects"] == effect["effects"] and observed["kind"] == 1
    # Disconnect is deliberate: do not bypass the client's in-combat logout restriction.
    player.close()
    live_worker.wait_state(observer.name, lambda s: str(entity) not in s["actors"], "fighter disconnect", 30)
    observer.logout()
    observer.close()

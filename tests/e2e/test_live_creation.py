"""Normal lobby character creation and the first source-defined Ul'dah opening scenes."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from .support.worker import Bot

pytestmark = pytest.mark.live


def test_lobby_character_creation_and_opening_persistence(environment, live_worker):
    account = environment.fresh_account()
    catalog = json.loads((Path(__file__).parent / "scene_catalog/opening_uldah.json").read_text())
    assert catalog["profile"] == "sapphire-3.3" and catalog["event_id"] == 1245187
    player = Bot(live_worker, "new-character")
    state = player.create_character_via_lobby(account["auth"], account["name"])
    assert state["created_via_lobby"] is True and state["territory"] == 182
    assert state["gm_rank"] == 0 and state["actors"][str(state["entity_id"])]["level"] == 1
    assert [row["name"] for row in state["characters"]] == [account["name"]]
    before = player.reward_snapshot(1)
    assert before["items"] == {} and before["exp"] == 0 and before["level"] == 1

    player.start_uldah_opening()
    player.choose_dialogue(catalog, "choose_ring")
    scene = live_worker.wait_state(player.name,
        lambda s: s["scene"] is not None and s["scene"]["event_id"] == 1245187
                  and s["scene"]["scene_id"] == 1,
        "source-defined chained Ul'dah opening scene 1")
    assert scene["territory"] == 182 and scene["gm_rank"] == 0
    player.choose_dialogue(catalog, "finish")
    player.wait_event_finished()
    player.logout(wait_server_close=True)
    player.close()

    auth = environment.api("login", {"username": account["username"], "pass": account["password"]})
    reloaded = Bot(live_worker, "new-character-reloaded")
    state = reloaded.login_via_lobby(auth, account["name"])
    assert state["created_via_lobby"] is False and state["territory"] == 182 and state["gm_rank"] == 0
    expected = deepcopy(before)
    expected["items"]["4423"] = 1
    state = reloaded.expect_rewards(expected, 1)
    inventory = deepcopy(state["rewards"]["inventory"])
    assert len([item for item in inventory.values() if item["id"] == 4423 and item["count"] == 1]) == 1

    # OpeningSequence=1 must select scene 40 after fresh authentication, not replay scene 0.
    reloaded.start_uldah_opening()
    scene = live_worker.wait_state(reloaded.name,
        lambda s: s["scene"] is not None and s["scene"]["event_id"] == 1245187,
        "persisted Ul'dah opening continuation")
    assert scene["scene"]["scene_id"] == 40
    reloaded.choose_dialogue(catalog, "finish")
    reloaded.wait_event_finished()
    reloaded.logout(wait_server_close=True)
    reloaded.close()

    environment.restart_world()
    auth = environment.api("login", {"username": account["username"], "pass": account["password"]})
    restarted = Bot(live_worker, "new-character-restarted")
    state = restarted.login_via_lobby(auth, account["name"])
    assert state["territory"] == 182 and state["gm_rank"] == 0
    state = restarted.expect_rewards(expected, 1)
    restarted.start_uldah_opening()
    scene = live_worker.wait_state(restarted.name,
        lambda s: s["scene"] is not None and s["scene"]["event_id"] == 1245187,
        "restarted Ul'dah opening continuation")
    assert scene["scene"]["scene_id"] == 40
    restarted.choose_dialogue(catalog, "finish")
    restarted.wait_event_finished()
    restarted.logout()
    restarted.close()
    (environment.artifacts / "character-creation-opening.json").write_text(json.dumps({
        "character": account["name"], "created_via_lobby": True, "initial_territory": 182,
        "first_scenes": [0, 1], "scene_after_fresh_login": 40, "scene_after_restart": 40,
        "rewards_before": before, "rewards_after_restart": expected,
        "inventory_after_restart": inventory,
        "scope": "one canonical Gladiator created through lobby reserve/finalize, first Ul'dah opening branch and persisted continuation; not account signup UI or complete opening quest"
    }, indent=2), encoding="utf-8")

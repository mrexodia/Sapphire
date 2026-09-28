"""An authored quest journey. Requires the locally generated, validated route catalog."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import math
from pathlib import Path

import pytest
from .support.catalog import load_quest_catalog
from .support.worker import Bot

pytestmark = pytest.mark.live


def test_quest_cancel_complete_rewards_and_restart(environment, live_worker):
    path = environment.profile.get("quest_catalog")
    assert path, "quest suite requires profile.quest_catalog; generate a compatible local navigation catalog first"
    catalog = load_quest_catalog(path)
    quest = catalog["quest"]
    adapters = {65685: "due_diligence.json", 65686: "motivational_speaking.json"}
    scenes = json.loads((Path(__file__).parent / "scene_catalog" / adapters[quest]).read_text())
    assert scenes["quest_id"] == quest
    assert not catalog["optional_items"], "optional reward selection is not implemented in this scenario"
    assert catalog["class_job"] == 1
    if quest == 65686:
        # Independent authored expectation for this small known quest, not only a shared calculation.
        assert catalog["exp"] == 50 and catalog["gil"] == 0
        assert catalog["items"] == [{"id": 4551, "count": 2}]

    player_fixture = environment.fresh_character(catalog["route"][0])
    observer_fixture = environment.fresh_character(catalog["route"][0])
    player, observer = Bot(live_worker, "quester"), Bot(live_worker, "quest-observer")
    state = player.login_via_lobby(player_fixture["auth"], player_fixture["name"])
    observer.login_via_lobby(observer_fixture["auth"], observer_fixture["name"])
    actor = str(state["entity_id"])
    key = str(quest & 0xffff)
    assert key not in state["quests"] and not state["complete_quests"].get(key)
    assert math.dist(state["observed_position"], catalog["giver"]["position"]) <= 2
    before = player.reward_snapshot(catalog["work_index"])
    assert before["level"] == 1 and before["exp"] == 0

    # Cancellation must not grant acceptance, completion or rewards.
    player.interact(catalog["giver"]["layout_id"], quest)
    player.choose_dialogue(scenes, "cancel")
    state = player.wait_event_finished()
    assert key not in state["quests"] and not state["complete_quests"].get(key)
    assert player.reward_snapshot(catalog["work_index"]) == before

    player.interact(catalog["giver"]["layout_id"], quest)
    player.choose_dialogue(scenes, "accept")
    player.expect_quest_active(quest, sequence=255)
    player.wait_event_finished()

    # Both clients walk ordinary interpolated movement; the observer remains nearby.
    with ThreadPoolExecutor(max_workers=2) as pool:
        walks = [pool.submit(bot.walk_route, catalog["route"], 6.0, 180) for bot in (player, observer)]
        for walk in walks:
            walk.result(timeout=190)
    live_worker.wait_state(observer.name,
        lambda s: actor in s["actors"] and math.dist(s["actors"][actor]["position"], catalog["route"][-1]) < 0.15,
        "quester arrived as observed by a second client")
    assert math.dist(catalog["route"][-1], catalog["recipient"]["position"]) <= 2
    player.interact(catalog["recipient"]["layout_id"], quest)
    if quest == 65685:
        player.choose_dialogue(scenes, "hand_over")
    player.choose_dialogue(scenes, "complete_without_optional_item")
    player.expect_quest_complete(quest)
    state = player.wait_event_finished()
    assert key not in state["quests"]

    expected = deepcopy(before)
    expected["exp"] += catalog["exp"]
    for item in catalog["items"]:
        key_item = str(item["id"])
        expected["items"][key_item] = expected["items"].get(key_item, 0) + item["count"]
    if catalog["gil"]:
        expected["currencies"]["1"] = expected["currencies"].get("1", 0) + catalog["gil"]
    player.expect_rewards(expected, catalog["work_index"])

    player.logout()
    live_worker.wait_state(observer.name, lambda s: actor not in s["actors"], "quester session cleanup", timeout=30)
    observer.logout()
    player.close()
    observer.close()
    environment.restart_world()
    auth = environment.api("login", {"username": player_fixture["username"], "pass": player_fixture["password"]})
    reloaded = Bot(live_worker, "quest-reloaded")
    reloaded.login_via_lobby(auth, player_fixture["name"])
    reloaded.expect_quest_complete(quest)
    reloaded.expect_rewards(expected, catalog["work_index"])
    assert key not in live_worker.snapshot(reloaded.name)["quests"]
    reloaded.logout()
    reloaded.close()

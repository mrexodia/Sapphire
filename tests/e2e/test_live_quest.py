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


def walk_observed_route(worker, player, observer, actor, catalog):
    # Ordinary interpolated movement for both clients, keeping the observer nearby.
    with ThreadPoolExecutor(max_workers=2) as pool:
        walks = [pool.submit(bot.walk_route, catalog["route"], 6.0, 180) for bot in (player, observer)]
        for walk in walks:
            walk.result(timeout=190)
    worker.wait_state(observer.name,
        lambda s: actor in s["actors"] and math.dist(s["actors"][actor]["position"], catalog["route"][-1]) < 0.15,
        "quester arrived as observed by a second client")
    assert math.dist(catalog["route"][-1], catalog["recipient"]["position"]) <= 2


def complete_follow_up(environment, worker, player, observer, fixture, previous, before):
    path = environment.profile.get("follow_up_catalog")
    assert path, "quest chain requires profile.follow_up_catalog for quest 65687"
    state = worker.snapshot(player.name)
    completed = {int(key) | 0x10000 for key, value in state["complete_quests"].items() if value is True}
    catalog = load_quest_catalog(path, completed_quests=completed)
    assert catalog["quest"] == 65687 and catalog["previous_quests"] == [65686, 0, 0]
    assert catalog["class_job"] == previous["class_job"] == 1
    assert catalog["work_index"] == previous["work_index"]
    assert catalog["exp"] == 50 and catalog["gil"] == 0 and catalog["items"] == []
    assert catalog["optional_items"] == [{"id": 4551, "count": 3}, {"id": 4555, "count": 3}]
    # Shared giver/recipient must connect without teleporting or unverified bridging.
    assert math.dist(previous["route"][-1], catalog["route"][0]) < 0.01
    assert catalog["giver"]["layout_id"] == previous["recipient"]["layout_id"]
    scenes = json.loads((Path(__file__).parent / "scene_catalog" / "gil_for_gold.json").read_text())
    quest, key, actor = catalog["quest"], str(catalog["quest"] & 0xffff), str(state["entity_id"])
    assert key not in state["quests"] and not state["complete_quests"].get(key)
    player.interact(catalog["giver"]["layout_id"], quest)
    player.choose_dialogue(scenes, "cancel")
    state = player.wait_event_finished()
    assert key not in state["quests"] and not state["complete_quests"].get(key)
    assert player.reward_snapshot(catalog["work_index"]) == before
    player.interact(catalog["giver"]["layout_id"], quest)
    player.choose_dialogue(scenes, "accept")
    player.expect_quest_active(quest, sequence=255)
    player.wait_event_finished()

    # Reconnect while active: neither fixture edits nor optimistic acceptance count.
    player.logout()
    worker.wait_state(observer.name, lambda s: actor not in s["actors"], "active quest session cleanup", 30)
    player.close()
    auth = environment.api("login", {"username": fixture["username"], "pass": fixture["password"]})
    state = player.login_via_lobby(auth, fixture["name"])
    assert str(state["entity_id"]) == actor
    assert math.dist(state["observed_position"], catalog["route"][0]) < 0.15
    player.expect_quest_active(quest, sequence=255)
    player.expect_quest_complete(previous["quest"])
    player.expect_rewards(before, catalog["work_index"])
    walk_observed_route(worker, player, observer, actor, catalog)

    # Cancelling the hand-over triggers a separate acknowledgement scene, not success.
    player.interact(catalog["recipient"]["layout_id"], quest)
    player.choose_dialogue(scenes, "cancel")
    player.choose_dialogue(scenes, "acknowledge")
    state = player.wait_event_finished()
    assert not state["complete_quests"].get(key)
    player.expect_quest_active(quest, sequence=255)
    assert player.reward_snapshot(catalog["work_index"]) == before
    player.interact(catalog["recipient"]["layout_id"], quest)
    player.choose_dialogue(scenes, "hand_over")
    # This profile's completion result contains the chosen item ID, not an index.
    player.choose_dialogue(scenes, "complete_with_ether")
    player.expect_quest_complete(quest)
    state = player.wait_event_finished()
    assert key not in state["quests"]
    expected = deepcopy(before)
    expected["exp"] += 50
    expected["items"]["4555"] = expected["items"].get("4555", 0) + 3
    player.expect_rewards(expected, catalog["work_index"])
    return quest, expected


def discard_reward_and_verify_restart(environment, worker, player, fixture, expected, work_index, quests):
    state = worker.snapshot(player.name)
    inventory = deepcopy(state["rewards"]["inventory"])
    stacks = [(key, item) for key, item in inventory.items() if item["id"] == 4555 and item["storage"] in range(4)]
    assert len(stacks) == 1 and stacks[0][1]["count"] == 3
    key, item = stacks[0]
    actor = str(state["entity_id"])
    # Fresh independent observer for this lifecycle slice, not a player-state edit.
    observer_fixture = environment.fresh_character(state["observed_position"])
    observer = Bot(worker, "inventory-observer")
    observer.login_via_lobby(observer_fixture["auth"], observer_fixture["name"])
    worker.wait_state(observer.name, lambda s: actor in s["actors"], "inventory subject visible")
    state = player.discard_item(item["storage"], item["slot"], expected_item=4555)
    del inventory[key]
    assert state["rewards"]["inventory"] == inventory
    remaining = deepcopy(expected)
    del remaining["items"]["4555"]
    player.expect_rewards(remaining, work_index)
    player.logout()
    worker.wait_state(observer.name, lambda s: actor not in s["actors"], "inventory session cleanup", 30)
    player.close()
    observer.logout()
    observer.close()
    environment.restart_world()
    auth = environment.api("login", {"username": fixture["username"], "pass": fixture["password"]})
    reloaded = Bot(worker, "inventory-reloaded")
    reloaded.login_via_lobby(auth, fixture["name"])
    state = reloaded.expect_rewards(remaining, work_index)
    assert state["rewards"]["inventory"] == inventory
    for quest in quests:
        reloaded.expect_quest_complete(quest)
    return reloaded


@pytest.mark.parametrize("follow_up", [False, True], ids=["single", "chain"])
def test_quest_cancel_complete_rewards_and_restart(environment, live_worker, follow_up):
    if follow_up:
        assert environment.profile.get("follow_up_catalog"), "chain requires profile.follow_up_catalog for quest 65687"
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

    walk_observed_route(live_worker, player, observer, actor, catalog)
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
    completed_quests = [quest]
    if follow_up:
        next_quest, expected = complete_follow_up(environment, live_worker, player, observer,
                                                player_fixture, catalog, expected)
        completed_quests.append(next_quest)

    player.logout()
    live_worker.wait_state(observer.name, lambda s: actor not in s["actors"], "quester session cleanup", timeout=30)
    observer.logout()
    player.close()
    observer.close()
    environment.restart_world()
    auth = environment.api("login", {"username": player_fixture["username"], "pass": player_fixture["password"]})
    reloaded = Bot(live_worker, "quest-reloaded")
    reloaded.login_via_lobby(auth, player_fixture["name"])
    for completed_quest in completed_quests:
        reloaded.expect_quest_complete(completed_quest)
    reloaded.expect_rewards(expected, catalog["work_index"])
    state = live_worker.snapshot(reloaded.name)
    assert all(str(completed_quest & 0xffff) not in state["quests"] for completed_quest in completed_quests)
    if follow_up:
        reloaded = discard_reward_and_verify_restart(environment, live_worker, reloaded, player_fixture,
                                                    expected, catalog["work_index"], completed_quests)
    reloaded.logout()
    reloaded.close()

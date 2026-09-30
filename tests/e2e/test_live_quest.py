"""An authored quest journey. Requires the locally generated, validated route catalog."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import math
from pathlib import Path

import pytest
from .support.catalog import load_quest_catalog, load_shop_catalog
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


def move_reward_and_verify_reconnect(environment, worker, player, observer, fixture, expected, work_index, quests):
    state = player.expect_rewards(expected, work_index)
    before = deepcopy(state["rewards"]["inventory"])
    stacks = [(key, item) for key, item in before.items() if item["id"] == 4555 and item["storage"] in range(4)]
    assert len(stacks) == 1 and stacks[0][1]["count"] == 3
    source, item = stacks[0]
    destination = "3:24"
    assert source != destination and destination not in before
    assert state["rewards"]["containers"]["3"] is True
    actor = str(state["entity_id"])
    observed = worker.wait_state(observer.name, lambda s: actor in s["actors"], "inventory subject visible before move")
    position = observed["actors"][actor]["position"]
    expected_inventory = deepcopy(before)
    moved = expected_inventory.pop(source)
    moved.update(storage=3, slot=24)
    expected_inventory[destination] = moved
    receipt = player.request_item_move(item["storage"], item["slot"], 3, 24, expected_item=4555)
    assert receipt["acknowledged"] and receipt["inventory_change_verified"] is False
    # The current server sends only a pre-operation acknowledgement. Do not apply
    # this expected map to the worker or count that acknowledgement as a move.
    player.logout()
    worker.wait_state(observer.name, lambda s: actor not in s["actors"], "move session removed", 30)
    player.close()
    auth = environment.api("login", {"username": fixture["username"], "pass": fixture["password"]})
    state = player.login_via_lobby(auth, fixture["name"])
    assert str(state["entity_id"]) == actor and math.dist(state["observed_position"], position) < 0.15
    worker.wait_state(observer.name,
        lambda s: actor in s["actors"] and math.dist(s["actors"][actor]["position"], position) < 0.15,
        "moved-item character reconnect observed")
    state = player.expect_rewards(expected, work_index)
    assert state["rewards"]["inventory"] == expected_inventory
    for quest in quests:
        player.expect_quest_complete(quest)
    return expected_inventory, {"source": source, "destination": destination, "item": 4555, "count": 3,
        "receipt": receipt, "before": before, "after_reconnect": deepcopy(state["rewards"]["inventory"]),
        "scope": "earned whole stack to empty ordinary bag; no swap/split/merge/equipment claim"}


def swap_reward_and_verify_restart(environment, worker, player, fixture, expected, work_index, quests):
    state = player.expect_rewards(expected, work_index)
    before = deepcopy(state["rewards"]["inventory"])
    sources = [(key, item) for key, item in before.items()
               if item["id"] == 4555 and item["storage"] in range(4)]
    destinations = [(key, item) for key, item in sorted(before.items())
                    if item["id"] != 4555 and item["storage"] in range(4)]
    assert len(sources) == 1 and sources[0][1]["count"] == 3 and destinations
    source, source_item = sources[0]
    destination, destination_item = destinations[0]
    assert source != destination and source_item["id"] != destination_item["id"]
    expected_inventory = deepcopy(before)
    swapped_source = deepcopy(source_item)
    swapped_destination = deepcopy(destination_item)
    swapped_source.update(storage=destination_item["storage"], slot=destination_item["slot"])
    swapped_destination.update(storage=source_item["storage"], slot=source_item["slot"])
    expected_inventory[destination] = swapped_source
    expected_inventory[source] = swapped_destination
    entity = state["entity_id"]
    position = state["observed_position"]
    receipt = player.request_item_swap(source_item["storage"], source_item["slot"],
        destination_item["storage"], destination_item["slot"], source_item["id"], destination_item["id"])
    assert receipt["acknowledged"] and receipt["inventory_change_verified"] is False
    player.logout()
    player.close()
    environment.restart_world()
    auth = environment.api("login", {"username": fixture["username"], "pass": fixture["password"]})
    state = player.login_via_lobby(auth, fixture["name"])
    assert state["entity_id"] == entity and math.dist(state["observed_position"], position) < 0.15
    state = player.expect_rewards(expected, work_index)
    assert state["rewards"]["inventory"] == expected_inventory
    for quest in quests:
        player.expect_quest_complete(quest)
    evidence = {"source": source, "destination": destination,
        "source_item": source_item["id"], "destination_item": destination_item["id"],
        "receipt": receipt, "before": before,
        "after_restart": deepcopy(state["rewards"]["inventory"]),
        "scope": "two observed occupied ordinary bag slots; no equipment or arbitrary operation"}
    (environment.artifacts / "inventory-swap.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    return player, expected_inventory, evidence


def split_merge_reward_and_verify_restarts(environment, worker, player, fixture, expected, work_index, quests):
    state = player.expect_rewards(expected, work_index)
    before = deepcopy(state["rewards"]["inventory"])
    stacks = [(key, item) for key, item in before.items()
              if item["id"] == 4555 and item["storage"] in range(4)]
    assert len(stacks) == 1 and stacks[0][1]["count"] == 3
    source, item = stacks[0]
    empty = next((f"{storage}:{slot}" for storage in reversed(range(4)) for slot in reversed(range(25))
                  if f"{storage}:{slot}" not in before), None)
    assert empty is not None
    destination_storage, destination_slot = map(int, empty.split(":"))
    split_inventory = deepcopy(before)
    split_inventory[source]["count"] = 2
    split_inventory[empty] = {"storage": destination_storage, "slot": destination_slot,
                              "id": 4555, "count": 1}
    split_receipt = player.request_item_split(item["storage"], item["slot"],
        destination_storage, destination_slot, 4555, 3, 1)
    assert split_receipt["acknowledged"] and split_receipt["inventory_change_verified"] is False
    player.logout()
    player.close()
    environment.restart_world()
    auth = environment.api("login", {"username": fixture["username"], "pass": fixture["password"]})
    state = player.login_via_lobby(auth, fixture["name"])
    state = player.expect_rewards(expected, work_index)
    assert state["rewards"]["inventory"] == split_inventory
    for quest in quests:
        player.expect_quest_complete(quest)

    merge_receipt = player.request_item_merge(destination_storage, destination_slot,
        item["storage"], item["slot"], 4555, 1, 2)
    assert merge_receipt["acknowledged"] and merge_receipt["inventory_change_verified"] is False
    player.logout()
    player.close()
    environment.restart_world()
    auth = environment.api("login", {"username": fixture["username"], "pass": fixture["password"]})
    state = player.login_via_lobby(auth, fixture["name"])
    state = player.expect_rewards(expected, work_index)
    assert state["rewards"]["inventory"] == before
    for quest in quests:
        player.expect_quest_complete(quest)
    evidence = {"source": source, "destination": empty, "item": 4555,
        "split_receipt": split_receipt, "merge_receipt": merge_receipt, "before": before,
        "after_split_restart": split_inventory, "after_merge_restart": deepcopy(state["rewards"]["inventory"]),
        "scope": "partial 3-to-2+1 split and whole 1+2 merge in observed ordinary bag slots"}
    (environment.artifacts / "inventory-split-merge.json").write_text(
        json.dumps(evidence, indent=2), encoding="utf-8")
    return player, before, evidence


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


def sell_reward_and_verify_restart(environment, worker, player, fixture, work_index, quests):
    path = environment.profile.get("shop_catalog")
    assert path, "shop sale requires a source-bound private route catalog"
    catalog = load_shop_catalog(path)
    state = worker.snapshot(player.name)
    assert state["territory"] == 130 and math.dist(state["observed_position"], catalog["route"][0]) < 0.15
    before_rewards = player.reward_snapshot(work_index)
    before_inventory = deepcopy(state["rewards"]["inventory"])
    stacks = [(key, item) for key, item in before_inventory.items()
              if item["id"] == catalog["sale"]["item"] and item["storage"] in range(4)]
    assert len(stacks) == 1 and stacks[0][1]["count"] == 2
    source, item = stacks[0]
    empty = next((f"{storage}:{slot}" for storage in reversed(range(4)) for slot in reversed(range(25))
                  if f"{storage}:{slot}" not in before_inventory), None)
    assert empty is not None
    destination_storage, destination_slot = map(int, empty.split(":"))
    split_inventory = deepcopy(before_inventory)
    split_inventory[source]["count"] = 1
    split_inventory[empty] = {"storage": destination_storage, "slot": destination_slot,
                              "id": catalog["sale"]["item"], "count": 1}
    receipt = player.request_item_split(item["storage"], item["slot"], destination_storage,
        destination_slot, catalog["sale"]["item"], 2, 1)
    assert receipt["acknowledged"] and receipt["inventory_change_verified"] is False
    player.logout()
    player.close()
    environment.restart_world()
    auth = environment.api("login", {"username": fixture["username"], "pass": fixture["password"]})
    state = player.login_via_lobby(auth, fixture["name"])
    state = player.expect_rewards(before_rewards, work_index)
    assert state["rewards"]["inventory"] == split_inventory

    observer_fixture = environment.fresh_character(catalog["route"][-1])
    observer = Bot(worker, "shop-observer")
    observer.login_via_lobby(observer_fixture["auth"], observer_fixture["name"])
    actor = str(state["entity_id"])
    player.walk_route(catalog["route"], 6.0, 180)
    worker.wait_state(observer.name,
        lambda s: actor in s["actors"] and math.dist(s["actors"][actor]["position"], catalog["route"][-1]) < 0.15,
        "shop arrival observed by independent client", 30)
    assert math.dist(catalog["route"][-1], catalog["shop"]["position"]) <= 2
    player.open_gil_shop(catalog["shop"]["layout_id"], catalog["shop"]["event_id"])
    player.sell_shop_item(destination_storage, destination_slot, catalog["sale"]["item"])
    after_rewards = deepcopy(before_rewards)
    after_rewards["items"][str(catalog["sale"]["item"])] -= 1
    after_rewards["currencies"]["1"] = after_rewards["currencies"].get("1", 0) + catalog["sale"]["gil"]
    state = player.expect_rewards(after_rewards, work_index)
    sold_inventory = deepcopy(split_inventory)
    del sold_inventory[empty]
    sold_inventory["2000:0"] = {"storage": 2000, "slot": 0, "id": 1,
                                "count": catalog["sale"]["gil"]}
    assert state["rewards"]["inventory"] == sold_inventory

    player.buy_shop_item(catalog["shop"]["event_id"])
    purchased_rewards = deepcopy(after_rewards)
    purchased_rewards["items"][str(catalog["purchase"]["item"])] = catalog["purchase"]["quantity"]
    purchased_rewards["currencies"]["1"] -= catalog["purchase"]["gil"]
    state = player.expect_rewards(purchased_rewards, work_index)
    purchased_inventory = deepcopy(state["rewards"]["inventory"])
    expected_existing = deepcopy(sold_inventory)
    expected_existing["2000:0"]["count"] = purchased_rewards["currencies"]["1"]
    added = set(purchased_inventory) - set(expected_existing)
    assert len(added) == 1
    added_key = next(iter(added))
    assert purchased_inventory[added_key]["id"] == catalog["purchase"]["item"]
    assert purchased_inventory[added_key]["count"] == catalog["purchase"]["quantity"]
    assert {key: value for key, value in purchased_inventory.items() if key != added_key} == expected_existing
    player.exit_gil_shop(catalog["shop"]["event_id"])
    item_storage, item_slot = map(int, added_key.split(":"))
    used_state, used_effect, request = player.use_shop_vfx_item(item_storage, item_slot)
    assert request > 0
    assert used_effect == {"source": state["entity_id"], "target": state["entity_id"],
                           "action": catalog["purchase"]["item"], "kind": 1,
                           "request": 0, "result": 0,
                           "effects": [{"type": 54,
                                        "value": catalog["purchase"]["item_action"]["arg"],
                                        "flag": 0, "args": [0, 0, 0]}],
                           "source_effects": []}
    observer_effect = worker.wait_state(observer.name,
        lambda s: used_effect in s["combat"]["effects"],
        "independently received exact shop VFX item effect")
    assert observer_effect["phase"] == "ready" and observer_effect["gm_rank"] == 0
    unchanged = player.expect_rewards(purchased_rewards, work_index)
    assert unchanged["rewards"]["inventory"] == purchased_inventory
    for quest in quests:
        player.expect_quest_complete(quest)
    player.logout()
    worker.wait_state(observer.name, lambda s: actor not in s["actors"], "shopper session cleanup", 30)
    player.close()
    observer.logout()
    observer.close()
    environment.restart_world()
    auth = environment.api("login", {"username": fixture["username"], "pass": fixture["password"]})
    reloaded = Bot(worker, "shop-reloaded")
    state = reloaded.login_via_lobby(auth, fixture["name"])
    state = reloaded.expect_rewards(purchased_rewards, work_index)
    assert state["rewards"]["inventory"] == purchased_inventory
    for quest in quests:
        reloaded.expect_quest_complete(quest)

    def restart_shop_bot(bot, name, expected_rewards, expected_inventory):
        bot.logout()
        bot.close()
        environment.restart_world()
        auth = environment.api("login", {"username": fixture["username"], "pass": fixture["password"]})
        result = Bot(worker, name)
        state = result.login_via_lobby(auth, fixture["name"])
        state = result.expect_rewards(expected_rewards, work_index)
        assert state["rewards"]["inventory"] == expected_inventory
        for completed in quests:
            result.expect_quest_complete(completed)
        return result, state

    # The VFX stack must first survive a restart unchanged. Split it into three
    # exact one-item stacks, proving each operation only through a subsequent login.
    first_empty = next(key for key in (f"{storage}:{slot}" for storage in reversed(range(4))
                                       for slot in reversed(range(25)))
                       if key not in purchased_inventory)
    first_storage, first_slot = map(int, first_empty.split(":"))
    first_split = reloaded.request_item_split(item_storage, item_slot, first_storage, first_slot,
                                               catalog["purchase"]["item"], 3, 1)
    first_split_inventory = deepcopy(purchased_inventory)
    first_split_inventory[added_key]["count"] = 2
    first_split_inventory[first_empty] = {"storage": first_storage, "slot": first_slot,
                                          "id": catalog["purchase"]["item"], "count": 1}
    reloaded, state = restart_shop_bot(reloaded, "shop-stack-reloaded-1",
                                      purchased_rewards, first_split_inventory)
    second_empty = next(key for key in (f"{storage}:{slot}" for storage in reversed(range(4))
                                        for slot in reversed(range(25)))
                        if key not in first_split_inventory)
    second_storage, second_slot = map(int, second_empty.split(":"))
    second_split = reloaded.request_item_split(item_storage, item_slot, second_storage, second_slot,
                                                catalog["purchase"]["item"], 2, 1)
    sale_inventory = deepcopy(first_split_inventory)
    sale_inventory[added_key]["count"] = 1
    sale_inventory[second_empty] = {"storage": second_storage, "slot": second_slot,
                                    "id": catalog["purchase"]["item"], "count": 1}
    reloaded, state = restart_shop_bot(reloaded, "shop-stack-reloaded-2",
                                      purchased_rewards, sale_inventory)

    reloaded.open_gil_shop(catalog["shop"]["layout_id"], catalog["shop"]["event_id"])
    liquidation_rewards = deepcopy(purchased_rewards)
    liquidation_inventory = deepcopy(sale_inventory)
    vfx_stacks = [(key, item) for key, item in liquidation_inventory.items()
                  if item["id"] == catalog["purchase"]["item"] and item["storage"] in range(4)]
    assert len(vfx_stacks) == 3 and all(item["count"] == 1 for _, item in vfx_stacks)
    for key, item in vfx_stacks:
        reloaded.sell_shop_item(item["storage"], item["slot"], item["id"])
        liquidation_rewards["items"][str(item["id"])] -= 1
        if liquidation_rewards["items"][str(item["id"])] == 0:
            del liquidation_rewards["items"][str(item["id"])]
        liquidation_rewards["currencies"]["1"] += catalog["purchase"]["unit_gil"]
        del liquidation_inventory[key]
        liquidation_inventory["2000:0"]["count"] = liquidation_rewards["currencies"]["1"]
        state = reloaded.expect_rewards(liquidation_rewards, work_index)
        assert state["rewards"]["inventory"] == liquidation_inventory
    potion_stacks = [(key, item) for key, item in liquidation_inventory.items()
                     if item["id"] == catalog["sale"]["item"] and item["storage"] in range(4)]
    assert len(potion_stacks) == 1 and potion_stacks[0][1]["count"] == 1
    potion_key, potion = potion_stacks[0]
    reloaded.sell_shop_item(potion["storage"], potion["slot"], potion["id"])
    del liquidation_rewards["items"][str(potion["id"])]
    liquidation_rewards["currencies"]["1"] += catalog["sale"]["gil"]
    del liquidation_inventory[potion_key]
    liquidation_inventory["2000:0"]["count"] = liquidation_rewards["currencies"]["1"]
    state = reloaded.expect_rewards(liquidation_rewards, work_index)
    assert state["rewards"]["inventory"] == liquidation_inventory
    assert liquidation_rewards["currencies"]["1"] == 56

    reloaded.buy_shop_equipment(catalog["shop"]["event_id"])
    equipment_rewards = deepcopy(liquidation_rewards)
    equipment_rewards["items"][str(catalog["equipment_purchase"]["item"])] = 1
    equipment_rewards["currencies"]["1"] -= catalog["equipment_purchase"]["gil"]
    state = reloaded.expect_rewards(equipment_rewards, work_index)
    equipment_inventory = deepcopy(state["rewards"]["inventory"])
    expected_before_equipment = deepcopy(liquidation_inventory)
    expected_before_equipment["2000:0"]["count"] = equipment_rewards["currencies"]["1"]
    equipment_added = set(equipment_inventory) - set(expected_before_equipment)
    assert len(equipment_added) == 1
    equipment_key = next(iter(equipment_added))
    assert equipment_inventory[equipment_key]["id"] == catalog["equipment_purchase"]["item"]
    assert equipment_inventory[equipment_key]["count"] == 1
    assert {key: value for key, value in equipment_inventory.items() if key != equipment_key} == expected_before_equipment
    reloaded.exit_gil_shop(catalog["shop"]["event_id"])
    reloaded, state = restart_shop_bot(reloaded, "shop-equipment-reloaded",
                                      equipment_rewards, equipment_inventory)

    gear_slot = catalog["equipment_purchase"]["gear_slot"]
    starter_key = f"1000:{gear_slot}"
    assert equipment_inventory[starter_key] == {"storage": 1000, "slot": gear_slot,
                                                "id": 3296, "count": 1}
    gear_empty = next(key for key in (f"{storage}:{slot}" for storage in reversed(range(4))
                                      for slot in reversed(range(25)))
                      if key not in equipment_inventory)
    gear_empty_storage, gear_empty_slot = map(int, gear_empty.split(":"))
    unequip_receipt = reloaded.request_item_unequip(gear_slot, gear_empty_storage,
                                                     gear_empty_slot, 3296)
    unequipped_inventory = deepcopy(equipment_inventory)
    del unequipped_inventory[starter_key]
    unequipped_inventory[gear_empty] = {"storage": gear_empty_storage, "slot": gear_empty_slot,
                                        "id": 3296, "count": 1}
    unequipped_rewards = deepcopy(equipment_rewards)
    unequipped_rewards["items"]["3296"] = 1
    reloaded, state = restart_shop_bot(reloaded, "shop-gear-empty-reloaded",
                                      unequipped_rewards, unequipped_inventory)
    purchased_item = unequipped_inventory[equipment_key]
    equip_receipt = reloaded.request_shop_item_equip(purchased_item["storage"], purchased_item["slot"],
                                                      catalog["equipment_purchase"]["item"], gear_slot)
    equipped_inventory = deepcopy(unequipped_inventory)
    del equipped_inventory[equipment_key]
    equipped_inventory[starter_key] = {"storage": 1000, "slot": gear_slot,
                                        "id": catalog["equipment_purchase"]["item"], "count": 1}
    equipped_rewards = deepcopy(unequipped_rewards)
    del equipped_rewards["items"][str(catalog["equipment_purchase"]["item"])]
    reloaded, state = restart_shop_bot(reloaded, "shop-gear-equipped-reloaded",
                                      equipped_rewards, equipped_inventory)

    leg_sale_key = next(key for key in (f"{storage}:{slot}" for storage in reversed(range(4))
                                        for slot in reversed(range(25)))
                        if key not in equipped_inventory)
    leg_sale_storage, leg_sale_slot = map(int, leg_sale_key.split(":"))
    leg_unequip_receipt = reloaded.request_item_unequip(
        gear_slot, leg_sale_storage, leg_sale_slot, catalog["equipment_purchase"]["item"])
    leg_sale_inventory = deepcopy(equipped_inventory)
    del leg_sale_inventory[starter_key]
    leg_sale_inventory[leg_sale_key] = {"storage": leg_sale_storage, "slot": leg_sale_slot,
                                        "id": catalog["equipment_purchase"]["item"], "count": 1}
    leg_sale_rewards = deepcopy(equipped_rewards)
    leg_sale_rewards["items"][str(catalog["equipment_purchase"]["item"])] = 1
    reloaded, state = restart_shop_bot(reloaded, "shop-purchased-leg-unequipped",
                                      leg_sale_rewards, leg_sale_inventory)
    reloaded.open_gil_shop(catalog["shop"]["layout_id"], catalog["shop"]["event_id"])
    reloaded.sell_shop_item(leg_sale_storage, leg_sale_slot,
                            catalog["equipment_purchase"]["item"])
    resale_rewards = deepcopy(leg_sale_rewards)
    del resale_rewards["items"][str(catalog["equipment_purchase"]["item"])]
    resale_rewards["currencies"]["1"] += catalog["equipment_purchase"]["resale_gil"]
    resale_inventory = deepcopy(leg_sale_inventory)
    del resale_inventory[leg_sale_key]
    resale_inventory["2000:0"]["count"] = resale_rewards["currencies"]["1"]
    state = reloaded.expect_rewards(resale_rewards, work_index)
    assert state["rewards"]["inventory"] == resale_inventory
    reloaded, state = restart_shop_bot(reloaded, "shop-purchased-leg-sold",
                                      resale_rewards, resale_inventory)
    assert resale_rewards["currencies"]["1"] == 56

    second = catalog["second_equipment_purchase"]
    reloaded.open_gil_shop(catalog["shop"]["layout_id"], catalog["shop"]["event_id"])
    reloaded.buy_shop_second_equipment(catalog["shop"]["event_id"])
    second_rewards = deepcopy(resale_rewards)
    second_rewards["items"][str(second["item"])] = 1
    second_rewards["currencies"]["1"] -= second["gil"]
    state = reloaded.expect_rewards(second_rewards, work_index)
    second_inventory = deepcopy(state["rewards"]["inventory"])
    second_expected = deepcopy(resale_inventory)
    second_expected["2000:0"]["count"] = second_rewards["currencies"]["1"]
    second_added = set(second_inventory) - set(second_expected)
    assert len(second_added) == 1
    second_key = next(iter(second_added))
    assert second_inventory[second_key]["id"] == second["item"]
    assert second_inventory[second_key]["count"] == 1
    assert {key: value for key, value in second_inventory.items() if key != second_key} == second_expected
    reloaded.exit_gil_shop(catalog["shop"]["event_id"])
    reloaded, state = restart_shop_bot(reloaded, "shop-second-equipment-purchased",
                                      second_rewards, second_inventory)

    second_gear_key = f"1000:{second['gear_slot']}"
    assert second_inventory[second_gear_key] == {"storage": 1000, "slot": second["gear_slot"],
                                                 "id": 3750, "count": 1}
    second_empty = next(key for key in (f"{storage}:{slot}" for storage in reversed(range(4))
                                        for slot in reversed(range(25)))
                        if key not in second_inventory)
    second_empty_storage, second_empty_slot = map(int, second_empty.split(":"))
    second_unequip_receipt = reloaded.request_item_unequip(
        second["gear_slot"], second_empty_storage, second_empty_slot, 3750)
    second_unequipped_inventory = deepcopy(second_inventory)
    del second_unequipped_inventory[second_gear_key]
    second_unequipped_inventory[second_empty] = {
        "storage": second_empty_storage, "slot": second_empty_slot, "id": 3750, "count": 1}
    second_unequipped_rewards = deepcopy(second_rewards)
    second_unequipped_rewards["items"]["3750"] = 1
    reloaded, state = restart_shop_bot(reloaded, "shop-second-gear-empty",
                                      second_unequipped_rewards, second_unequipped_inventory)
    second_item = second_unequipped_inventory[second_key]
    second_equip_receipt = reloaded.request_shop_item_equip(
        second_item["storage"], second_item["slot"], second["item"], second["gear_slot"])
    final_inventory = deepcopy(second_unequipped_inventory)
    del final_inventory[second_key]
    final_inventory[second_gear_key] = {"storage": 1000, "slot": second["gear_slot"],
                                        "id": second["item"], "count": 1}
    final_rewards = deepcopy(second_unequipped_rewards)
    del final_rewards["items"][str(second["item"])]
    reloaded, state = restart_shop_bot(reloaded, "shop-second-gear-equipped",
                                      final_rewards, final_inventory)

    feet_sale_key = next(key for key in (f"{storage}:{slot}" for storage in reversed(range(4))
                                         for slot in reversed(range(25)))
                         if key not in final_inventory)
    feet_sale_storage, feet_sale_slot = map(int, feet_sale_key.split(":"))
    feet_unequip_receipt = reloaded.request_item_unequip(
        second["gear_slot"], feet_sale_storage, feet_sale_slot, second["item"])
    feet_sale_inventory = deepcopy(final_inventory)
    del feet_sale_inventory[second_gear_key]
    feet_sale_inventory[feet_sale_key] = {"storage": feet_sale_storage, "slot": feet_sale_slot,
                                          "id": second["item"], "count": 1}
    feet_sale_rewards = deepcopy(final_rewards)
    feet_sale_rewards["items"][str(second["item"])] = 1
    reloaded, state = restart_shop_bot(reloaded, "shop-purchased-feet-unequipped",
                                      feet_sale_rewards, feet_sale_inventory)
    reloaded.open_gil_shop(catalog["shop"]["layout_id"], catalog["shop"]["event_id"])
    reloaded.sell_shop_item(feet_sale_storage, feet_sale_slot, second["item"])
    feet_resale_rewards = deepcopy(feet_sale_rewards)
    del feet_resale_rewards["items"][str(second["item"])]
    feet_resale_rewards["currencies"]["1"] += second["resale_gil"]
    feet_resale_inventory = deepcopy(feet_sale_inventory)
    del feet_resale_inventory[feet_sale_key]
    feet_resale_inventory["2000:0"]["count"] = feet_resale_rewards["currencies"]["1"]
    state = reloaded.expect_rewards(feet_resale_rewards, work_index)
    assert state["rewards"]["inventory"] == feet_resale_inventory
    reloaded, state = restart_shop_bot(reloaded, "shop-purchased-feet-sold",
                                      feet_resale_rewards, feet_resale_inventory)
    assert feet_resale_rewards["currencies"]["1"] == 56

    starter_sale = catalog["starter_liquidation"]
    starter_sale_matches = [(key, item) for key, item in feet_resale_inventory.items()
                            if item["storage"] in range(4) and item["id"] == starter_sale["item"]]
    assert len(starter_sale_matches) == 1 and starter_sale_matches[0][1]["count"] == 1
    starter_sale_key, starter_sale_item = starter_sale_matches[0]
    reloaded.open_gil_shop(catalog["shop"]["layout_id"], catalog["shop"]["event_id"])
    reloaded.sell_shop_item(starter_sale_item["storage"], starter_sale_item["slot"],
                            starter_sale["item"])
    third_funds_rewards = deepcopy(feet_resale_rewards)
    del third_funds_rewards["items"][str(starter_sale["item"])]
    third_funds_rewards["currencies"]["1"] += starter_sale["gil"]
    third_funds_inventory = deepcopy(feet_resale_inventory)
    del third_funds_inventory[starter_sale_key]
    third_funds_inventory["2000:0"]["count"] = third_funds_rewards["currencies"]["1"]
    state = reloaded.expect_rewards(third_funds_rewards, work_index)
    assert state["rewards"]["inventory"] == third_funds_inventory
    reloaded, state = restart_shop_bot(reloaded, "shop-starter-leg-sold",
                                      third_funds_rewards, third_funds_inventory)
    assert third_funds_rewards["currencies"]["1"] == 101

    third = catalog["third_equipment_purchase"]
    reloaded.open_gil_shop(catalog["shop"]["layout_id"], catalog["shop"]["event_id"])
    reloaded.buy_shop_third_equipment(catalog["shop"]["event_id"])
    third_rewards = deepcopy(third_funds_rewards)
    third_rewards["items"][str(third["item"])] = 1
    third_rewards["currencies"]["1"] -= third["gil"]
    state = reloaded.expect_rewards(third_rewards, work_index)
    third_inventory = deepcopy(state["rewards"]["inventory"])
    third_expected = deepcopy(third_funds_inventory)
    third_expected["2000:0"]["count"] = third_rewards["currencies"]["1"]
    third_added = set(third_inventory) - set(third_expected)
    assert len(third_added) == 1
    third_key = next(iter(third_added))
    assert third_inventory[third_key]["id"] == third["item"]
    assert third_inventory[third_key]["count"] == 1
    assert {key: value for key, value in third_inventory.items() if key != third_key} == third_expected
    reloaded.exit_gil_shop(catalog["shop"]["event_id"])
    reloaded, state = restart_shop_bot(reloaded, "shop-third-equipment-purchased",
                                      third_rewards, third_inventory)

    third_gear_key = f"1000:{third['gear_slot']}"
    assert third_inventory[third_gear_key] == {"storage": 1000, "slot": third["gear_slot"],
                                               "id": 2983, "count": 1}
    third_empty = next(key for key in (f"{storage}:{slot}" for storage in reversed(range(4))
                                       for slot in reversed(range(25)))
                       if key not in third_inventory)
    third_empty_storage, third_empty_slot = map(int, third_empty.split(":"))
    third_unequip_receipt = reloaded.request_item_unequip(
        third["gear_slot"], third_empty_storage, third_empty_slot, 2983)
    third_unequipped_inventory = deepcopy(third_inventory)
    del third_unequipped_inventory[third_gear_key]
    third_unequipped_inventory[third_empty] = {
        "storage": third_empty_storage, "slot": third_empty_slot, "id": 2983, "count": 1}
    third_unequipped_rewards = deepcopy(third_rewards)
    third_unequipped_rewards["items"]["2983"] = 1
    reloaded, state = restart_shop_bot(reloaded, "shop-third-gear-empty",
                                      third_unequipped_rewards, third_unequipped_inventory)
    third_item = third_unequipped_inventory[third_key]
    third_equip_receipt = reloaded.request_shop_item_equip(
        third_item["storage"], third_item["slot"], third["item"], third["gear_slot"])
    third_final_inventory = deepcopy(third_unequipped_inventory)
    del third_final_inventory[third_key]
    third_final_inventory[third_gear_key] = {"storage": 1000, "slot": third["gear_slot"],
                                             "id": third["item"], "count": 1}
    third_final_rewards = deepcopy(third_unequipped_rewards)
    del third_final_rewards["items"][str(third["item"])]
    reloaded, state = restart_shop_bot(reloaded, "shop-third-gear-equipped",
                                      third_final_rewards, third_final_inventory)
    currency_move_receipt = reloaded.request_currency_move_rejection(
        third_final_rewards["currencies"]["1"])
    reloaded, state = restart_shop_bot(reloaded, "shop-currency-move-rejected",
                                      third_final_rewards, third_final_inventory)
    currency_move_receipt["rejection_verified_after_restart"] = True

    starter_body_sale = catalog["starter_body_liquidation"]
    starter_body_matches = [(key, item) for key, item in third_final_inventory.items()
                            if item["storage"] in range(4) and item["id"] == starter_body_sale["item"]]
    assert len(starter_body_matches) == 1 and starter_body_matches[0][1]["count"] == 1
    starter_body_key, starter_body_item = starter_body_matches[0]
    reloaded.open_gil_shop(catalog["shop"]["layout_id"], catalog["shop"]["event_id"])
    reloaded.sell_shop_item(starter_body_item["storage"], starter_body_item["slot"],
                            starter_body_sale["item"])
    head_funds_rewards = deepcopy(third_final_rewards)
    del head_funds_rewards["items"][str(starter_body_sale["item"])]
    head_funds_rewards["currencies"]["1"] += starter_body_sale["gil"]
    head_funds_inventory = deepcopy(third_final_inventory)
    del head_funds_inventory[starter_body_key]
    head_funds_inventory["2000:0"]["count"] = head_funds_rewards["currencies"]["1"]
    state = reloaded.expect_rewards(head_funds_rewards, work_index)
    assert state["rewards"]["inventory"] == head_funds_inventory
    reloaded, state = restart_shop_bot(reloaded, "shop-starter-body-sold",
                                      head_funds_rewards, head_funds_inventory)
    assert head_funds_rewards["currencies"]["1"] == 101

    head = catalog["head_purchase"]
    head_observer_fixture = environment.fresh_character(head["route"][-1])
    head_observer = Bot(worker, "head-shop-observer")
    head_observer.login_via_lobby(head_observer_fixture["auth"], head_observer_fixture["name"])
    actor = str(state["entity_id"])
    reloaded.walk_route(head["route"], 6.0, 90)
    head_arrival = worker.wait_state(head_observer.name,
        lambda s: actor in s["actors"]
                  and math.dist(s["actors"][actor]["position"], head["route"][-1]) < 0.15,
        "head-shop arrival independently observed", 30)
    head_observer.logout()
    head_observer.close()
    reloaded.open_gil_shop(head["shop"]["layout_id"], head["shop"]["event_id"])
    reloaded.buy_shop_head_equipment(head["shop"]["event_id"])
    head_rewards = deepcopy(head_funds_rewards)
    head_rewards["items"][str(head["item"])] = 1
    head_rewards["currencies"]["1"] -= head["gil"]
    state = reloaded.expect_rewards(head_rewards, work_index)
    head_inventory = deepcopy(state["rewards"]["inventory"])
    head_expected = deepcopy(head_funds_inventory)
    head_expected["2000:0"]["count"] = head_rewards["currencies"]["1"]
    head_added = set(head_inventory) - set(head_expected)
    assert len(head_added) == 1
    head_key = next(iter(head_added))
    assert head_inventory[head_key]["id"] == head["item"] and head_inventory[head_key]["count"] == 1
    assert {key: value for key, value in head_inventory.items() if key != head_key} == head_expected
    reloaded.exit_gil_shop(head["shop"]["event_id"])
    reloaded, state = restart_shop_bot(reloaded, "shop-head-equipment-purchased",
                                      head_rewards, head_inventory)
    head_gear_key = f"1000:{head['gear_slot']}"
    assert head_gear_key not in head_inventory
    head_item = head_inventory[head_key]
    head_equip_receipt = reloaded.request_shop_item_equip(
        head_item["storage"], head_item["slot"], head["item"], head["gear_slot"])
    head_final_inventory = deepcopy(head_inventory)
    del head_final_inventory[head_key]
    head_final_inventory[head_gear_key] = {"storage": 1000, "slot": head["gear_slot"],
                                           "id": head["item"], "count": 1}
    head_final_rewards = deepcopy(head_rewards)
    del head_final_rewards["items"][str(head["item"])]
    reloaded, state = restart_shop_bot(reloaded, "shop-head-equipment-equipped",
                                      head_final_rewards, head_final_inventory)

    starter_feet_sale = catalog["starter_feet_liquidation"]
    starter_feet_matches = [(key, item) for key, item in head_final_inventory.items()
                            if item["storage"] in range(4) and item["id"] == starter_feet_sale["item"]]
    assert len(starter_feet_matches) == 1 and starter_feet_matches[0][1]["count"] == 1
    starter_feet_key, starter_feet_item = starter_feet_matches[0]
    reloaded.open_gil_shop(head["shop"]["layout_id"], head["shop"]["event_id"])
    reloaded.sell_shop_item(starter_feet_item["storage"], starter_feet_item["slot"],
                            starter_feet_sale["item"])
    ear_funds_rewards = deepcopy(head_final_rewards)
    del ear_funds_rewards["items"][str(starter_feet_sale["item"])]
    ear_funds_rewards["currencies"]["1"] += starter_feet_sale["gil"]
    ear_funds_inventory = deepcopy(head_final_inventory)
    del ear_funds_inventory[starter_feet_key]
    ear_funds_inventory["2000:0"]["count"] = ear_funds_rewards["currencies"]["1"]
    state = reloaded.expect_rewards(ear_funds_rewards, work_index)
    assert state["rewards"]["inventory"] == ear_funds_inventory
    reloaded, state = restart_shop_bot(reloaded, "shop-starter-feet-sold",
                                      ear_funds_rewards, ear_funds_inventory)
    assert ear_funds_rewards["currencies"]["1"] == 102

    ear = catalog["ear_purchase"]
    ear_observer_fixture = environment.fresh_character(ear["route"][-1])
    ear_observer = Bot(worker, "ear-shop-observer")
    ear_observer.login_via_lobby(ear_observer_fixture["auth"], ear_observer_fixture["name"])
    actor = str(state["entity_id"])
    reloaded.walk_route(ear["route"], 6.0, 90)
    ear_arrival = worker.wait_state(ear_observer.name,
        lambda s: actor in s["actors"]
                  and math.dist(s["actors"][actor]["position"], ear["route"][-1]) < 0.15,
        "ear-shop arrival independently observed", 30)
    ear_observer.logout()
    ear_observer.close()
    reloaded.open_gil_shop(ear["shop"]["layout_id"], ear["shop"]["event_id"])
    reloaded.buy_shop_ear_equipment(ear["shop"]["event_id"])
    ear_rewards = deepcopy(ear_funds_rewards)
    ear_rewards["items"][str(ear["item"])] = 1
    ear_rewards["currencies"]["1"] -= ear["gil"]
    state = reloaded.expect_rewards(ear_rewards, work_index)
    ear_inventory = deepcopy(state["rewards"]["inventory"])
    ear_expected = deepcopy(ear_funds_inventory)
    ear_expected["2000:0"]["count"] = ear_rewards["currencies"]["1"]
    ear_added = set(ear_inventory) - set(ear_expected)
    assert len(ear_added) == 1
    ear_key = next(iter(ear_added))
    assert ear_inventory[ear_key]["id"] == ear["item"] and ear_inventory[ear_key]["count"] == 1
    assert {key: value for key, value in ear_inventory.items() if key != ear_key} == ear_expected
    reloaded.exit_gil_shop(ear["shop"]["event_id"])
    reloaded, state = restart_shop_bot(reloaded, "shop-ear-equipment-purchased",
                                      ear_rewards, ear_inventory)
    ear_gear_key = f"1000:{ear['gear_slot']}"
    assert ear_gear_key not in ear_inventory
    ear_item = ear_inventory[ear_key]
    ear_equip_receipt = reloaded.request_shop_item_equip(
        ear_item["storage"], ear_item["slot"], ear["item"], ear["gear_slot"])
    ear_final_inventory = deepcopy(ear_inventory)
    del ear_final_inventory[ear_key]
    ear_final_inventory[ear_gear_key] = {"storage": 1000, "slot": ear["gear_slot"],
                                         "id": ear["item"], "count": 1}
    ear_final_rewards = deepcopy(ear_rewards)
    del ear_final_rewards["items"][str(ear["item"])]
    reloaded, state = restart_shop_bot(reloaded, "shop-ear-equipment-equipped",
                                      ear_final_rewards, ear_final_inventory)

    liquidation_rewards = deepcopy(ear_final_rewards)
    liquidation_inventory = deepcopy(ear_final_inventory)
    liquidation_receipts = []
    liquidation_sources = [
        (ear["gear_slot"], ear["item"], ear["gil"], 24),
        (head["gear_slot"], head["item"], head["gil"], 23),
        (third["gear_slot"], third["item"], third["gil"], 22),
    ]
    for gear_slot, item_id, _, destination_slot in liquidation_sources:
        receipt = reloaded.request_item_unequip(gear_slot, 1, destination_slot, item_id)
        liquidation_receipts.append(receipt)
        liquidation_rewards["items"][str(item_id)] = 1
        del liquidation_inventory[f"1000:{gear_slot}"]
        liquidation_inventory[f"1:{destination_slot}"] = {
            "storage": 1, "slot": destination_slot, "id": item_id, "count": 1}
        reloaded, state = restart_shop_bot(
            reloaded, f"shop-liquidation-unequipped-{gear_slot}",
            liquidation_rewards, liquidation_inventory)

    reloaded.open_gil_shop(ear["shop"]["layout_id"], ear["shop"]["event_id"])
    for _, item_id, sale_gil, destination_slot in liquidation_sources:
        reloaded.sell_shop_item(1, destination_slot, item_id)
        del liquidation_rewards["items"][str(item_id)]
        liquidation_rewards["currencies"]["1"] += sale_gil
        del liquidation_inventory[f"1:{destination_slot}"]
        liquidation_inventory["2000:0"]["count"] = liquidation_rewards["currencies"]["1"]
        state = reloaded.expect_rewards(liquidation_rewards, work_index)
        assert state["rewards"]["inventory"] == liquidation_inventory
    reloaded, state = restart_shop_bot(reloaded, "shop-later-equipment-sold",
                                      liquidation_rewards, liquidation_inventory)
    assert liquidation_rewards["currencies"]["1"] == 208

    neck = catalog["neck_purchase"]
    neck_observer_fixture = environment.fresh_character(neck["route"][-1])
    neck_observer = Bot(worker, "neck-shop-observer")
    neck_observer.login_via_lobby(neck_observer_fixture["auth"], neck_observer_fixture["name"])
    actor = str(state["entity_id"])
    reloaded.walk_route(neck["route"], 6.0, 60)
    neck_arrival = worker.wait_state(neck_observer.name,
        lambda s: actor in s["actors"]
                  and math.dist(s["actors"][actor]["position"], neck["route"][-1]) < 0.15,
        "neck-shop arrival independently observed", 30)
    neck_observer.logout()
    neck_observer.close()
    reloaded.open_gil_shop(neck["shop"]["layout_id"], neck["shop"]["event_id"])
    reloaded.buy_shop_neck_equipment(neck["shop"]["event_id"])
    neck_rewards = deepcopy(liquidation_rewards)
    neck_rewards["items"][str(neck["item"])] = 1
    neck_rewards["currencies"]["1"] -= neck["gil"]
    state = reloaded.expect_rewards(neck_rewards, work_index)
    neck_inventory = deepcopy(state["rewards"]["inventory"])
    neck_expected = deepcopy(liquidation_inventory)
    neck_expected["2000:0"]["count"] = neck_rewards["currencies"]["1"]
    neck_added = set(neck_inventory) - set(neck_expected)
    assert len(neck_added) == 1
    neck_key = next(iter(neck_added))
    assert neck_inventory[neck_key]["id"] == neck["item"] and neck_inventory[neck_key]["count"] == 1
    assert {key: value for key, value in neck_inventory.items() if key != neck_key} == neck_expected
    reloaded.exit_gil_shop(neck["shop"]["event_id"])
    reloaded, state = restart_shop_bot(reloaded, "shop-neck-equipment-purchased",
                                      neck_rewards, neck_inventory)
    neck_gear_key = f"1000:{neck['gear_slot']}"
    assert neck_gear_key not in neck_inventory
    neck_item = neck_inventory[neck_key]
    neck_equip_receipt = reloaded.request_shop_item_equip(
        neck_item["storage"], neck_item["slot"], neck["item"], neck["gear_slot"])
    neck_final_inventory = deepcopy(neck_inventory)
    del neck_final_inventory[neck_key]
    neck_final_inventory[neck_gear_key] = {"storage": 1000, "slot": neck["gear_slot"],
                                           "id": neck["item"], "count": 1}
    neck_final_rewards = deepcopy(neck_rewards)
    del neck_final_rewards["items"][str(neck["item"])]
    reloaded, state = restart_shop_bot(reloaded, "shop-neck-equipment-equipped",
                                      neck_final_rewards, neck_final_inventory)

    neck_liquidation_slot = 21
    neck_unequip_receipt = reloaded.request_item_unequip(
        neck["gear_slot"], 1, neck_liquidation_slot, neck["item"])
    wrist_funds_rewards = deepcopy(neck_final_rewards)
    wrist_funds_rewards["items"][str(neck["item"])] = 1
    wrist_funds_inventory = deepcopy(neck_final_inventory)
    del wrist_funds_inventory[neck_gear_key]
    wrist_funds_inventory[f"1:{neck_liquidation_slot}"] = {
        "storage": 1, "slot": neck_liquidation_slot, "id": neck["item"], "count": 1}
    reloaded, state = restart_shop_bot(reloaded, "shop-neck-equipment-unequipped",
                                      wrist_funds_rewards, wrist_funds_inventory)
    reloaded.open_gil_shop(neck["shop"]["layout_id"], neck["shop"]["event_id"])
    reloaded.sell_shop_item(1, neck_liquidation_slot, neck["item"])
    del wrist_funds_rewards["items"][str(neck["item"])]
    wrist_funds_rewards["currencies"]["1"] += neck["gil"]
    del wrist_funds_inventory[f"1:{neck_liquidation_slot}"]
    wrist_funds_inventory["2000:0"]["count"] = wrist_funds_rewards["currencies"]["1"]
    state = reloaded.expect_rewards(wrist_funds_rewards, work_index)
    assert state["rewards"]["inventory"] == wrist_funds_inventory
    reloaded, state = restart_shop_bot(reloaded, "shop-neck-equipment-sold",
                                      wrist_funds_rewards, wrist_funds_inventory)
    assert wrist_funds_rewards["currencies"]["1"] == 208

    wrist = catalog["wrist_purchase"]
    assert wrist["shop_id"] == neck["shop"]["event_id"]
    reloaded.open_gil_shop(neck["shop"]["layout_id"], wrist["shop_id"])
    reloaded.buy_shop_wrist_equipment(wrist["shop_id"])
    wrist_rewards = deepcopy(wrist_funds_rewards)
    wrist_rewards["items"][str(wrist["item"])] = 1
    wrist_rewards["currencies"]["1"] -= wrist["gil"]
    state = reloaded.expect_rewards(wrist_rewards, work_index)
    wrist_inventory = deepcopy(state["rewards"]["inventory"])
    wrist_expected = deepcopy(wrist_funds_inventory)
    wrist_expected["2000:0"]["count"] = wrist_rewards["currencies"]["1"]
    wrist_added = set(wrist_inventory) - set(wrist_expected)
    assert len(wrist_added) == 1
    wrist_key = next(iter(wrist_added))
    assert wrist_inventory[wrist_key]["id"] == wrist["item"] and wrist_inventory[wrist_key]["count"] == 1
    assert {key: value for key, value in wrist_inventory.items() if key != wrist_key} == wrist_expected
    reloaded.exit_gil_shop(wrist["shop_id"])
    reloaded, state = restart_shop_bot(reloaded, "shop-wrist-equipment-purchased",
                                      wrist_rewards, wrist_inventory)
    wrist_gear_key = f"1000:{wrist['gear_slot']}"
    assert wrist_gear_key not in wrist_inventory
    wrist_item = wrist_inventory[wrist_key]
    wrist_equip_receipt = reloaded.request_shop_item_equip(
        wrist_item["storage"], wrist_item["slot"], wrist["item"], wrist["gear_slot"])
    wrist_final_inventory = deepcopy(wrist_inventory)
    del wrist_final_inventory[wrist_key]
    wrist_final_inventory[wrist_gear_key] = {"storage": 1000, "slot": wrist["gear_slot"],
                                             "id": wrist["item"], "count": 1}
    wrist_final_rewards = deepcopy(wrist_rewards)
    del wrist_final_rewards["items"][str(wrist["item"])]
    reloaded, state = restart_shop_bot(reloaded, "shop-wrist-equipment-equipped",
                                      wrist_final_rewards, wrist_final_inventory)

    (environment.artifacts / "gil-shop-sale.json").write_text(json.dumps({
        "shop": catalog["shop"], "route_length": catalog["route_length"],
        "split_receipt": receipt, "rewards_before": before_rewards,
        "inventory_after_split_restart": split_inventory,
        "rewards_after_sale": after_rewards, "inventory_after_sale": sold_inventory,
        "purchase": catalog["purchase"], "item_use_request": request,
        "item_use_effect": used_effect, "item_use_observer_received": True,
        "inventory_after_item_use": unchanged["rewards"]["inventory"],
        "rewards_after_purchase_restart": purchased_rewards,
        "inventory_after_purchase_restart": purchased_inventory,
        "liquidation_split_receipts": [first_split, second_split],
        "inventory_before_liquidation": sale_inventory,
        "rewards_after_liquidation": liquidation_rewards,
        "equipment_purchase": catalog["equipment_purchase"],
        "rewards_after_equipment_purchase_restart": equipment_rewards,
        "inventory_after_equipment_purchase_restart": equipment_inventory,
        "unequip_receipt": unequip_receipt,
        "rewards_after_starter_unequip_restart": unequipped_rewards,
        "inventory_after_starter_unequip_restart": unequipped_inventory,
        "shop_equip_receipt": equip_receipt,
        "rewards_after_shop_equip_restart": equipped_rewards,
        "inventory_after_shop_equip_restart": equipped_inventory,
        "purchased_leg_unequip_receipt": leg_unequip_receipt,
        "rewards_after_purchased_leg_resale_restart": resale_rewards,
        "inventory_after_purchased_leg_resale_restart": resale_inventory,
        "second_equipment_purchase": second,
        "rewards_after_second_equipment_purchase_restart": second_rewards,
        "inventory_after_second_equipment_purchase_restart": second_inventory,
        "second_starter_unequip_receipt": second_unequip_receipt,
        "second_shop_equip_receipt": second_equip_receipt,
        "rewards_after_second_shop_equip_restart": final_rewards,
        "inventory_after_second_shop_equip_restart": final_inventory,
        "purchased_feet_unequip_receipt": feet_unequip_receipt,
        "rewards_after_purchased_feet_resale_restart": feet_resale_rewards,
        "inventory_after_purchased_feet_resale_restart": feet_resale_inventory,
        "starter_liquidation": starter_sale,
        "rewards_after_starter_liquidation_restart": third_funds_rewards,
        "inventory_after_starter_liquidation_restart": third_funds_inventory,
        "third_equipment_purchase": third,
        "rewards_after_third_equipment_purchase_restart": third_rewards,
        "inventory_after_third_equipment_purchase_restart": third_inventory,
        "third_starter_unequip_receipt": third_unequip_receipt,
        "third_shop_equip_receipt": third_equip_receipt,
        "rewards_after_third_shop_equip_restart": third_final_rewards,
        "inventory_after_third_shop_equip_restart": third_final_inventory,
        "currency_move_rejection_receipt": currency_move_receipt,
        "inventory_after_currency_move_rejection_restart": third_final_inventory,
        "starter_body_liquidation": starter_body_sale,
        "rewards_after_starter_body_liquidation_restart": head_funds_rewards,
        "inventory_after_starter_body_liquidation_restart": head_funds_inventory,
        "head_purchase": {key: value for key, value in head.items() if key != "route"},
        "head_route_points": len(head["route"]),
        "head_arrival_witness": head_arrival["actors"][actor]["position"],
        "rewards_after_head_purchase_restart": head_rewards,
        "inventory_after_head_purchase_restart": head_inventory,
        "head_equip_receipt": head_equip_receipt,
        "rewards_after_head_equip_restart": head_final_rewards,
        "inventory_after_head_equip_restart": head_final_inventory,
        "starter_feet_liquidation": starter_feet_sale,
        "rewards_after_starter_feet_liquidation_restart": ear_funds_rewards,
        "inventory_after_starter_feet_liquidation_restart": ear_funds_inventory,
        "ear_purchase": {key: value for key, value in ear.items() if key != "route"},
        "ear_route_points": len(ear["route"]),
        "ear_arrival_witness": ear_arrival["actors"][actor]["position"],
        "rewards_after_ear_purchase_restart": ear_rewards,
        "inventory_after_ear_purchase_restart": ear_inventory,
        "ear_equip_receipt": ear_equip_receipt,
        "rewards_after_ear_equip_restart": ear_final_rewards,
        "inventory_after_ear_equip_restart": ear_final_inventory,
        "later_equipment_liquidation_unequip_receipts": liquidation_receipts,
        "rewards_after_later_equipment_liquidation_restart": liquidation_rewards,
        "inventory_after_later_equipment_liquidation_restart": liquidation_inventory,
        "neck_purchase": {key: value for key, value in neck.items() if key != "route"},
        "neck_route_points": len(neck["route"]),
        "neck_arrival_witness": neck_arrival["actors"][actor]["position"],
        "rewards_after_neck_purchase_restart": neck_rewards,
        "inventory_after_neck_purchase_restart": neck_inventory,
        "neck_equip_receipt": neck_equip_receipt,
        "rewards_after_neck_equip_restart": neck_final_rewards,
        "inventory_after_neck_equip_restart": neck_final_inventory,
        "neck_liquidation_unequip_receipt": neck_unequip_receipt,
        "rewards_after_neck_liquidation_restart": wrist_funds_rewards,
        "inventory_after_neck_liquidation_restart": wrist_funds_inventory,
        "wrist_purchase": wrist,
        "rewards_after_wrist_purchase_restart": wrist_rewards,
        "inventory_after_wrist_purchase_restart": wrist_inventory,
        "wrist_equip_receipt": wrist_equip_receipt,
        "rewards_after_wrist_equip_restart": wrist_final_rewards,
        "inventory_after_wrist_equip_restart": wrist_final_inventory,
        "arrival_observed": True,
        "scope": "source-bound sale, VFX stack purchase/action/liquidation, and later equipment purchase through one gil shop"
    }, indent=2), encoding="utf-8")
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
    moved_inventory, move_evidence = None, None
    if follow_up:
        next_quest, expected = complete_follow_up(environment, live_worker, player, observer,
                                                player_fixture, catalog, expected)
        completed_quests.append(next_quest)
        moved_inventory, move_evidence = move_reward_and_verify_reconnect(
            environment, live_worker, player, observer, player_fixture, expected,
            catalog["work_index"], completed_quests)

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
        assert state["rewards"]["inventory"] == moved_inventory
        move_evidence["after_restart"] = deepcopy(state["rewards"]["inventory"])
        (environment.artifacts / "inventory-move.json").write_text(json.dumps(move_evidence, indent=2), encoding="utf-8")
        reloaded, swapped_inventory, _ = swap_reward_and_verify_restart(
            environment, live_worker, reloaded, player_fixture, expected,
            catalog["work_index"], completed_quests)
        assert live_worker.snapshot(reloaded.name)["rewards"]["inventory"] == swapped_inventory
        reloaded, merged_inventory, _ = split_merge_reward_and_verify_restarts(
            environment, live_worker, reloaded, player_fixture, expected,
            catalog["work_index"], completed_quests)
        assert live_worker.snapshot(reloaded.name)["rewards"]["inventory"] == merged_inventory
        reloaded = discard_reward_and_verify_restart(environment, live_worker, reloaded, player_fixture,
                                                    expected, catalog["work_index"], completed_quests)
        reloaded = sell_reward_and_verify_restart(environment, live_worker, reloaded, player_fixture,
                                                  catalog["work_index"], completed_quests)
    reloaded.logout()
    reloaded.close()

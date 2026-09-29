"""Normal lobby character creation and all source-defined Ul'dah opening ring branches."""
from copy import deepcopy
import json
import math
from pathlib import Path

import pytest

from .support.catalog import load_opening_quest_catalog
from .support.worker import Bot

pytestmark = pytest.mark.live


def test_lobby_character_creation_and_opening_persistence(environment, live_worker):
    catalog = json.loads((Path(__file__).parent / "scene_catalog/opening_uldah.json").read_text())
    assert catalog["profile"] == "sapphire-3.3" and catalog["event_id"] == 1245187
    opening_path = environment.profile.get("opening_quest_catalog")
    assert opening_path, "creation journey requires a source-bound opening quest catalog"
    opening = load_opening_quest_catalog(opening_path)
    branches = [("choose_ring_4423", 4423, 1), ("choose_ring_4424", 4424, 2),
                ("choose_ring_4425", 4425, 7), ("choose_ring_4426", 4426, 1)]
    records = []

    for index, (choice, item_id, class_job) in enumerate(branches):
        account = environment.fresh_account()
        player = Bot(live_worker, f"new-character-{index}")
        state = player.create_character_via_lobby(account["auth"], account["name"], class_job)
        assert state["created_via_lobby"] is True and state["territory"] == 182
        assert state["gm_rank"] == 0 and state["actors"][str(state["entity_id"])]["level"] == 1
        assert state["rewards"]["class_job"] == class_job
        assert [row["name"] for row in state["characters"]] == [account["name"]]
        work_indices = [index for index, level in enumerate(state["rewards"]["level_by_index"]) if level == 1]
        assert len(work_indices) == 1
        work_index = work_indices[0]
        before = player.reward_snapshot(work_index)
        assert before["items"] == {} and before["exp"] == 0 and before["level"] == 1
        expected_inventory = deepcopy(live_worker.snapshot(player.name)["rewards"]["inventory"])
        unequipped = []
        gear_slots = [0, 3, 4, 6, 7] if index == 0 else [0] if index < 3 else []
        if gear_slots:
            for gear_slot in gear_slots:
                gear_key = f"1000:{gear_slot}"
                source = expected_inventory[gear_key]
                destination = next((f"{bag}:{slot}" for bag in range(4) for slot in range(25)
                                    if f"{bag}:{slot}" not in expected_inventory), None)
                assert destination is not None and source["count"] == 1
                destination_storage, destination_slot = map(int, destination.split(":"))
                receipt = player.request_item_unequip(gear_slot, destination_storage,
                                                       destination_slot, source["id"])
                assert receipt["acknowledged"] is True and receipt["inventory_change_verified"] is False
                moved = expected_inventory.pop(gear_key)
                moved.update(storage=destination_storage, slot=destination_slot)
                expected_inventory[destination] = moved
                unequipped.append({"item": source["id"], "gear_slot": gear_slot,
                                   "from": gear_key, "to": destination,
                                   "acknowledgement_is_not_mutation_proof": True})

        player.start_uldah_opening()
        player.choose_dialogue(catalog, choice)
        scene = live_worker.wait_state(player.name,
            lambda s: s["scene"] is not None and s["scene"]["event_id"] == 1245187
                      and s["scene"]["scene_id"] == 1,
            "source-defined chained Ul'dah opening scene 1")
        assert scene["territory"] == 182 and scene["gm_rank"] == 0
        player.choose_dialogue(catalog, "finish")
        player.wait_event_finished()
        expected = deepcopy(before)
        expected["items"][str(item_id)] = 1
        for moved in unequipped:
            expected["items"][str(moved["item"])] = 1
        # The opening grant is deliberately silent on this server. Locate and
        # bind the ring only from the authoritative fresh-login inventory below.
        ring_slot = next(f"{bag}:{slot}" for bag in range(4) for slot in range(25)
                         if f"{bag}:{slot}" not in expected_inventory)
        expected_inventory[ring_slot] = {"storage": int(ring_slot.split(":")[0]),
                                         "slot": int(ring_slot.split(":")[1]),
                                         "id": item_id, "count": 1}
        player.logout(wait_server_close=True)
        player.close()

        auth = environment.api("login", {"username": account["username"], "pass": account["password"]})
        reloaded = Bot(live_worker, f"new-character-reloaded-{index}")
        state = reloaded.login_via_lobby(auth, account["name"])
        assert state["created_via_lobby"] is False and state["territory"] == 182 and state["gm_rank"] == 0
        state = reloaded.expect_rewards(expected, work_index)
        inventory = deepcopy(state["rewards"]["inventory"])
        inventory_after_fresh = deepcopy(inventory)
        reequipped = []
        assert inventory == expected_inventory
        for unequip in unequipped:
            source = inventory[unequip["to"]]
            storage, slot = map(int, unequip["to"].split(":"))
            gear_slot = unequip["gear_slot"]
            receipt = reloaded.request_item_reequip_starter(storage, slot, source["id"], gear_slot)
            assert receipt["acknowledged"] is True and receipt["inventory_change_verified"] is False
            moved = inventory.pop(unequip["to"])
            moved.update(storage=1000, slot=gear_slot)
            gear_key = f"1000:{gear_slot}"
            inventory[gear_key] = moved
            del expected["items"][str(source["id"])]
            reequipped.append({"item": source["id"], "gear_slot": gear_slot,
                               "from": unequip["to"], "to": gear_key,
                               "acknowledgement_is_not_mutation_proof": True})
        ring = inventory[ring_slot]
        ring_storage, ring_index = map(int, ring_slot.split(":"))
        receipt = reloaded.request_item_reequip_starter(ring_storage, ring_index, item_id, 11)
        assert receipt["acknowledged"] is True and receipt["inventory_change_verified"] is False
        moved_ring = inventory.pop(ring_slot)
        moved_ring.update(storage=1000, slot=11)
        inventory["1000:11"] = moved_ring
        del expected["items"][str(item_id)]
        equipped_ring = {"item": item_id, "gear_slot": 11, "from": ring_slot, "to": "1000:11",
                         "acknowledgement_is_not_mutation_proof": True}
        assert len([item for item in inventory.values() if item["id"] == item_id and item["count"] == 1]) == 1

        # OpeningSequence=1 must select scene 40 after fresh authentication, not replay scene 0.
        reloaded.start_uldah_opening()
        scene = live_worker.wait_state(reloaded.name,
            lambda s: s["scene"] is not None and s["scene"]["event_id"] == 1245187,
            "persisted Ul'dah opening continuation")
        assert scene["scene"]["scene_id"] == 40
        reloaded.choose_dialogue(catalog, "finish")
        reloaded.wait_event_finished()
        opening_position = None
        opening_quest_active = False
        if index == 0:
            reloaded.walk_route(opening["approach_route"], 2.0, 30)
            reloaded.interact(opening["giver"]["layout_id"], opening["quest"])
            reloaded.choose_dialogue(catalog, "accept_coming_to_uldah")
            reloaded.choose_dialogue(catalog, "continue_coming_to_uldah")
            reloaded.choose_dialogue(catalog, "continue_coming_to_uldah")
            reloaded.wait_event_finished()
            reloaded.expect_quest_active(opening["quest"], 255)
            opening_position = opening["approach_route"][-1]
            opening_quest_active = True
        reloaded.logout(wait_server_close=True)
        reloaded.close()
        records.append({"account": account, "choice": choice, "item": item_id, "class_job": class_job,
                        "work_index": work_index,
                        "before": before, "expected": expected, "inventory": inventory,
                        "inventory_after_fresh": inventory_after_fresh,
                        "unequipped": unequipped, "reequipped": reequipped,
                        "equipped_ring": equipped_ring, "ring_slot": ring_slot,
                        "opening_position": opening_position,
                        "opening_quest_active": opening_quest_active})

    environment.restart_world()
    evidence = []
    for index, record in enumerate(records):
        account = record["account"]
        auth = environment.api("login", {"username": account["username"], "pass": account["password"]})
        restarted = Bot(live_worker, f"new-character-restarted-{index}")
        state = restarted.login_via_lobby(auth, account["name"])
        assert state["territory"] == 182 and state["gm_rank"] == 0
        state = restarted.expect_rewards(record["expected"], record["work_index"])
        assert state["rewards"]["inventory"] == record["inventory"]
        if record["opening_quest_active"]:
            restarted.expect_quest_active(opening["quest"], 255)
            assert math.dist(state["observed_position"], record["opening_position"]) < 0.15
        restarted.start_uldah_opening()
        scene = live_worker.wait_state(restarted.name,
            lambda s: s["scene"] is not None and s["scene"]["event_id"] == 1245187,
            "restarted Ul'dah opening continuation")
        assert scene["scene"]["scene_id"] == 40
        restarted.choose_dialogue(catalog, "finish")
        if record["opening_quest_active"]:
            scene = live_worker.wait_state(restarted.name,
                lambda s: s["scene"] is not None and s["scene"]["event_id"] == 1245187,
                "OpeningSequence=2 chained scene")
            assert scene["scene"]["scene_id"] == 30
            restarted.choose_dialogue(catalog, "finish")
        restarted.wait_event_finished()
        ring_storage, ring_index = map(int, record["ring_slot"].split(":"))
        receipt = restarted.request_item_unequip(11, ring_storage, ring_index, record["item"])
        assert receipt["acknowledged"] is True and receipt["inventory_change_verified"] is False
        unequipped_ring = {"item": record["item"], "gear_slot": 11, "from": "1000:11",
                           "to": record["ring_slot"],
                           "acknowledgement_is_not_mutation_proof": True}
        final_inventory = deepcopy(record["inventory"])
        moved_ring = final_inventory.pop("1000:11")
        moved_ring.update(storage=ring_storage, slot=ring_index)
        final_inventory[record["ring_slot"]] = moved_ring
        final_expected = deepcopy(record["expected"])
        final_expected["items"][str(record["item"])] = 1
        restarted.logout(wait_server_close=True)
        restarted.close()

        auth = environment.api("login", {"username": account["username"], "pass": account["password"]})
        roundtrip = Bot(live_worker, f"new-character-ring-roundtrip-{index}")
        state = roundtrip.login_via_lobby(auth, account["name"])
        assert state["territory"] == 182 and state["gm_rank"] == 0
        state = roundtrip.expect_rewards(final_expected, record["work_index"])
        assert state["rewards"]["inventory"] == final_inventory
        roundtrip.logout()
        roundtrip.close()
        evidence.append({"character": account["name"], "choice": record["choice"],
                         "item": record["item"], "class_job": record["class_job"],
                         "work_index": record["work_index"],
                         "first_scenes": [0, 1],
                         "scene_after_fresh_login": 40, "scene_after_restart": 40,
                         "rewards_before": record["before"],
                         "rewards_after_restart": record["expected"],
                         "inventory_after_fresh": record["inventory_after_fresh"],
                         "inventory_after_restart": record["inventory"],
                         "rewards_after_ring_unequip_fresh_login": final_expected,
                         "inventory_after_ring_unequip_fresh_login": final_inventory,
                         "unequipped": record["unequipped"], "reequipped": record["reequipped"],
                         "equipped_ring": record["equipped_ring"],
                         "unequipped_ring": unequipped_ring,
                         "coming_to_uldah_active_sequence": 255 if record["opening_quest_active"] else None,
                         "opening_position_after_restart": record["opening_position"],
                         "scene_after_opening_sequence_2": 30 if record["opening_quest_active"] else None})

    (environment.artifacts / "character-creation-opening.json").write_text(json.dumps({
        "branches": evidence, "created_via_lobby": True, "initial_territory": 182,
        "coming_to_uldah_completion_blocker": opening["completion_route_blocker"],
        "scope": "four canonical Ul'dah characters across Gladiator, Pugilist and Thaumaturge created through lobby reserve/finalize, all ring choices with persisted Ring1 equip/unequip round trips, all five persisted Gladiator starter-equipment slots plus each distinct starter main hand, source-routed Coming to Ul'dah acceptance through scenes 0/1/2 and persisted sequence 255 plus opening scene 30; completion remains blocked by the missing navigation corridor"
    }, indent=2), encoding="utf-8")

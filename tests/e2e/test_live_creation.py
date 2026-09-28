"""Normal lobby character creation and all source-defined Ul'dah opening ring branches."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from .support.worker import Bot

pytestmark = pytest.mark.live


def test_lobby_character_creation_and_opening_persistence(environment, live_worker):
    catalog = json.loads((Path(__file__).parent / "scene_catalog/opening_uldah.json").read_text())
    assert catalog["profile"] == "sapphire-3.3" and catalog["event_id"] == 1245187
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
        expected_inventory = None
        unequipped = None
        if index == 0:
            inventory = deepcopy(live_worker.snapshot(player.name)["rewards"]["inventory"])
            source = inventory["1000:0"]
            destination = next((f"{bag}:{slot}" for bag in range(4) for slot in range(25)
                                if f"{bag}:{slot}" not in inventory), None)
            assert destination is not None and source["count"] == 1
            destination_storage, destination_slot = map(int, destination.split(":"))
            receipt = player.request_item_unequip(0, destination_storage, destination_slot, source["id"])
            assert receipt["acknowledged"] is True and receipt["inventory_change_verified"] is False
            expected_inventory = deepcopy(inventory)
            moved = expected_inventory.pop("1000:0")
            moved.update(storage=destination_storage, slot=destination_slot)
            expected_inventory[destination] = moved
            unequipped = {"item": source["id"], "from": "1000:0", "to": destination,
                          "acknowledgement_is_not_mutation_proof": True}

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
        if unequipped is not None:
            expected["items"][str(unequipped["item"])] = 1
            # The ring is added after the unequip request, into the next empty bag slot.
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
        if expected_inventory is not None:
            assert inventory == expected_inventory
        assert len([item for item in inventory.values() if item["id"] == item_id and item["count"] == 1]) == 1

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
        records.append({"account": account, "choice": choice, "item": item_id, "class_job": class_job,
                        "work_index": work_index,
                        "before": before, "expected": expected, "inventory": inventory,
                        "unequipped": unequipped})

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
        restarted.start_uldah_opening()
        scene = live_worker.wait_state(restarted.name,
            lambda s: s["scene"] is not None and s["scene"]["event_id"] == 1245187,
            "restarted Ul'dah opening continuation")
        assert scene["scene"]["scene_id"] == 40
        restarted.choose_dialogue(catalog, "finish")
        restarted.wait_event_finished()
        restarted.logout()
        restarted.close()
        evidence.append({"character": account["name"], "choice": record["choice"],
                         "item": record["item"], "class_job": record["class_job"],
                         "work_index": record["work_index"],
                         "first_scenes": [0, 1],
                         "scene_after_fresh_login": 40, "scene_after_restart": 40,
                         "rewards_before": record["before"],
                         "rewards_after_restart": record["expected"],
                         "inventory_after_restart": record["inventory"],
                         "unequipped": record["unequipped"]})

    (environment.artifacts / "character-creation-opening.json").write_text(json.dumps({
        "branches": evidence, "created_via_lobby": True, "initial_territory": 182,
        "scope": "four canonical Ul'dah characters across Gladiator, Pugilist and Thaumaturge created through lobby reserve/finalize, all source-defined ring choices, one persisted observed main-hand unequip, first opening branch and continuation; not account signup UI, appearance breadth or complete opening quest"
    }, indent=2), encoding="utf-8")

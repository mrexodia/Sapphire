"""Explicit starter-body round trip, using normal client inventory operations only."""
import copy
import time

from .development import DevelopmentError, received_character_identity
from .development_inventory import capture_inventory, inventory_projection
from .development_party import ungrouped

METHODS = {"request_item_unequip", "request_item_reequip_starter"}
BODY = {"storage": 1000, "slot": 3, "id": 2983, "count": 1}
BAG = {"storage": 0, "slot": 0, "id": 2983, "count": 1}


def require_equipment_worker(worker):
    methods = worker.request("capabilities").get("methods")
    if not isinstance(methods, list) or not METHODS.issubset(methods):
        raise DevelopmentError("equipment round trip requires advertised ordinary equipment methods")


def participant(state, identity, territory, expected_job=None):
    if not ungrouped(state, territory):
        raise DevelopmentError("equipment round trip requires idle nonparty state")
    result = inventory_projection(state, identity, territory)
    job = state.get("rewards", {}).get("class_job")
    if type(job) is not int or job not in {1, 2, 7} or (expected_job is not None and job != expected_job):
        raise DevelopmentError("equipment round trip requires an Ul'dah starter class")
    return result


def check_receipt(receipt):
    context = receipt.get("context")
    if type(context) is not int or not 1 <= context <= 0xffffffff:
        raise DevelopmentError("invalid equipment request context; no retry")


def observe(worker, bot, identity, territory, expected, baseline_seq, deadline, job):
    def matches(state):
        value = participant(state, identity, territory, job)
        return (value is not None and value["received_sequence"] > baseline_seq
                and value["inventory"] == expected)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise DevelopmentError("equipment observation deadline exceeded after publication; no retry")
    state = worker.wait_state(bot.name, matches, "exact received equipment round-trip projection", timeout=remaining)
    if time.monotonic() >= deadline or not matches(state):
        raise DevelopmentError("late or changed equipment observation; no retry")
    return participant(state, identity, territory, job)


def begin_roundtrip(profile, worker, mover, initial, report, timings):
    identity = received_character_identity(initial, profile["accounts"][0]["character"])
    territory = profile["territory"]
    report.update(identity=identity, scope="starter-body-slot-count-roundtrip-not-item-instances-or-world-restart")
    with timings.phase("equipment_before_unequip"):
        capture_inventory(worker, mover, identity, territory)
        state = worker.snapshot(mover.name)
        before = participant(state, identity, territory)
        if before is None or before["inventory"].get("1000:3") != BODY or "0:0" in before["inventory"]:
            raise DevelopmentError("round trip requires exact starter body and empty ordinary bag0 slot0")
        report["before"] = before
        report["class_job"] = state["rewards"]["class_job"]
        expected = copy.deepcopy(before["inventory"])
        del expected["1000:3"]
        expected["0:0"] = dict(BAG)
        report["unequip_expected"] = expected
    with timings.phase("equipment_unequip_received_mutation"):
        deadline = time.monotonic() + 10
        # Intent precedes publication. On any failure, do not re-equip in cleanup.
        report["unequip_publication_attempted"] = True
        report["unequip_receipt"] = mover.request_item_unequip(3, 0, 0, 2983)
        check_receipt(report["unequip_receipt"])
        report["unequipped"] = observe(worker, mover, identity, territory, expected,
                                      before["received_sequence"], deadline, report["class_job"])


def finish_roundtrip(profile, worker, mover, report, timings):
    identity, territory = report["identity"], profile["territory"]
    with timings.phase("equipment_before_reequip"):
        capture_inventory(worker, mover, identity, territory)
        before = participant(worker.snapshot(mover.name), identity, territory, report["class_job"])
        if before is None or before["inventory"] != report["unequip_expected"]:
            raise DevelopmentError("received inventory changed before re-equip; no restoration attempted")
        report["before_reequip"] = before
    with timings.phase("equipment_reequip_received_mutation"):
        deadline = time.monotonic() + 10
        report["reequip_publication_attempted"] = True
        report["reequip_receipt"] = mover.request_item_reequip_starter(0, 0, 2983, gear_slot=3)
        check_receipt(report["reequip_receipt"])
        report["reequipped"] = observe(worker, mover, identity, territory, report["before"]["inventory"],
                                      before["received_sequence"], deadline, report["class_job"])
    report["verified"] = True

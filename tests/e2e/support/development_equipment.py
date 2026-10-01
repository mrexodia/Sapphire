"""Ordinary starter-body operations; mutations require fresh-login observations."""
import copy
import time

from .development import DevelopmentError, received_character_identity
from .development_inventory import capture_inventory, inventory_projection
from .development_party import ungrouped

METHODS = {"request_item_unequip", "request_item_reequip_starter"}
SCOPE = "starter-body-slot-count-roundtrip-not-item-instances-or-world-restart"
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
        raise DevelopmentError("equipment round trip requires the same Ul'dah starter class")
    return result


def check_receipt(receipt, deadline):
    context = receipt.get("context")
    if type(context) is not int or not 1 <= context <= 0xffffffff or time.monotonic() >= deadline:
        raise DevelopmentError("invalid or late equipment acknowledgement; no retry")


def begin_roundtrip(profile, worker, mover, initial, report, timings):
    identity = received_character_identity(initial, profile["accounts"][0]["character"])
    territory = profile["territory"]
    report.update(identity=identity, scope=SCOPE,
                  reconnects_required=3, mutation_observation="fresh-login-not-current-session-acknowledgement")
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
    with timings.phase("equipment_unequip_ack_not_mutation"):
        deadline = time.monotonic() + 10
        report["unequip_publication_attempted"] = True
        report["unequip_receipt"] = mover.request_item_unequip(3, 0, 0, 2983)
        check_receipt(report["unequip_receipt"], deadline)
        # moveItem persists containers without sending current-session inventory
        # contents. Never synthesize that cache mutation from acknowledgement.


def observe_after_reconnect(profile, worker, mover, report, timings, *, reequipped=False):
    key = "reequipped" if reequipped else "unequipped"
    expected = report["before"]["inventory"] if reequipped else report["unequip_expected"]
    with timings.phase(f"equipment_{key}_fresh_login_projection"):
        report[key] = capture_inventory(worker, mover, report["identity"], profile["territory"])
        current = participant(worker.snapshot(mover.name), report["identity"], profile["territory"], report["class_job"])
        if (current is None or current["inventory"] != expected
                or report[key]["inventory"] != expected):
            raise DevelopmentError("fresh-login equipment mutation not observed; no restoration/retry")
    if reequipped:
        report["verified"] = True


def finish_roundtrip(profile, worker, mover, report, timings):
    identity, territory = report["identity"], profile["territory"]
    with timings.phase("equipment_before_reequip"):
        capture_inventory(worker, mover, identity, territory)
        before = participant(worker.snapshot(mover.name), identity, territory, report["class_job"])
        if before is None or before["inventory"] != report["unequip_expected"]:
            raise DevelopmentError("received inventory changed before re-equip; no restoration attempted")
        report["before_reequip"] = before
    with timings.phase("equipment_reequip_ack_not_mutation"):
        deadline = time.monotonic() + 10
        report["reequip_publication_attempted"] = True
        report["reequip_receipt"] = mover.request_item_reequip_starter(0, 0, 2983, gear_slot=3)
        check_receipt(report["reequip_receipt"], deadline)

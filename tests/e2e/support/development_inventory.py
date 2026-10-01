"""Received inventory projection only; no item mutation or administrative setup."""
import time

from .development import DevelopmentError, idle_state, received_character_identity

# Ordinary bags, equipment and Currency. Crystal/armoury/other containers are
# outside this read-only comparison, and currency is never a generic bag action.
CONTAINERS = (0, 1, 2, 3, 1000, 2000)
SCOPE = "fresh-login-slot-catalog-counts-not-item-instances-or-world-restart"


def uint(value, maximum):
    return type(value) is int and 0 <= value <= maximum


def inventory_projection(state, identity, territory):
    """None means not complete yet; malformed or changed identity fails immediately."""
    if (not idle_state(state, territory) or state.get("between_areas") is not False
            or received_character_identity(state, identity["name"]) != identity
            or not uint(state.get("seq"), 2**64-1)):
        raise DevelopmentError("inventory observation identity/idle/sequence changed")
    rewards = state.get("rewards", {})
    if not isinstance(rewards, dict):
        raise DevelopmentError("malformed received rewards")
    ready = rewards.get("inventory_ready", False)
    containers = rewards.get("containers", {})
    if type(ready) is not bool or not isinstance(containers, dict):
        raise DevelopmentError("malformed inventory completeness flags")
    for storage in CONTAINERS:
        if str(storage) in containers and type(containers[str(storage)]) is not bool:
            raise DevelopmentError("container completeness must be boolean")
    if not ready or any(containers.get(str(storage)) is not True for storage in CONTAINERS):
        return None
    inventory = rewards.get("inventory")
    if not isinstance(inventory, dict):
        raise DevelopmentError("complete inventory lacks a slot map")
    selected = {}
    for key, row in inventory.items():
        if not isinstance(row, dict):
            raise DevelopmentError("malformed received inventory row")
        storage, slot = row.get("storage"), row.get("slot")
        if (not uint(storage, 2**32-1) or not uint(slot, 65535)
                or key != f"{storage}:{slot}"
                or not uint(row.get("id"), 2**32-1) or row["id"] == 0
                or not uint(row.get("count"), 2**32-1) or row["count"] == 0):
            raise DevelopmentError("inventory slot metadata/catalog/count mismatch")
        if storage not in CONTAINERS:
            continue
        if (storage < 4 and slot >= 25) or (storage == 1000 and slot > 13):
            raise DevelopmentError("unsupported bag/equipment slot")
        selected[key] = {field: row[field] for field in ("storage", "slot", "id", "count")}
    return {"containers": list(CONTAINERS), "inventory": dict(sorted(selected.items())),
            "received_sequence": state["seq"]}


def capture_inventory(worker, bot, identity, territory):
    deadline = time.monotonic() + 10
    state = worker.wait_state(bot.name,
        lambda s: inventory_projection(s, identity, territory) is not None,
        "complete received bag/equipment/currency snapshots", timeout=10)
    result = inventory_projection(state, identity, territory)
    if time.monotonic() >= deadline or result is None:
        raise DevelopmentError("late or incomplete inventory observation")
    return result


def compare_inventory(report):
    before, after = report["before"]["inventory"], report["after"]["inventory"]
    changed = sorted(key for key in before.keys() | after.keys() if before.get(key) != after.get(key))
    report["changed_slots"] = changed
    if changed:
        raise DevelopmentError("fresh-login inventory projection changed; no restore/retry")
    report["verified"] = True

"""Narrow received-state checks, not a general combat AI/cooldown scheduler."""
import math


def fast_blade_ready(state, target):
    if type(target) is not int or not 0 < target <= 0xffffffff:
        raise ValueError("combat target must be an observed 32-bit actor id")
    remaining = state["combat"].get("fast_blade_guard_remaining_ms")
    if type(remaining) is not int or remaining < 0:
        raise ValueError("worker must expose the conservative Fast Blade pacing guard")
    if state["phase"] != "ready" or state["moving"] or state["event_id"] is not None or state["scene"] is not None:
        return False
    if state["gm_rank"] != 0 or state["rewards"]["class_job"] != 1:
        raise ValueError("Fast Blade readiness requires a non-GM Gladiator")
    own = state["actors"].get(str(state["entity_id"]))
    enemy = state["actors"].get(str(target))
    if own is None or enemy is None:
        return False
    if own["hp"] <= 0:
        raise ValueError("fighter was defeated while waiting for combat readiness")
    if enemy["kind"] != 2 or enemy["level"] != 1 or enemy["hp"] <= 0:
        return False
    # Estimated request range only. Independent observer positions must establish
    # actual range in a scenario; this helper never certifies movement/arrival.
    positions = state["predicted_position"], enemy["position"]
    if any(len(p) != 3 or any(type(v) not in (int, float) or not math.isfinite(v) for v in p) for p in positions):
        raise ValueError("invalid estimated combat position")
    return remaining == 0 and own["tp"] >= 60 and math.dist(*positions) <= 2.5


def damage_value(effect):
    return sum(row["value"] for row in effect["effects"] if row["type"] in (3, 5) and row["flag"] == 0)


def committed_damage(state, effect, before):
    """Require the identical received effect AND its exact committed HP result.

    `before` must be an independently captured pre-action target snapshot, not a
    value inferred by subtracting damage from the desired final HP.
    """
    damage = damage_value(effect)
    return (damage > 0 and effect in state["combat"]["effects"]
            and any(row["target"] == effect["target"] and row["result"] == effect["result"]
                    and row["hp_max"] == before["hp_max"]
                    and row["hp"] == max(0, before["hp"] - damage)
                    for row in state["combat"]["integrities"]))

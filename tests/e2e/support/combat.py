"""Narrow received-state checks, not a general combat AI/cooldown scheduler."""
import math


def starting_melee_ready(state, target, class_job, class_name, tp_cost=60, minimum_level=1, work_index=None):
    if type(target) is not int or not 0 < target <= 0xffffffff:
        raise ValueError("combat target must be an observed 32-bit actor id")
    remaining = state["combat"].get("starting_action_guard_remaining_ms")
    if type(remaining) is not int or remaining < 0:
        raise ValueError("worker must expose the conservative starting-melee pacing guard")
    if state["phase"] != "ready" or state["moving"] or state["event_id"] is not None or state["scene"] is not None:
        return False
    if state["gm_rank"] != 0 or state["rewards"]["class_job"] != class_job:
        raise ValueError(f"starting-melee readiness requires a non-GM {class_name}")
    if work_index is not None:
        levels = state["rewards"].get("level_by_index")
        if not isinstance(levels, list) or len(levels) <= work_index or levels[work_index] < minimum_level:
            raise ValueError(f"{class_name} action requires received level {minimum_level} progression")
    own = state["actors"].get(str(state["entity_id"]))
    enemy = state["actors"].get(str(target))
    if own is None or enemy is None:
        return False
    if own["hp"] <= 0:
        raise ValueError("fighter was defeated while waiting for combat readiness")
    if enemy["kind"] != 2 or enemy["hp"] <= 0:
        return False
    # Estimated request range only. Independent observer positions must establish
    # actual range in a scenario; this helper never certifies movement/arrival.
    positions = state["predicted_position"], enemy["position"]
    if any(len(p) != 3 or any(type(v) not in (int, float) or not math.isfinite(v) for v in p) for p in positions):
        raise ValueError("invalid estimated combat position")
    if own["level"] < minimum_level:
        raise ValueError(f"{class_name} actor level does not satisfy the source action")
    return remaining == 0 and own["tp"] >= tp_cost and math.dist(*positions) <= 2.5


def sprint_ready(state):
    remaining = state["combat"].get("starting_action_guard_remaining_ms")
    if type(remaining) is not int or remaining < 0:
        raise ValueError("worker must expose the conservative starting-action pacing guard")
    if state["phase"] != "ready" or state["moving"] or state["event_id"] is not None or state["scene"] is not None:
        return False
    if state["gm_rank"] != 0:
        raise ValueError("Sprint readiness requires a non-GM player")
    own = state["actors"].get(str(state["entity_id"]))
    if own is None:
        return False
    if own["kind"] != 1 or own["hp"] <= 0:
        raise ValueError("player was defeated while waiting for Sprint readiness")
    return remaining == 0 and own["tp"] >= 50


def fast_blade_ready(state, target):
    return starting_melee_ready(state, target, 1, "Gladiator")


def savage_blade_ready(state, target):
    if not starting_melee_ready(state, target, 1, "Gladiator", 60, 4, 1):
        return False
    for row in reversed(state["combat"]["effects"]):
        if row["source"] == state["entity_id"]:
            return (row["target"] == target and row["action"] == 9
                    and any(effect == {"type": 29, "value": 9, "flag": 0x80,
                                       "args": [0, 0, 0]}
                            for effect in row.get("source_effects", [])))
    return False


def bootshine_ready(state, target):
    return starting_melee_ready(state, target, 2, "Pugilist")


def true_strike_ready(state, target):
    return starting_melee_ready(state, target, 2, "Pugilist", 50, 2, 0)


def blizzard_ready(state, target):
    if type(target) is not int or not 0 < target <= 0xffffffff:
        raise ValueError("combat target must be an observed 32-bit actor id")
    remaining = state["combat"].get("starting_action_guard_remaining_ms")
    if type(remaining) is not int or remaining < 0:
        raise ValueError("worker must expose the conservative starting-action pacing guard")
    if state["phase"] != "ready" or state["moving"] or state["event_id"] is not None or state["scene"] is not None:
        return False
    if state["gm_rank"] != 0 or state["rewards"]["class_job"] != 7:
        raise ValueError("Blizzard readiness requires a non-GM Thaumaturge")
    own = state["actors"].get(str(state["entity_id"]))
    enemy = state["actors"].get(str(target))
    if own is None or enemy is None:
        return False
    if own["hp"] <= 0:
        raise ValueError("caster was defeated while waiting for combat readiness")
    if enemy["kind"] != 2 or enemy["hp"] <= 0:
        return False
    positions = state["predicted_position"], enemy["position"]
    if any(len(p) != 3 or any(type(v) not in (int, float) or not math.isfinite(v) for v in p) for p in positions):
        raise ValueError("invalid estimated combat position")
    return remaining == 0 and own["mp"] >= 4 and math.dist(*positions) <= 24.5


def require_unchanged_death_state(before_rewards, before_inventory,
                                  after_rewards, after_inventory):
    """Require exact tracked reward/inventory equality across defeat or return.

    This deliberately covers only received EXP, level, currencies, item totals and
    complete inventory rows. It does not infer unexposed durability or other death
    penalties.
    """
    if not isinstance(before_rewards, dict) or not isinstance(after_rewards, dict):
        raise ValueError("death reward state must be received mappings")
    if before_rewards != after_rewards:
        raise ValueError("death changed received EXP, level, currency or item totals")
    if not isinstance(before_inventory, dict) or not isinstance(after_inventory, dict):
        raise ValueError("death inventory state must be received mappings")
    if before_inventory != after_inventory:
        raise ValueError("death changed received inventory rows")


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


def combat_reward_delta(before, after, base_exp):
    """Validate the server's current fixed BNpc EXP and test-table loot contract."""
    if type(base_exp) is not int or base_exp <= 0:
        raise ValueError("combat base EXP must be a positive integer")
    if after["exp"] != before["exp"] + base_exp or after["level"] != before["level"]:
        raise ValueError("combat EXP/level reward mismatch")
    if after["currencies"] != before["currencies"]:
        raise ValueError("combat unexpectedly changed currency")
    keys = set(before["items"]) | set(after["items"])
    delta = {key: after["items"].get(key, 0) - before["items"].get(key, 0) for key in keys}
    if any(value < 0 for value in delta.values()):
        raise ValueError("combat loot removed an existing item")
    delta = {key: value for key, value in delta.items() if value}
    first_pool = [key for key in ("8", "9") if delta.get(key) == 5]
    if len(first_pool) != 1 or delta != {
            first_pool[0]: 5, "5016": 1, "12728": 1, "4551": delta.get("4551")}:
        raise ValueError("combat loot does not match enabled testTable pools")
    if delta["4551"] not in {1, 2, 3}:
        raise ValueError("combat variable-quantity loot is out of range")
    return {"items": delta, "exp": base_exp, "level": 0, "currencies": {}}


# --- choosing natural targets on a shared, long-running world -----------------
# Enemies respawn on their own after their popInterval and heal fully when they
# retreat to spawn, so scenarios wait for a healthy enemy instead of resetting
# the world. Timeouts are generous enough to cover one respawn cycle.

def healthy_enemies(state, base_id, level, maximum=60.0, origin=None):
    """Full-HP enemies of one kind near the bot, nearest first."""
    origin = origin if origin is not None else state["predicted_position"]
    rows = [(key, actor) for key, actor in state["actors"].items()
            if actor["kind"] == 2 and actor["base_id"] == base_id and actor["level"] == level
            and actor["hp"] == actor["hp_max"] > 0
            and math.dist(actor["position"], origin) <= maximum]
    return sorted(rows, key=lambda row: math.dist(row[1]["position"], origin))


def wait_healthy_enemy(worker, bot, base_id, level, maximum=60.0, timeout=90):
    """Wait for a healthy enemy of one kind to be visible (covers one respawn)."""
    state = worker.wait_state(bot.name, lambda s: bool(healthy_enemies(s, base_id, level, maximum)),
                              f"healthy level-{level} enemy {base_id} within {maximum:.0f}m", timeout)
    return healthy_enemies(state, base_id, level, maximum)[0]


def approach_target(worker, bot, target, within=2.5, attempts=6, speed=6.0):
    """Walk toward a (possibly roaming) enemy using only received positions."""
    for _ in range(attempts):
        state = worker.snapshot(bot.name)
        actor = state["actors"].get(target)
        if actor is None or actor["hp"] <= 0:
            raise AssertionError(f"{bot.name}: target {target} disappeared during the approach")
        if math.dist(actor["position"], state["predicted_position"]) < within:
            return state
        # Stop one metre beside the enemy, not on top of it: face() needs a direction.
        destination = list(actor["position"])
        destination[0] += 1.0
        bot.walk_to(destination, speed, 30)
    raise AssertionError(f"{bot.name}: could not reach target {target} in {attempts} legs")

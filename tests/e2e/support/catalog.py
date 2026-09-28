"""Validation for locally generated route catalogs; never invent missing routes."""
import json
import math
from pathlib import Path
from .worker import WorkerError


def validate_quest_catalog(data, completed_quests=()):
    if data.get("profile") != "sapphire-3.3" or data.get("version") != 1:
        raise WorkerError("unsupported quest catalog version/profile")
    if data.get("quest") not in {65685, 65686, 65687}:
        raise WorkerError("quest has no implemented scenario/scene adapter")
    previous = data.get("previous_quests")
    if data.get("level") != 1 or not isinstance(previous, list) or len(previous) != 3:
        raise WorkerError("quest fixture prerequisites are unsupported")
    if any(type(quest) is not int or (quest and quest not in completed_quests) for quest in previous):
        raise WorkerError("quest prerequisites have not been observed complete")
    route = validated_route(data)
    actors = {}
    for role, endpoint in (("client", route[0]), ("finish", route[-1])):
        candidates = [actor for actor in data.get("actors", [])
                      if actor["base_id"] == data[role] and actor["territory"] == 130
                      and math.dist(actor["position"], endpoint) <= 2]
        if len(candidates) != 1:
            raise WorkerError(f"route endpoint must resolve exactly one {role} NPC within interaction range")
        actors[role] = candidates[0]
    data = dict(data)
    data["giver"], data["recipient"] = actors["client"], actors["finish"]
    return data


def validated_route(data):
    route = data.get("route", [])
    if not 2 <= len(route) <= 2048:
        raise WorkerError("catalog requires a complete bounded navigation route")
    for point in route:
        if len(point) != 3 or not all(type(x) in (int, float) and math.isfinite(x) and abs(x) < 1000 for x in point):
            raise WorkerError("invalid route position")
    lengths = [math.dist(a, b) for a, b in zip(route, route[1:])]
    if max(lengths) > 2 or sum(lengths) > 500:
        raise WorkerError("route contains a jump or exceeds distance budget")
    if not math.isclose(sum(lengths), data.get("route_length", -1), rel_tol=1e-5, abs_tol=0.01):
        raise WorkerError("route length metadata mismatch")
    return route


def validate_transition_catalog(data):
    if data.get("profile") != "sapphire-3.3" or data.get("version") != 1 or data.get("territory") != 130:
        raise WorkerError("unsupported transition catalog profile/source")
    route = validated_route(data)
    transition = data["transition"]
    if transition["territory"] != 130 or transition["enabled"] is not True or transition["shape"] != 1 or transition["exit_type"] != 1:
        raise WorkerError("unsupported transition exit")
    if transition["target_territory"] not in {131, 140, 141}:
        raise WorkerError("destination is not a supported public territory")
    destinations = transition.get("destinations", [])
    if len(destinations) != 1 or destinations[0]["id"] != transition["target_pop"] or destinations[0]["territory"] != transition["target_territory"]:
        raise WorkerError("exit must resolve exactly one destination pop range")
    for point in (transition["position"], transition["scale"], transition["rotation"], destinations[0]["position"]):
        if len(point) != 3 or not all(type(x) in (int, float) and math.isfinite(x) and abs(x) < 1000 for x in point):
            raise WorkerError("invalid transition transform")
    scale, center, rotation = transition["scale"], transition["position"], transition["rotation"]
    if any(v <= 0 or v > 100 for v in scale) or abs(rotation[0]) > 1e-4 or abs(rotation[2]) > 1e-4:
        raise WorkerError("unsupported exit transform")
    distance = lambda point: math.hypot(point[0] - center[0], point[2] - center[2])
    if distance(route[0]) <= math.hypot(scale[0], scale[2]):
        raise WorkerError("route must begin outside exit volume")
    if distance(route[-1]) > min(scale[0], scale[2]) * 0.5 or abs(route[-1][1] - center[1]) > scale[1] * 0.5:
        raise WorkerError("route must end inside conservative exit volume")
    return data


def validate_pursuit_catalog(data):
    if data.get("profile") != "sapphire-3.3" or data.get("version") != 1 or data.get("territory") != 141:
        raise WorkerError("unsupported pursuit catalog profile/territory")
    enemy = data.get("enemy", {})
    if {key: enemy.get(key) for key in ("layout_id", "base_id", "level")} != {
            "layout_id": 3749193, "base_id": 302, "level": 14}:
        raise WorkerError("unsupported pursuit population binding")
    position = enemy.get("position")
    if (not isinstance(position, list) or len(position) != 3
            or not all(type(value) in (int, float) and math.isfinite(value) for value in position)):
        raise WorkerError("invalid pursuit enemy position")
    route = validated_route(data)
    if math.dist(route[0], position) > 3:
        raise WorkerError("pursuit route must start beside the bound enemy")
    if math.hypot(route[-1][0] - enemy["position"][0], route[-1][2] - enemy["position"][2]) < 8:
        raise WorkerError("pursuit route endpoint is not meaningfully displaced")
    return data


def validate_respawn_catalog(data):
    if (data.get("profile") != "sapphire-3.3" or data.get("version") != 1
            or data.get("homepoint") != 9 or data.get("territory") != 130):
        raise WorkerError("unsupported respawn catalog binding")
    pop = data.get("pop_range", {})
    if set(pop) != {"id", "position", "rotation"} or type(pop.get("id")) is not int or pop["id"] <= 0:
        raise WorkerError("invalid homepoint pop-range binding")
    for field in ("position", "rotation"):
        point = pop[field]
        if (not isinstance(point, list) or len(point) != 3
                or not all(type(value) in (int, float) and math.isfinite(value) and abs(value) < 1000
                           for value in point)):
            raise WorkerError("invalid homepoint transform")
    return data


def validate_shop_catalog(data):
    if data.get("profile") != "sapphire-3.3" or data.get("version") != 1 or data.get("territory") != 130:
        raise WorkerError("unsupported shop catalog profile/territory")
    if data.get("start_actor") != 1001289 or data.get("sale") != {"item": 4551, "quantity": 1, "gil": 28}:
        raise WorkerError("unsupported shop sale binding")
    if data.get("purchase") != {"shop_id": 262468, "index": 0, "item": 5890,
                               "quantity": 1, "gil": 8}:
        raise WorkerError("unsupported shop purchase binding")
    shop = data.get("shop", {})
    if (set(shop) != {"layout_id", "base_id", "event_id", "position"}
            or any(type(shop.get(key)) is not int or shop[key] <= 0
                   for key in ("layout_id", "base_id", "event_id"))
            or shop["event_id"] >> 16 != 4 or shop["event_id"] != data["purchase"]["shop_id"]):
        raise WorkerError("invalid gil-shop actor binding")
    route = validated_route(data)
    if math.dist(route[-1], shop["position"]) > 2:
        raise WorkerError("shop route must end within interaction range")
    return data


def validate_combat_catalog(data):
    expected = {"version": 1, "profile": "sapphire-3.3", "action": 9, "class_job": 1,
                "work_index": 1, "level": 1, "base_exp": 50,
                "category": 3, "cost_type": 5, "cost": 60, "range": -1,
                "cast_ms": 0, "recast_ms": 2500, "recast_group": 58,
                "effect_type": 1, "target_enemy": True}
    if any(type(data.get(key)) is not type(value) or data[key] != value for key, value in expected.items()):
        raise WorkerError("combat catalog does not match the supported level-one Fast Blade profile")
    return data


def load_pursuit_catalog(path):
    return validate_pursuit_catalog(json.loads(Path(path).read_text(encoding="utf-8")))


def load_respawn_catalog(path):
    return validate_respawn_catalog(json.loads(Path(path).read_text(encoding="utf-8")))


def load_shop_catalog(path):
    return validate_shop_catalog(json.loads(Path(path).read_text(encoding="utf-8")))


def load_combat_catalog(path):
    return validate_combat_catalog(json.loads(Path(path).read_text(encoding="utf-8")))


def load_transition_catalog(path):
    return validate_transition_catalog(json.loads(Path(path).read_text(encoding="utf-8")))


def load_quest_catalog(path, completed_quests=()):
    return validate_quest_catalog(json.loads(Path(path).read_text(encoding="utf-8")), completed_quests)

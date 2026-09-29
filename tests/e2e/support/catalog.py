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
    discovery = data.get("supported_discovery", {})
    if (discovery.get("id") != 3643706 or discovery.get("territory") != 141
            or discovery.get("kind") != "map_range" or discovery.get("enabled") is not True
            or discovery.get("discovery_enabled") is not True or discovery.get("shape") != 3
            or discovery.get("discovery_index") != 1 or discovery.get("map_id") != 21
            or discovery.get("map_discovery_index") != 8 or discovery.get("uint16_storage") is not True
            or discovery.get("map_discovery_flag") != 16382
            or discovery.get("level_one_exp_reward") != 15):
        raise WorkerError("unsupported source discovery binding")
    for point in (discovery.get("position", []), discovery.get("scale", []), discovery.get("rotation", [])):
        if len(point) != 3 or not all(type(x) in (int, float) and math.isfinite(x) and abs(x) < 1000 for x in point):
            raise WorkerError("invalid discovery transform")
    dcenter, dscale = discovery["position"], discovery["scale"]
    arrival = destinations[0]["position"]
    if (min(dscale[0], dscale[2]) <= 0
            or math.hypot(arrival[0] - dcenter[0], arrival[2] - dcenter[2]) > min(dscale[0], dscale[2]) * 0.5
            or abs(arrival[1] - dcenter[1]) > dscale[1] * 0.5):
        raise WorkerError("arrival is outside supported discovery range")
    discoveries = data.get("supported_discoveries", [])
    if len(discoveries) != 2 or discoveries[0] != discovery:
        raise WorkerError("unsupported discovery sequence")
    second = discoveries[1]
    if (second.get("id") != 4204061 or second.get("territory") != 141
            or second.get("kind") != "map_range" or second.get("enabled") is not True
            or second.get("discovery_enabled") is not True or second.get("shape") != 1
            or second.get("discovery_index") != 3 or second.get("map_id") != 21
            or second.get("map_discovery_index") != 8 or second.get("uint16_storage") is not True
            or second.get("map_discovery_flag") != 16382
            or second.get("level_one_exp_reward") != 15):
        raise WorkerError("unsupported second source discovery binding")
    second_nav = second.get("navigation", {})
    if (second_nav.get("format") != "TSET-v1" or second_nav.get("polyref_bits") not in (32, 64)
            or not str(second_nav.get("mesh", "")).replace("\\", "/").endswith("/w1f2/w1f2.nav")):
        raise WorkerError("unsupported second discovery navigation identity")
    second_route = second.get("route", [])
    second_length = sum(math.dist(a, b) for a, b in zip(second_route, second_route[1:]))
    if (len(second_route) < 2 or len(second_route) > 1000 or second.get("route_length", 0) <= 0
            or abs(second_length - second["route_length"]) > 0.01
            or math.dist(second_route[0], arrival) > 0.15):
        raise WorkerError("invalid second discovery route")
    for point in (*[second.get(key, []) for key in ("position", "scale", "rotation")], *second_route):
        if len(point) != 3 or not all(type(x) in (int, float) and math.isfinite(x) and abs(x) < 1000 for x in point):
            raise WorkerError("invalid second discovery transform/route")
    center, scale, rotation, endpoint = (second["position"], second["scale"],
                                          second["rotation"], second_route[-1])
    x, z = endpoint[0] - center[0], endpoint[2] - center[2]
    local_x = math.cos(rotation[1]) * x - math.sin(rotation[1]) * z
    local_z = math.sin(rotation[1]) * x + math.cos(rotation[1]) * z
    if (abs(local_x) > scale[0] * 0.5 or abs(local_z) > scale[2] * 0.5
            or abs(endpoint[1] - center[1]) > scale[1] * 0.5):
        raise WorkerError("second discovery route does not end in its source box")
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
    leash = validated_route({"route": data.get("leash_route") or [],
                             "route_length": data.get("leash_route_length")})
    if math.dist(leash[0], position) > 3:
        raise WorkerError("leash route must start beside the bound enemy")
    displacement = math.hypot(leash[-1][0] - position[0], leash[-1][2] - position[2])
    if displacement < 45 or data["leash_route_length"] > 70:
        raise WorkerError("leash route does not cross the bounded retreat distance")
    return data


def validate_opening_quest_catalog(data):
    if ({key: data.get(key) for key in ("version", "profile", "territory", "quest")} !=
            {"version": 1, "profile": "sapphire-3.3", "territory": 182, "quest": 66130}):
        raise WorkerError("unsupported opening quest catalog binding")
    expected = (("giver", 3969639, 1003987, [33.375702, 4.1, -151.994003]),
                ("recipient", 3969632, 1003988, [21.077101, 7.45, -78.8134]))
    for role, layout_id, base_id, position in expected:
        actor = data.get(role, {})
        if actor.get("layout_id") != layout_id or actor.get("base_id") != base_id \
                or not isinstance(actor.get("position"), list) \
                or len(actor["position"]) != 3 or math.dist(actor["position"], position) > 0.001:
            raise WorkerError(f"invalid Coming to Ul'dah {role} binding")
    if data.get("reward") != {"exp": 50, "gil": 103}:
        raise WorkerError("Coming to Ul'dah source reward mismatch")
    route = validated_route({"route": data.get("approach_route") or [],
                             "route_length": data.get("approach_route_length")})
    if math.dist(route[0], [42.0, 4.0, -157.6]) > 1 or math.dist(route[-1], data["giver"]["position"]) > 2:
        raise WorkerError("opening quest approach does not bind source start and giver")
    if data.get("completion_route_supported") is not False \
            or data.get("completion_route_blocker") != "incomplete navigation corridor" \
            or "completion_route" in data:
        raise WorkerError("opening quest completion must fail closed without a corridor")
    rings = data.get("starter_ring_items")
    if rings != [{"item": item, "equip_slot_category": 12, "stack_max": 1}
                 for item in (4423, 4424, 4425, 4426)]:
        raise WorkerError("opening ring equipment source binding mismatch")
    ranges = data.get("opening_event_ranges")
    if (not isinstance(ranges, list) or {row.get("id") for row in ranges} != {4101525, 4101535, 4101537}
            or any(row.get("shape") != 1 or row.get("enabled") is not False for row in ranges)):
        raise WorkerError("opening event-range source binding mismatch")
    binding = data.get("supported_range", {})
    if ({key: binding.get(key) for key in ("event_id", "param", "expected_scene")} !=
            {"event_id": 1245187, "param": 4101537, "expected_scene": 20}):
        raise WorkerError("unsupported opening range binding")
    range_route = validated_route(binding)
    source = next(row for row in ranges if row["id"] == 4101537)
    if math.dist(range_route[0], [42, 4, -157.6]) > 1 or math.dist(range_route[-1], source["position"]) > 0.25:
        raise WorkerError("opening range route does not bind source geometry")
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
                               "quantity": 3, "unit_gil": 8, "gil": 24,
                               "item_action": {"row": 232, "type": 852, "arg": 235}}:
        raise WorkerError("unsupported shop purchase binding")
    if data.get("equipment_purchase") != {"shop_id": 262468, "index": 11, "item": 3286,
                                         "quantity": 1, "gil": 39, "resale_gil": 39,
                                         "source_slot": 7, "gear_slot": 6}:
        raise WorkerError("unsupported shop equipment-purchase binding")
    if data.get("starter_liquidation") != {"item": 3296, "quantity": 1, "gil": 45}:
        raise WorkerError("unsupported starter-equipment liquidation binding")
    if data.get("starter_body_liquidation") != {"item": 2983, "quantity": 1, "gil": 59}:
        raise WorkerError("unsupported starter-body liquidation binding")
    if data.get("starter_feet_liquidation") != {"item": 3750, "quantity": 1, "gil": 48}:
        raise WorkerError("unsupported starter-feet liquidation binding")
    if data.get("second_equipment_purchase") != {
            "shop_id": 262468, "index": 9, "item": 3748, "quantity": 1, "gil": 54,
            "resale_gil": 54, "source_slot": 8, "gear_slot": 7}:
        raise WorkerError("unsupported second shop equipment-purchase binding")
    if data.get("third_equipment_purchase") != {
            "shop_id": 262468, "index": 3, "item": 2967, "quantity": 1, "gil": 59,
            "source_slot": 4, "gear_slot": 3}:
        raise WorkerError("unsupported third shop equipment-purchase binding")
    head = data.get("head_purchase", {})
    if ({key: head.get(key) for key in ("index", "item", "quantity", "gil", "source_slot", "gear_slot")} !=
            {"index": 0, "item": 2638, "quantity": 1, "gil": 47,
             "source_slot": 3, "gear_slot": 2}):
        raise WorkerError("unsupported source head-equipment purchase binding")
    head_shop = head.get("shop", {})
    if ({key: head_shop.get(key) for key in ("layout_id", "base_id", "event_id")} !=
            {"layout_id": 4393619, "base_id": 1005495, "event_id": 262415}
            or len(head_shop.get("position", [])) != 3
            or not all(type(value) in (int, float) and math.isfinite(value)
                       for value in head_shop["position"])):
        raise WorkerError("unsupported source head-shop actor binding")
    head_route = validated_route(head)
    if math.dist(head_route[0], data["shop"]["position"]) > 2 or \
       math.dist(head_route[-1], head_shop["position"]) > 2:
        raise WorkerError("head-shop route endpoints do not bind both exact shop actors")
    ear = data.get("ear_purchase", {})
    if ({key: ear.get(key) for key in ("index", "item", "quantity", "gil", "source_slot", "gear_slot")} !=
            {"index": 0, "item": 4200, "quantity": 1, "gil": 66,
             "source_slot": 9, "gear_slot": 8}):
        raise WorkerError("unsupported source ear-equipment purchase binding")
    ear_shop = ear.get("shop", {})
    if ({key: ear_shop.get(key) for key in ("layout_id", "base_id", "event_id")} !=
            {"layout_id": 4614930, "base_id": 1005900, "event_id": 262425}
            or len(ear_shop.get("position", [])) != 3
            or not all(type(value) in (int, float) and math.isfinite(value)
                       for value in ear_shop["position"])):
        raise WorkerError("unsupported source ear-shop actor binding")
    ear_route = validated_route(ear)
    if math.dist(ear_route[0], head_shop["position"]) > 2 or \
       math.dist(ear_route[-1], ear_shop["position"]) > 2:
        raise WorkerError("ear-shop route endpoints do not bind both exact shop actors")
    neck = data.get("neck_purchase", {})
    if ({key: neck.get(key) for key in ("index", "item", "quantity", "gil", "source_slot", "gear_slot")} !=
            {"index": 1, "item": 15130, "quantity": 1, "gil": 168,
             "source_slot": 10, "gear_slot": 9}):
        raise WorkerError("unsupported source neck-equipment purchase binding")
    neck_shop = neck.get("shop", {})
    if ({key: neck_shop.get(key) for key in ("layout_id", "base_id", "event_id")} !=
            {"layout_id": 4067692, "base_id": 1004417, "event_id": 262640}
            or len(neck_shop.get("position", [])) != 3
            or not all(type(value) in (int, float) and math.isfinite(value)
                       for value in neck_shop["position"])):
        raise WorkerError("unsupported source neck-shop actor binding")
    neck_route = validated_route(neck)
    if math.dist(neck_route[0], ear_shop["position"]) > 2 or \
       math.dist(neck_route[-1], neck_shop["position"]) > 2:
        raise WorkerError("neck-shop route endpoints do not bind both exact shop actors")
    if data.get("wrist_purchase") != {"shop_id": 262640, "index": 2, "item": 15132,
                                       "quantity": 1, "gil": 168,
                                       "source_slot": 11, "gear_slot": 10}:
        raise WorkerError("unsupported source wrist-equipment purchase binding")
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
    sprint = {"action": 3, "class_job": 0, "work_index": -1, "level": 0, "base_exp": 45,
              "category": 0, "cost_type": 18, "cost": 0, "range": 0,
              "cast_ms": 0, "recast_ms": 30000, "recast_group": 56,
              "effect_type": 1, "target_enemy": False}
    if data.get("sprint") != sprint:
        raise WorkerError("combat catalog does not match the supported level-zero Sprint profile")
    living_return = {"action": 6, "class_job": 0, "work_index": -1, "level": 0,
                     "base_exp": 45, "category": 10, "cost_type": 0, "cost": 0,
                     "range": 0, "cast_ms": 5000, "recast_ms": 900000,
                     "recast_group": 57, "effect_type": 1, "target_enemy": False}
    if data.get("return") != living_return:
        raise WorkerError("combat catalog does not match the supported level-zero Return profile")
    bootshine = {"action": 53, "class_job": 2, "work_index": 0, "level": 1, "base_exp": 50,
                 "category": 3, "cost_type": 5, "cost": 60, "range": -1,
                 "cast_ms": 0, "recast_ms": 2500, "recast_group": 58,
                 "effect_type": 1, "target_enemy": True}
    if data.get("bootshine") != bootshine:
        raise WorkerError("combat catalog does not match the supported level-one Bootshine profile")
    blizzard = {"action": 142, "class_job": 7, "work_index": 5, "level": 1, "base_exp": 50,
                "category": 2, "cost_type": 3, "cost": 4, "range": 25,
                "cast_ms": 2500, "recast_ms": 2500, "recast_group": 58,
                "effect_type": 1, "target_enemy": True}
    if data.get("blizzard") != blizzard:
        raise WorkerError("combat catalog does not match the supported level-one Blizzard profile")
    return data


def load_opening_quest_catalog(path):
    return validate_opening_quest_catalog(json.loads(Path(path).read_text(encoding="utf-8")))


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

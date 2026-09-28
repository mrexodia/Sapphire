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
    route = data.get("route", [])
    if not 2 <= len(route) <= 2048:
        raise WorkerError("quest requires a complete bounded navigation route")
    for point in route:
        if len(point) != 3 or not all(isinstance(x, (int, float)) and math.isfinite(x) and abs(x) < 1000 for x in point):
            raise WorkerError("invalid route position")
    lengths = [math.dist(a, b) for a, b in zip(route, route[1:])]
    if max(lengths) > 2 or sum(lengths) > 500:
        raise WorkerError("route contains a jump or exceeds distance budget")
    if not math.isclose(sum(lengths), data.get("route_length", -1), rel_tol=1e-5, abs_tol=0.01):
        raise WorkerError("route length metadata mismatch")
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


def load_quest_catalog(path, completed_quests=()):
    return validate_quest_catalog(json.loads(Path(path).read_text(encoding="utf-8")), completed_quests)

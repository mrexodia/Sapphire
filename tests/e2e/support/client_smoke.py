"""Policy for the separate, manually operated real-client compatibility lane.

Screenshots require explicit review; received headless state cannot certify rendering.
"""
from __future__ import annotations

import math

CLIENT_SHA256 = "d818584c782bbe3cacbc2b306391e6f3246bc3065c517a3324784e49d572ba12"
CLIENT_VERSION = "2016.07.05.0000.0001"
REAL_SAY = "E2E real client verified"
WITNESS_SAY = "E2E independent witness"
REVIEW_CHECKS = ["fixture_character_in_world", "witness_say_rendered"]


def position(value):
    if (not isinstance(value, list) or len(value) != 3 or
            any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) >= 1000 for v in value)):
        raise ValueError("invalid received position")
    return value


def other_player(state, expected=None, allow_absent=False):
    if (state["phase"] != "ready" or state["gm_rank"] != 0 or state["territory"] != 130 or
            state["between_areas"] or state["scene"] is not None):
        raise ValueError("witness no longer ready in public territory")
    peers = [(int(key), actor) for key, actor in state["actors"].items()
             if actor["kind"] == 1 and int(key) != state["entity_id"]]
    if not peers:
        if expected is not None and not allow_absent:
            raise ValueError("real player disappeared before logout")
        return None
    if len(peers) != 1:
        raise ValueError("ambiguous real-player identity")
    entity, actor = peers[0]
    if expected is not None and entity != expected:
        raise ValueError("real-player identity changed")
    if actor["gm_rank"] != 0 or actor["level"] != 1 or actor["hp"] <= 0:
        raise ValueError("unexpected real-player fixture state")
    position(actor["position"])
    return entity, actor


def moved(origin, current):
    distance = math.dist(position(origin), position(current))
    if distance > 5:
        raise ValueError("smoke movement exceeded five-metre bound")
    return distance >= 1


def validate_review(review, ticket):
    expected = {"version": 1, "run": ticket["run"], "frame_sha256": ticket["frame_sha256"],
                "checks": REVIEW_CHECKS, "manual_review": True}
    if review != expected or type(review.get("version")) is not int or review.get("manual_review") is not True:
        raise ValueError("explicit manual review of this run's exact frame is required")
    return review

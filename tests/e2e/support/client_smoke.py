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


def real_spawn_baseline(state):
    """Require no player before graphical launch and retain received sequence."""
    if other_player(state) is not None:
        raise ValueError("unexpected player before real-client launch")
    sequence = state.get("seq")
    if type(sequence) is not int or not 0 <= sequence < 2**64:
        raise ValueError("real-client spawn baseline lacks a received sequence")
    return sequence


def received_real_spawn(state, expected_name, fixture_position, baseline):
    """Return a fresh exact-name fixture spawn, or None while absent."""
    if (not isinstance(expected_name, str) or not 1 <= len(expected_name) <= 31
            or type(baseline) is not int or not 0 <= baseline < 2**64):
        raise ValueError("real-client spawn expectation is invalid")
    peer = other_player(state)
    if peer is None:
        return None
    entity, actor = peer
    sequence = state.get("seq")
    if (actor.get("name") != expected_name or type(sequence) is not int
            or not baseline < sequence < 2**64
            or math.dist(position(actor.get("position")), position(fixture_position)) > 1):
        raise ValueError("real-client spawn is stale, foreign, or outside the fixture")
    return {"verified": True,
            "scope": "fresh-exact-fixture-real-client-spawn-not-client-provenance",
            "entity_id": entity, "name": expected_name, "gm_rank": 0, "level": 1,
            "position": list(actor["position"]), "baseline_sequence": baseline,
            "received_sequence": sequence}


def real_movement_baseline(state, expected_entity, origin):
    """Reject displacement that occurred before the authored movement window."""
    _, actor = other_player(state, expected_entity)
    sequence = state.get("seq")
    if (type(sequence) is not int or not 0 <= sequence < 2**64
            or math.dist(position(origin), position(actor.get("position"))) > 0.15):
        raise ValueError("real-client movement baseline is stale or displaced")
    return {"sequence": sequence, "position": list(actor["position"])}


def received_real_movement(state, expected_entity, origin, baseline):
    """Return one independently received bounded displacement, or None while waiting."""
    if (not isinstance(baseline, dict) or set(baseline) != {"sequence", "position"}
            or type(baseline.get("sequence")) is not int
            or not 0 <= baseline["sequence"] < 2**64
            or not position(baseline.get("position"))
            or math.dist(position(origin), baseline["position"]) > 0.15):
        raise ValueError("real-client movement baseline receipt is invalid")
    _, actor = other_player(state, expected_entity)
    sequence = state.get("seq")
    if type(sequence) is not int or not baseline["sequence"] <= sequence < 2**64:
        raise ValueError("real-client movement observation lacks a valid sequence")
    current = position(actor.get("position"))
    distance = math.dist(position(origin), current)
    if distance < 1:
        return None
    if not moved(origin, current) or sequence <= baseline["sequence"]:
        raise ValueError("real-client movement is stale, excessive, or not freshly received")
    return {"verified": True,
            "scope": "fresh-bounded-real-client-movement-received-by-independent-witness",
            "actor": expected_entity, "origin": list(origin),
            "baseline_position": list(baseline["position"]),
            "received_position": list(current), "baseline_sequence": baseline["sequence"],
            "received_sequence": sequence, "movement_metres": distance}


def real_say_baseline(state, expected_entity):
    """Reject a pre-sent fixed challenge before opening its received-state window."""
    other_player(state, expected_entity)
    sequence = state.get("seq")
    if type(sequence) is not int or not 0 <= sequence < 2**64:
        raise ValueError("real-client Say baseline lacks a received sequence")
    chat = state.get("chat")
    if not isinstance(chat, list):
        raise ValueError("real-client Say baseline lacks received chat history")
    if any(isinstance(row, dict) and row.get("actor") == expected_entity
           and row.get("message") == REAL_SAY for row in chat):
        raise ValueError("real-client Say challenge was already present at baseline")
    return sequence


def received_real_say(state, expected_entity, baseline):
    """Return one fresh ordinary Say receipt, or None while it has not arrived."""
    other_player(state, expected_entity)
    sequence, chat = state.get("seq"), state.get("chat")
    if (type(baseline) is not int or not 0 <= baseline < 2**64
            or type(sequence) is not int or not baseline <= sequence < 2**64
            or not isinstance(chat, list)):
        raise ValueError("real-client Say observation lacks a valid sequence window")
    matches = [row for row in chat if isinstance(row, dict)
               and row.get("actor") == expected_entity and row.get("message") == REAL_SAY]
    if not matches:
        return None
    if len(matches) != 1:
        raise ValueError("real-client Say observation is ambiguous")
    row = matches[0]
    if (set(row) != {"actor", "kind", "message", "token"}
            or type(row.get("actor")) is not int or row["actor"] != expected_entity
            or type(row.get("kind")) is not int or row["kind"] != 10
            or type(row.get("token")) is not int
            or not baseline < row["token"] <= sequence):
        raise ValueError("real-client Say is stale, malformed, or not ordinary Say")
    return {"verified": True,
            "scope": "fresh-ordinary-real-client-say-received-by-independent-witness",
            "actor": expected_entity, "message": REAL_SAY, "kind": 10,
            "baseline_sequence": baseline, "message_token": row["token"],
            "received_sequence": sequence}


def validate_review(review, ticket):
    expected = {"version": 1, "run": ticket["run"], "frame_sha256": ticket["frame_sha256"],
                "checks": REVIEW_CHECKS, "manual_review": True}
    if review != expected or type(review.get("version")) is not int or review.get("manual_review") is not True:
        raise ValueError("explicit manual review of this run's exact frame is required")
    return review

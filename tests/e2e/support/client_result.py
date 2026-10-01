"""Read-only verification of a current development-enabled graphical guest result.

This validates structured/received evidence before the separate operator Sandbox
disposal check. It does not inspect pixels or prove rendering, server exclusion,
 reset authority, or VM disposal.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from .client_development import (require_graphical_check, require_graphical_decline_check,
                                 require_graphical_run_pair)
from .client_smoke import (CLIENT_SHA256, other_player,
                           real_logout_baseline, real_movement_baseline,
                           real_say_baseline, real_spawn_baseline,
                           received_real_logout, received_real_movement,
                           received_real_say, received_real_spawn, validate_review,
                           witness_say_challenge)
from .development import (DevelopmentError, position, received_character_identity,
                          require_normal_worker_exit)


RESULT_SCOPE = "current-graphical-development-result-before-separate-sandbox-disposal"
PAIR_SCOPE = "same-dedicated-bot-identities-across-distinct-runs-not-offline-or-reset-proof"
HANDOFF_SCOPE = "same-dedicated-witness-across-normal-handoff-not-offline-exclusion"
RESTORATION_SCOPE = "fresh-paired-witness-login-and-viewer-presence-not-offline-exclusion"
RETIREMENT_SCOPE = "normal-witness-session-retirement-not-offline-exclusion"
DEADLINE_SCOPE = "cooperative-manual-activity-success-deadline-not-hard-cleanup-limit"


def _read_json(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DevelopmentError(f"cannot read graphical result evidence: {path.name}") from error
    if not isinstance(value, dict):
        raise DevelopmentError(f"graphical result evidence is not an object: {path.name}")
    return value


def _sha256(path):
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise DevelopmentError(f"cannot hash graphical result evidence: {path.name}") from error


def _hex(value, length):
    return (isinstance(value, str) and len(value) == length
            and all(char in "0123456789abcdef" for char in value))


def _typed_equal(value, expected):
    if type(value) is not type(expected):
        return False
    if isinstance(expected, dict):
        return (set(value) == set(expected)
                and all(_typed_equal(value[key], expected[key]) for key in expected))
    if isinstance(expected, list):
        return (len(value) == len(expected)
                and all(_typed_equal(left, right) for left, right in zip(value, expected)))
    return value == expected


def _retirement(value, bot):
    if (not isinstance(value, dict)
            or set(value) != {"bot", "server_close_observed", "native_bot_removed", "scope"}
            or value.get("bot") != bot
            or value.get("server_close_observed") is not True
            or value.get("native_bot_removed") is not True
            or value.get("scope") != RETIREMENT_SCOPE):
        raise DevelopmentError("invalid graphical witness retirement receipt")
    return value


def _activity_deadline(value):
    if (not isinstance(value, dict)
            or set(value) != {"enabled", "limit_seconds", "expired",
                              "activity_and_worker_exit_completed_within_budget", "scope",
                              "environment_cleanup_may_exceed_deadline"}
            or value.get("enabled") is not True
            or type(value.get("limit_seconds")) is not int or value["limit_seconds"] != 1200
            or value.get("expired") is not False
            or value.get("activity_and_worker_exit_completed_within_budget") is not True
            or value.get("scope") != DEADLINE_SCOPE
            or value.get("environment_cleanup_may_exceed_deadline") is not True):
        raise DevelopmentError("invalid or incomplete graphical activity deadline receipt")
    return value


def _timing(value):
    phases = ["setup", "spawn", "movement", "say", "review", "development",
              "logout", "witness_retirement", "cleanup"]
    note = ("Includes operator waits and worker unwinding; cleanup is client/environment "
            "teardown. Not gameplay CPU time.")
    if (not isinstance(value, dict)
            or set(value) != {"version", "scope", "elapsed_seconds", "phases", "note"}
            or type(value.get("version")) is not int or value["version"] != 1
            or value.get("scope") != "manual-client-phase-wall-time-not-coverage"
            or value.get("note") != note
            or not isinstance(value.get("phases"), list)
            or [row.get("phase") if isinstance(row, dict) else None
                for row in value["phases"]] != phases):
        raise DevelopmentError("invalid graphical phase timing receipt")
    seconds = []
    for row in value["phases"]:
        number = row.get("seconds")
        if (set(row) != {"phase", "seconds"} or type(number) not in (int, float)
                or not math.isfinite(number) or number < 0):
            raise DevelopmentError("invalid graphical phase timing row")
        seconds.append(number)
    elapsed = value.get("elapsed_seconds")
    if (type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0
            or not math.isclose(sum(seconds), elapsed, rel_tol=0, abs_tol=1e-6)):
        raise DevelopmentError("graphical phase timing total does not match rows")
    return value


def _outer_journey(report, pair, fixture):
    states = {key: report.get(key) for key in
              ("pre_client_state", "spawn", "movement_baseline", "movement",
               "say_baseline", "say", "review", "logout_baseline", "logout")}
    if any(not isinstance(value, dict) for value in states.values()):
        raise DevelopmentError("graphical outer received-state journey is incomplete")
    expected_self = pair["identities"][0]
    try:
        initial_identity = received_character_identity(
            states["pre_client_state"], report.get("witness_name"))
        if (not _typed_equal(initial_identity, expected_self)
                or type(states["pre_client_state"].get("entity_id")) is not int
                or states["pre_client_state"]["entity_id"] != expected_self["entity_id"]):
            raise DevelopmentError("graphical initial witness differs from paired mover")
        spawn_baseline = real_spawn_baseline(states["pre_client_state"])
        spawn_receipt = received_real_spawn(
            states["spawn"], report["real_name"], fixture["position"], spawn_baseline)
        if (spawn_receipt is None or spawn_receipt["entity_id"] != report["real_entity"]
                or not _typed_equal(report.get("real_spawn_receipt"), spawn_receipt)):
            raise DevelopmentError("graphical result lacks exact fresh fixture spawn evidence")
        observations = {}
        for stage in ("spawn", "movement_baseline", "movement", "say_baseline",
                      "say", "review", "logout_baseline"):
            state = states[stage]
            if (type(state.get("entity_id")) is not int
                    or state["entity_id"] != expected_self["entity_id"]
                    or not _typed_equal(received_character_identity(
                        state, report["witness_name"]), expected_self)):
                raise DevelopmentError("graphical outer witness identity changed")
            entity, actor = other_player(state, report["real_entity"])
            if actor.get("name") != report["real_name"]:
                raise DevelopmentError("graphical outer viewer name changed")
            observations[stage] = (entity, actor)
        if math.dist(observations["spawn"][1]["position"], fixture["position"]) > 1:
            raise DevelopmentError("graphical viewer did not spawn at the bounded fixture")
        origin = observations["spawn"][1]["position"]
        movement_baseline = real_movement_baseline(
            states["movement_baseline"], report["real_entity"], origin)
        movement_receipt = received_real_movement(
            states["movement"], report["real_entity"], origin, movement_baseline)
        if (movement_receipt is None
                or not _typed_equal(report.get("real_movement_receipt"), movement_receipt)):
            raise DevelopmentError("graphical result lacks exact fresh movement evidence")
        distance = movement_receipt["movement_metres"]
        recorded_distance = report.get("observed_movement_metres")
        if (type(recorded_distance) not in (int, float) or not math.isfinite(recorded_distance)
                or not math.isclose(recorded_distance, distance, rel_tol=0, abs_tol=1e-9)):
            raise DevelopmentError("graphical movement distance differs from received snapshots")
        baseline = real_say_baseline(states["say_baseline"], report["real_entity"])
        say_receipt = received_real_say(states["say"], report["real_entity"], baseline)
        if say_receipt is None or not _typed_equal(report.get("real_say_receipt"), say_receipt):
            raise DevelopmentError("graphical result lacks exact fresh real-client Say evidence")
        logout_baseline = real_logout_baseline(
            states["logout_baseline"], report["real_entity"], report["real_name"])
        logout_receipt = received_real_logout(
            states["logout"], report["real_entity"], logout_baseline)
        if (logout_receipt is None
                or not _typed_equal(report.get("real_logout_receipt"), logout_receipt)):
            raise DevelopmentError("graphical result lacks exact fresh logout absence evidence")
        if (type(states["logout"].get("entity_id")) is not int
                or states["logout"]["entity_id"] != expected_self["entity_id"]
                or not _typed_equal(received_character_identity(
                    states["logout"], report["witness_name"]), expected_self)):
            raise DevelopmentError("graphical final logout witness differs from paired mover")
    except (KeyError, TypeError, ValueError) as error:
        raise DevelopmentError("invalid graphical outer received-state journey") from error
    return {"verified": True,
            "scope": "received-real-client-spawn-movement-say-review-logout-not-rendering",
            "viewer_entity": report["real_entity"], "movement_metres": distance,
            "spawn_scope": spawn_receipt["scope"],
            "movement_scope": movement_receipt["scope"],
            "say_scope": say_receipt["scope"],
            "logout_scope": logout_receipt["scope"]}


def _pair_dependent_receipts(report, pair):
    identities = pair["identities"]
    handoff = report.get("development_witness_handoff")
    if (not isinstance(handoff, dict)
            or set(handoff) != {"verified", "scope", "identity", "retirement_scope",
                               "comprehensive_run_id", "decline_run_id"}
            or handoff.get("verified") is not True or handoff.get("scope") != HANDOFF_SCOPE
            or not _typed_equal(handoff.get("identity"), identities[0])
            or handoff.get("retirement_scope") != RETIREMENT_SCOPE
            or handoff.get("comprehensive_run_id") != pair["comprehensive_run_id"]
            or handoff.get("decline_run_id") != pair["decline_run_id"]):
        raise DevelopmentError("invalid graphical original-witness handoff receipt")
    restoration = report.get("logout_witness_restoration")
    viewer = restoration.get("viewer") if isinstance(restoration, dict) else None
    if (not isinstance(restoration, dict)
            or set(restoration) != {"verified", "scope", "identity", "viewer",
                                   "received_sequence"}
            or restoration.get("verified") is not True
            or restoration.get("scope") != RESTORATION_SCOPE
            or not _typed_equal(restoration.get("identity"), identities[0])
            or not isinstance(viewer, dict)
            or set(viewer) != {"entity_id", "name", "gm_rank", "position", "presence_token"}
            or viewer.get("entity_id") != report.get("real_entity")
            or viewer.get("name") != report.get("real_name") or viewer.get("gm_rank") != 0
            or not position(viewer.get("position"))
            or type(viewer.get("presence_token")) is not int
            or type(restoration.get("received_sequence")) is not int
            or not 0 <= viewer["presence_token"] <= restoration["received_sequence"] < 2**64):
        raise DevelopmentError("invalid graphical final-witness restoration receipt")


def inspect_client_development_result(output, expected_source_revision):
    """Validate a current result directory without changing it or claiming disposal."""
    output = Path(output)
    if not output.is_dir():
        raise DevelopmentError("graphical output directory is missing")
    result_path = output / "result.json"
    report = _read_json(result_path)
    run_id, viewer_name, viewer_entity = (report.get("run"), report.get("real_name"),
                                           report.get("real_entity"))
    if (not _hex(expected_source_revision, 40)
            or report.get("source_revision") != expected_source_revision
            or type(report.get("version")) is not int or report["version"] != 1
            or report.get("status") != "passed"
            or report.get("scope") != "manual-real-client-login-movement-say-logout"
            or not _hex(run_id, 32)
            or not isinstance(viewer_name, str) or not 1 <= len(viewer_name) <= 31
            or type(viewer_entity) is not int or viewer_entity <= 0
            or report.get("client_sha256") != CLIENT_SHA256
            or report.get("sandbox_disposal") != "operator_required"
            or report.get("runtime_removed") is not True):
        raise DevelopmentError("graphical result is not a current successful pre-disposal result")
    fixture = report.get("fixture")
    if (not isinstance(fixture, dict)
            or set(fixture) != {"position", "territory", "catalog_sha256",
                               "placement_is_travel", "development_check"}
            or not position(fixture.get("position")) or fixture.get("territory") != 130
            or not _hex(fixture.get("catalog_sha256"), 64)
            or fixture.get("placement_is_travel") is not False
            or fixture.get("development_check") is not True):
        raise DevelopmentError("invalid graphical development fixture boundary")

    main_path = output / "development" / "development-summary.json"
    decline_path = output / "development-decline" / "development-summary.json"
    main, decline = _read_json(main_path), _read_json(decline_path)
    main_hash, decline_hash = _sha256(main_path), _sha256(decline_path)
    main_proof = require_graphical_check(main, viewer_name, viewer_entity)
    decline_proof = require_graphical_decline_check(decline, viewer_name, viewer_entity)
    main_check, decline_check = report.get("development_check"), report.get("decline_check")
    for check, nested, digest, proof in ((main_check, main, main_hash, main_proof),
                                         (decline_check, decline, decline_hash, decline_proof)):
        if (not isinstance(check, dict)
                or set(check) != {"requested", "status", "summary_sha256",
                                  "elapsed_seconds", "evidence"}
                or check.get("requested") is not True or check.get("status") != "passed"
                or check.get("summary_sha256") != digest
                or not _typed_equal(check.get("elapsed_seconds"), nested.get("elapsed_seconds"))
                or not _typed_equal(check.get("evidence"), proof)):
            raise DevelopmentError("graphical nested result/hash/evidence mismatch")
    if (fixture["catalog_sha256"] != main.get("catalog_sha256")
            or math.dist(fixture["position"], main["movement_verification"]["authored_route"][0]) > 0.15):
        raise DevelopmentError("graphical fixture does not bind the comprehensive route/catalog")

    names = [row["name"] for row in main["sprint_verification"]["identities"]]
    pair = require_graphical_run_pair(main, decline, names, main["worker_sha256"])
    if (not _typed_equal(report.get("development_run_pair"), pair)
            or pair["scope"] != PAIR_SCOPE):
        raise DevelopmentError("graphical result does not retain the exact nested run pair")
    if (report.get("witness_name") != identities_name(pair, 0)
            or viewer_name.casefold() in {name.casefold() for name in names}):
        raise DevelopmentError("graphical viewer/witness identities are not separate and bound")
    outer_journey = _outer_journey(report, pair, fixture)
    _pair_dependent_receipts(report, pair)

    retirements = report.get("witness_retirements")
    if (not isinstance(retirements, list) or len(retirements) != 2):
        raise DevelopmentError("graphical result requires two exact witness retirements")
    _retirement(retirements[0], "witness")
    _retirement(retirements[1], "witness-after-development")
    require_normal_worker_exit({"worker_exit": report.get("observer_worker_exit")})
    deadline = _activity_deadline(report.get("activity_deadline"))
    timing = _timing(report.get("timing"))

    ticket = _read_json(output / "review-ticket.json")
    review = _read_json(output / "review.json")
    challenge = witness_say_challenge(run_id)
    if (not _typed_equal(report.get("manual_review"), review) or ticket.get("run") != run_id
            or report.get("witness_say_challenge") != challenge
            or ticket.get("witness_say_challenge") != challenge
            or not _hex(ticket.get("frame_sha256"), 64)
            or _sha256(output / "review.png") != ticket["frame_sha256"]):
        raise DevelopmentError("graphical manual-review frame binding is invalid")
    try:
        validate_review(review, ticket)
    except ValueError as error:
        raise DevelopmentError("graphical manual-review receipt is invalid") from error
    logout = output / "logout.png"
    if not logout.is_file() or logout.stat().st_size <= 0:
        raise DevelopmentError("graphical logout screenshot is missing")
    expected_logout = f"[{viewer_entity}] Zone IPC : StartLogoutCountdown"
    if report.get("logout_request") != expected_logout:
        raise DevelopmentError("graphical ordinary logout marker is missing or foreign")
    status = _read_json(output / "status.json")
    if (status.get("run") != run_id or status.get("phase") != "finished"
            or status.get("status") != "passed"):
        raise DevelopmentError("graphical terminal status is not bound to the passing result")

    return {"version": 1, "status": "accepted", "scope": RESULT_SCOPE,
            "run": run_id, "source_revision": expected_source_revision,
            "result_sha256": _sha256(result_path),
            "development_summary_sha256": main_hash,
            "decline_summary_sha256": decline_hash,
            "worker_sha256": pair["worker_sha256"],
            "outer_journey": outer_journey,
            "activity_deadline": deadline, "timing": timing,
            "runtime_removed": True, "sandbox_disposal_verified": False,
            "note": "Structured current guest evidence only; inspect rendering and dispose the owned Sandbox separately."}


def identities_name(pair, index):
    identities = pair.get("identities") if isinstance(pair, dict) else None
    if not isinstance(identities, list) or len(identities) != 2:
        raise DevelopmentError("invalid graphical paired identities")
    row = identities[index]
    if not isinstance(row, dict) or not isinstance(row.get("name"), str):
        raise DevelopmentError("invalid graphical paired identity name")
    return row["name"]

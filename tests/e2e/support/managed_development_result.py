"""Read-only correlation of one managed development run and terminal owned host.

This validates retained structured received-state evidence plus lifecycle/provenance
boundaries. It does not prove rendering, offline exclusion, reset authority,
external-server identity, shared-world cleanliness, or acceptance coverage.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from .development import (DevelopmentError, require_managed_host_binding,
                          require_normal_worker_exit)
from .client_development import (INVENTORY_SCOPE, require_decline_receipt,
                                 require_equipment_receipt, require_inventory_projection,
                                 require_movement_receipt, require_party_receipt,
                                 require_reconnect_receipt, require_say_receipt,
                                 require_shared_runner_metadata,
                                 require_sprint_receipt, require_tell_receipt)
from .development_host_result import inspect_owned_development_host
from .development_artifact import RUN_SCOPE, require_worker_artifacts
from .development_lease import require_clear_terminal_account_leases
from .development_placement import require_placement_receipt

SCOPE = "managed-development-received-evidence-and-terminal-owned-host-correlation"


def _read(path, label):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DevelopmentError(f"cannot read managed development {label}") from error
    if not isinstance(value, dict):
        raise DevelopmentError(f"managed development {label} is not an object")
    return value


def _sha256(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError as error:
        raise DevelopmentError("cannot hash managed development summary") from error


def _hex(value, length):
    return (isinstance(value, str) and len(value) == length
            and all(char in "0123456789abcdef" for char in value))


def validate_requested_checks(report):
    movement_value = report.get("movement_verification")
    movement_requested = (isinstance(movement_value, dict)
                          and movement_value.get("requested") is True)
    placement_requested = report.get("administrative_preparation_wait_enabled") is True
    require_shared_runner_metadata(
        report, catalog_required=movement_requested or placement_requested,
        administrative_preparation_allowed=True)
    deadline = report.get("run_deadline")
    if (not isinstance(deadline, dict)
            or set(deadline) != {"enabled","limit_seconds","expired",
                                 "session_work_completed_within_budget","scope",
                                 "cleanup_may_exceed_deadline"}
            or deadline.get("enabled") is not True
            or type(deadline.get("limit_seconds")) is not int
            or not 1 <= deadline["limit_seconds"] <= 900
            or deadline.get("expired") is not False
            or deadline.get("session_work_completed_within_budget") is not True
            or deadline.get("scope") != "cooperative-success-deadline-not-hard-process-limit"
            or deadline.get("cleanup_may_exceed_deadline") is not True):
        raise DevelopmentError("managed development success deadline is missing or failed")
    entities, territory, run_id = report.get("entities"), report.get("territory"), report.get("run_id")
    if (not isinstance(entities, list) or len(entities) != 2
            or any(type(value) is not int or value <= 0 for value in entities)
            or len(set(entities)) != 2 or type(territory) is not int or territory != 130):
        raise DevelopmentError("managed development entities or territory are invalid")
    say = require_say_receipt(report.get("say_verification"), entities,
                              report.get("cycles"), run_id)
    checks = {"say":say["scope"]}
    values = {name:report.get(f"{name}_verification") for name in
              ("movement","party","tell","reconnect","inventory","sprint","equipment","decline")}
    for name, value in values.items():
        if not isinstance(value, dict) or type(value.get("requested")) is not bool:
            raise DevelopmentError("managed development check request state is invalid")
        if value["requested"] is False:
            if value != {"requested":False,"verified":False}:
                raise DevelopmentError("unrequested managed development check has evidence")
        elif value.get("verified") is not True:
            raise DevelopmentError("requested managed development check did not verify")
    movement = None
    if values["movement"]["requested"]:
        movement = require_movement_receipt(values["movement"], entities, report.get("cycles"),
                                            report.get("movement_waypoints_per_cycle"),
                                            report.get("catalog_sha256"))
        checks["movement"] = movement["scope"]
    placement = require_placement_receipt(
        report.get("placement_verification"), entities, report.get("catalog_sha256"),
        movement["authored_route"] if movement is not None else None, placement_requested)
    if placement is not None:
        checks["placement"] = placement["scope"]
    party = None
    if values["party"]["requested"]:
        party = require_party_receipt(values["party"], entities, run_id, territory)
        checks["party"] = party["scope"]
    if values["tell"]["requested"]:
        checks["tell"] = require_tell_receipt(values["tell"], entities, run_id)["scope"]
    normal_inventory = None
    if values["inventory"]["requested"]:
        value = values["inventory"]
        if (set(value) != {"requested","verified","scope","before","after","changed_slots"}
                or value.get("scope") != INVENTORY_SCOPE or value.get("changed_slots") != []):
            raise DevelopmentError("managed reconnect inventory receipt is invalid")
        before, after = require_inventory_projection(value.get("before")), require_inventory_projection(value.get("after"))
        if before["inventory"] != after["inventory"]:
            raise DevelopmentError("managed reconnect inventory projection changed")
        normal_inventory = before
        checks["inventory"] = INVENTORY_SCOPE
    equipment = None
    if values["equipment"]["requested"]:
        if normal_inventory is None:
            raise DevelopmentError("managed equipment check lacks inventory projection")
        equipment = require_equipment_receipt(values["equipment"], entities, territory, normal_inventory)
        checks["equipment"] = equipment["scope"]
    reconnect = None
    if values["reconnect"]["requested"]:
        identity = equipment["identity"] if equipment is not None else values["reconnect"].get("identity_before")
        if (not isinstance(identity, dict) or identity.get("entity_id") != entities[0]
                or party is not None and identity != party["identities"][0]):
            raise DevelopmentError("managed reconnect identity differs from the exact bot")
        reconnect = require_reconnect_receipt(values["reconnect"], identity, territory)
        if movement is not None and math.dist(
                movement["authored_route"][0], reconnect["expected_position"]) > 0.15:
            raise DevelopmentError("managed movement and reconnect origins disagree")
        checks["reconnect"] = reconnect["scope"]
    elif values["inventory"]["requested"] or values["equipment"]["requested"]:
        raise DevelopmentError("managed persistence evidence lacks reconnect check")
    if values["sprint"]["requested"]:
        checks["sprint"] = require_sprint_receipt(values["sprint"], entities)["scope"]
    if values["decline"]["requested"]:
        if party is not None:
            raise DevelopmentError("party and decline require separate fresh runs")
        checks["decline"] = require_decline_receipt(values["decline"], entities)["scope"]
    viewer = report.get("viewer_verification")
    if viewer != {"requested":False,"verified":False,
                  "scope":"two-endpoint-say-and-persistent-witness-presence-not-rendering",
                  "viewer_login_or_control_performed":False}:
        raise DevelopmentError("managed result requires a separate graphical viewer inspector")
    return checks


def inspect_managed_development_run(session_dir, summary_path):
    session_dir, summary_path = Path(session_dir).resolve(), Path(summary_path).resolve()
    host = inspect_owned_development_host(session_dir)
    terminal = _read(session_dir / "status.json", "terminal host status")
    report = _read(summary_path, "run summary")
    run_id = report.get("run_id")
    if (type(report.get("version")) is not int or report["version"] != 1
            or report.get("status") != "passed"
            or report.get("scope") != "shared-development-not-acceptance"
            or not _hex(run_id, 32)
            or report.get("server_identity_verified") is not False
            or report.get("server_processes_owned") is not False
            or report.get("database_access") is not False
            or report.get("account_reset_performed_by_runner") is not False
            or report.get("world_restart_performed") is not False
            or report.get("lease_retained") is not False
            or report.get("worker_closed") is not True
            or report.get("lease_snapshot_matches_run_state") is not True):
        raise DevelopmentError("managed development run boundary is not passing or remains mutable")
    worker_artifacts = require_worker_artifacts(summary_path, report, RUN_SCOPE)
    binding = require_managed_host_binding(report.get("managed_host_binding"), True)
    receipt = binding["finish"]
    expected = {"session_id":terminal.get("session_id"),
                "owner_pid":terminal.get("owner_pid"),
                "owner_created":terminal.get("owner_created"),
                "deadline_monotonic":terminal.get("deadline_monotonic"),
                "api_port":terminal.get("api_port"),
                "lobby_port":terminal.get("lobby_port"),
                "worker_sha256":terminal.get("worker_sha256"),
                "preflight_worker_pid":terminal.get("worker_preflight_exit", {}).get("process_id")}
    for key, value in expected.items():
        if type(receipt.get(key)) is not type(value) or receipt.get(key) != value:
            raise DevelopmentError("managed development run and terminal host identities differ")
    if (receipt["session_id"] != host["session_id"]
            or receipt["worker_sha256"] != host["worker_sha256"]
            or report.get("worker_sha256") != receipt["worker_sha256"]):
        raise DevelopmentError("managed development run worker/session differs from host evidence")
    require_normal_worker_exit(report)
    lease = require_clear_terminal_account_leases(report)
    checks = validate_requested_checks(report)
    if not checks:
        raise DevelopmentError("managed development run has no received scenario evidence")
    return {"version":1,"status":"accepted","scope":SCOPE,
            "run_id":run_id,"summary_sha256":_sha256(summary_path),
            "host_session_id":host["session_id"],
            "ready_status_sha256":receipt["status_sha256"],
            "worker_sha256":receipt["worker_sha256"],
            "run_deadline":report["run_deadline"],
            "run_worker_exit":report["worker_exit"],"verified_checks":checks,
            "worker_artifacts":worker_artifacts,
            "lease_snapshot":lease,"host_process_teardown":host["process_teardown"],
            "host_lifecycle_sha256":host["lifecycle_sha256"],
            "host_environment_artifact_tree_sha256":host["environment_artifact_tree_sha256"],
            "note":"Strict retained received-state evidence plus lifecycle correlation; rendering, offline/reset authority and acceptance are out of scope."}

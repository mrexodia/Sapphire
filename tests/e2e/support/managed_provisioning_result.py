"""Strict retained provisioning evidence and optional owned-host correlation.

The private credential profile is consumed only to validate exact dedicated-account
association; secrets are never returned. This is not offline exclusion, reset
authority, or permission to retry uncertain creation.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import stat

from .development import (DevelopmentError, require_managed_host_binding,
                          require_normal_worker_exit, validate_profile)
from .development_binding import require_provisioning_binding
from .development_host_result import inspect_owned_development_host
from .development_artifact import PROVISIONING_SCOPE, require_worker_artifacts
from .development_lease import require_clear_terminal_account_leases

SCOPE = "managed-provisioning-and-terminal-owned-host-evidence-correlation"


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise DevelopmentError("provisioning evidence contains a duplicate JSON key")
        value[key] = item
    return value


def _read(path, label, max_bytes):
    try:
        path = Path(path)
        metadata = path.lstat()
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if (path.is_symlink() or not stat.S_ISREG(metadata.st_mode)
                or getattr(metadata, "st_file_attributes", 0) & reparse
                or metadata.st_nlink != 1 or not 0 < metadata.st_size <= max_bytes):
            raise OSError()
        raw = path.read_bytes()
        if not 0 < len(raw) <= max_bytes:
            raise OSError()
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DevelopmentError(f"cannot read provisioning {label}") from error
    if not isinstance(value, dict):
        raise DevelopmentError(f"provisioning {label} is not an object")
    return raw, value


def _hex(value, length):
    return (isinstance(value, str) and len(value) == length
            and all(char in "0123456789abcdef" for char in value))


def validate_provisioning_evidence(summary_path, profile_path, *, managed):
    if managed is not None and type(managed) is not bool:
        raise DevelopmentError("provisioning host mode must be explicit")
    summary_path = Path(summary_path)
    summary_raw, report = _read(summary_path, "summary", 1024 * 1024)
    summary_path = summary_path.resolve()
    _, profile = _read(profile_path, "private profile", 64 * 1024)
    validate_profile(profile)
    if managed is None:
        managed = profile.get("host_session") is not None
    run_id = report.get("run_id")
    fields = {"version","run_id","status","scope","ready_for_shared_checks",
              "server_identity_verified","server_processes_owned","database_access",
              "administrative_placement_performed","lease_retained","credential_profile_saved",
              "worker_closed","worker_exit","managed_host_binding","worker_sha256",
              "worker_artifact_tree_sha256","accounts",
              "provisioning_binding","next_step","run_deadline","lease_snapshot",
              "lease_snapshot_matches_run_state","elapsed_seconds","timings"}
    expected_phases = ["reserve_private_credential_profile","account_lease",
        "create_account_0","fresh_http_login_0","lobby_create_and_world_0","logout_0",
        "create_account_1","fresh_http_login_1","lobby_create_and_world_1","logout_1",
        "worker_session_including_close"]
    if managed:
        expected_phases.append("managed_host_completion_binding")
    expected_phases += ["provisioning_deadline_completion","release_accounts"]
    timings = report.get("timings")
    if (set(report) != fields
            or not isinstance(timings, list) or len(timings) != len(expected_phases)
            or [row.get("phase") if isinstance(row, dict) else None for row in timings] != expected_phases
            or any(set(row) != {"phase","seconds","outcome"}
                   or type(row.get("seconds")) is not float
                   or not math.isfinite(row["seconds"]) or row["seconds"] < 0
                   or row.get("outcome") != "passed" for row in timings)
            or type(report.get("elapsed_seconds")) is not float
            or not math.isfinite(report["elapsed_seconds"]) or report["elapsed_seconds"] < 0
            or type(report.get("version")) is not int or report["version"] != 1
            or not _hex(run_id, 32) or report.get("status") != "provisioned"
            or report.get("scope") != "shared-development-provisioning-not-gameplay"
            or report.get("ready_for_shared_checks") is not False
            or report.get("server_identity_verified") is not False
            or report.get("server_processes_owned") is not False
            or report.get("database_access") is not False
            or report.get("administrative_placement_performed") is not False
            or report.get("credential_profile_saved") is not True
            or report.get("worker_closed") is not True
            or report.get("lease_retained") is not False
            or report.get("lease_snapshot_matches_run_state") is not True
            or report.get("next_step") != ("Opening/public-world preparation is still required before "
                                            "run_development. No placement or reset command was run.")):
        raise DevelopmentError("provisioning boundary is incomplete or mutable")
    worker_artifacts = require_worker_artifacts(summary_path, report, PROVISIONING_SCOPE)
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
        raise DevelopmentError("provisioning success deadline is missing or failed")
    binding = require_managed_host_binding(report.get("managed_host_binding"), managed)
    accounts = report.get("accounts")
    account_fields = {"slot","character","account_creation","character_creation","entity_id",
                      "character_id","territory","gm_rank","logout_server_close_verified"}
    if not isinstance(accounts, list) or len(accounts) != 2:
        raise DevelopmentError("provisioning requires two exact account outcomes")
    for index, row in enumerate(accounts):
        if (not isinstance(row, dict) or set(row) != account_fields
                or type(row.get("slot")) is not int or row["slot"] != index
                or row.get("character") != profile["accounts"][index]["character"]
                or row.get("account_creation") != "fresh_login_verified"
                or row.get("character_creation") != "refreshed_lobby_and_world_verified"
                or type(row.get("entity_id")) is not int or not 0 < row["entity_id"] < 2**32
                or type(row.get("character_id")) is not int or not 0 < row["character_id"] < 2**64
                or type(row.get("territory")) is not int or row["territory"] not in {130, 182}
                or type(row.get("gm_rank")) is not int or row["gm_rank"] != 0
                or row.get("logout_server_close_verified") is not True):
            raise DevelopmentError("provisioning account outcome is incomplete")
    if (accounts[0]["entity_id"] == accounts[1]["entity_id"]
            or accounts[0]["character_id"] == accounts[1]["character_id"]):
        raise DevelopmentError("provisioning identities are not distinct")
    require_provisioning_binding(profile, report)
    require_normal_worker_exit(report)
    lease = require_clear_terminal_account_leases(report)
    return {"summary_raw":summary_raw,"report":report,"profile":profile,
            "run_id":run_id,"worker_artifacts":worker_artifacts,"deadline":deadline,
            "binding":binding,"accounts":accounts,"lease":lease}


def inspect_managed_provisioning(session_dir, summary_path, profile_path):
    evidence = validate_provisioning_evidence(summary_path, profile_path, managed=True)
    report, profile = evidence["report"], evidence["profile"]
    session_dir = Path(session_dir).resolve()
    host = inspect_owned_development_host(session_dir)
    _, terminal = _read(session_dir / "status.json", "terminal host status", 64 * 1024)
    receipt = evidence["binding"]["finish"]
    expected = {"session_id":terminal.get("session_id"),
                "owner_pid":terminal.get("owner_pid"),
                "owner_created":terminal.get("owner_created"),
                "deadline_monotonic":terminal.get("deadline_monotonic"),
                "api_port":terminal.get("api_port"),"lobby_port":terminal.get("lobby_port"),
                "worker_sha256":terminal.get("worker_sha256"),
                "preflight_worker_pid":terminal.get("worker_preflight_exit", {}).get("process_id")}
    if any(type(receipt.get(key)) is not type(value) or receipt.get(key) != value
           for key, value in expected.items()):
        raise DevelopmentError("managed provisioning and terminal host identities differ")
    if (receipt["session_id"] != host["session_id"]
            or receipt["worker_sha256"] != host["worker_sha256"]
            or report.get("worker_sha256") != receipt["worker_sha256"]
            or profile.get("host_session", {}).get("id") != receipt["session_id"]):
        raise DevelopmentError("managed provisioning profile/worker/session differs from host evidence")
    accounts = evidence["accounts"]
    return {"version":1,"status":"accepted","scope":SCOPE,"run_id":evidence["run_id"],
            "summary_sha256":hashlib.sha256(evidence["summary_raw"]).hexdigest(),
            "host_session_id":host["session_id"],"ready_status_sha256":receipt["status_sha256"],
            "worker_sha256":receipt["worker_sha256"],"run_deadline":evidence["deadline"],
            "provisioning_binding":report["provisioning_binding"],
            "received_identities":[{"slot":row["slot"],"character":row["character"],
                                    "entity_id":row["entity_id"],"character_id":row["character_id"]}
                                   for row in accounts],
            "run_worker_exit":report["worker_exit"],"lease_snapshot":evidence["lease"],
            "worker_artifacts":evidence["worker_artifacts"],
            "host_process_teardown":host["process_teardown"],
            "host_lifecycle_sha256":host["lifecycle_sha256"],
            "host_environment_artifact_tree_sha256":host["environment_artifact_tree_sha256"],
            "note":"Retained provisioning/lifecycle correlation only; no offline, reset, retry or gameplay authority."}

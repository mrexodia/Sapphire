"""Strict read-only result inspection for an external shared-development run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .development import (DevelopmentError, require_managed_host_binding,
                          require_normal_worker_exit)
from .development_artifact import RUN_SCOPE, require_worker_artifacts
from .development_lease import require_clear_terminal_account_leases
from .managed_development_result import validate_requested_checks

SCOPE = "external-shared-development-received-evidence-not-managed-host-or-acceptance"


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise DevelopmentError("shared development summary contains a duplicate key")
        value[key] = item
    return value


def _read(path):
    path = Path(path)
    try:
        if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 1024 * 1024:
            raise OSError()
        raw = path.read_bytes()
        if len(raw) > 1024 * 1024:
            raise OSError()
        value = json.loads(raw, object_pairs_hook=_pairs)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DevelopmentError("cannot read external shared-development summary") from error
    if not isinstance(value, dict):
        raise DevelopmentError("external shared-development summary is not an object")
    return raw, value


def _hex(value, length):
    return (isinstance(value, str) and len(value) == length
            and all(char in "0123456789abcdef" for char in value))


def inspect_development_result(summary_path):
    summary_path = Path(summary_path).resolve()
    raw, report = _read(summary_path)
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
        raise DevelopmentError("external shared-development boundary is not passing or remains mutable")
    binding = require_managed_host_binding(report.get("managed_host_binding"), False)
    worker_artifacts = require_worker_artifacts(summary_path, report, RUN_SCOPE)
    require_normal_worker_exit(report)
    lease = require_clear_terminal_account_leases(report)
    checks = validate_requested_checks(report)
    if not checks:
        raise DevelopmentError("external shared-development result has no received scenario evidence")
    return {"version":1,"status":"accepted","scope":SCOPE,"run_id":run_id,
            "summary_sha256":hashlib.sha256(raw).hexdigest(),
            "worker_sha256":report["worker_sha256"],
            "worker_artifacts":worker_artifacts,
            "run_worker_exit":report["worker_exit"],
            "run_deadline":report["run_deadline"],
            "lease_snapshot":lease,"verified_checks":checks,
            "managed_host":False,"managed_host_binding":binding,
            "server_identity_verified":False,
            "note":"External shared-world received-state evidence only; not isolation, rendering, reset, offline, cleanup or acceptance proof."}

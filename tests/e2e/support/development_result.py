"""Strict read-only result inspection for an external shared-development run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import stat

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
        metadata = path.lstat()
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if (path.is_symlink() or not stat.S_ISREG(metadata.st_mode)
                or getattr(metadata, "st_file_attributes", 0) & reparse
                or metadata.st_nlink != 1
                or not 0 < metadata.st_size <= 1024 * 1024):
            raise OSError()
        raw = path.read_bytes()
        if not 0 < len(raw) <= 1024 * 1024:
            raise OSError()
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DevelopmentError("cannot read external shared-development summary") from error
    if not isinstance(value, dict):
        raise DevelopmentError("external shared-development summary is not an object")
    return raw, value


def _hex(value, length):
    return (isinstance(value, str) and len(value) == length
            and all(char in "0123456789abcdef" for char in value))


def validate_development_evidence(summary_path):
    summary_path = Path(summary_path)
    raw, report = _read(summary_path)
    summary_path = summary_path.resolve()
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
    return {"summary_path":summary_path,"raw":raw,"report":report,"run_id":run_id,
            "binding":binding,"worker_artifacts":worker_artifacts,
            "lease":lease,"checks":checks}


def inspect_development_result(summary_path):
    evidence = validate_development_evidence(summary_path)
    report = evidence["report"]
    return {"version":1,"status":"accepted","scope":SCOPE,"run_id":evidence["run_id"],
            "summary_sha256":hashlib.sha256(evidence["raw"]).hexdigest(),
            "worker_sha256":report["worker_sha256"],
            "worker_artifacts":evidence["worker_artifacts"],
            "run_worker_exit":report["worker_exit"],
            "run_deadline":report["run_deadline"],
            "lease_snapshot":evidence["lease"],"verified_checks":evidence["checks"],
            "managed_host":False,"managed_host_binding":evidence["binding"],
            "server_identity_verified":False,
            "note":"External shared-world received-state evidence only; not isolation, rendering, reset, offline, cleanup or acceptance proof."}

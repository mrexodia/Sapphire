"""Read-only correlation of one managed development run and terminal owned host.

This validates lifecycle/provenance boundaries only. It does not revalidate the
run's gameplay details or prove offline exclusion, reset authority, external-server
identity, shared-world cleanliness, or acceptance coverage.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .development import (DevelopmentError, require_managed_host_binding,
                          require_normal_worker_exit)
from .development_host_result import inspect_owned_development_host
from .development_lease import require_clear_terminal_account_leases

SCOPE = "managed-development-run-and-terminal-owned-host-lifecycle-correlation"


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
            or report.get("lease_snapshot_matches_run_state") is not True):
        raise DevelopmentError("managed development run boundary is not passing or remains mutable")
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
    return {"version":1,"status":"accepted","scope":SCOPE,
            "run_id":run_id,"summary_sha256":_sha256(summary_path),
            "host_session_id":host["session_id"],
            "ready_status_sha256":receipt["status_sha256"],
            "worker_sha256":receipt["worker_sha256"],
            "run_worker_exit":report["worker_exit"],
            "lease_snapshot":lease,"host_process_teardown":host["process_teardown"],
            "host_lifecycle_sha256":host["lifecycle_sha256"],
            "note":"Lifecycle correlation only; gameplay, offline/reset authority and acceptance are out of scope."}

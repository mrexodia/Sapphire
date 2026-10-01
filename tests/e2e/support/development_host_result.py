"""Read-only strict terminal evidence for one owned warm development host.

This is not an inspector for an already-running external server. Exact owned
process teardown does not prove graceful shutdown, account offline exclusion,
cache quiescence, reset authority, or shared-world cleanliness.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from .development import DevelopmentError, require_normal_worker_exit
from .environment import (SetupError, has_cleanup_failure_marker,
                          require_process_teardowns)

SCOPE = "terminal-owned-warm-host-cleanup-not-external-server-or-offline-proof"
TEARDOWN_SCOPE = "exact-owned-warm-host-service-teardown-not-server-offline-proof"


def _read(path, label):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DevelopmentError(f"cannot read owned-host {label}") from error
    if not isinstance(value, dict):
        raise DevelopmentError(f"owned-host {label} is not an object")
    return value


def _sha256(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError as error:
        raise DevelopmentError("cannot hash owned-host lifecycle evidence") from error


def _hex(value, length):
    return (isinstance(value, str) and len(value) == length
            and all(char in "0123456789abcdef" for char in value))


def _typed_equal(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return (set(left) == set(right)
                and all(_typed_equal(left[key], right[key]) for key in left))
    if isinstance(left, list):
        return len(left) == len(right) and all(map(lambda pair: _typed_equal(*pair), zip(left, right)))
    return left == right


def inspect_owned_development_host(session_dir):
    session_dir = Path(session_dir).resolve()
    try:
        if has_cleanup_failure_marker(session_dir):
            raise DevelopmentError("owned host records terminal cleanup failure")
    except SetupError as error:
        raise DevelopmentError("cannot inspect owned-host cleanup-failure markers") from error
    status = _read(session_dir / "status.json", "terminal status")
    fields = {"version", "kind", "session_id", "status", "scope", "protocol",
              "maximum_seconds", "owner_pid", "owner_created", "existing_database_access",
              "graphical_client_started", "fixture_setup", "normal_lobby_creation_verified",
              "cleanup_verified", "process_cleanup_verified", "worker_preflight_exit",
              "api_port", "lobby_port", "world_port", "artifacts", "owned_pids",
              "worker_sha256", "deadline_monotonic", "profiles", "stop_reason",
              "environment_process_teardown", "private_profiles_removed",
              "elapsed_seconds", "timings"}
    if (set(status) != fields or type(status.get("version")) is not int or status["version"] != 1
            or status.get("kind") != "owned-development-host"
            or not _hex(status.get("session_id"), 32)
            or status.get("status") != "stopped"
            or status.get("scope") != "owned-private-warm-world-not-acceptance"
            or status.get("protocol") != "sapphire-3.3"
            or type(status.get("maximum_seconds")) is not int
            or not 60 <= status["maximum_seconds"] <= 14400
            or type(status.get("owner_pid")) is not int or status["owner_pid"] <= 0
            or type(status.get("owner_created")) not in (int, float)
            or not math.isfinite(status["owner_created"]) or status["owner_created"] <= 0
            or status.get("existing_database_access") is not False
            or status.get("graphical_client_started") is not False
            or status.get("normal_lobby_creation_verified") is not False
            or status.get("cleanup_verified") is not True
            or status.get("process_cleanup_verified") is not True
            or status.get("private_profiles_removed") is not True
            or status.get("fixture_setup") !=
                "three new non-GM pre-connection fixtures, including one separate viewer"
            or status.get("profiles") != ["bot-profile.json", "server-profile.json",
                                           "viewer-profile.json"]
            or status.get("stop_reason") not in {"operator_stop_file", "bounded_lifetime_expired"}
            or not isinstance(status.get("artifacts"), str) or not status["artifacts"]
            or not _hex(status.get("worker_sha256"), 64)):
        raise DevelopmentError("owned-host terminal boundary is malformed or incomplete")
    ports = [status.get(key) for key in ("api_port", "lobby_port", "world_port")]
    if any(type(value) is not int or not 0 < value <= 65535 for value in ports) or len(set(ports)) != 3:
        raise DevelopmentError("owned-host terminal ports are malformed")
    for key in ("deadline_monotonic", "elapsed_seconds"):
        value = status.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise DevelopmentError("owned-host terminal duration is malformed")
    require_normal_worker_exit({"worker_exit": status.get("worker_preflight_exit")})

    receipt = status.get("environment_process_teardown")
    if (not isinstance(receipt, dict)
            or set(receipt) != {"verified", "scope", "relative_path", "sha256", "evidence"}
            or receipt.get("verified") is not True or receipt.get("scope") != TEARDOWN_SCOPE
            or receipt.get("relative_path") != "process-lifecycle.json"
            or not _hex(receipt.get("sha256"), 64)):
        raise DevelopmentError("owned-host service teardown receipt is malformed")
    lifecycle_path = session_dir / "process-lifecycle.json"
    lifecycle = _read(lifecycle_path, "process lifecycle")
    artifact_dir = Path(status["artifacts"])
    try:
        artifact_resolved = artifact_dir.resolve()
    except (OSError, RuntimeError) as error:
        raise DevelopmentError("cannot resolve owned-host environment artifacts") from error
    if (not artifact_dir.is_absolute() or artifact_dir.is_symlink()
            or not artifact_dir.is_dir() or artifact_resolved == session_dir
            or artifact_resolved in session_dir.parents
            or session_dir in artifact_resolved.parents):
        raise DevelopmentError("owned-host environment artifact directory is unsafe")
    artifact_dir = artifact_resolved
    try:
        if has_cleanup_failure_marker(artifact_dir):
            raise DevelopmentError("owned host environment records terminal cleanup failure")
    except SetupError as error:
        raise DevelopmentError("cannot inspect owned-host environment cleanup markers") from error
    artifact_lifecycle = artifact_dir / "process-lifecycle.json"
    if artifact_lifecycle.is_symlink() or not artifact_lifecycle.is_file():
        raise DevelopmentError("owned-host environment lifecycle is missing or unsafe")
    artifact_lifecycle_value = _read(artifact_lifecycle, "environment process lifecycle")
    if not _typed_equal(artifact_lifecycle_value, lifecycle):
        raise DevelopmentError("owned-host retained lifecycle differs from environment artifact")
    if (set(lifecycle) != {"version", "scope", "starts", "teardowns"}
            or type(lifecycle.get("version")) is not int or lifecycle["version"] != 1
            or lifecycle.get("scope") !=
                "exact-owned-isolated-process-teardown-not-graceful-server-exit"
            or _sha256(lifecycle_path) != receipt["sha256"]):
        raise DevelopmentError("owned-host process lifecycle file is malformed or changed")
    try:
        proof = require_process_teardowns(lifecycle["starts"], lifecycle["teardowns"])
    except (KeyError, TypeError, ValueError, RuntimeError) as error:
        raise DevelopmentError("owned-host process teardown is incomplete") from error
    if (not _typed_equal(receipt.get("evidence"), proof)
            or proof.get("process_count") != 4
            or proof.get("generations") != {"api":1,"database":1,"lobby":1,"world":1}):
        raise DevelopmentError("owned-host teardown proof differs or lacks exact services")
    pids = status.get("owned_pids")
    expected_pids = {row["process"]:row["pid"] for row in lifecycle["starts"]}
    if (not isinstance(pids, dict) or not _typed_equal(pids, expected_pids)
            or len(pids) != 4 or len(set(pids.values())) != 4
            or any(type(pid) is not int or pid <= 0 for pid in pids.values())):
        raise DevelopmentError("owned-host published PIDs differ from lifecycle generations")

    timings = status.get("timings")
    phases = ["environment_construction", "worker_preflight", "environment_start_once",
              "pre_connection_fixture_preparation", "private_profile_export",
              "warm_host_available_not_gameplay", "owned_environment_cleanup"]
    if not isinstance(timings, list) or len(timings) != len(phases):
        raise DevelopmentError("owned-host timing receipt is incomplete")
    for row, phase in zip(timings, phases):
        seconds = row.get("seconds") if isinstance(row, dict) else None
        if (not isinstance(row, dict) or set(row) != {"phase", "seconds", "outcome"}
                or row.get("phase") != phase or row.get("outcome") != "passed"
                or type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0):
            raise DevelopmentError("owned-host timing receipt is malformed")
    return {"version":1,"status":"accepted","scope":SCOPE,
            "session_id":status["session_id"],"stop_reason":status["stop_reason"],
            "worker_sha256":status["worker_sha256"],
            "lifecycle_sha256":receipt["sha256"],"process_teardown":proof,
            "private_profiles_removed":True,
            "note":"Owned warm-host teardown only; not external-server or offline/reset proof."}

"""Strict sanitized inspection of terminal isolated-fixture cleanup failures."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .environment import SetupError

_SCOPE = "terminal-isolated-cleanup-failure-not-success-evidence"
_LIFECYCLE_SCOPE = "exact-owned-isolated-process-teardown-not-graceful-server-exit"
_SERVICES = {"database", "api", "lobby", "world"}
_CLASSIFICATIONS = {
    "owned_process_cleanup_incomplete",
    "owned_process_cleanup_evidence_incomplete",
}
_RETRY_POLICY = "exact-process-poll-only-no-second-termination"


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SetupError("cleanup failure evidence contains a duplicate JSON key")
        result[key] = value
    return result


def _read(path: Path, limit: int, label: str):
    if path.is_symlink() or not path.is_file():
        raise SetupError(f"cleanup failure {label} is missing or unsafe")
    raw = path.read_bytes()
    if not raw or len(raw) > limit:
        raise SetupError(f"cleanup failure {label} exceeds its evidence bound")
    try:
        value = json.loads(raw, object_pairs_hook=_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SetupError(f"cleanup failure {label} is invalid JSON") from error
    if not isinstance(value, dict):
        raise SetupError(f"cleanup failure {label} must be a JSON object")
    return raw, value


def _validate_start(row):
    return (isinstance(row, dict) and set(row) == {"process", "generation", "pid"}
            and row.get("process") in _SERVICES
            and type(row.get("generation")) is int and row["generation"] > 0
            and type(row.get("pid")) is int and row["pid"] > 0)


def _validate_teardown(row):
    if (not isinstance(row, dict)
            or set(row) != {"process", "generation", "pid", "was_running_before_cleanup",
                            "terminate_requested", "kill_requested", "exit_observed",
                            "returncode", "scope"}
            or row.get("process") not in _SERVICES
            or type(row.get("generation")) is not int or row["generation"] <= 0
            or type(row.get("pid")) is not int or row["pid"] <= 0
            or type(row.get("was_running_before_cleanup")) is not bool
            or type(row.get("terminate_requested")) is not bool
            or type(row.get("kill_requested")) is not bool
            or type(row.get("exit_observed")) is not bool
            or row.get("scope") != _LIFECYCLE_SCOPE):
        return False
    if row["was_running_before_cleanup"]:
        if not row["terminate_requested"]:
            return False
    elif row["terminate_requested"] or row["kill_requested"] or not row["exit_observed"]:
        return False
    if row["kill_requested"] and (not row["terminate_requested"] or not row["exit_observed"]):
        return False
    if row["exit_observed"]:
        return type(row.get("returncode")) is int
    return row.get("returncode") is None and not row["kill_requested"]


def _inspect_lifecycle(value, marker_services, classification):
    if (set(value) != {"version", "scope", "starts", "teardowns"}
            or type(value.get("version")) is not int or value["version"] != 1
            or value.get("scope") != _LIFECYCLE_SCOPE
            or not isinstance(value.get("starts"), list)
            or not isinstance(value.get("teardowns"), list)
            or any(not _validate_start(row) for row in value["starts"])
            or any(not _validate_teardown(row) for row in value["teardowns"])):
        raise SetupError("cleanup failure lifecycle schema is invalid")
    starts = [(row["process"], row["generation"], row["pid"]) for row in value["starts"]]
    teardowns = [(row["process"], row["generation"], row["pid"]) for row in value["teardowns"]]
    if len(starts) != len(set(starts)) or len(teardowns) != len(set(teardowns)):
        raise SetupError("cleanup failure lifecycle identities are duplicated")
    if not set(teardowns).issubset(starts):
        raise SetupError("cleanup failure teardown has no exact owned start")
    generations = {}
    for service, generation, _ in starts:
        generations.setdefault(service, []).append(generation)
    if any(values != list(range(1, len(values) + 1))
           for values in generations.values()):
        raise SetupError("cleanup failure process generations are not contiguous")
    rows = {key: row for key, row in zip(teardowns, value["teardowns"])}
    unresolved = {service for service, generation, pid in starts
                  if (service, generation, pid) not in rows
                  or not rows[(service, generation, pid)]["exit_observed"]}
    if not unresolved.issubset(set(marker_services)):
        raise SetupError("cleanup failure lifecycle uncertainty is not declared")
    if classification == "owned_process_cleanup_incomplete":
        if any(service not in generations for service in marker_services):
            raise SetupError("cleanup failure service has no exact owned start")
    elif unresolved:
        raise SetupError("evidence-only cleanup failure contains process uncertainty")
    complete = len(starts) == len(teardowns) and not unresolved
    return complete, len(starts), len(unresolved)


def inspect_cleanup_failure(artifact_dir: Path):
    supplied = Path(artifact_dir)
    if not supplied.is_absolute() or supplied.is_symlink() or not supplied.is_dir():
        raise SetupError("cleanup failure artifact directory must be an absolute safe directory")
    root = supplied.resolve()
    marker_raw, marker = _read(root / "cleanup-failure.json", 64 * 1024, "marker")
    if (set(marker) != {"version", "classification", "services", "runtime_retained",
                        "retry_policy"}
            or type(marker.get("version")) is not int or marker["version"] != 1
            or marker.get("classification") not in _CLASSIFICATIONS
            or not isinstance(marker.get("services"), list)
            or marker["services"] != sorted(set(marker["services"]))
            or any(type(name) is not str or name not in _SERVICES for name in marker["services"])
            or type(marker.get("runtime_retained")) is not bool
            or marker.get("retry_policy") != _RETRY_POLICY):
        raise SetupError("cleanup failure marker schema is invalid")
    if ((marker["classification"] == "owned_process_cleanup_incomplete")
            != bool(marker["services"])):
        raise SetupError("cleanup failure classification and services disagree")
    lifecycle_path = root / "process-lifecycle.json"
    lifecycle_sha256 = None
    complete = None
    start_count = unresolved_count = 0
    if lifecycle_path.exists() or lifecycle_path.is_symlink():
        lifecycle_raw, lifecycle = _read(lifecycle_path, 256 * 1024, "lifecycle")
        lifecycle_sha256 = hashlib.sha256(lifecycle_raw).hexdigest()
        complete, start_count, unresolved_count = _inspect_lifecycle(
            lifecycle, marker["services"], marker["classification"])
    return {
        "version":1,
        "status":"terminal-cleanup-failure",
        "scope":_SCOPE,
        "classification":marker["classification"],
        "services":marker["services"],
        "runtime_retained_at_marker":marker["runtime_retained"],
        "retry_policy":marker["retry_policy"],
        "marker_sha256":hashlib.sha256(marker_raw).hexdigest(),
        "lifecycle_present":lifecycle_sha256 is not None,
        "lifecycle_sha256":lifecycle_sha256,
        "current_lifecycle_complete":complete,
        "owned_process_generation_count":start_count,
        "current_unresolved_generation_count":unresolved_count,
        "success_evidence":False,
        "process_exit_independently_verified":False,
    }

"""Read-only verification of one retained standalone isolated owned-world fault case."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .environment import SetupError, artifact_tree_sha256, require_process_teardowns
from .isolated_case_result import inspect_isolated_case

SCOPE = "current-standalone-owned-world-fault-evidence"
FAULT_CASE = ("tests/e2e/test_live_fault_diagnostics.py::"
              "test_owned_world_exit_preserves_classification_logs_and_cleanup")
FAULT_CLASSIFICATION = "intentional_owned_process_exit"
FAULT_SCOPE = ("one intentional termination of the exact owned disposable world process; "
               "proves bounded exit classification, generation-correlated teardown, "
               "redacted text-log publication and cleanup, not crash-dump retention, "
               "cancellation cleanup or server crash behavior")


def _hex(value, length=64):
    return (isinstance(value, str) and len(value) == length
            and all(char in "0123456789abcdef" for char in value))


def _raw(path, limit, label):
    try:
        path = Path(path)
        if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= limit:
            raise OSError()
        raw = path.read_bytes()
        if len(raw) > limit:
            raise OSError()
        return raw
    except OSError as error:
        raise SetupError(f"cannot read isolated fault {label}") from error


def _read(path, limit, label):
    raw = _raw(path, limit, label)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise SetupError(f"cannot parse isolated fault {label}") from error
    if not isinstance(value, dict):
        raise SetupError(f"isolated fault {label} is not an object")
    return raw, value


def _digest(path, limit, label):
    try:
        path = Path(path)
        if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= limit:
            raise OSError()
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda:stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()
    except OSError as error:
        raise SetupError(f"cannot hash isolated fault {label}") from error


def inspect_isolated_fault(artifact_dir, junit_path, pytest_log, expected_revision):
    if not _hex(expected_revision, 40):
        raise SetupError("expected isolated fault revision must be exact lowercase git identity")
    supplied = Path(artifact_dir)
    if supplied.is_symlink() or not supplied.is_dir():
        raise SetupError("isolated fault artifact directory is missing or unsafe")
    root = supplied.resolve()
    manifest_raw, manifest = _read(root / "manifest.json", 1024 * 1024, "manifest")
    lifecycle_raw, lifecycle = _read(root / "process-lifecycle.json", 256 * 1024, "lifecycle")
    failure_raw, failure = _read(root / "process-failure.json", 64 * 1024, "classification")
    verification_raw, verification = _read(
        root / "fault-diagnostics-verification.json", 64 * 1024, "verification")
    world_sha256 = _digest(root / "world.log", 512 * 1024 * 1024, "world log")
    runner = inspect_isolated_case(root, junit_path, pytest_log, FAULT_CASE, expected_revision)

    database, runtime, ports = manifest.get("database"), manifest.get("runtime"), manifest.get("ports")
    runtime_path = Path(runtime).resolve() if isinstance(runtime, str) else None
    if (manifest.get("revision") != expected_revision or manifest.get("dirty") is not False
            or manifest.get("profile") != "sapphire-3.3"
            or type(manifest.get("fixture_version")) is not int or manifest["fixture_version"] != 2
            or type(manifest.get("deadline_scale")) is not int
            or not 1 <= manifest["deadline_scale"] <= 3
            or not isinstance(database, str) or not database.startswith("sapphire_e2e_")
            or len(database) != len("sapphire_e2e_") + 32
            or any(char not in "0123456789abcdef" for char in database[len("sapphire_e2e_"):])
            or not isinstance(runtime, str) or not Path(runtime).is_absolute()
            or runtime_path.name != "runtime" or runtime_path.exists() or runtime_path.parent.exists()
            or runtime_path == root or runtime_path in root.parents or root in runtime_path.parents
            or not isinstance(ports, dict) or set(ports) != {"database","api","lobby","world"}
            or any(type(port) is not int or not 1 <= port <= 65535 for port in ports.values())
            or len(set(ports.values())) != 4
            or not _hex(manifest.get("worker_sha256"))
            or not isinstance(manifest.get("binaries"), dict)
            or set(manifest["binaries"]) != {"api","lobby","server","dbm"}
            or any(not _hex(value) for value in manifest["binaries"].values())
            or not isinstance(manifest.get("scripts"), dict) or not manifest["scripts"]
            or any(not isinstance(name, str) or not _hex(value)
                   for name,value in manifest["scripts"].items())
            or not isinstance(manifest.get("server_navigation"), dict)
            or set(manifest["server_navigation"]) != {"w1t1/w1t1.nav","w1f2/w1f2.nav"}
            or any(not _hex(value) for value in manifest["server_navigation"].values())):
        raise SetupError("isolated fault manifest is foreign, malformed or retains runtime")

    if (set(lifecycle) != {"version","scope","starts","teardowns"}
            or type(lifecycle.get("version")) is not int or lifecycle["version"] != 1
            or lifecycle.get("scope") != "exact-owned-isolated-process-teardown-not-graceful-server-exit"):
        raise SetupError("isolated fault lifecycle schema is invalid")
    lifecycle_proof = require_process_teardowns(lifecycle["starts"], lifecycle["teardowns"])
    if (lifecycle_proof["process_count"] != 4
            or lifecycle_proof["generations"] != {"api":1,"database":1,"lobby":1,"world":1}):
        raise SetupError("isolated fault lifecycle is not one exact fixture generation")

    failure_fields = {"version","classification","process","generation","pid",
                      "returncode","log","cleanup_required"}
    if (set(failure) != failure_fields
            or type(failure.get("version")) is not int or failure["version"] != 1
            or failure.get("classification") != FAULT_CLASSIFICATION
            or failure.get("process") != "world" or failure.get("log") != "world.log"
            or type(failure.get("generation")) is not int or failure["generation"] != 1
            or type(failure.get("pid")) is not int or failure["pid"] <= 0
            or type(failure.get("returncode")) is not int
            or failure.get("cleanup_required") is not True):
        raise SetupError("isolated fault classification is invalid")
    matches = [row for row in lifecycle["teardowns"] if row["process"] == "world"
               and row["generation"] == failure["generation"] and row["pid"] == failure["pid"]]
    if (len(matches) != 1 or matches[0]["returncode"] != failure["returncode"]
            or matches[0]["exit_observed"] is not True):
        raise SetupError("isolated fault classification lacks exact world teardown")

    verification_fields = {"classification","process","generation","pid","returncode",
                           "world_log_sha256","manifest_sha256","lifecycle_sha256",
                           "runtime_removed","secrets_absent_from_published_logs","scope"}
    if (set(verification) != verification_fields
            or any(verification.get(key) != failure[key]
                   for key in ("classification","process","generation","pid","returncode"))
            or verification.get("world_log_sha256") != world_sha256
            or verification.get("manifest_sha256") != hashlib.sha256(manifest_raw).hexdigest()
            or verification.get("lifecycle_sha256") != hashlib.sha256(lifecycle_raw).hexdigest()
            or verification.get("runtime_removed") is not True
            or verification.get("secrets_absent_from_published_logs") is not True
            or verification.get("scope") != FAULT_SCOPE):
        raise SetupError("isolated fault verification is invalid")

    return {"version":1,"status":"accepted","scope":SCOPE,
            "source_revision":expected_revision,"source_dirty":False,
            "case":FAULT_CASE,"exact_single_passing_junit_case":True,
            "junit_sha256":runner["junit_sha256"],
            "pytest_log_sha256":runner["pytest_log_sha256"],
            "runner_scope":runner["scope"],
            "classification":FAULT_CLASSIFICATION,"service":"world",
            "exact_world_teardown_correlated":True,"lifecycle":lifecycle_proof,
            "runtime_and_disposable_root_absent":True,
            "secrets_absent_from_published_logs":True,
            "manifest_sha256":hashlib.sha256(manifest_raw).hexdigest(),
            "lifecycle_sha256":hashlib.sha256(lifecycle_raw).hexdigest(),
            "failure_sha256":hashlib.sha256(failure_raw).hexdigest(),
            "verification_sha256":hashlib.sha256(verification_raw).hexdigest(),
            "world_log_sha256":world_sha256,"artifact_tree_sha256":artifact_tree_sha256(root),
            "private_paths_ports_database_or_pids_disclosed":False,
            "note":"Exact single-case runner binding plus one intentional exact-owned world exit; not gameplay, organic crash, dump, hosted cancellation or build provenance."}

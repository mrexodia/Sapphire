"""Read-only evidence validation for one allowlisted standalone isolated case."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from .ci_result import EXPECTED_CASES
from .environment import (SetupError, artifact_tree_sha256,
                          has_cleanup_failure_marker, require_process_teardowns)

SCOPE = "current-standalone-allowlisted-isolated-case-evidence"
REJECTED_CREDENTIALS_CASE = "tests/e2e/test_live.py::test_rejected_credentials"
HTTP_RECEIPT_SCOPE = "genuine-http-response-metadata-no-request-or-response-content"


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
        raise SetupError(f"cannot read standalone isolated {label}") from error


def _read(path, limit, label):
    raw = _raw(path, limit, label)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise SetupError(f"cannot parse standalone isolated {label}") from error
    if not isinstance(value, dict):
        raise SetupError(f"standalone isolated {label} is not an object")
    return raw, value


def inspect_isolated_case(artifact_dir, junit_path, pytest_log, expected_case, expected_revision):
    if expected_case not in EXPECTED_CASES:
        raise SetupError("standalone isolated case is not allowlisted")
    if not _hex(expected_revision, 40):
        raise SetupError("expected standalone case revision must be exact lowercase git identity")
    supplied = Path(artifact_dir)
    if supplied.is_symlink() or not supplied.is_dir():
        raise SetupError("standalone isolated artifact directory is missing or unsafe")
    root = supplied.resolve()
    if has_cleanup_failure_marker(root):
        raise SetupError("standalone isolated evidence records uncertain process cleanup")
    manifest_raw, manifest = _read(root / "manifest.json", 1024 * 1024, "manifest")
    lifecycle_raw, lifecycle = _read(root / "process-lifecycle.json", 256 * 1024, "lifecycle")
    junit_raw = _raw(junit_path, 16 * 1024 * 1024, "JUnit report")
    pytest_raw = _raw(pytest_log, 16 * 1024 * 1024, "pytest log")

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
        raise SetupError("standalone isolated manifest is foreign, malformed or retains runtime")
    if (set(lifecycle) != {"version","scope","starts","teardowns"}
            or type(lifecycle.get("version")) is not int or lifecycle["version"] != 1
            or lifecycle.get("scope") != "exact-owned-isolated-process-teardown-not-graceful-server-exit"):
        raise SetupError("standalone isolated lifecycle schema is invalid")
    lifecycle_proof = require_process_teardowns(lifecycle["starts"], lifecycle["teardowns"])

    scenario_receipt_verified = False
    if expected_case == REJECTED_CREDENTIALS_CASE:
        _, receipt = _read(root / "rejected-credentials.json", 64 * 1024,
                           "rejected-credentials receipt")
        if (set(receipt) != {"version","scope","method","expected_status","received_status",
                             "response_bytes","response_sha256","session_returned"}
                or type(receipt.get("version")) is not int or receipt["version"] != 1
                or receipt.get("scope") != HTTP_RECEIPT_SCOPE or receipt.get("method") != "login"
                or type(receipt.get("expected_status")) is not int
                or receipt["expected_status"] != 400
                or type(receipt.get("received_status")) is not int
                or receipt["received_status"] != 400
                or type(receipt.get("response_bytes")) is not int or receipt["response_bytes"] < 0
                or not _hex(receipt.get("response_sha256"))
                or receipt.get("session_returned") is not False):
            raise SetupError("standalone rejected-credentials HTTP receipt is malformed")
        scenario_receipt_verified = True

    try:
        junit = ET.fromstring(junit_raw)
    except ET.ParseError as error:
        raise SetupError("standalone isolated JUnit report is malformed") from error
    path, name = expected_case.split("::", 1)
    expected_junit = (path[:-3].replace("/", "."),name)
    cases = junit.findall(".//testcase")
    if ([(case.get("classname"),case.get("name")) for case in cases] != [expected_junit]
            or junit.findall(".//failure") or junit.findall(".//error")
            or junit.findall(".//skipped")):
        raise SetupError("standalone isolated JUnit identity or outcome is not exact passing case")

    return {"version":1,"status":"accepted","scope":SCOPE,
            "source_revision":expected_revision,"source_dirty":False,"case":expected_case,
            "exact_single_passing_junit_case":True,"lifecycle":lifecycle_proof,
            "runtime_and_disposable_root_absent":True,
            "manifest_sha256":hashlib.sha256(manifest_raw).hexdigest(),
            "lifecycle_sha256":hashlib.sha256(lifecycle_raw).hexdigest(),
            "junit_sha256":hashlib.sha256(junit_raw).hexdigest(),
            "pytest_log_sha256":hashlib.sha256(pytest_raw).hexdigest(),
            "artifact_tree_sha256":artifact_tree_sha256(root),
            "private_paths_ports_database_or_pids_disclosed":False,
            "sanitized_scenario_receipt_verified":scenario_receipt_verified,
            "scenario_semantics_independently_verified":False,
            "note":"Exact standalone runner/fixture evidence only; test pass is not independent scenario truth, compatibility, hosted execution or build provenance."}

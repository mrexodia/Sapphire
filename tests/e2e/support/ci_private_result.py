"""Read-only correlation of a current public gate summary and retained private evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from ..run_ci import inputs_match
from .ci_result import EXPECTED_CASES, inspect_ci_result
from .environment import SetupError, artifact_tree_sha256, require_process_teardowns

SCOPE = "current-isolated-public-summary-to-private-per-case-evidence-correlation"
FAULT_CASE = ("tests/e2e/test_live_fault_diagnostics.py::"
              "test_owned_world_exit_preserves_classification_logs_and_cleanup")
FAULT_SCOPE = ("one intentional termination of the exact owned disposable world process; "
               "proves bounded exit classification, generation-correlated teardown, "
               "redacted text-log publication and cleanup, not crash-dump retention, "
               "cancellation cleanup or server crash behavior")


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
        raise SetupError(f"cannot read private isolated {label}") from error


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
        raise SetupError(f"cannot read private isolated {label}") from error


def _read(path, limit, label):
    try:
        raw = _raw(path, limit, label)
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise SetupError(f"cannot read private isolated {label}") from error
    if not isinstance(value, dict):
        raise SetupError(f"private isolated {label} is not an object")
    return raw, value


def _verify_fault_evidence(root, manifest_raw, lifecycle_raw, lifecycle):
    _, failure = _read(root / "process-failure.json", 64 * 1024, "fault classification")
    world_sha256 = _digest(root / "world.log", 512 * 1024 * 1024, "fault world log")
    _, proof = _read(root / "fault-diagnostics-verification.json", 64 * 1024,
                     "fault verification")
    failure_fields = {"version","classification","process","generation","pid",
                      "returncode","log","cleanup_required"}
    if (set(failure) != failure_fields
            or type(failure.get("version")) is not int or failure["version"] != 1
            or failure.get("classification") != "intentional_owned_process_exit"
            or failure.get("process") != "world" or failure.get("log") != "world.log"
            or type(failure.get("generation")) is not int or failure["generation"] <= 0
            or type(failure.get("pid")) is not int or failure["pid"] <= 0
            or type(failure.get("returncode")) is not int
            or failure.get("cleanup_required") is not True):
        raise SetupError("private isolated fault classification is invalid")
    matches = [row for row in lifecycle["teardowns"]
               if row["process"] == "world"
               and row["generation"] == failure["generation"]
               and row["pid"] == failure["pid"]]
    if (len(matches) != 1 or matches[0]["returncode"] != failure["returncode"]
            or matches[0]["exit_observed"] is not True):
        raise SetupError("private isolated fault classification lacks exact teardown")
    proof_fields = {"classification","process","generation","pid","returncode",
                    "world_log_sha256","manifest_sha256","lifecycle_sha256",
                    "runtime_removed","secrets_absent_from_published_logs","scope"}
    if (set(proof) != proof_fields
            or any(proof.get(key) != failure[key]
                   for key in ("classification","process","generation","pid","returncode"))
            or proof.get("world_log_sha256") != world_sha256
            or proof.get("manifest_sha256") != hashlib.sha256(manifest_raw).hexdigest()
            or proof.get("lifecycle_sha256") != hashlib.sha256(lifecycle_raw).hexdigest()
            or proof.get("runtime_removed") is not True
            or proof.get("secrets_absent_from_published_logs") is not True
            or proof.get("scope") != FAULT_SCOPE):
        raise SetupError("private isolated fault verification is invalid")


def inspect_ci_private_evidence(summary_path, private_run_dir, expected_revision):
    public_proof = inspect_ci_result(summary_path, expected_revision)
    _, public = _read(summary_path, 1024 * 1024, "public summary")
    supplied_root = Path(private_run_dir)
    if supplied_root.is_symlink() or not supplied_root.is_dir():
        raise SetupError("private isolated run root is missing or unsafe")
    root = supplied_root.resolve()
    pytest_raw = _raw(root / "pytest.log", 16 * 1024 * 1024, "pytest log")
    junit_raw = _raw(root / "live.xml", 16 * 1024 * 1024, "JUnit report")
    private_artifacts = public["private_test_artifacts"]
    if (hashlib.sha256(pytest_raw).hexdigest() != private_artifacts["pytest_log_sha256"]
            or hashlib.sha256(junit_raw).hexdigest() != private_artifacts["junit_sha256"]):
        raise SetupError("private isolated test artifact hash differs from public result")
    try:
        junit = ET.fromstring(junit_raw)
    except ET.ParseError as error:
        raise SetupError("private isolated JUnit report is malformed") from error
    if (len(junit.findall(".//testcase")) != len(EXPECTED_CASES)
            or junit.findall(".//failure") or junit.findall(".//error")
            or junit.findall(".//skipped")):
        raise SetupError("private isolated JUnit outcomes are incomplete or failed")
    diagnostics_raw, diagnostics = _read(root / "gate-diagnostics.json", 1024 * 1024,
                                         "gate diagnostics")
    expected_diagnostics = {"collected","reports","unexpected","environment_count",
                            "case_environment_count","environment_evidence"}
    reports = diagnostics.get("reports")
    if (hashlib.sha256(diagnostics_raw).hexdigest() != public["gate_diagnostics_sha256"]
            or set(diagnostics) != expected_diagnostics
            or diagnostics.get("collected") != list(EXPECTED_CASES)
            or type(diagnostics.get("unexpected")) is not int or diagnostics["unexpected"] != 0
            or type(diagnostics.get("environment_count")) is not int
            or diagnostics["environment_count"] != len(EXPECTED_CASES)
            or type(diagnostics.get("case_environment_count")) is not int
            or diagnostics["case_environment_count"] != len(EXPECTED_CASES)
            or diagnostics.get("environment_evidence") != public["environment_evidence"]
            or not isinstance(reports, dict) or list(reports) != list(EXPECTED_CASES)
            or any(not isinstance(phases, dict)
                   or list(phases) != ["setup","call","teardown"]
                   or any(phases[phase] != ["passed"] for phase in ("setup","call","teardown"))
                   for phases in reports.values())):
        raise SetupError("private isolated gate diagnostics differ from public result")
    artifacts = root / "artifacts"
    if artifacts.is_symlink() or not artifacts.is_dir():
        raise SetupError("private isolated artifact root is missing or unsafe")
    children = sorted(artifacts.iterdir(), key=lambda path:path.name)
    if (len(children) != len(EXPECTED_CASES)
            or any(path.is_symlink() or not path.is_dir()
                   or not path.name.startswith("sapphire-e2e-") for path in children)):
        raise SetupError("private isolated environment evidence set is incomplete or foreign")
    expected = {(row["manifest_sha256"],row["lifecycle_sha256"],
                 row["artifact_tree_sha256"]):row["case"]
                for row in public["environment_evidence"]}
    found, databases, runtimes = {}, set(), set()
    for child in children:
        manifest_raw, manifest = _read(child / "manifest.json", 1024 * 1024, "manifest")
        lifecycle_raw, lifecycle = _read(child / "process-lifecycle.json", 256 * 1024, "lifecycle")
        pair = (hashlib.sha256(manifest_raw).hexdigest(),
                hashlib.sha256(lifecycle_raw).hexdigest(), artifact_tree_sha256(child))
        case = expected.get(pair)
        if case is None or case in found:
            raise SetupError("private isolated evidence hash is foreign or duplicated")
        if (set(lifecycle) != {"version","scope","starts","teardowns"}
                or type(lifecycle.get("version")) is not int or lifecycle["version"] != 1
                or lifecycle.get("scope") != "exact-owned-isolated-process-teardown-not-graceful-server-exit"):
            raise SetupError("private isolated lifecycle schema is invalid")
        require_process_teardowns(lifecycle.get("starts"), lifecycle.get("teardowns"))
        if case == FAULT_CASE:
            _verify_fault_evidence(child, manifest_raw, lifecycle_raw, lifecycle)
        if not inputs_match(public["identities"], manifest, public["revision"],
                            public["source_dirty"], public["deadline_scale"]):
            raise SetupError("private isolated staged source/input identity differs from public summary")
        database, runtime, ports = manifest.get("database"), manifest.get("runtime"), manifest.get("ports")
        runtime_path = Path(runtime).resolve() if isinstance(runtime, str) else None
        artifact_path = child.resolve()
        if (not isinstance(database, str) or not database.startswith("sapphire_e2e_")
                or len(database) != len("sapphire_e2e_") + 32
                or any(char not in "0123456789abcdef" for char in database[len("sapphire_e2e_"):])
                or not isinstance(runtime, str) or not Path(runtime).is_absolute()
                or runtime_path.name != "runtime"
                or runtime_path == artifact_path or runtime_path in artifact_path.parents
                or artifact_path in runtime_path.parents
                or runtime_path.exists() or runtime_path.parent.exists()
                or not isinstance(ports, dict) or set(ports) != {"database","api","lobby","world"}
                or any(type(port) is not int or not 1 <= port <= 65535 for port in ports.values())
                or len(set(ports.values())) != 4):
            raise SetupError("private isolated fixture identity is malformed")
        databases.add(database); runtimes.add(runtime_path); found[case] = pair
    if len(databases) != len(EXPECTED_CASES) or len(runtimes) != len(EXPECTED_CASES):
        raise SetupError("private isolated fixture identities are not distinct")
    runtime_rows = tuple(runtimes)
    if any(left in right.parents or right in left.parents
           for index,left in enumerate(runtime_rows) for right in runtime_rows[index + 1:]):
        raise SetupError("private isolated runtime identities overlap")
    if set(found) != set(EXPECTED_CASES):
        raise SetupError("private isolated case evidence mapping is incomplete")
    rows = [{"case":case,"manifest_sha256":found[case][0],
             "lifecycle_sha256":found[case][1],"artifact_tree_sha256":found[case][2]}
            for case in EXPECTED_CASES]
    if rows != public["environment_evidence"]:
        raise SetupError("private isolated evidence order or identity differs from public summary")
    return {"version":1,"status":"accepted","scope":SCOPE,
            "revision":expected_revision,"summary_sha256":public_proof["summary_sha256"],
            "case_count":len(rows),"private_manifest_count":len(rows),
            "private_lifecycle_count":len(rows),
            "gate_diagnostics_sha256":public["gate_diagnostics_sha256"],
            "private_test_artifacts":private_artifacts,
            "environment_evidence":rows,
            "process_generations_verified":True,"fault_evidence_verified":True,
            "runtime_absence_verified":True,"staged_inputs_verified":True,
            "private_paths_or_runtime_identities_disclosed":False,
            "note":"Exact private-byte correlation only; hashes do not prove hosted execution, VM disposal or gameplay beyond the gate."}

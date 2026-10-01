"""Read-only correlation of a current public gate summary and retained private evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..run_ci import inputs_match
from .ci_result import EXPECTED_CASES, inspect_ci_result
from .environment import SetupError, require_process_teardowns

SCOPE = "current-isolated-public-summary-to-private-per-case-evidence-correlation"


def _read(path, limit, label):
    try:
        path = Path(path)
        if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= limit:
            raise OSError()
        raw = path.read_bytes()
        if len(raw) > limit:
            raise OSError()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SetupError(f"cannot read private isolated {label}") from error
    if not isinstance(value, dict):
        raise SetupError(f"private isolated {label} is not an object")
    return raw, value


def inspect_ci_private_evidence(summary_path, private_run_dir, expected_revision):
    public_proof = inspect_ci_result(summary_path, expected_revision)
    _, public = _read(summary_path, 1024 * 1024, "public summary")
    supplied_root = Path(private_run_dir)
    if supplied_root.is_symlink() or not supplied_root.is_dir():
        raise SetupError("private isolated run root is missing or unsafe")
    root = supplied_root.resolve()
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
    expected = {(row["manifest_sha256"],row["lifecycle_sha256"]):row["case"]
                for row in public["environment_evidence"]}
    found, databases, runtimes = {}, set(), set()
    for child in children:
        manifest_raw, manifest = _read(child / "manifest.json", 1024 * 1024, "manifest")
        lifecycle_raw, lifecycle = _read(child / "process-lifecycle.json", 256 * 1024, "lifecycle")
        pair = (hashlib.sha256(manifest_raw).hexdigest(),
                hashlib.sha256(lifecycle_raw).hexdigest())
        case = expected.get(pair)
        if case is None or case in found:
            raise SetupError("private isolated evidence hash is foreign or duplicated")
        if (set(lifecycle) != {"version","scope","starts","teardowns"}
                or type(lifecycle.get("version")) is not int or lifecycle["version"] != 1
                or lifecycle.get("scope") != "exact-owned-isolated-process-teardown-not-graceful-server-exit"):
            raise SetupError("private isolated lifecycle schema is invalid")
        require_process_teardowns(lifecycle.get("starts"), lifecycle.get("teardowns"))
        if not inputs_match(public["identities"], manifest, public["revision"],
                            public["source_dirty"], public["deadline_scale"]):
            raise SetupError("private isolated staged source/input identity differs from public summary")
        database, runtime, ports = manifest.get("database"), manifest.get("runtime"), manifest.get("ports")
        runtime_path = Path(runtime).resolve() if isinstance(runtime, str) else None
        if (not isinstance(database, str) or not database.startswith("sapphire_e2e_")
                or len(database) != len("sapphire_e2e_") + 32
                or any(char not in "0123456789abcdef" for char in database[len("sapphire_e2e_"):])
                or not isinstance(runtime, str) or not Path(runtime).is_absolute()
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
             "lifecycle_sha256":found[case][1]} for case in EXPECTED_CASES]
    if rows != public["environment_evidence"]:
        raise SetupError("private isolated evidence order or identity differs from public summary")
    return {"version":1,"status":"accepted","scope":SCOPE,
            "revision":expected_revision,"summary_sha256":public_proof["summary_sha256"],
            "case_count":len(rows),"private_manifest_count":len(rows),
            "private_lifecycle_count":len(rows),
            "gate_diagnostics_sha256":public["gate_diagnostics_sha256"],
            "environment_evidence":rows,
            "process_generations_verified":True,"staged_inputs_verified":True,
            "private_paths_or_runtime_identities_disclosed":False,
            "note":"Exact private-byte correlation only; hashes do not prove hosted execution, VM disposal or gameplay beyond the gate."}

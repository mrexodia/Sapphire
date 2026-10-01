"""Fail-closed host evidence for one explicitly launched Windows Sandbox session.

Process absence is not guest logout, server exclusion, or proof of the pixels in a
discard dialog. A separate operator confirmation is required by the composite
verifier. This module never kills a Sandbox process.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time
import uuid

from .client_provenance import require_prepared_inputs
from .development import DevelopmentError
from .environment import REPO

SANDBOX_NAMES = frozenset({"windowssandbox.exe", "windowssandboxclient.exe",
                           "windowssandboxremotesession.exe"})
SESSION_SCOPE = "exact-prepared-windows-sandbox-launch-with-no-preexisting-sandbox-ui"
DISPOSAL_SCOPE = "owned-sandbox-ui-processes-observed-absent-after-launch-not-dialog-review"
CONFIRMATION_SCOPE = "manual-owned-sandbox-discard-confirmation-not-process-proof"
COMPOSITE_SCOPE = "current-graphical-result-and-explicit-owned-sandbox-disposal"


def _sha256(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError as error:
        raise DevelopmentError(f"cannot hash disposal evidence: {Path(path).name}") from error


def _read(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DevelopmentError(f"cannot read disposal evidence: {Path(path).name}") from error
    if not isinstance(value, dict):
        raise DevelopmentError(f"disposal evidence is not an object: {Path(path).name}")
    return value


def _write_new(path, value):
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"refuse to overwrite disposal evidence: {path.name}")
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    try:
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def sandbox_processes():
    """Return exact host Sandbox UI identities or fail rather than omit ambiguity."""
    import psutil
    rows = []
    for process in psutil.process_iter(["pid", "name", "create_time"]):
        try:
            name = process.info["name"]
            if isinstance(name, str) and name.casefold() in SANDBOX_NAMES:
                pid, created = process.info["pid"], process.info["create_time"]
                if type(pid) is not int or pid <= 0 or type(created) not in (int, float):
                    raise DevelopmentError("Sandbox process identity is malformed")
                rows.append({"pid": pid, "name": name.casefold(),
                             "create_time": float(created)})
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied as error:
            raise DevelopmentError("cannot inspect all Sandbox UI processes") from error
    return sorted(rows, key=lambda row: (row["pid"], row["create_time"], row["name"]))


def _prepared(prepared):
    prepared = Path(prepared).resolve()
    if not prepared.is_relative_to((REPO / ".e2e-artifacts").resolve()):
        raise DevelopmentError("prepared Sandbox must be under .e2e-artifacts")
    config, inputs = prepared / "run.wsb", prepared / "inputs.json"
    if not config.is_file() or not inputs.is_file() or not (prepared / "output").is_dir():
        raise DevelopmentError("prepared Sandbox inputs are incomplete")
    manifest = _read(inputs)
    if (manifest.get("status") != "prepared_not_executed"
            or manifest.get("config_sha256") != _sha256(config)):
        raise DevelopmentError("prepared Sandbox manifest/config binding is invalid")
    require_prepared_inputs(prepared, manifest.get("source_revision"))
    return prepared, config, inputs


def run_prepared_sandbox(prepared, timeout_seconds=1800, *, snapshot=sandbox_processes,
                         launch=subprocess.Popen, monotonic=time.monotonic,
                         wall_time=time.time, sleep=time.sleep, executable=None):
    """Launch exactly one prepared Sandbox and record bounded host-side disposal.

    The operator must close the owned window and confirm its discard dialog. On a
    timeout this function records failure but deliberately leaves the Sandbox for
    explicit operator handling; it never retries or kills the process.
    """
    if type(timeout_seconds) is not int or not 60 <= timeout_seconds <= 7200:
        raise DevelopmentError("Sandbox disposal timeout must be an integer from 60 to 7200")
    prepared, config, inputs = _prepared(prepared)
    session_path = prepared / "sandbox-session.json"
    disposal_path = prepared / "sandbox-disposal.json"
    failure_path = prepared / "sandbox-disposal-failure.json"
    if any(path.exists() for path in (session_path, disposal_path, failure_path)):
        raise FileExistsError("refuse to reuse Sandbox lifecycle evidence")
    before = snapshot()
    if before:
        raise DevelopmentError("refuse to launch while any Sandbox UI process exists")
    if executable is None and os.name != "nt":
        raise DevelopmentError("Windows Sandbox launch requires a Windows host")
    executable = (Path(executable) if executable is not None else
                  Path(os.environ.get("WINDIR", "")) / "System32/WindowsSandbox.exe")
    if not executable.is_file():
        raise DevelopmentError("Windows Sandbox executable is unavailable")

    session_id, started_at, start = uuid.uuid4().hex, wall_time(), monotonic()
    process = launch([str(executable), str(config)])
    if type(getattr(process, "pid", None)) is not int or process.pid <= 0:
        raise DevelopmentError("Windows Sandbox launcher PID is invalid")
    observed = {}
    session = {"version": 1, "session": session_id, "scope": SESSION_SCOPE,
               "config_sha256": _sha256(config), "inputs_sha256": _sha256(inputs),
               "launcher_pid": process.pid, "timeout_seconds": timeout_seconds,
               "started_at_unix": started_at}
    _write_new(session_path, session)
    deadline = start + timeout_seconds
    try:
        launcher_observed = False
        while monotonic() < deadline:
            rows = snapshot()
            for row in rows:
                observed[(row["pid"], row["create_time"], row["name"])] = row
                launcher_observed |= row["pid"] == process.pid
            if launcher_observed:
                break
            if process.poll() is not None:
                raise DevelopmentError("Sandbox launcher exited before its exact PID was observed")
            sleep(0.25)
        if not launcher_observed:
            raise TimeoutError("Sandbox launcher PID was not observed before deadline")

        while monotonic() < deadline:
            rows = snapshot()
            for row in rows:
                observed[(row["pid"], row["create_time"], row["name"])] = row
            if not rows:
                break
            sleep(0.5)
        else:
            raise TimeoutError("owned Sandbox was not disposed before deadline")
        sleep(1)
        remaining = snapshot()
        if remaining:
            raise DevelopmentError("Sandbox UI process reappeared after disposal observation")
        try:
            returncode = process.wait(timeout=5)
        except subprocess.TimeoutExpired as error:
            raise DevelopmentError("exact Sandbox launcher exit was not observed") from error
        if type(returncode) is not int:
            raise DevelopmentError("exact Sandbox launcher return code is unavailable")
        elapsed = monotonic() - start
        if not math.isfinite(elapsed) or elapsed < 0 or elapsed > timeout_seconds + 6:
            raise DevelopmentError("Sandbox lifecycle elapsed time is invalid")
        result_path = prepared / "output/result.json"
        result = _read(result_path) if result_path.is_file() else {}
        result_binding = {"present": result_path.is_file(), "run": result.get("run"),
                          "status": result.get("status"),
                          "result_sha256": _sha256(result_path) if result_path.is_file() else None}
        disposal = {"version": 1, "status": "disposed", "scope": DISPOSAL_SCOPE,
                    "session": session_id, "session_sha256": _sha256(session_path),
                    "launcher_pid": process.pid, "launcher_returncode": returncode,
                    "observed_processes": sorted(observed.values(),
                        key=lambda row: (row["pid"], row["create_time"], row["name"])),
                    "remaining_processes": [], "elapsed_seconds": elapsed,
                    "result": result_binding}
        _write_new(disposal_path, disposal)
        return disposal
    except BaseException as error:
        failure = {"version": 1, "status": "failed", "scope": DISPOSAL_SCOPE,
                   "session": session_id, "session_sha256": _sha256(session_path),
                   "launcher_pid": process.pid, "observed_processes": sorted(
                       observed.values(), key=lambda row: (row["pid"], row["create_time"], row["name"])),
                   "remaining_processes": snapshot(),
                   "error": f"{type(error).__name__}: {error}",
                   "automatic_kill_attempted": False, "retry_attempted": False}
        _write_new(failure_path, failure)
        raise


def approve_disposal(prepared):
    """Record an operator's explicit confirmation of the owned discard dialog."""
    prepared, _, _ = _prepared(prepared)
    session_path, disposal_path = (prepared / "sandbox-session.json",
                                   prepared / "sandbox-disposal.json")
    session, disposal = _read(session_path), _read(disposal_path)
    if (disposal.get("status") != "disposed"
            or disposal.get("session") != session.get("session")
            or disposal.get("session_sha256") != _sha256(session_path)):
        raise DevelopmentError("cannot confirm an incomplete or foreign Sandbox disposal")
    receipt = {"version": 1, "confirmed": True, "scope": CONFIRMATION_SCOPE,
               "session": session["session"], "disposal_sha256": _sha256(disposal_path)}
    _write_new(prepared / "sandbox-disposal-review.json", receipt)
    return receipt


def require_disposal(prepared):
    """Read-only strict verification of exact launch, absence, and manual confirmation."""
    prepared, config, inputs = _prepared(prepared)
    session_path, disposal_path = (prepared / "sandbox-session.json",
                                   prepared / "sandbox-disposal.json")
    session, disposal = _read(session_path), _read(disposal_path)
    confirmation = _read(prepared / "sandbox-disposal-review.json")
    if (set(session) != {"version", "session", "scope", "config_sha256", "inputs_sha256",
                         "launcher_pid", "timeout_seconds", "started_at_unix"}
            or type(session.get("version")) is not int or session["version"] != 1
            or not isinstance(session.get("session"), str) or len(session["session"]) != 32
            or any(char not in "0123456789abcdef" for char in session["session"])
            or session.get("scope") != SESSION_SCOPE
            or session.get("config_sha256") != _sha256(config)
            or session.get("inputs_sha256") != _sha256(inputs)
            or type(session.get("launcher_pid")) is not int or session["launcher_pid"] <= 0
            or type(session.get("timeout_seconds")) is not int
            or not 60 <= session["timeout_seconds"] <= 7200
            or type(session.get("started_at_unix")) not in (int, float)
            or not math.isfinite(session["started_at_unix"])
            or session["started_at_unix"] <= 0):
        raise DevelopmentError("invalid Sandbox launch session evidence")
    if (set(disposal) != {"version", "status", "scope", "session", "session_sha256",
                          "launcher_pid", "launcher_returncode", "observed_processes",
                          "remaining_processes", "elapsed_seconds", "result"}
            or type(disposal.get("version")) is not int or disposal["version"] != 1
            or disposal.get("status") != "disposed" or disposal.get("scope") != DISPOSAL_SCOPE
            or disposal.get("session") != session["session"]
            or disposal.get("session_sha256") != _sha256(session_path)
            or type(disposal.get("launcher_pid")) is not int
            or disposal["launcher_pid"] != session["launcher_pid"]
            or type(disposal.get("launcher_returncode")) is not int
            or disposal.get("remaining_processes") != []
            or type(disposal.get("elapsed_seconds")) not in (int, float)
            or not math.isfinite(disposal["elapsed_seconds"])
            or not 0 <= disposal["elapsed_seconds"] <= session["timeout_seconds"] + 6
            or not isinstance(disposal.get("observed_processes"), list)
            or not isinstance(disposal.get("result"), dict)):
        raise DevelopmentError("invalid Sandbox disposal process evidence")
    rows = disposal["observed_processes"]
    identities = []
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {"pid", "name", "create_time"}
                or type(row.get("pid")) is not int or row["pid"] <= 0
                or row.get("name") not in SANDBOX_NAMES
                or type(row.get("create_time")) not in (int, float)
                or not math.isfinite(row["create_time"]) or row["create_time"] <= 0):
            raise DevelopmentError("invalid observed Sandbox process identity")
        identities.append((row["pid"], row["create_time"], row["name"]))
    if len(identities) != len(set(identities)):
        raise DevelopmentError("duplicate observed Sandbox process identity")
    if rows != sorted(rows, key=lambda row: (
            row["pid"], row["create_time"], row["name"])):
        raise DevelopmentError("observed Sandbox process identities are not canonical")
    if not any(row["pid"] == session["launcher_pid"] for row in rows):
        raise DevelopmentError("exact launched Sandbox PID was never observed")
    if (set(confirmation) != {"version", "confirmed", "scope", "session", "disposal_sha256"}
            or type(confirmation.get("version")) is not int or confirmation["version"] != 1
            or confirmation.get("confirmed") is not True
            or confirmation.get("scope") != CONFIRMATION_SCOPE
            or confirmation.get("session") != session["session"]
            or confirmation.get("disposal_sha256") != _sha256(disposal_path)):
        raise DevelopmentError("invalid manual Sandbox discard confirmation")
    result = disposal["result"]
    if (set(result) != {"present", "run", "status", "result_sha256"}
            or result.get("present") is not True or result.get("status") != "passed"
            or not isinstance(result.get("run"), str) or len(result["run"]) != 32
            or any(char not in "0123456789abcdef" for char in result["run"])
            or result.get("result_sha256") != _sha256(prepared / "output/result.json")):
        raise DevelopmentError("Sandbox disposal is not bound to one passing guest result")
    return {"version": 1, "verified": True, "scope": COMPOSITE_SCOPE,
            "session": session["session"], "run": result["run"],
            "launcher_pid": session["launcher_pid"],
            "launcher_returncode": disposal["launcher_returncode"],
            "result_sha256": result["result_sha256"],
            "operator_confirmation": True, "sandbox_disposal_verified": True}


def inspect_completed_sandbox(prepared, expected_source_revision):
    """Combine current guest evidence with separately verified owned disposal."""
    from .client_result import inspect_client_development_result
    prepared = Path(prepared).resolve()
    graphical = inspect_client_development_result(
        prepared / "output", expected_source_revision)
    disposal = require_disposal(prepared)
    if (disposal["run"] != graphical["run"]
            or disposal["result_sha256"] != graphical["result_sha256"]):
        raise DevelopmentError("Sandbox disposal and graphical result differ")
    return {"version": 1, "status": "accepted", "scope": COMPOSITE_SCOPE,
            "run": graphical["run"], "source_revision": expected_source_revision,
            "result_sha256": graphical["result_sha256"],
            "graphical_result_scope": graphical["scope"],
            "disposal": disposal, "sandbox_disposal_verified": True,
            "note": "Exact owned host UI process disposal plus manual confirmation; not server-offline, reset, or pixel-recognition proof."}

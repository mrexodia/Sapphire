"""Strict read-only validation of the sanitized isolated-gate public summary.

The public process-cleanup boolean is produced only after run_ci validates private
exact generation records. This consumer cannot reconstruct those deleted private
records and is not independent process-teardown evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..run_ci import CASES, CATALOGS
from .environment import SetupError

SCOPE = "current-isolated-public-summary-with-exact-process-cleanup-claim"


def _hex(value, length=64):
    return (isinstance(value, str) and len(value) == length
            and all(char in "0123456789abcdef" for char in value))


def _hashes(value, keys):
    return (isinstance(value, dict) and set(value) == set(keys)
            and all(_hex(value[key]) for key in keys))


def inspect_ci_result(summary_path, expected_revision):
    path = Path(summary_path).resolve()
    if not _hex(expected_revision, 40):
        raise SetupError("expected isolated-gate revision must be exact lowercase git identity")
    try:
        raw = path.read_bytes()
        report = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SetupError("cannot read isolated-gate public summary") from error
    fields = {"version","status","stage","scope","revision","source_dirty","identities",
              "deadline_scale","collection_verified","cleanup_verified",
              "process_cleanup_verified","cases","pytest_exit_code","inputs_verified"}
    if (not isinstance(report, dict) or set(report) != fields
            or type(report.get("version")) is not int or report["version"] != 1
            or report.get("status") != "passed" or report.get("stage") != "verified"
            or report.get("scope") != "headless-live-not-real-client"
            or report.get("revision") != expected_revision
            or report.get("source_dirty") is not False
            or type(report.get("deadline_scale")) is not int
            or not 1 <= report["deadline_scale"] <= 3
            or report.get("collection_verified") is not True
            or report.get("cleanup_verified") is not True
            or report.get("process_cleanup_verified") is not True
            or report.get("inputs_verified") is not True
            or type(report.get("pytest_exit_code")) is not int
            or report["pytest_exit_code"] != 0
            or not isinstance(report.get("cases"), dict)
            or list(report["cases"]) != list(CASES)
            or any(value is not True for value in report["cases"].values())):
        raise SetupError("isolated-gate public summary is incomplete, foreign or failed")
    identities = report.get("identities")
    if (not isinstance(identities, dict)
            or set(identities) != {"worker","binaries","catalogs","meshes","script_modules"}
            or not _hex(identities.get("worker"))
            or not _hashes(identities.get("binaries"), ("api","lobby","server","dbm"))
            or not _hashes(identities.get("catalogs"), CATALOGS)
            or not _hashes(identities.get("meshes"), ("w1t1","w1f2"))
            or not isinstance(identities.get("script_modules"), list)
            or not identities["script_modules"]
            or identities["script_modules"] != sorted(identities["script_modules"])
            or len(set(identities["script_modules"])) != len(identities["script_modules"])
            or any(not _hex(value) for value in identities["script_modules"])):
        raise SetupError("isolated-gate input identities are malformed")
    return {"version":1,"status":"accepted","scope":SCOPE,
            "revision":expected_revision,"summary_sha256":hashlib.sha256(raw).hexdigest(),
            "case_count":len(CASES),"deadline_scale":report["deadline_scale"],
            "collection_verified":True,"inputs_verified":True,"cleanup_verified":True,
            "process_cleanup_verified":True,
            "note":"Public gate claim only; private PID/generation records, hosted execution and real-client compatibility are out of scope."}

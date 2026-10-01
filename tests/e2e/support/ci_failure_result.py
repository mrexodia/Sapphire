"""Fail-only validation for sanitized isolated-gate summaries before publication."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .ci_result import EXPECTED_CASES, EXPECTED_CATALOGS
from .environment import SetupError

SCOPE = "failed-isolated-gate-sanitized-publication-not-success-evidence"
_BASE = {"version","status","stage","scope"}
_SOURCE = {"revision","source_dirty","identities","deadline_scale"}
_GATE = {"collection_verified","environment_isolation_verified","environment_evidence",
         "cleanup_verified","process_cleanup_verified","cases","pytest_exit_code"}
_POST = {"gate_diagnostics_sha256","private_test_artifacts","inputs_verified"}


def _hex(value, length=64):
    return (isinstance(value, str) and len(value) == length
            and all(char in "0123456789abcdef" for char in value))


def _identities(value):
    if (not isinstance(value, dict)
            or set(value) != {"worker","binaries","catalogs","meshes","script_modules"}
            or not _hex(value.get("worker"))
            or not isinstance(value.get("binaries"), dict)
            or set(value["binaries"]) != {"api","lobby","server","dbm"}
            or any(not _hex(digest) for digest in value["binaries"].values())
            or not isinstance(value.get("catalogs"), dict)
            or tuple(value["catalogs"]) != EXPECTED_CATALOGS
            or any(not _hex(digest) for digest in value["catalogs"].values())
            or not isinstance(value.get("meshes"), dict)
            or set(value["meshes"]) != {"w1t1","w1f2"}
            or any(not _hex(digest) for digest in value["meshes"].values())
            or not isinstance(value.get("script_modules"), list)
            or not value["script_modules"]
            or value["script_modules"] != sorted(value["script_modules"])
            or len(set(value["script_modules"])) != len(value["script_modules"])
            or any(not _hex(digest) for digest in value["script_modules"])):
        raise SetupError("failed isolated-gate component identities are malformed")


def _source_fields(report, expected_revision):
    if (report.get("revision") != expected_revision or report.get("source_dirty") is not False
            or type(report.get("deadline_scale")) is not int
            or not 1 <= report["deadline_scale"] <= 3):
        raise SetupError("failed isolated-gate source identity is malformed")
    _identities(report.get("identities"))


def _gate_fields(report):
    if (any(type(report.get(key)) is not bool for key in
            ("collection_verified","environment_isolation_verified","cleanup_verified",
             "process_cleanup_verified"))
            or not isinstance(report.get("cases"), dict)
            or list(report["cases"]) != list(EXPECTED_CASES)
            or any(type(value) is not bool for value in report["cases"].values())
            or type(report.get("pytest_exit_code")) is not int):
        raise SetupError("failed isolated-gate outcomes are malformed")
    rows = report.get("environment_evidence")
    if not isinstance(rows, list) or len(rows) not in {0,len(EXPECTED_CASES)}:
        raise SetupError("failed isolated-gate environment evidence is malformed")
    if rows:
        if ([row.get("case") for row in rows] != list(EXPECTED_CASES)
                or any(not isinstance(row, dict)
                       or set(row) != {"case","manifest_sha256","lifecycle_sha256",
                                      "artifact_tree_sha256"}
                       or any(not _hex(row.get(key)) for key in
                              ("manifest_sha256","lifecycle_sha256","artifact_tree_sha256"))
                       for row in rows)):
            raise SetupError("failed isolated-gate environment evidence is malformed")


def inspect_ci_failure_result(summary_path, expected_revision):
    if not _hex(expected_revision, 40):
        raise SetupError("expected failed-gate revision must be exact lowercase git identity")
    path = Path(summary_path).resolve()
    try:
        if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 1024 * 1024:
            raise OSError()
        raw = path.read_bytes()
        report = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SetupError("cannot read failed isolated-gate public summary") from error
    if (not isinstance(report, dict) or report.get("version") != 1
            or type(report.get("version")) is not int or report.get("status") != "failed"
            or report.get("stage") not in {"preflight","suite","verification"}
            or report.get("scope") != "headless-live-not-real-client"):
        raise SetupError("failed isolated-gate public summary is foreign or malformed")
    keys, stage = set(report), report["stage"]
    if stage == "preflight":
        if keys not in (_BASE, _BASE | _SOURCE):
            raise SetupError("failed isolated-gate preflight summary exposes unexpected fields")
        if keys == _BASE | _SOURCE:
            _source_fields(report, expected_revision)
    else:
        if (not (_BASE | _SOURCE) <= keys
                or keys - (_BASE | _SOURCE | _GATE | _POST)):
            raise SetupError("failed isolated-gate suite summary exposes unexpected fields")
        _source_fields(report, expected_revision)
        gate_present = keys & _GATE
        if gate_present and gate_present != _GATE:
            raise SetupError("failed isolated-gate outcome group is incomplete")
        if gate_present:
            _gate_fields(report)
        if "gate_diagnostics_sha256" in report and (not gate_present
                or not _hex(report["gate_diagnostics_sha256"])):
            raise SetupError("failed isolated-gate diagnostics identity is malformed")
        if "private_test_artifacts" in report:
            artifacts = report["private_test_artifacts"]
            if ("gate_diagnostics_sha256" not in report or not isinstance(artifacts, dict)
                    or set(artifacts) != {"profile_sha256","pytest_log_sha256","junit_sha256"}
                    or any(not _hex(value) for value in artifacts.values())):
                raise SetupError("failed isolated-gate private artifact identities are malformed")
        if "inputs_verified" in report and ("private_test_artifacts" not in report
                or type(report["inputs_verified"]) is not bool):
            raise SetupError("failed isolated-gate input result is malformed")
        if stage == "verification":
            if keys != _BASE | _SOURCE | _GATE | _POST:
                raise SetupError("failed isolated-gate verification summary is incomplete")
            failed = (report["pytest_exit_code"] != 0
                      or any(report[key] is False for key in
                             ("collection_verified","environment_isolation_verified",
                              "cleanup_verified","process_cleanup_verified","inputs_verified"))
                      or any(value is False for value in report["cases"].values()))
            if not failed:
                raise SetupError("failed isolated-gate verification summary has no failed outcome")
    return {"version":1,"status":"accepted","scope":SCOPE,"gate_status":"failed",
            "stage":stage,"summary_sha256":hashlib.sha256(raw).hexdigest(),
            "success_evidence_accepted":False}

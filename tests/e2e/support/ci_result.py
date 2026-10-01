"""Strict read-only validation of the sanitized isolated-gate public summary.

The public process-cleanup boolean is produced only after run_ci validates private
exact generation records. This consumer cannot reconstruct those deleted private
records and is not independent process-teardown evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .environment import SetupError

SCOPE = "current-isolated-public-summary-with-exact-process-cleanup-claim"
EXPECTED_CASES = (
    "tests/e2e/test_live.py::test_rejected_credentials",
    "tests/e2e/test_live.py::test_login_idle_logout",
    "tests/e2e/test_live.py::test_received_party_join_and_leave",
    "tests/e2e/test_live.py::test_observed_movement_and_position_persistence",
    "tests/e2e/test_live_quest.py::test_quest_cancel_complete_rewards_and_restart[single]",
    "tests/e2e/test_live_quest.py::test_quest_cancel_complete_rewards_and_restart[chain]",
    "tests/e2e/test_live_zoning.py::test_observed_exit_crossing_and_territory_persistence",
    "tests/e2e/test_live_zoning.py::test_observed_living_return_action",
    "tests/e2e/test_live_combat.py::test_observed_sprint_status_and_tp_debit",
    "tests/e2e/test_live_combat.py::test_observed_fast_blade_damage",
    "tests/e2e/test_live_progression.py::test_natural_pugilist_level_two_true_strike",
    "tests/e2e/test_live_combo.py::test_natural_level_four_fast_blade_combo",
    "tests/e2e/test_live_aggro.py::test_natural_vision_aggro_without_player_action",
    "tests/e2e/test_live_player_defeat.py::test_natural_enemy_defeats_level_one_player",
    "tests/e2e/test_live_creation.py::test_lobby_character_creation_and_opening_persistence",
)
EXPECTED_CATALOGS = ("quest_catalog","follow_up_catalog","transition_catalog",
                     "combat_catalog","shop_catalog","respawn_catalog",
                     "pursuit_catalog","opening_quest_catalog")


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
              "deadline_scale","collection_verified","environment_isolation_verified",
              "environment_evidence","gate_diagnostics_sha256","cleanup_verified",
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
            or report.get("environment_isolation_verified") is not True
            or not _hex(report.get("gate_diagnostics_sha256"))
            or report.get("cleanup_verified") is not True
            or report.get("process_cleanup_verified") is not True
            or report.get("inputs_verified") is not True
            or type(report.get("pytest_exit_code")) is not int
            or report["pytest_exit_code"] != 0
            or not isinstance(report.get("cases"), dict)
            or list(report["cases"]) != list(EXPECTED_CASES)
            or any(value is not True for value in report["cases"].values())):
        raise SetupError("isolated-gate public summary is incomplete, foreign or failed")
    evidence = report.get("environment_evidence")
    if (not isinstance(evidence, list) or len(evidence) != len(EXPECTED_CASES)
            or [row.get("case") if isinstance(row, dict) else None for row in evidence]
               != list(EXPECTED_CASES)
            or any(set(row) != {"case","manifest_sha256","lifecycle_sha256"}
                   or not _hex(row.get("manifest_sha256"))
                   or not _hex(row.get("lifecycle_sha256")) for row in evidence)
            or len({row["manifest_sha256"] for row in evidence}) != len(EXPECTED_CASES)):
        raise SetupError("isolated-gate per-case evidence identities are malformed")
    identities = report.get("identities")
    if (not isinstance(identities, dict)
            or set(identities) != {"worker","binaries","catalogs","meshes","script_modules"}
            or not _hex(identities.get("worker"))
            or not _hashes(identities.get("binaries"), ("api","lobby","server","dbm"))
            or not _hashes(identities.get("catalogs"), EXPECTED_CATALOGS)
            or not _hashes(identities.get("meshes"), ("w1t1","w1f2"))
            or not isinstance(identities.get("script_modules"), list)
            or not identities["script_modules"]
            or identities["script_modules"] != sorted(identities["script_modules"])
            or len(set(identities["script_modules"])) != len(identities["script_modules"])
            or any(not _hex(value) for value in identities["script_modules"])):
        raise SetupError("isolated-gate input identities are malformed")
    return {"version":1,"status":"accepted","scope":SCOPE,
            "revision":expected_revision,"summary_sha256":hashlib.sha256(raw).hexdigest(),
            "case_count":len(EXPECTED_CASES),"deadline_scale":report["deadline_scale"],
            "collection_verified":True,"environment_isolation_verified":True,
            "environment_evidence":evidence,
            "gate_diagnostics_sha256":report["gate_diagnostics_sha256"],
            "inputs_verified":True,"cleanup_verified":True,
            "process_cleanup_verified":True,
            "note":"Public gate claim only; private PID/generation records, hosted execution and real-client compatibility are out of scope."}

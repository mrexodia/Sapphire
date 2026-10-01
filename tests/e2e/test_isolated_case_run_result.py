"""Publication-boundary contracts for strict standalone private runs."""
import hashlib
import json
import os
from pathlib import Path

import pytest

from .run_ci import CASES
from .support import isolated_case_run_result as result_support
from .support.environment import SetupError
from .support.isolated_case_runner import SCOPE as RUNNER_SCOPE
from .support.isolated_fault_result import FAULT_CASE

REVISION = "a" * 40


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def make_run(tmp_path, monkeypatch, case=CASES[0]):
    tmp_path.mkdir(parents=True, exist_ok=True)
    repository = tmp_path / "repo"
    repository.mkdir()
    root = tmp_path / "private"
    artifact = root / "artifacts" / "sapphire-e2e-fixture"
    artifact.mkdir(parents=True)
    (root / "profile.json").write_text("{}", encoding="utf-8")
    (root / "pytest.log").write_text("private pytest output\n", encoding="utf-8")
    (root / "live.xml").write_text("<testsuites />\n", encoding="utf-8")
    write_json(artifact / "manifest.json", {"fixture": "exact"})
    proof = {
        "version": 1, "status": "accepted",
        "scope": "fault-proof" if case == FAULT_CASE else "generic-proof",
        "sanitized_scenario_receipt_verified": case == CASES[0],
    }
    write_json(root / "inspection.json", proof)
    inspection_hash = hashlib.sha256((root / "inspection.json").read_bytes()).hexdigest()
    runner_result = {
        "version": 1, "status": "accepted", "stage": "verified", "scope": RUNNER_SCOPE,
        "case": case, "source_revision": REVISION, "source_dirty": False,
        "execution_authorized": True, "pytest_exit_code": 0, "exact_single_case_verified": True,
        "profile_inputs_verified": True, "inspection_sha256": inspection_hash,
        "inspection_scope": proof["scope"], "short_feedback_only": True,
        "generic_scenario_semantics_independently_verified": False,
        "specialized_fault_inspection_applied": case == FAULT_CASE,
        "combined_gate_verified": False,
    }
    write_json(root / "runner-result.json", runner_result)

    monkeypatch.setattr(result_support, "REPO", repository)
    monkeypatch.setattr(result_support, "_repository_identity", lambda: (REVISION, False))
    monkeypatch.setattr(result_support, "_validated_profile",
                        lambda *args, **kwargs: (b"{}", {
                            "artifacts": str(root / "artifacts"), "deadline_scale": 1,
                        }, {"inputs": "exact"}))
    monkeypatch.setattr(result_support, "inputs_match",
                        lambda identities, manifest, revision, dirty, scale:
                        identities == {"inputs": "exact"} and manifest == {"fixture": "exact"}
                        and revision == REVISION and dirty is False and scale == 1)
    monkeypatch.setattr(result_support, "inspect_isolated_case",
                        lambda artifact_dir, junit, log, expected_case, revision: dict(proof))
    monkeypatch.setattr(result_support, "inspect_isolated_fault",
                        lambda artifact_dir, junit, log, revision: dict(proof))
    return root, artifact, proof, runner_result


@pytest.mark.parametrize("case", [CASES[0], FAULT_CASE])
def test_private_run_reinspection_emits_only_sanitized_fixed_receipt(tmp_path, monkeypatch, case):
    root, artifact, retained, runner_result = make_run(tmp_path, monkeypatch, case)
    proof = result_support.inspect_isolated_case_run(root, case, REVISION)
    assert proof == {
        "version": 1, "status": "accepted", "scope": result_support.SCOPE,
        "source_revision": REVISION, "source_dirty": False, "case": case,
        "execution_authorized": True, "runner_result_sha256": hashlib.sha256((root / "runner-result.json").read_bytes()).hexdigest(),
        "inspection_sha256": hashlib.sha256((root / "inspection.json").read_bytes()).hexdigest(),
        "inspection_scope": retained["scope"], "private_evidence_reinspected": True,
        "profile_inputs_verified": True, "short_feedback_only": True,
        "generic_scenario_semantics_independently_verified": False,
        "specialized_fault_inspection_applied": case == FAULT_CASE,
        "sanitized_scenario_receipt_verified": case == CASES[0],
        "combined_gate_verified": False,
        "private_paths_ports_credentials_database_or_pids_disclosed": False,
        "note": "One exact private standalone case only; not combined acceptance, hosted execution, compatibility, build provenance or independent generic scenario truth.",
    }
    text = json.dumps(proof)
    assert str(root) not in text and str(artifact) not in text


@pytest.mark.parametrize("mutation", [
    "status", "stage", "dirty", "authorization", "typed_exit", "inspection_hash", "short_feedback",
    "generic_semantics", "fault_flag", "combined", "unknown_field", "foreign_case",
])
def test_private_run_reinspection_rejects_malformed_or_overclaimed_result(
        tmp_path, monkeypatch, mutation):
    root, _, _, value = make_run(tmp_path, monkeypatch)
    if mutation == "status": value["status"] = "failed"
    elif mutation == "stage": value["stage"] = "inspection"
    elif mutation == "dirty": value["source_dirty"] = True
    elif mutation == "authorization": value["execution_authorized"] = False
    elif mutation == "typed_exit": value["pytest_exit_code"] = False
    elif mutation == "inspection_hash": value["inspection_sha256"] = "0" * 64
    elif mutation == "short_feedback": value["short_feedback_only"] = False
    elif mutation == "generic_semantics": value["generic_scenario_semantics_independently_verified"] = True
    elif mutation == "fault_flag": value["specialized_fault_inspection_applied"] = True
    elif mutation == "combined": value["combined_gate_verified"] = True
    elif mutation == "unknown_field": value["private_path"] = "PRIVATE"
    else: value["case"] = CASES[1]
    write_json(root / "runner-result.json", value)
    with pytest.raises(SetupError, match="runner result"):
        result_support.inspect_isolated_case_run(root, CASES[0], REVISION)


@pytest.mark.parametrize("mutation", [
    "extra_root", "missing_root", "two_artifacts", "profile_owner", "inputs",
    "inspection_changed", "repository_dirty", "repository_revision",
])
def test_private_run_reinspection_rejects_ambiguous_or_changed_evidence(
        tmp_path, monkeypatch, mutation):
    root, _, proof, _ = make_run(tmp_path, monkeypatch)
    if mutation == "extra_root": (root / "foreign.txt").write_text("foreign")
    elif mutation == "missing_root": (root / "pytest.log").unlink()
    elif mutation == "two_artifacts": (root / "artifacts" / "foreign").mkdir()
    elif mutation == "profile_owner":
        monkeypatch.setattr(result_support, "_validated_profile",
                            lambda *args, **kwargs: (b"{}", {
                                "artifacts": str(tmp_path / "foreign"), "deadline_scale": 1,
                            }, {"inputs": "exact"}))
    elif mutation == "inputs": monkeypatch.setattr(result_support, "inputs_match", lambda *args: False)
    elif mutation == "inspection_changed":
        monkeypatch.setattr(result_support, "inspect_isolated_case",
                            lambda *args: {**proof, "scope": "changed"})
    elif mutation == "repository_dirty":
        monkeypatch.setattr(result_support, "_repository_identity", lambda: (REVISION, True))
    else:
        monkeypatch.setattr(result_support, "_repository_identity", lambda: ("b" * 40, False))
    with pytest.raises(SetupError):
        result_support.inspect_isolated_case_run(root, CASES[0], REVISION)


def test_private_run_reinspection_rejects_duplicate_keys_and_hard_links(tmp_path, monkeypatch):
    root, _, _, _ = make_run(tmp_path, monkeypatch)
    result_path = root / "runner-result.json"
    result_path.write_text('{"version":1,"version":1}\n')
    with pytest.raises(SetupError, match="parse"):
        result_support.inspect_isolated_case_run(root, CASES[0], REVISION)

    root, _, _, _ = make_run(tmp_path / "hardlink", monkeypatch)
    result_path = root / "runner-result.json"
    other = tmp_path / "linked-result.json"
    other.write_bytes(result_path.read_bytes())
    result_path.unlink()
    try:
        os.link(other, result_path)
    except OSError:
        pytest.skip("hard links unavailable")
    with pytest.raises(SetupError, match="cannot read"):
        result_support.inspect_isolated_case_run(root, CASES[0], REVISION)

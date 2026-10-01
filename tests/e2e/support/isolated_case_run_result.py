"""Independent private-root consumer for one strict standalone case run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import stat
import subprocess

from ..run_ci import CASES, inputs_match
from .ci_profile_result import _validated_profile
from .environment import REPO, SetupError
from .isolated_case_result import inspect_isolated_case
from .isolated_fault_result import FAULT_CASE, inspect_isolated_fault
from .isolated_case_runner import SCOPE as RUNNER_SCOPE

SCOPE = "sanitized-strict-standalone-case-publication-v1"
_RESULT_FIELDS = {
    "version", "status", "stage", "scope", "case", "source_revision", "source_dirty",
    "execution_authorized", "pytest_exit_code", "exact_single_case_verified", "profile_inputs_verified",
    "inspection_sha256", "inspection_scope", "short_feedback_only",
    "generic_scenario_semantics_independently_verified",
    "specialized_fault_inspection_applied", "combined_gate_verified",
}
_ROOT_ENTRIES = {
    "artifacts", "profile.json", "pytest.log", "live.xml", "inspection.json",
    "runner-result.json",
}


def _hex(value, length):
    return (isinstance(value, str) and len(value) == length
            and all(char in "0123456789abcdef" for char in value))


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _raw(path, limit, label):
    path = Path(path)
    try:
        metadata = path.lstat()
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if (path.is_symlink() or not stat.S_ISREG(metadata.st_mode)
                or getattr(metadata, "st_file_attributes", 0) & reparse
                or metadata.st_nlink != 1 or not 0 < metadata.st_size <= limit):
            raise OSError()
        raw = path.read_bytes()
        if not 0 < len(raw) <= limit:
            raise OSError()
        return raw
    except OSError as error:
        raise SetupError(f"cannot read standalone publication {label}") from error


def _object(path, limit, label):
    raw = _raw(path, limit, label)
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise SetupError(f"cannot parse standalone publication {label}") from error
    if not isinstance(value, dict):
        raise SetupError(f"standalone publication {label} is not an object")
    return raw, value


def _repository_identity():
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    dirty = bool(subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=REPO, text=True))
    return revision, dirty


def inspect_isolated_case_run(private_root, expected_case, expected_revision, *, suffix=None):
    if expected_case not in CASES:
        raise SetupError("standalone publication case is not allowlisted")
    if not _hex(expected_revision, 40):
        raise SetupError("expected standalone publication revision must be exact lowercase git identity")
    supplied = Path(private_root)
    try:
        metadata = supplied.lstat()
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        root = supplied.resolve(strict=True)
        repository = Path(REPO).resolve()
        if (not supplied.is_absolute() or supplied.is_symlink()
                or not stat.S_ISDIR(metadata.st_mode)
                or getattr(metadata, "st_file_attributes", 0) & reparse
                or root == repository or repository in root.parents):
            raise OSError()
        entries = {entry.name: entry for entry in root.iterdir()}
    except (OSError, RuntimeError) as error:
        raise SetupError("standalone publication private root is missing or unsafe") from error
    if set(entries) != _ROOT_ENTRIES:
        raise SetupError("standalone publication private root is incomplete or ambiguous")
    try:
        artifact_metadata = entries["artifacts"].lstat()
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if (entries["artifacts"].is_symlink() or not stat.S_ISDIR(artifact_metadata.st_mode)
                or getattr(artifact_metadata, "st_file_attributes", 0) & reparse):
            raise OSError()
    except OSError as error:
        raise SetupError("standalone publication artifact root is unsafe") from error
    _raw(entries["profile.json"], 1024 * 1024, "profile")
    _raw(entries["pytest.log"], 16 * 1024 * 1024, "pytest log")
    _raw(entries["live.xml"], 16 * 1024 * 1024, "JUnit report")

    result_raw, result = _object(entries["runner-result.json"], 64 * 1024, "runner result")
    inspection_raw, retained_inspection = _object(
        entries["inspection.json"], 1024 * 1024, "inspection")
    if (set(result) != _RESULT_FIELDS
            or type(result.get("version")) is not int or result["version"] != 1
            or result.get("status") != "accepted" or result.get("stage") != "verified"
            or result.get("scope") != RUNNER_SCOPE or result.get("case") != expected_case
            or result.get("source_revision") != expected_revision
            or result.get("source_dirty") is not False
            or result.get("execution_authorized") is not True
            or type(result.get("pytest_exit_code")) is not int or result["pytest_exit_code"] != 0
            or result.get("exact_single_case_verified") is not True
            or result.get("profile_inputs_verified") is not True
            or not _hex(result.get("inspection_sha256"), 64)
            or result["inspection_sha256"] != hashlib.sha256(inspection_raw).hexdigest()
            or result.get("short_feedback_only") is not True
            or result.get("generic_scenario_semantics_independently_verified") is not False
            or result.get("specialized_fault_inspection_applied") is not (expected_case == FAULT_CASE)
            or result.get("combined_gate_verified") is not False):
        raise SetupError("standalone publication runner result is malformed or unsuccessful")

    revision, dirty = _repository_identity()
    if revision != expected_revision or dirty:
        raise SetupError("standalone publication requires the exact clean reviewed revision")
    _, profile, identities = _validated_profile(entries["profile.json"], suffix=suffix)
    artifacts_root = entries["artifacts"].resolve()
    if Path(profile.get("artifacts", "")).resolve() != artifacts_root:
        raise SetupError("standalone publication profile does not own the artifact root")
    try:
        artifact_entries = list(artifacts_root.iterdir())
    except OSError as error:
        raise SetupError("standalone publication artifact root is unavailable") from error
    if (artifacts_root.is_symlink() or len(artifact_entries) != 1
            or artifact_entries[0].is_symlink() or not artifact_entries[0].is_dir()):
        raise SetupError("standalone publication artifact ownership is ambiguous")
    artifact = artifact_entries[0]
    _, manifest = _object(artifact / "manifest.json", 1024 * 1024, "manifest")
    if not inputs_match(identities, manifest, expected_revision, False,
                        profile.get("deadline_scale", 1)):
        raise SetupError("standalone publication inputs do not match the reviewed profile")

    if expected_case == FAULT_CASE:
        proof = inspect_isolated_fault(
            artifact, entries["live.xml"], entries["pytest.log"], expected_revision)
    else:
        proof = inspect_isolated_case(
            artifact, entries["live.xml"], entries["pytest.log"],
            expected_case, expected_revision)
    if retained_inspection != proof or result.get("inspection_scope") != proof.get("scope"):
        raise SetupError("standalone publication retained inspection does not reproduce")
    final_revision, final_dirty = _repository_identity()
    if final_revision != expected_revision or final_dirty:
        raise SetupError("standalone publication source changed during inspection")

    return {
        "version": 1, "status": "accepted", "scope": SCOPE,
        "source_revision": expected_revision, "source_dirty": False,
        "case": expected_case, "execution_authorized": True,
        "runner_result_sha256": hashlib.sha256(result_raw).hexdigest(),
        "inspection_sha256": hashlib.sha256(inspection_raw).hexdigest(),
        "inspection_scope": proof["scope"], "private_evidence_reinspected": True,
        "profile_inputs_verified": True, "short_feedback_only": True,
        "generic_scenario_semantics_independently_verified": False,
        "specialized_fault_inspection_applied": expected_case == FAULT_CASE,
        "sanitized_scenario_receipt_verified": bool(
            proof.get("sanitized_scenario_receipt_verified", False)),
        "combined_gate_verified": False,
        "private_paths_ports_credentials_database_or_pids_disclosed": False,
        "note": "One exact private standalone case only; not combined acceptance, hosted execution, compatibility, build provenance or independent generic scenario truth.",
    }

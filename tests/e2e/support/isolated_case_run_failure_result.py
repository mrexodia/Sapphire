"""Sanitize one failed strict standalone run without accepting success evidence."""
from __future__ import annotations

import hashlib
from pathlib import Path
import stat

from .ci_result import EXPECTED_CASES
from .environment import REPO, SetupError
from .isolated_case_run_result import _hex, _object, _repository_identity
from .isolated_case_runner import SCOPE as RUNNER_SCOPE

SCOPE = "sanitized-failed-strict-standalone-case-publication-v1"
_BASE_FIELDS = {
    "version", "status", "stage", "scope", "case", "source_revision", "source_dirty",
    "execution_authorized",
}
_CLEANUP_FIELDS = {
    "captured_environment_cleanup_attempted", "captured_environment_cleanup_failed",
}


def _safe_diagnostic(path, limit):
    path = Path(path)
    try:
        metadata = path.lstat()
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        return (not path.is_symlink() and stat.S_ISREG(metadata.st_mode)
                and not getattr(metadata, "st_file_attributes", 0) & reparse
                and metadata.st_nlink == 1 and 0 < metadata.st_size <= limit)
    except OSError:
        return False


def inspect_failed_isolated_case_run(private_root, expected_case, expected_revision):
    if expected_case not in EXPECTED_CASES:
        raise SetupError("failed standalone publication case is not allowlisted")
    if not _hex(expected_revision, 40):
        raise SetupError("expected failed standalone revision must be exact lowercase git identity")
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
    except (OSError, RuntimeError) as error:
        raise SetupError("failed standalone private root is missing or unsafe") from error

    result_raw, result = _object(root / "runner-result.json", 64 * 1024, "failed runner result")
    fields = set(result)
    allowed = _BASE_FIELDS | {"pytest_exit_code"} | _CLEANUP_FIELDS
    if (not _BASE_FIELDS <= fields or fields - allowed
            or bool(fields & _CLEANUP_FIELDS) != (_CLEANUP_FIELDS <= fields)
            or type(result.get("version")) is not int or result["version"] != 1
            or result.get("status") != "failed"
            or result.get("stage") not in {"preflight", "suite", "inspection"}
            or result.get("scope") != RUNNER_SCOPE or result.get("case") != expected_case
            or result.get("source_revision") != expected_revision
            or result.get("source_dirty") is not False
            or result.get("execution_authorized") is not True
            or ("pytest_exit_code" in result
                and (type(result["pytest_exit_code"]) is not int or result["pytest_exit_code"] == 0))
            or ("pytest_exit_code" in result and result["stage"] == "preflight")):
        raise SetupError("failed standalone runner result is malformed or relabeled")
    cleanup_attempted = result.get("captured_environment_cleanup_attempted", False)
    cleanup_failed = result.get("captured_environment_cleanup_failed")
    if (_CLEANUP_FIELDS <= fields
            and (cleanup_attempted is not True or type(cleanup_failed) is not bool)):
        raise SetupError("failed standalone cleanup classification is malformed")
    if (root / "inspection.json").exists():
        raise SetupError("failed standalone run contains success inspection evidence")
    if not _safe_diagnostic(root / "entry-error.log", 16 * 1024 * 1024):
        raise SetupError("failed standalone entry diagnostic is missing or unsafe")
    cleanup_error = (root / "cleanup-error.log").exists()
    if cleanup_error != (cleanup_failed is True):
        raise SetupError("failed standalone cleanup diagnostic disagrees with classification")
    if cleanup_error and not _safe_diagnostic(root / "cleanup-error.log", 16 * 1024 * 1024):
        raise SetupError("failed standalone cleanup diagnostic is unsafe")
    pytest_log = (root / "pytest.log").exists()
    if pytest_log and not _safe_diagnostic(root / "pytest.log", 16 * 1024 * 1024):
        raise SetupError("failed standalone pytest diagnostic is unsafe")

    revision, dirty = _repository_identity()
    if revision != expected_revision or dirty:
        raise SetupError("failed standalone publication requires the exact clean reviewed revision")
    return {
        "version": 1, "status": "failed", "scope": SCOPE,
        "source_revision": expected_revision, "source_dirty": False,
        "case": expected_case, "execution_authorized": True,
        "failure_stage": result["stage"],
        "pytest_exit_code": result.get("pytest_exit_code"),
        "captured_environment_cleanup_attempted": cleanup_attempted,
        "captured_environment_cleanup_failed": cleanup_failed,
        "entry_error_retained": True, "pytest_log_retained": pytest_log,
        "cleanup_error_retained": cleanup_error,
        "runner_result_sha256": hashlib.sha256(result_raw).hexdigest(),
        "success_evidence_accepted": False, "combined_gate_verified": False,
        "private_diagnostic_content_or_paths_disclosed": False,
        "note": "Failure-only standalone diagnosis; never success, scenario, cleanup, compatibility, hosted-execution or combined-gate evidence.",
    }

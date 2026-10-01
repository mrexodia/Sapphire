import json
import os

import pytest

from tests.e2e.support.environment import SetupError
from tests.e2e.support.ci_result import EXPECTED_CASES
from tests.e2e.support.isolated_case_run_failure_result import (
    SCOPE, inspect_failed_isolated_case_run,
)
from tests.e2e.support.isolated_case_runner import SCOPE as RUNNER_SCOPE

REVISION = "a" * 40
CASE = EXPECTED_CASES[0]


def make_failure(tmp_path, monkeypatch, *, stage="suite", exit_code=1,
                 cleanup=None, pytest_log=True):
    root = tmp_path / "private"
    root.mkdir()
    result = {
        "version": 1, "status": "failed", "stage": stage,
        "scope": RUNNER_SCOPE, "case": CASE,
        "source_revision": REVISION, "source_dirty": False,
        "execution_authorized": True,
    }
    if exit_code is not None:
        result["pytest_exit_code"] = exit_code
    if cleanup is not None:
        result["captured_environment_cleanup_attempted"] = True
        result["captured_environment_cleanup_failed"] = cleanup
        if cleanup:
            (root / "cleanup-error.log").write_text("private cleanup traceback\n")
    (root / "runner-result.json").write_text(json.dumps(result))
    (root / "entry-error.log").write_text("private entry traceback\n")
    if pytest_log:
        (root / "pytest.log").write_text("private pytest output\n")
    monkeypatch.setattr(
        "tests.e2e.support.isolated_case_run_failure_result._repository_identity",
        lambda: (REVISION, False))
    return root, result


@pytest.mark.parametrize("cleanup", [None, False, True])
def test_failure_receipt_is_fixed_and_never_accepts_success(tmp_path, monkeypatch, cleanup):
    root, _ = make_failure(tmp_path, monkeypatch, cleanup=cleanup)
    receipt = inspect_failed_isolated_case_run(root, CASE, REVISION)
    assert receipt["scope"] == SCOPE and receipt["status"] == "failed"
    assert receipt["execution_authorized"] is True
    assert receipt["success_evidence_accepted"] is False
    assert receipt["combined_gate_verified"] is False
    assert receipt["captured_environment_cleanup_attempted"] is (cleanup is not None)
    assert receipt["captured_environment_cleanup_failed"] is cleanup
    assert receipt["cleanup_error_retained"] is (cleanup is True)
    serialized = json.dumps(receipt)
    assert str(root) not in serialized and "private pytest output" not in serialized


@pytest.mark.parametrize("change", [
    "success", "extra", "zero-exit", "preflight-exit", "inspection", "missing-entry",
    "unexpected-cleanup-log", "missing-cleanup-log", "one-cleanup-field", "authorization",
])
def test_failure_consumer_rejects_malformed_or_relabelled_runs(tmp_path, monkeypatch, change):
    cleanup = True if change == "missing-cleanup-log" else None
    root, result = make_failure(tmp_path, monkeypatch, cleanup=cleanup)
    if change == "success": result["status"] = "passed"
    elif change == "extra": result["private_path"] = "secret"
    elif change == "zero-exit": result["pytest_exit_code"] = 0
    elif change == "preflight-exit": result["stage"] = "preflight"
    elif change == "inspection": (root / "inspection.json").write_text("{}")
    elif change == "missing-entry": (root / "entry-error.log").unlink()
    elif change == "unexpected-cleanup-log": (root / "cleanup-error.log").write_text("x")
    elif change == "missing-cleanup-log": (root / "cleanup-error.log").unlink()
    elif change == "one-cleanup-field": result["captured_environment_cleanup_attempted"] = True
    elif change == "authorization": result["execution_authorized"] = False
    (root / "runner-result.json").write_text(json.dumps(result))
    with pytest.raises(SetupError):
        inspect_failed_isolated_case_run(root, CASE, REVISION)


def test_failure_consumer_rejects_duplicate_result_keys(tmp_path, monkeypatch):
    root, _ = make_failure(tmp_path, monkeypatch)
    text = (root / "runner-result.json").read_text()
    (root / "runner-result.json").write_text(text.replace('"version": 1', '"version": 1, "version": 1'))
    with pytest.raises(SetupError):
        inspect_failed_isolated_case_run(root, CASE, REVISION)


def test_failure_consumer_rejects_linked_result_and_root_alias(tmp_path, monkeypatch):
    root, _ = make_failure(tmp_path, monkeypatch)
    original = root / "runner-result.json"
    other = tmp_path / "other.json"
    original.replace(other)
    os.link(other, original)
    with pytest.raises(SetupError):
        inspect_failed_isolated_case_run(root, CASE, REVISION)
    original.unlink()
    other.unlink()
    original.write_text("{}")
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(root, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks unavailable")
    with pytest.raises(SetupError):
        inspect_failed_isolated_case_run(alias, CASE, REVISION)


def test_failure_consumer_requires_exact_clean_source(tmp_path, monkeypatch):
    root, _ = make_failure(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "tests.e2e.support.isolated_case_run_failure_result._repository_identity",
        lambda: (REVISION, True))
    with pytest.raises(SetupError):
        inspect_failed_isolated_case_run(root, CASE, REVISION)

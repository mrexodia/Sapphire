"""Offline exact-lease inspection contracts; never server/offline evidence."""
import hashlib
import json
from pathlib import Path

import pytest

from . import inspect_development_leases
from .support.development import AccountLease, DevelopmentError, validate_profile
from .support.development_lease import inspect_account_leases
from .test_development import profile


RECOVERY = "verify bots offline before removing lease"


def receipt(run_id):
    return json.dumps({"run_id": run_id, "recovery": RECOVERY})


def paths(profile, root):
    lease = AccountLease(profile, "inspection-only", root)
    return [lease.root / (key + ".lock") for key in lease.keys]


def test_absent_root_is_clear_and_not_created(profile, tmp_path):
    root = tmp_path / "absent"
    report = inspect_account_leases(profile, root)
    assert report["state"] == "clear" and report["present_lease_count"] == 0
    assert [row["state"] for row in report["records"]] == ["absent", "absent"]
    assert not root.exists() and not report["offline_verified"] and not report["release_authorized"]
    assert not report["filesystem_mutation_performed"] and not report["server_or_database_contacted"]
    assert not report["cross_file_snapshot_atomic"]


def test_exact_retained_pair_is_read_only_and_sanitized(profile, tmp_path):
    root, run_id = tmp_path / "leases", "a" * 32
    lease = AccountLease(profile, run_id, root); lease.acquire()
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in lease.paths}
    report = inspect_account_leases(profile, root)
    after = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in lease.paths}
    assert report["state"] == "retained" and report["retained_run_id"] == run_id
    assert report["present_lease_count"] == 2
    assert [row["state"] for row in report["records"]] == ["valid", "valid"]
    assert before == after
    encoded = json.dumps(report)
    for account in profile["accounts"]:
        assert account["username"] not in encoded and account["password"] not in encoded
    for key in lease.keys:
        assert key not in encoded


@pytest.mark.parametrize("case", ["partial", "different_runs", "invalid_json", "invalid_schema",
                                  "oversized", "directory"])
def test_partial_malformed_or_inconsistent_state_is_ambiguous(profile, tmp_path, case):
    root = tmp_path / case; root.mkdir()
    first, second = paths(profile, root)
    if case == "partial":
        first.write_text(receipt("a" * 32))
    elif case == "different_runs":
        first.write_text(receipt("a" * 32)); second.write_text(receipt("b" * 32))
    elif case == "invalid_json":
        first.write_text("{"); second.write_text(receipt("a" * 32))
    elif case == "invalid_schema":
        first.write_text(json.dumps({"run_id": True, "recovery": RECOVERY})); second.write_text(receipt("a" * 32))
    elif case == "oversized":
        first.write_bytes(b"x" * 4097); second.write_text(receipt("a" * 32))
    else:
        first.mkdir(); second.write_text(receipt("a" * 32))
    report = inspect_account_leases(profile, root)
    assert report["state"] == "ambiguous" and report["retained_run_id"] is None
    assert not report["release_authorized"] and not report["offline_verified"]


def test_invalid_or_symlink_root_fails_closed_without_traversal(profile, tmp_path):
    root = tmp_path / "not-directory"; root.write_text("unrelated")
    report = inspect_account_leases(profile, root)
    assert report["state"] == "ambiguous"
    assert [row["state"] for row in report["records"]] == ["unreadable", "unreadable"]
    target, link = tmp_path / "target", tmp_path / "link"
    target.mkdir()
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation is unavailable")
    report = inspect_account_leases(profile, link)
    assert report["state"] == "ambiguous" and not list(target.iterdir())

    exact_root = tmp_path / "exact-root"; exact_root.mkdir()
    external = tmp_path / "external-receipt"; external.write_text(receipt("e" * 32))
    first, second = paths(profile, exact_root)
    first.symlink_to(external); second.write_text(receipt("e" * 32))
    report = inspect_account_leases(profile, exact_root)
    assert report["state"] == "ambiguous"
    assert [row["state"] for row in report["records"]] == ["malformed", "valid"]
    assert external.read_text() == receipt("e" * 32)


def test_unrelated_entries_are_neither_inspected_nor_changed(profile, tmp_path):
    root = tmp_path / "leases"; root.mkdir()
    foreign = root / "unrelated.lock"; foreign.write_text("private unrelated contents")
    digest = hashlib.sha256(foreign.read_bytes()).hexdigest()
    report = inspect_account_leases(profile, root)
    assert report["state"] == "clear" and not report["unrelated_entries_inspected"]
    assert hashlib.sha256(foreign.read_bytes()).hexdigest() == digest


def test_recovery_inspection_does_not_require_worker_to_still_exist(profile, tmp_path):
    Path(profile["worker"]).unlink()
    with pytest.raises(DevelopmentError):
        validate_profile(profile)
    assert inspect_account_leases(profile, tmp_path / "absent")["state"] == "clear"


@pytest.mark.parametrize("mutation", ["boolean_port", "duplicate_account", "missing_password"])
def test_invalid_identity_is_rejected_before_artifacts(profile, tmp_path, mutation):
    if mutation == "boolean_port":
        profile["api_port"] = True
    elif mutation == "duplicate_account":
        profile["accounts"][1]["username"] = profile["accounts"][0]["username"]
    else:
        profile["accounts"][0].pop("password")
    with pytest.raises(DevelopmentError):
        inspect_development_leases.run(profile, tmp_path / "artifacts", lease_root=tmp_path / "leases")
    assert not (tmp_path / "artifacts").exists() and not (tmp_path / "leases").exists()


def test_cli_retained_result_is_successful_private_evidence(profile, tmp_path, capsys):
    private = tmp_path / "profile.json"; private.write_text(json.dumps(profile))
    root, run_id = tmp_path / "leases", "c" * 32
    lease = AccountLease(profile, run_id, root); lease.acquire()
    artifacts = tmp_path / "artifacts"
    assert inspect_development_leases.main([
        "--profile", str(private), "--artifacts", str(artifacts), "--lease-root", str(root)]) == 0
    output = capsys.readouterr().out
    summary = (artifacts / "lease-inspection-summary.json").read_text()
    assert json.loads(summary)["state"] == "retained" and "offline" in summary
    for secret in [*(account["username"] for account in profile["accounts"]),
                   *(account["password"] for account in profile["accounts"]),
                   *lease.keys, str(root)]:
        assert secret not in output and secret not in summary


def test_cli_ambiguous_result_persists_failure_without_mutation(profile, tmp_path, capsys):
    private = tmp_path / "profile.json"; private.write_text(json.dumps(profile))
    root = tmp_path / "leases"; root.mkdir()
    first, _ = paths(profile, root); first.write_text(receipt("d" * 32))
    artifacts = tmp_path / "artifacts"
    assert inspect_development_leases.main([
        "--profile", str(private), "--artifacts", str(artifacts), "--lease-root", str(root)]) == 1
    report = json.loads((artifacts / "lease-inspection-summary.json").read_text())
    assert report["status"] == "failed" and report["state"] == "ambiguous"
    assert first.exists() and first.read_text() == receipt("d" * 32)
    assert json.loads(capsys.readouterr().out)["status"] == "failed"

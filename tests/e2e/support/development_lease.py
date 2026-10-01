"""Read-only snapshots of exact cooperating-runner leases; never offline proof."""
import json
import os
from pathlib import Path
import stat

from .development import AccountLease, DevelopmentError, validate_profile

_SCOPE = "exact-local-account-lease-snapshot-not-server-session-or-offline-proof"
_RECOVERY = "verify bots offline before removing lease"
_MAX_RECEIPT_BYTES = 4096


def _receipt(path):
    """Read one exact receipt without following a final symlink.

    Per-file before/open/after identity checks detect ordinary replacement races.
    They are not a lock or a cross-file atomic snapshot.
    """
    path = Path(path)
    try:
        before = path.lstat()
    except FileNotFoundError:
        return "absent", None
    except OSError:
        return "unreadable", None
    if not stat.S_ISREG(before.st_mode) or path.is_symlink():
        return "malformed", None
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return "unreadable", None
    try:
        opened = os.fstat(descriptor)
        if opened.st_size > _MAX_RECEIPT_BYTES:
            return "malformed", None
        data = os.read(descriptor, _MAX_RECEIPT_BYTES + 1)
    except OSError:
        return "unreadable", None
    finally:
        os.close(descriptor)
    try:
        after = path.lstat()
    except OSError:
        return "unreadable", None
    identity = lambda row: (row.st_dev, row.st_ino, row.st_size, row.st_mtime_ns)
    if identity(before) != identity(opened) or identity(opened) != identity(after):
        return "unreadable", None
    if len(data) > _MAX_RECEIPT_BYTES:
        return "malformed", None
    try:
        receipt = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "malformed", None
    if (not isinstance(receipt, dict) or set(receipt) != {"run_id", "recovery"}
            or not isinstance(receipt.get("run_id"), str) or len(receipt["run_id"]) != 32
            or any(character not in "0123456789abcdef" for character in receipt["run_id"])
            or receipt.get("recovery") != _RECOVERY):
        return "malformed", None
    return "valid", receipt["run_id"]


def inspect_account_leases(profile, root=None):
    """Inspect only the two exact profile-derived paths and mutate nothing."""
    validate_profile(profile, require_worker=False)
    lease = AccountLease(profile, "inspection-only", root)
    try:
        root_status = lease.root.lstat()
    except FileNotFoundError:
        root_status = None
    except OSError as error:
        raise DevelopmentError("lease root cannot be inspected") from error
    if root_status is not None and (not stat.S_ISDIR(root_status.st_mode) or lease.root.is_symlink()):
        rows = [{"lease_index": index, "state": "unreadable"} for index in range(len(lease.keys))]
        state, run_id = "ambiguous", None
    else:
        inspected = [_receipt(lease.root / (key + ".lock")) for key in lease.keys]
        rows = [{"lease_index": index, "state": result[0]}
                for index, result in enumerate(inspected)]
        states, run_ids = [result[0] for result in inspected], [result[1] for result in inspected]
        if states == ["absent", "absent"]:
            state, run_id = "clear", None
        elif states == ["valid", "valid"] and run_ids[0] == run_ids[1]:
            state, run_id = "retained", run_ids[0]
        else:
            state, run_id = "ambiguous", None
    report = {
        "version": 1,
        "scope": _SCOPE,
        "state": state,
        "expected_lease_count": 2,
        "present_lease_count": sum(row["state"] != "absent" for row in rows),
        "records": rows,
        "retained_run_id": run_id,
        "profile_or_account_values_disclosed": False,
        "lease_paths_or_keys_disclosed": False,
        "unrelated_entries_inspected": False,
        "filesystem_mutation_performed": False,
        "server_or_database_contacted": False,
        "active_session_checked": False,
        "offline_verified": False,
        "release_authorized": False,
        "cross_file_snapshot_atomic": False,
    }
    return report


def require_clear_terminal_account_leases(report):
    """Reject legacy, malformed or non-clear terminal lease evidence."""
    expected = {
        "version": 1,
        "scope": _SCOPE,
        "state": "clear",
        "expected_lease_count": 2,
        "present_lease_count": 0,
        "records": [{"lease_index": 0, "state": "absent"},
                    {"lease_index": 1, "state": "absent"}],
        "retained_run_id": None,
        "profile_or_account_values_disclosed": False,
        "lease_paths_or_keys_disclosed": False,
        "unrelated_entries_inspected": False,
        "filesystem_mutation_performed": False,
        "server_or_database_contacted": False,
        "active_session_checked": False,
        "offline_verified": False,
        "release_authorized": False,
        "cross_file_snapshot_atomic": False,
        "retained_receipts_match_run": False,
    }
    snapshot = report.get("lease_snapshot")
    if not isinstance(snapshot, dict):
        raise DevelopmentError("exact clear terminal account-lease evidence is required")
    records = snapshot.get("records")
    false_fields = ("profile_or_account_values_disclosed", "lease_paths_or_keys_disclosed",
                    "unrelated_entries_inspected", "filesystem_mutation_performed",
                    "server_or_database_contacted", "active_session_checked",
                    "offline_verified", "release_authorized", "cross_file_snapshot_atomic",
                    "retained_receipts_match_run")
    if (type(snapshot.get("version")) is not int
            or type(snapshot.get("expected_lease_count")) is not int
            or type(snapshot.get("present_lease_count")) is not int
            or not isinstance(records, list)
            or any(not isinstance(row, dict) or type(row.get("lease_index")) is not int
                   for row in records)
            or any(snapshot.get(key) is not False for key in false_fields)
            or snapshot != expected
            or report.get("lease_snapshot_matches_run_state") is not True):
        raise DevelopmentError("exact clear terminal account-lease evidence is required")
    return report["lease_snapshot"]


def terminal_account_lease_snapshot(profile, root, expected_run_id):
    """Return sanitized terminal evidence even if inspection itself fails."""
    try:
        report = inspect_account_leases(profile, root)
    except BaseException as error:
        report = {
            "version": 1,
            "scope": _SCOPE,
            "state": "unavailable",
            "inspection_error_type": type(error).__name__,
            "profile_or_account_values_disclosed": False,
            "lease_paths_or_keys_disclosed": False,
            "unrelated_entries_inspected": False,
            "filesystem_mutation_performed": False,
            "server_or_database_contacted": False,
            "active_session_checked": False,
            "offline_verified": False,
            "release_authorized": False,
            "cross_file_snapshot_atomic": False,
        }
    report["retained_receipts_match_run"] = (
        report.get("state") == "retained" and report.get("retained_run_id") == expected_run_id)
    return report

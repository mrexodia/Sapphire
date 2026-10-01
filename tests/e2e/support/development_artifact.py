"""Owned worker-journal identity for shared-development runs."""
from __future__ import annotations

import json
from pathlib import Path

from .development import DevelopmentError
from .environment import artifact_tree_sha256, has_cleanup_failure_marker

RUN_SCOPE = "shared-development-worker-artifacts-not-gameplay-or-server-proof"
PROVISIONING_SCOPE = "shared-provisioning-worker-artifacts-not-gameplay-or-server-proof"


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise DevelopmentError("worker artifact ownership contains a duplicate key")
        value[key] = item
    return value


def _hex(value, length):
    return (isinstance(value, str) and len(value) == length
            and all(char in "0123456789abcdef" for char in value))


def initialize_worker_artifacts(root: Path, run_id: str, scope: str):
    if scope not in {RUN_SCOPE, PROVISIONING_SCOPE} or not _hex(run_id, 32):
        raise DevelopmentError("worker artifact ownership identity is invalid")
    root = Path(root)
    root.mkdir(parents=False, exist_ok=False)
    ownership = {"version":1,"scope":scope,"run_id":run_id}
    with (root / "ownership.json").open("x", encoding="utf-8") as stream:
        json.dump(ownership, stream, indent=2)
    return root


def bind_worker_artifacts(report: dict, root: Path):
    try:
        report["worker_artifact_tree_sha256"] = artifact_tree_sha256(root)
    except Exception as error:
        raise DevelopmentError("cannot bind exact worker artifact tree") from error


def require_worker_artifacts(summary_path: Path, report: dict, scope: str):
    summary_path = Path(summary_path)
    worker = summary_path.parent / "worker"
    ownership_path = worker / "ownership.json"
    if (summary_path.is_symlink() or not summary_path.is_file()
            or worker.is_symlink() or not worker.is_dir()
            or ownership_path.is_symlink() or not ownership_path.is_file()):
        raise DevelopmentError("worker artifact tree is missing or unsafe")
    try:
        raw = ownership_path.read_bytes()
        ownership = json.loads(raw, object_pairs_hook=_pairs)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DevelopmentError("worker artifact ownership is unreadable") from error
    if (len(raw) > 4096 or not isinstance(ownership, dict)
            or set(ownership) != {"version","scope","run_id"}
            or type(ownership.get("version")) is not int or ownership["version"] != 1
            or ownership.get("scope") != scope
            or ownership.get("run_id") != report.get("run_id")):
        raise DevelopmentError("worker artifact ownership differs from run")
    expected = report.get("worker_artifact_tree_sha256")
    try:
        if (not _hex(expected, 64) or has_cleanup_failure_marker(worker)
                or artifact_tree_sha256(worker) != expected):
            raise DevelopmentError("worker artifact tree differs from summary")
    except DevelopmentError:
        raise
    except Exception as error:
        raise DevelopmentError("cannot inspect exact worker artifact tree") from error
    return {"scope":scope,"sha256":expected,"run_id":report["run_id"]}

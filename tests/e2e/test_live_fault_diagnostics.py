"""Intentional owned-process fault lane; not gameplay or crash-dump coverage."""
import json
from pathlib import Path

import pytest

from .support.environment import SetupError, sha256

pytestmark = pytest.mark.live


def test_owned_world_exit_preserves_classification_logs_and_cleanup(environment):
    root = environment.root
    artifacts = environment.artifacts
    secret = environment.secret
    database_password = environment.db_password
    world = environment.processes["world"]
    metadata = dict(environment._process_metadata["world"])
    assert world.poll() is None
    with pytest.raises(SetupError,
                       match=r"world generation \d+ exited intentionally for fault test \(-?\d+\)"):
        environment.terminate_world_for_fault_test()
    diagnostic = json.loads((artifacts / "process-failure.json").read_text(encoding="utf-8"))
    assert diagnostic == {
        "version": 1,
        "classification": "intentional_owned_process_exit",
        "process": "world",
        "generation": metadata["generation"],
        "pid": metadata["pid"],
        "returncode": world.returncode,
        "log": "world.log",
        "cleanup_required": True,
    }
    environment.close()

    assert not root.exists()
    world_log = artifacts / "world.log"
    manifest_path = artifacts / "manifest.json"
    lifecycle_path = artifacts / "process-lifecycle.json"
    assert world_log.is_file() and manifest_path.is_file() and lifecycle_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["dirty"] is False
    assert manifest["runtime"] == str(root / "runtime")
    assert not Path(manifest["runtime"]).exists()
    lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8"))
    world_receipts = [row for row in lifecycle["teardowns"]
                      if row["process"] == "world" and row["generation"] == metadata["generation"]]
    assert len(world_receipts) == 1
    assert world_receipts[0]["pid"] == metadata["pid"]
    assert world_receipts[0]["exit_observed"] is True
    assert world_receipts[0]["returncode"] == world.returncode
    published = "\n".join(path.read_text(encoding="utf-8", errors="replace")
                           for path in artifacts.rglob("*.log"))
    assert secret not in published and database_password not in published
    (artifacts / "fault-diagnostics-verification.json").write_text(json.dumps({
        "classification": diagnostic["classification"],
        "process": diagnostic["process"],
        "generation": diagnostic["generation"],
        "pid": diagnostic["pid"],
        "returncode": diagnostic["returncode"],
        "world_log_sha256": sha256(world_log),
        "manifest_sha256": sha256(manifest_path),
        "lifecycle_sha256": sha256(lifecycle_path),
        "runtime_removed": True,
        "secrets_absent_from_published_logs": True,
        "scope": "one intentional termination of the exact owned disposable world process; proves bounded exit classification, generation-correlated teardown, redacted text-log publication and cleanup, not crash-dump retention, cancellation cleanup or server crash behavior"
    }, indent=2), encoding="utf-8")

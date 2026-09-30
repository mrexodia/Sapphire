"""Intentional owned-process fault lane; not gameplay or crash-dump coverage."""
import json
from pathlib import Path

import pytest

from .support.environment import Environment, SetupError, sha256

pytestmark = pytest.mark.live


def test_unexpected_world_exit_preserves_classification_logs_and_cleanup(request):
    profile_path = request.config.getoption("--e2e-profile")
    if not profile_path:
        pytest.skip("fault diagnostics require explicit --e2e-profile")
    profile = json.loads(Path(profile_path).read_text(encoding="utf-8"))
    isolated = Environment(profile)
    root = isolated.root
    artifacts = isolated.artifacts
    secret = isolated.secret
    database_password = isolated.db_password
    try:
        isolated.start()
        world = isolated.processes["world"]
        assert world.poll() is None
        world.terminate()
        world.wait(timeout=10)
        with pytest.raises(SetupError, match=r"world exited unexpectedly \(-?\d+\)"):
            isolated.check_alive()
        diagnostic = json.loads((artifacts / "process-failure.json").read_text(encoding="utf-8"))
        assert diagnostic == {
            "version": 1,
            "classification": "unexpected_process_exit",
            "process": "world",
            "returncode": world.returncode,
            "log": "world.log",
            "cleanup_required": True,
        }
    finally:
        isolated.close()

    assert not root.exists()
    world_log = artifacts / "world.log"
    manifest_path = artifacts / "manifest.json"
    assert world_log.is_file() and manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["dirty"] is False
    assert manifest["runtime"] == str(root / "runtime")
    assert not Path(manifest["runtime"]).exists()
    published = "\n".join(path.read_text(encoding="utf-8", errors="replace")
                           for path in artifacts.rglob("*.log"))
    assert secret not in published and database_password not in published
    (artifacts / "fault-diagnostics-verification.json").write_text(json.dumps({
        "classification": diagnostic["classification"],
        "process": diagnostic["process"],
        "returncode": diagnostic["returncode"],
        "world_log_sha256": sha256(world_log),
        "manifest_sha256": sha256(manifest_path),
        "runtime_removed": True,
        "secrets_absent_from_published_logs": True,
        "scope": "one intentional termination of the owned disposable world process; proves bounded exit classification, redacted text-log publication and cleanup, not crash-dump retention, cancellation cleanup or server crash behavior"
    }, indent=2), encoding="utf-8")

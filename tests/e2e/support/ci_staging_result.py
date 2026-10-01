"""Stage and remove one service-free isolated fixture from a private profile."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..run_ci import inputs_match
from .ci_profile_result import _validated_profile
from .environment import (Environment, SetupError, artifact_tree_sha256,
                          has_cleanup_failure_marker, sha256)

SCOPE = "clean-exact-revision-environment-staging-and-root-removal-only"


def _hex(value, length):
    return (isinstance(value, str) and len(value) == length
            and all(char in "0123456789abcdef" for char in value))


def stage_ci_profile(profile_path, private_artifacts, expected_revision, *,
                     worker=None, binaries=None, suffix=None):
    if not _hex(expected_revision, 40):
        raise SetupError("expected staging revision must be exact lowercase git identity")
    requested = Path(private_artifacts)
    if (not requested.is_absolute() or requested.exists() or requested.is_symlink()
            or not requested.parent.is_dir() or requested.parent.is_symlink()):
        raise SetupError("private staging artifact root must be a new absolute directory")
    raw, profile, identities = _validated_profile(
        profile_path, worker=worker, binaries=binaries, suffix=suffix)
    requested.mkdir()
    profile["artifacts"] = str(requested)
    environment = Environment(profile)
    runtime, disposable_root, artifact = environment.runtime, environment.root, environment.artifacts
    manifest = None
    try:
        environment.stage()
        manifest_path = artifact / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not inputs_match(identities, manifest, expected_revision, False, profile.get("deadline_scale", 1)):
            raise SetupError("staged fixture does not match clean source/profile identities")
        if environment.process_starts or environment.processes:
            raise SetupError("service-free staging unexpectedly started a process")
    finally:
        environment.close()
    if runtime.exists() or disposable_root.exists():
        raise SetupError("service-free staging retained disposable runtime")
    try:
        entries = list(requested.iterdir())
    except OSError as error:
        raise SetupError("private staging artifact root became unavailable") from error
    if (requested.is_symlink() or len(entries) != 1 or entries[0].is_symlink()
            or not entries[0].is_dir() or entries[0].resolve() != artifact.resolve()):
        raise SetupError("private staging artifact root is ambiguous or foreign")
    if has_cleanup_failure_marker(artifact):
        raise SetupError("service-free staging records terminal cleanup failure")
    lifecycle_path = artifact / "process-lifecycle.json"
    try:
        lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SetupError("service-free staging lifecycle is unreadable") from error
    if (set(lifecycle) != {"version","scope","starts","teardowns"}
            or type(lifecycle.get("version")) is not int or lifecycle["version"] != 1
            or lifecycle.get("scope") !=
                "exact-owned-isolated-process-teardown-not-graceful-server-exit"
            or lifecycle.get("starts") != [] or lifecycle.get("teardowns") != []):
        raise SetupError("service-free staging lifecycle is not process-free")
    return {"version":1,"status":"accepted","scope":SCOPE,
            "source_revision":expected_revision,"source_dirty":False,
            "profile_sha256":hashlib.sha256(raw).hexdigest(),
            "fixture_version":manifest["fixture_version"],"profile":manifest["profile"],
            "manifest_sha256":sha256(artifact / "manifest.json"),
            "lifecycle_sha256":sha256(lifecycle_path),
            "artifact_tree_sha256":artifact_tree_sha256(artifact),
            "binary_count":len(manifest["binaries"]),
            "script_module_count":len(manifest["scripts"]),
            "catalog_count":sum(key.endswith("_catalog") for key in profile),
            "process_start_count":0,"process_teardown_count":0,
            "runtime_and_disposable_root_absent":True,
            "private_artifacts_retained":True,"private_paths_disclosed":False,
            "services_database_accounts_or_gameplay_started":False,
            "note":"Staging, manifest correlation and root removal only; not service execution, database isolation, gameplay, compatibility or secure-erasure evidence."}

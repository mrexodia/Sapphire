"""Trusted-runner entry point. Only the allowlisted summary is safe to publish.

Profiles, pytest/JUnit output, received state and server logs remain private.
This is not a sandbox for untrusted repository code or a real-client verifier.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import traceback

from .support.catalog import load_combat_catalog, load_quest_catalog, load_transition_catalog
from .support.environment import REPO, sha256

VERSION = "2016.07.05.0000.0001"
CASES = (
    "tests/e2e/test_live.py::test_rejected_credentials",
    "tests/e2e/test_live.py::test_login_idle_logout",
    "tests/e2e/test_live.py::test_observed_movement_and_position_persistence",
    "tests/e2e/test_live_quest.py::test_quest_cancel_complete_rewards_and_restart[single]",
    "tests/e2e/test_live_quest.py::test_quest_cancel_complete_rewards_and_restart[chain]",
    "tests/e2e/test_live_zoning.py::test_observed_exit_crossing_and_territory_persistence",
    "tests/e2e/test_live_combat.py::test_observed_fast_blade_damage",
    "tests/e2e/test_live_player_defeat.py::test_natural_enemy_defeats_level_one_player",
    "tests/e2e/test_live_creation.py::test_lobby_character_creation_and_opening_persistence",
)
SUITES = tuple(dict.fromkeys(case.split("::", 1)[0] for case in CASES))
CATALOGS = ("quest_catalog", "follow_up_catalog", "transition_catalog", "combat_catalog")
PATH_KEYS = ("binaries", "worker", "game_data", "mariadb_bin", "navigation", *CATALOGS)


class PreflightError(RuntimeError):
    pass


def preflight(profile, *, suffix=None):
    """Availability/metadata gate only; it cannot certify gameplay or binary provenance."""
    suffix = (".exe" if os.name == "nt" else "") if suffix is None else suffix
    if set(profile) - {*PATH_KEYS, "artifacts"} or any(not profile.get(key) for key in PATH_KEYS):
        raise PreflightError("unsupported or incomplete profile")
    result = dict(profile)
    paths = {key: Path(profile[key]).resolve() for key in PATH_KEYS}
    for key in PATH_KEYS:
        result[key] = str(paths[key])
    required = [paths["worker"], *[paths[key] for key in CATALOGS]]
    required += [paths["binaries"] / (name + suffix) for name in ("api", "lobby", "server", "dbm")]
    required += [paths["mariadb_bin"] / (name + suffix) for name in ("mariadbd", "mariadb-install-db", "mariadb")]
    scripts = paths["binaries"] / "compiledscripts"
    if not scripts.is_dir() or not any(scripts.glob("*.dll" if suffix else "*.so")):
        raise PreflightError("native script modules missing")
    if any(not path.is_file() or not path.stat().st_size for path in required):
        raise PreflightError("required input missing")
    version_file = paths["game_data"].parent / "ffxivgame.ver"
    if not version_file.is_file() or version_file.read_text(encoding="utf-8-sig").strip() != VERSION:
        raise PreflightError("game data version mismatch")
    if not list((paths["game_data"] / "ffxiv").glob("*.index")):
        raise PreflightError("game archives missing")
    meshes = {}
    for name in ("w1t1", "w1f2"):
        mesh = paths["navigation"] / name / (name + ".nav")
        with mesh.open("rb") as stream:
            header = stream.read(12)
        if len(header) != 12 or struct.unpack("<III", header)[:2] != (0x54534554, 1) or struct.unpack("<III", header)[2] == 0:
            raise PreflightError("unsupported server mesh header")
        meshes[name] = sha256(mesh)
    first = load_quest_catalog(paths["quest_catalog"])
    # Static dependency validation, NOT observed completion or gameplay fixture setup.
    second = load_quest_catalog(paths["follow_up_catalog"], completed_quests={65686})
    if first["quest"] != 65686 or second["quest"] != 65687 or 65686 not in second["previous_quests"]:
        raise PreflightError("unsupported quest chain")
    transition = load_transition_catalog(paths["transition_catalog"])
    if transition["transition"]["target_territory"] != 141:
        raise PreflightError("unsupported CI destination")
    load_combat_catalog(paths["combat_catalog"])
    for catalog in (first, second, transition):
        if sha256(Path(catalog["navigation"]["mesh"])) != meshes["w1t1"]:
            raise PreflightError("route/server mesh mismatch")
    identities = {"worker": sha256(paths["worker"]),
                  "binaries": {name: sha256(paths["binaries"] / (name + suffix))
                               for name in ("api", "lobby", "server", "dbm")},
                  "catalogs": {key: sha256(paths[key]) for key in CATALOGS}, "meshes": meshes,
                  "script_modules": sorted(sha256(p) for p in scripts.glob("*.dll" if suffix else "*.so"))}
    return result, identities


def inputs_match(identities, manifest):
    """Bind public input hashes to the hashes of the environment actually staged."""
    try:
        return (identities["worker"] == manifest["worker_sha256"]
                and identities["binaries"] == manifest["binaries"]
                and identities["script_modules"] == sorted(manifest["scripts"].values())
                and all(identities["catalogs"][key] == manifest[key]["sha256"] for key in CATALOGS)
                and all(digest == manifest["server_navigation"][f"{name}/{name}.nav"]
                        for name, digest in identities["meshes"].items()))
    except (KeyError, TypeError):
        return False


class EvidenceGate:
    def __init__(self):
        self.collected = []
        self.reports = {case: {phase: [] for phase in ("setup", "call", "teardown")} for case in CASES}
        self.unexpected = 0
        self.environment = None

    def pytest_collection_finish(self, session):
        self.collected = [item.nodeid for item in session.items]

    def pytest_runtest_logreport(self, report):
        if report.nodeid not in self.reports or report.when not in self.reports[report.nodeid]:
            self.unexpected += 1
            return
        # Never copy longrepr, captured output, properties or arbitrary test names.
        outcome = report.outcome if report.outcome in {"passed", "failed", "skipped"} else "invalid"
        self.reports[report.nodeid][report.when].append(outcome)

    def pytest_runtest_call(self, item):
        if "environment" in item.funcargs:
            self.environment = item.funcargs["environment"]

    def summary(self, exit_code):
        cases = {case: all(values == ["passed"] for values in phases.values())
                 for case, phases in self.reports.items()}
        collection_ok = len(self.collected) == len(CASES) and set(self.collected) == set(CASES)
        env = self.environment
        cleanup_ok = bool(env is not None and env._closed and not env.root.exists()
                          and all(p.poll() is not None for p in env.processes.values()))
        passed = exit_code == 0 and collection_ok and not self.unexpected and all(cases.values()) and cleanup_ok
        return {"status": "passed" if passed else "failed", "collection_verified": collection_ok,
                "cleanup_verified": cleanup_ok, "cases": cases, "pytest_exit_code": int(exit_code)}


def run(profile_path, private_root, summary_path, *, worker=None, binaries=None, require_clean=False):
    summary_path = Path(summary_path).resolve()
    if summary_path.exists():
        raise PreflightError("summary destination must be fresh")
    # Reserve a NEW summary, never reuse evidence from an earlier job.
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("x", encoding="utf-8") as public:
        report = {"version": 1, "status": "failed", "stage": "preflight", "scope": "headless-live-not-real-client"}
        private = None
        try:
            private_root = Path(private_root).resolve()
            private_root.mkdir(parents=True, exist_ok=True)
            private = Path(tempfile.mkdtemp(prefix="gameplay-ci-", dir=private_root))
            profile = json.loads(Path(profile_path).read_text(encoding="utf-8"))
            if worker:
                profile["worker"] = str(Path(worker).resolve())
            if binaries:
                profile["binaries"] = str(Path(binaries).resolve())
            profile, identities = preflight(profile)
            revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
            if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
                raise PreflightError("invalid repository identity")
            dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO, text=True))
            if require_clean and dirty:
                raise PreflightError("CI requires a clean checkout")
            report.update(revision=revision, source_dirty=dirty, identities=identities)
            profile["artifacts"] = str(private / "artifacts")
            local_profile = private / "profile.json"
            local_profile.write_text(json.dumps(profile), encoding="utf-8")
            report["stage"] = "suite"
            # CI must not inherit -k/-m selection, xdist/retry plugins, or caller addopts.
            saved = {key: os.environ.get(key) for key in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PYTEST_DISABLE_PLUGIN_AUTOLOAD")}
            original_cwd = Path.cwd()
            try:
                os.environ.pop("PYTEST_ADDOPTS", None)
                os.environ.pop("PYTEST_PLUGINS", None)
                os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
                os.chdir(REPO)
                with (private / "pytest.log").open("w", encoding="utf-8") as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                    import pytest
                    gate = EvidenceGate()
                    code = pytest.main([*SUITES, "--e2e-profile", str(local_profile), "-q", "--capture=sys",
                                        "-o", "addopts=", "-p", "no:cacheprovider", "--strict-markers",
                                        "--junitxml", str(private / "live.xml")], plugins=[gate])
                report.update(gate.summary(code))
                report["inputs_verified"] = False
                if gate.environment is not None:
                    manifest = json.loads((gate.environment.artifacts / "manifest.json").read_text(encoding="utf-8"))
                    report["inputs_verified"] = inputs_match(identities, manifest)
                if not report["inputs_verified"]:
                    report["status"] = "failed"
                report["stage"] = "verified" if report["status"] == "passed" else "verification"
            finally:
                os.chdir(original_cwd)
                for key, value in saved.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value
        except BaseException:
            # Raw exceptions/JUnit can contain profile paths, scene data or credentials.
            # Existing private fixture/worker logs hold diagnostics; public output is fixed-schema only.
            report["status"] = "failed"
            if private is not None:
                with (private / "entry-error.log").open("w", encoding="utf-8") as log:
                    traceback.print_exc(file=log)
        public.write(json.dumps(report, indent=2) + "\n")
    return 0 if report["status"] == "passed" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--private-root", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--worker")
    parser.add_argument("--binaries")
    parser.add_argument("--require-clean", action="store_true")
    args = parser.parse_args()
    try:
        code = run(args.profile, args.private_root, args.summary, worker=args.worker,
                   binaries=args.binaries, require_clean=args.require_clean)
    except BaseException:
        code = 1
    print("Gameplay CI gate passed." if code == 0 else "Gameplay CI gate failed; inspect private runner diagnostics.")
    return code


if __name__ == "__main__":
    sys.exit(main())

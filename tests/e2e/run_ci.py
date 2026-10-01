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

from .support.catalog import (load_combat_catalog, load_opening_quest_catalog,
                              load_pursuit_catalog, load_quest_catalog, load_respawn_catalog,
                              load_shop_catalog, load_transition_catalog)
from .support.environment import REPO, SetupError, require_process_teardowns, sha256

VERSION = "2016.07.05.0000.0001"
CASES = (
    "tests/e2e/test_live.py::test_rejected_credentials",
    "tests/e2e/test_live.py::test_login_idle_logout",
    "tests/e2e/test_live.py::test_received_party_join_and_leave",
    "tests/e2e/test_live.py::test_observed_movement_and_position_persistence",
    "tests/e2e/test_live_quest.py::test_quest_cancel_complete_rewards_and_restart[single]",
    "tests/e2e/test_live_quest.py::test_quest_cancel_complete_rewards_and_restart[chain]",
    "tests/e2e/test_live_zoning.py::test_observed_exit_crossing_and_territory_persistence",
    "tests/e2e/test_live_zoning.py::test_observed_living_return_action",
    "tests/e2e/test_live_combat.py::test_observed_sprint_status_and_tp_debit",
    "tests/e2e/test_live_combat.py::test_observed_fast_blade_damage",
    "tests/e2e/test_live_progression.py::test_natural_pugilist_level_two_true_strike",
    "tests/e2e/test_live_combo.py::test_natural_level_four_fast_blade_combo",
    "tests/e2e/test_live_aggro.py::test_natural_vision_aggro_without_player_action",
    "tests/e2e/test_live_player_defeat.py::test_natural_enemy_defeats_level_one_player",
    "tests/e2e/test_live_creation.py::test_lobby_character_creation_and_opening_persistence",
)
SUITES = tuple(dict.fromkeys(case.split("::", 1)[0] for case in CASES))
CATALOGS = ("quest_catalog", "follow_up_catalog", "transition_catalog", "combat_catalog", "shop_catalog",
            "respawn_catalog", "pursuit_catalog", "opening_quest_catalog")
PATH_KEYS = ("binaries", "worker", "game_data", "mariadb_bin", "navigation", *CATALOGS)


class PreflightError(RuntimeError):
    pass


def preflight(profile, *, suffix=None):
    """Availability/metadata gate only; it cannot certify gameplay or binary provenance."""
    suffix = (".exe" if os.name == "nt" else "") if suffix is None else suffix
    if set(profile) - {*PATH_KEYS, "artifacts", "deadline_scale"} or any(not profile.get(key) for key in PATH_KEYS):
        raise PreflightError("unsupported or incomplete profile")
    deadline_scale = profile.get("deadline_scale", 1)
    if type(deadline_scale) is not int or not 1 <= deadline_scale <= 3:
        raise PreflightError("deadline_scale must be an integer from 1 through 3")
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
    shop = load_shop_catalog(paths["shop_catalog"])
    load_respawn_catalog(paths["respawn_catalog"])
    pursuit = load_pursuit_catalog(paths["pursuit_catalog"])
    opening = load_opening_quest_catalog(paths["opening_quest_catalog"])
    for catalog in (first, second, transition, shop, opening):
        if sha256(Path(catalog["navigation"]["mesh"])) != meshes["w1t1"]:
            raise PreflightError("route/server mesh mismatch")
    if sha256(Path(pursuit["navigation"]["mesh"])) != meshes["w1f2"]:
        raise PreflightError("pursuit/server mesh mismatch")
    identities = {"worker": sha256(paths["worker"]),
                  "binaries": {name: sha256(paths["binaries"] / (name + suffix))
                               for name in ("api", "lobby", "server", "dbm")},
                  "catalogs": {key: sha256(paths[key]) for key in CATALOGS}, "meshes": meshes,
                  "script_modules": sorted(sha256(p) for p in scripts.glob("*.dll" if suffix else "*.so"))}
    return result, identities


def inputs_match(identities, manifest, revision, source_dirty, deadline_scale):
    """Bind public source/input metadata to each environment actually staged."""
    if (not isinstance(revision, str) or len(revision) != 40
            or any(char not in "0123456789abcdef" for char in revision)
            or type(source_dirty) is not bool or type(deadline_scale) is not int
            or not 1 <= deadline_scale <= 3):
        return False
    try:
        return (type(manifest["fixture_version"]) is int and manifest["fixture_version"] == 2
                and manifest["profile"] == "sapphire-3.3"
                and manifest["revision"] == revision
                and manifest["dirty"] is source_dirty
                and type(manifest["deadline_scale"]) is int
                and manifest["deadline_scale"] == deadline_scale
                and identities["worker"] == manifest["worker_sha256"]
                and identities["binaries"] == manifest["binaries"]
                and identities["script_modules"] == sorted(manifest["scripts"].values())
                and all(identities["catalogs"][key] == manifest[key]["sha256"] for key in CATALOGS)
                and all(digest == manifest["server_navigation"][f"{name}/{name}.nav"]
                        for name, digest in identities["meshes"].items()))
    except (KeyError, TypeError):
        return False


def isolated_environment_identities(environments, case_environments):
    """Validate private fixture identities without returning publishable values."""
    if (set(case_environments) != set(CASES)
            or len({id(environment) for environment in case_environments.values()}) != len(CASES)
            or len(environments) != len(CASES)
            or {id(environment) for environment in environments}
               != {id(environment) for environment in case_environments.values()}):
        return False
    roots, artifacts, databases = set(), set(), set()
    try:
        for environment in environments:
            root, runtime = Path(environment.root).resolve(), Path(environment.runtime).resolve()
            artifact = Path(environment.artifacts).resolve()
            database = environment.db_name
            ports = {"database":environment.db_port,"api":environment.api_port,
                     "lobby":environment.lobby_port,"world":environment.zone_port}
            manifest = json.loads((artifact / "manifest.json").read_text(encoding="utf-8"))
            if (runtime != root / "runtime" or root == artifact
                    or root in artifact.parents or artifact in root.parents
                    or not isinstance(database, str) or not database.startswith("sapphire_e2e_")
                    or len(database) != len("sapphire_e2e_") + 32
                    or any(char not in "0123456789abcdef" for char in database[len("sapphire_e2e_"):])
                    or any(type(port) is not int or not 1 <= port <= 65535 for port in ports.values())
                    or len(set(ports.values())) != 4
                    or manifest.get("database") != database
                    or manifest.get("runtime") != str(environment.runtime)
                    or manifest.get("ports") != ports):
                return False
            roots.add(root); artifacts.add(artifact); databases.add(database)
    except (AttributeError, OSError, UnicodeError, json.JSONDecodeError, TypeError):
        return False
    return len(roots) == len(artifacts) == len(databases) == len(CASES)


class EvidenceGate:
    def __init__(self):
        self.collected = []
        self.reports = {case: {phase: [] for phase in ("setup", "call", "teardown")} for case in CASES}
        self.unexpected = 0
        self.environment = None
        self.environments = []
        self.case_environments = {}

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
            prior = self.case_environments.get(item.nodeid)
            if prior is not None and prior is not self.environment:
                self.unexpected += 1
            self.case_environments[item.nodeid] = self.environment
            if all(environment is not self.environment for environment in self.environments):
                self.environments.append(self.environment)

    def summary(self, exit_code):
        cases = {case: all(values == ["passed"] for values in phases.values())
                 for case, phases in self.reports.items()}
        collection_ok = len(self.collected) == len(CASES) and set(self.collected) == set(CASES)
        environments = self.environments or ([self.environment] if self.environment is not None else [])
        environment_isolation_ok = isolated_environment_identities(
            environments, self.case_environments)
        environment_evidence = []
        if environment_isolation_ok:
            try:
                for case in CASES:
                    environment = self.case_environments[case]
                    environment_evidence.append({
                        "case":case,
                        "manifest_sha256":sha256(environment.artifacts / "manifest.json"),
                        "lifecycle_sha256":sha256(environment.artifacts / "process-lifecycle.json")})
            except (AttributeError, OSError):
                environment_evidence = []
        environment_evidence_ok = len(environment_evidence) == len(CASES)
        process_cleanup_ok = bool(environments)
        for environment in environments:
            try:
                require_process_teardowns(environment.process_starts,
                                          environment.process_teardowns)
                lifecycle = json.loads((environment.artifacts / "process-lifecycle.json").read_text(
                    encoding="utf-8"))
                process_cleanup_ok &= (lifecycle == {
                    "version": 1,
                    "scope": "exact-owned-isolated-process-teardown-not-graceful-server-exit",
                    "starts": environment.process_starts,
                    "teardowns": environment.process_teardowns})
            except (AttributeError, OSError, UnicodeError, json.JSONDecodeError, SetupError):
                process_cleanup_ok = False
        cleanup_ok = bool(environments and process_cleanup_ok and all(
            env._closed and not env.root.exists()
            and all(p.poll() is not None for p in env.processes.values())
            for env in environments))
        passed = (exit_code == 0 and collection_ok and environment_isolation_ok
                  and environment_evidence_ok and not self.unexpected
                  and all(cases.values()) and cleanup_ok)
        return {"status": "passed" if passed else "failed", "collection_verified": collection_ok,
                "environment_isolation_verified": environment_isolation_ok,
                "environment_evidence": environment_evidence,
                "cleanup_verified": cleanup_ok,
                "process_cleanup_verified": process_cleanup_ok,
                "cases": cases, "pytest_exit_code": int(exit_code)}


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
            report.update(revision=revision, source_dirty=dirty, identities=identities,
                          deadline_scale=profile.get("deadline_scale", 1))
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
                    code = pytest.main([*SUITES, "--rootdir", str(REPO),
                                        "--e2e-profile", str(local_profile), "-q", "--capture=sys",
                                        "-o", "addopts=", "-p", "no:cacheprovider", "--strict-markers",
                                        "--junitxml", str(private / "live.xml")], plugins=[gate])
                report.update(gate.summary(code))
                (private / "gate-diagnostics.json").write_text(json.dumps({
                    "collected": gate.collected,
                    "reports": gate.reports,
                    "unexpected": gate.unexpected,
                    "environment_count": len(gate.environments),
                    "case_environment_count": len(gate.case_environments),
                }, indent=2), encoding="utf-8")
                environments = gate.environments or ([gate.environment] if gate.environment is not None else [])
                report["inputs_verified"] = bool(environments) and all(
                    inputs_match(identities, json.loads(
                        (environment.artifacts / "manifest.json").read_text(encoding="utf-8")),
                        report["revision"], report["source_dirty"], report["deadline_scale"])
                    for environment in environments)
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

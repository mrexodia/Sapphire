"""Bounded owned warm world for repeated development checks and a separate viewer.

Uses ONE private database/runtime, never an existing database. Fixture preparation
is administrative, before first connection, and is not normal-creation evidence.
Create <session-dir>/stop to stop. The host also stops on expiry or process loss.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import uuid

import psutil

from .provision_development import require_private_output, reserve_private_profile
from .support.catalog import load_quest_catalog
from .support.development import DevelopmentError, Timings, validate_profile
from .support.development_party import require_bound_party_worker
from .support.environment import (Environment, artifact_tree_sha256,
                                  require_process_teardowns)
from .support.worker import Worker
from .support.development_worker_exit import ObservedWorker, unobserved_worker_exit


def publish_status(path, report):
    temporary = path.with_name(".status-" + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def serve(profile, session_dir, *, maximum_seconds=3600, environment_factory=Environment,
          worker_factory=Worker, clock=time.monotonic, sleeper=time.sleep, on_ready=None):
    if type(maximum_seconds) is not int or not 60 <= maximum_seconds <= 14400:
        raise DevelopmentError("host lifetime must be an integer in 60..14400 seconds")
    catalog_path = Path(profile["quest_catalog"]).resolve()
    catalog = load_quest_catalog(catalog_path)
    if catalog["quest"] != 65686:
        raise DevelopmentError("warm host requires the Motivational Speaking source corridor")
    session_dir = require_private_output(Path(session_dir) / "bot-profile.json").parent
    session_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    status_path = session_dir / "status.json"
    owner = psutil.Process()
    timings = Timings()
    report = {"version": 1, "kind": "owned-development-host", "session_id": uuid.uuid4().hex,
              "status": "starting", "scope": "owned-private-warm-world-not-acceptance",
              "protocol": "sapphire-3.3", "maximum_seconds": maximum_seconds,
              "owner_pid": owner.pid, "owner_created": owner.create_time(),
              "existing_database_access": False, "graphical_client_started": False,
              "fixture_setup": "three new non-GM pre-connection fixtures, including one separate viewer",
              "normal_lobby_creation_verified": False, "cleanup_verified": False,
              "process_cleanup_verified": False,
              "worker_preflight_exit": unobserved_worker_exit()}
    environment = None
    owned_profiles = {}
    started = clock()
    try:
        publish_status(status_path, report)
        with timings.phase("environment_construction"):
            environment = environment_factory(profile)
        with timings.phase("worker_preflight"):
            with ObservedWorker(worker_factory(environment.worker, environment.artifacts / "host-worker-preflight"),
                                report["worker_preflight_exit"]) as worker:
                require_bound_party_worker(worker)
        with timings.phase("environment_start_once"):
            environment.start()
        with timings.phase("pre_connection_fixture_preparation"):
            fixtures = [environment.fresh_character(catalog["route"][0]) for _ in range(3)]
        binding = {"path": str(status_path), "id": report["session_id"]}
        common = {"version": 1, "mode": "shared-development", "protocol": "sapphire-3.3",
                  "worker": str(environment.worker.resolve()), "api_port": environment.api_port,
                  "lobby_port": environment.lobby_port, "territory": 130,
                  "quest_catalog": str(catalog_path), "host_session": binding}
        accounts = [{"username": row["username"], "password": row["password"], "character": row["name"]}
                    for row in fixtures]
        bots = {**common, "accounts": accounts[:2]}
        validate_profile(bots)
        exports = {"bot-profile.json": bots, "server-profile.json": common,
                   "viewer-profile.json": {**common, "role": "separate-viewer", "account": accounts[2]}}
        with timings.phase("private_profile_export"):
            for filename, contents in exports.items():
                path = session_dir / filename
                try:
                    reserve_private_profile(path, contents)
                except BaseException:
                    # A partial write or an externally created file is not ours
                    # to delete on a guessed identity. Report retention honestly.
                    if path.exists():
                        report["profile_export_incomplete"] = True
                    raise
                owned_profiles[path] = hashlib.sha256(path.read_bytes()).hexdigest()
        report.update(api_port=environment.api_port, lobby_port=environment.lobby_port,
                      world_port=environment.zone_port, artifacts=str(environment.artifacts),
                      owned_pids={name: process.pid for name, process in environment.processes.items()},
                      worker_sha256=hashlib.sha256(environment.worker.read_bytes()).hexdigest(),
                      deadline_monotonic=clock() + maximum_seconds,
                      profiles=list(exports), status="ready")
        environment.check_alive()
        publish_status(status_path, report)
        if on_ready:
            on_ready({"status": "ready", "session_directory": str(session_dir),
                      "maximum_seconds": maximum_seconds, "stop_file": str(session_dir / "stop")})
        with timings.phase("warm_host_available_not_gameplay"):
            while True:
                environment.check_alive()
                if (session_dir / "stop").exists():
                    report["stop_reason"] = "operator_stop_file"
                    break
                remaining = report["deadline_monotonic"] - clock()
                if remaining <= 0:
                    report["stop_reason"] = "bounded_lifetime_expired"
                    break
                # Operator control / process-health polling, not a gameplay wait
                # or a sleep used to make an assertion pass.
                sleeper(min(0.25, remaining))
        report["status"] = "stopping"
    except (Exception, KeyboardInterrupt) as error:
        report.update(status="failed", error_type=type(error).__name__,
                      failure_stage=next((row["phase"] for row in timings.rows
                                          if row["outcome"] == "failed"), "status_publication_or_ready_callback"))
    finally:
        # Invalidate exported bindings before stopping servers. Publication failure
        # must never skip process cleanup; expiry/owner identity also protect readers.
        try:
            publish_status(status_path, report)
        except Exception as error:
            report.update(status="failed", status_write_error=type(error).__name__)
        if environment is not None:
            try:
                with timings.phase("owned_environment_cleanup"):
                    environment.close()
                report["cleanup_verified"] = not environment.root.exists() and not environment.processes
                lifecycle_path = environment.artifacts / "process-lifecycle.json"
                lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8"))
                expected = {"version":1,
                    "scope":"exact-owned-isolated-process-teardown-not-graceful-server-exit",
                    "starts":environment.process_starts,"teardowns":environment.process_teardowns}
                if lifecycle != expected:
                    raise DevelopmentError("owned host process lifecycle artifact differs from cleanup")
                if lifecycle["starts"]:
                    proof = require_process_teardowns(lifecycle["starts"], lifecycle["teardowns"])
                    retained = session_dir / "process-lifecycle.json"
                    publish_status(retained, lifecycle)
                    report["environment_process_teardown"] = {"verified":True,
                        "scope":"exact-owned-warm-host-service-teardown-not-server-offline-proof",
                        "relative_path":"process-lifecycle.json",
                        "sha256":hashlib.sha256(retained.read_bytes()).hexdigest(),
                        "evidence":proof}
                    report["environment_artifact_tree_sha256"] = artifact_tree_sha256(
                        environment.artifacts)
                    report["process_cleanup_verified"] = True
                if (not report["cleanup_verified"]
                        or (report["status"] == "stopping"
                            and not report["process_cleanup_verified"])):
                    report["status"] = "failed"
            except Exception as error:
                report.update(status="failed", cleanup_error_type=type(error).__name__)
        report["private_profiles_removed"] = not report.get("profile_export_incomplete", False)
        for path, expected_hash in owned_profiles.items():
            try:
                if path.exists():
                    # Never delete a file subsequently replaced/edited by the user.
                    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
                        raise DevelopmentError("private profile was changed externally")
                    path.unlink()
            except Exception as error:
                report.update(status="failed", private_profiles_removed=False,
                              profile_cleanup_error_type=type(error).__name__)
        if report["status"] == "stopping" and report["cleanup_verified"]:
            report["status"] = "stopped"
        report["elapsed_seconds"] = clock() - started
        report["timings"] = timings.rows
        publish_status(status_path, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, help="Existing disposable-environment asset/binary profile")
    parser.add_argument("--session-dir", required=True, help="NEW private/ignored control and credential directory")
    parser.add_argument("--worker", help="Optional rebuilt headless worker override")
    parser.add_argument("--max-seconds", type=int, default=3600)
    args = parser.parse_args(argv)
    try:
        profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
        if args.worker:
            profile["worker"] = args.worker
        report = serve(profile, args.session_dir, maximum_seconds=args.max_seconds,
                       on_ready=lambda status: print(json.dumps(status), flush=True))
    except (Exception, KeyboardInterrupt) as error:
        print(json.dumps({"status": "failed", "error_type": type(error).__name__}), flush=True)
        return 1
    print(json.dumps({"status": report["status"], "cleanup_verified": report["cleanup_verified"],
                      "session_directory": args.session_dir}), flush=True)
    return 0 if report["status"] == "stopped" else 1


if __name__ == "__main__":
    raise SystemExit(main())

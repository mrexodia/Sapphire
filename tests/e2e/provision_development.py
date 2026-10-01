"""Create NEW dedicated dev bot accounts/characters; never adopt/reset existing ones.

Credentials are reserved in a new private profile before any network mutation.
This command does not skip openings, grant progress or prepare public-world state.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import string
import subprocess
import time
import uuid

from .support.development import (AccountLease, DevelopmentError, Timings, authenticate,
                                  create_account, received_character_identity, validate_profile, check_managed_host)
from .support.worker import Bot, Worker
from .support.development_binding import provisioning_binding
from .support.development_worker_exit import ObservedWorker, unobserved_worker_exit
from .support.development_deadline import RunDeadline, DeadlineWorker
from .support.development_lease import terminal_account_lease_snapshot

REPO = Path(__file__).resolve().parents[2]


def new_profile(server):
    required = {"version", "mode", "protocol", "worker", "api_port", "lobby_port", "territory"}
    if not isinstance(server, dict) or not required <= server.keys() or server.keys() - (required | {"quest_catalog", "host_session"}):
        raise DevelopmentError("provisioning requires a server-only profile, without existing accounts")
    profile = dict(server)
    profile["accounts"] = [{"username": "e2e_dev_" + uuid.uuid4().hex,
                            "password": secrets.token_hex(24),
                            "character": "Tester " + "".join(secrets.choice(string.ascii_uppercase) for _ in range(12))}
                           for _ in range(2)]
    return validate_profile(profile)


def require_private_output(path):
    path = Path(path).resolve()
    if path.is_relative_to(REPO):
        # Refuse accidental credential publication inside the checkout, including
        # a tracked file that happens to match an ignore rule.
        ignored = subprocess.run(["git", "check-ignore", "--quiet", "--", str(path)], cwd=REPO,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        if not ignored:
            raise DevelopmentError("credential output inside the checkout must be git-ignored")
    return path


def reserve_private_profile(path, profile):
    path = require_private_output(path)
    # No overwrite, no symlink following; POSIX 0600, inherited directory ACLs on Windows.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(profile, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def run(server, output_profile, artifacts, *, confirmed=False, max_seconds=None,
        worker_factory=Worker, register=create_account, login=authenticate, lease_root=None):
    if not confirmed:
        raise DevelopmentError("explicit --create-new-bot-accounts opt-in is required")
    deadline = RunDeadline(max_seconds) if max_seconds is not None else None
    profile = new_profile(server)
    check_managed_host(profile)
    artifacts = Path(artifacts)
    if Path(output_profile).resolve().is_relative_to(artifacts.resolve()):
        raise DevelopmentError("credential profile must be outside the diagnostic artifact directory")
    artifacts.mkdir(parents=True, exist_ok=False)
    run_id, start = uuid.uuid4().hex, time.monotonic()
    timings = Timings()
    lease = AccountLease(profile, run_id, lease_root)
    report = {"version": 1, "run_id": run_id, "status": "failed",
              "scope": "shared-development-provisioning-not-gameplay",
              "ready_for_shared_checks": False, "server_identity_verified": False,
              "server_processes_owned": False, "database_access": False,
              "administrative_placement_performed": False, "lease_retained": False,
              "credential_profile_saved": False, "worker_closed": False,
              "worker_exit": unobserved_worker_exit(),
              "worker_sha256": hashlib.sha256(Path(profile["worker"]).read_bytes()).hexdigest(),
              "accounts": []}
    acquired = False
    try:
        with timings.phase("reserve_private_credential_profile"):
            # Save generated credentials before making any requests. On uncertain
            # network results the operator can still identify/recover the accounts.
            if deadline is not None:
                deadline.check()
            reserve_private_profile(output_profile, profile)
            report["credential_profile_saved"] = True
            if deadline is not None:
                deadline.check()
        with timings.phase("account_lease"):
            if deadline is not None:
                deadline.check()
            lease.acquire()
            acquired = True
            report["lease_retained"] = True
            if deadline is not None:
                deadline.check()
        with timings.phase("worker_session_including_close"):
            with ObservedWorker(worker_factory(Path(profile["worker"]), artifacts / "worker"),
                                report["worker_exit"]) as raw_worker:
                if deadline is not None:
                    deadline.check()
                    worker = DeadlineWorker(raw_worker, deadline)
                else:
                    worker = raw_worker
                for index, account in enumerate(profile["accounts"]):
                    row = {"slot": index, "character": account["character"],
                           "account_creation": "not_started", "character_creation": "not_started"}
                    report["accounts"].append(row)
                    with timings.phase(f"create_account_{index}"):
                        row["account_creation"] = "requested_outcome_unknown"
                        if deadline is None:
                            register(profile, account)
                        else:
                            deadline.call(register, profile, account)
                        row["account_creation"] = "acknowledged"
                    with timings.phase(f"fresh_http_login_{index}"):
                        auth = (login(profile, account) if deadline is None
                                else deadline.call(login, profile, account))
                        row["account_creation"] = "fresh_login_verified"
                    bot = Bot(worker, f"provision-{index}")
                    with timings.phase(f"lobby_create_and_world_{index}"):
                        row["character_creation"] = "requested_outcome_unknown"
                        state = bot.create_character_via_lobby(auth, account["character"], creation_class=1)
                        identity = received_character_identity(state, account["character"])
                        row.update(character_creation="refreshed_lobby_and_world_verified",
                                   entity_id=identity["entity_id"], character_id=identity["character_id"],
                                   territory=state["territory"], gm_rank=state["gm_rank"])
                    with timings.phase(f"logout_{index}"):
                        bot.logout(wait_server_close=True)
                        bot.close()
                        row["logout_server_close_verified"] = True
            report["worker_closed"] = True
        if deadline is not None:
            with timings.phase("provisioning_deadline_completion"):
                deadline.complete()
        with timings.phase("release_accounts"):
            lease.release()
            report["lease_retained"] = False
        report["provisioning_binding"] = provisioning_binding(profile, report["accounts"])
        report["status"] = "provisioned"
        report["next_step"] = "Opening/public-world preparation is still required before run_development. No placement or reset command was run."
    except (Exception, KeyboardInterrupt) as error:
        report["error_type"] = type(error).__name__
        report["failure_stage"] = next((row["phase"] for row in timings.rows
                                         if row["outcome"] == "failed"), "unknown")
        if acquired:
            report["recovery"] = "Keep the private credential profile; inspect partial account/character state and verify bots offline before releasing this run's leases. Do not retry creation automatically."
    finally:
        report["run_deadline"] = deadline.report() if deadline is not None else {"enabled": False}
        snapshot = terminal_account_lease_snapshot(profile, lease.root, run_id)
        report["lease_snapshot"] = snapshot
        if not acquired:
            report["lease_snapshot_matches_run_state"] = None
        elif report["lease_retained"]:
            report["lease_snapshot_matches_run_state"] = (
                snapshot.get("state") == "retained"
                and snapshot.get("retained_receipts_match_run") is True)
        else:
            report["lease_snapshot_matches_run_state"] = snapshot.get("state") == "clear"
        if report["status"] == "provisioned" and report["lease_snapshot_matches_run_state"] is not True:
            report["status"] = "failed"
            report["error_type"] = "DevelopmentError"
            report["failure_stage"] = "terminal_lease_snapshot"
            report["recovery"] = "Lease release cannot be verified; keep the private credentials and do not retry, reuse accounts or remove lease files without independent offline evidence."
            report.pop("provisioning_binding", None)
            report.pop("next_step", None)
        report["elapsed_seconds"] = time.monotonic() - start
        report["timings"] = timings.rows
        (artifacts / "provisioning-summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-profile", required=True, help="Private server-only JSON; no existing accounts")
    parser.add_argument("--output-profile", required=True, help="NEW private credential file; parent must exist")
    parser.add_argument("--artifacts", required=True, help="NEW private artifact directory")
    parser.add_argument("--create-new-bot-accounts", action="store_true")
    parser.add_argument("--max-seconds", type=int, default=300,
                        help="Cooperative provisioning budget 1..900 seconds (default 300); final lease/report cleanup excluded")
    args = parser.parse_args(argv)
    try:
        server = json.loads(Path(args.server_profile).read_text(encoding="utf-8"))
        report = run(server, args.output_profile, args.artifacts,
                     confirmed=args.create_new_bot_accounts, max_seconds=args.max_seconds)
    except (Exception, KeyboardInterrupt) as error:
        print(json.dumps({"status": "failed", "stage": "preflight", "error_type": type(error).__name__}))
        return 1
    print(json.dumps({"status": report["status"], "scope": report["scope"],
                      "ready_for_shared_checks": False, "artifacts": args.artifacts}))
    return 0 if report["status"] == "provisioned" else 1


if __name__ == "__main__":
    raise SystemExit(main())

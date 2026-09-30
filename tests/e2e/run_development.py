"""Fast, opt-in two-bot checks on an already-running LOCAL development server.

Never starts/stops servers, changes configuration, accesses a database or retries
mutations. This is explicitly non-isolated evidence, NOT an acceptance gate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
import uuid

from .support.development import (AccountLease, DevelopmentError, Timings, authenticate,
                                  idle_state, movement_route, validate_profile, witnessed)
from .support.worker import Bot, Worker


def run(profile, artifacts, *, confirmed=False, cycles=1, worker_factory=Worker,
        login=authenticate, lease_root=None):
    if not confirmed:
        raise DevelopmentError("explicit --allow-shared-development opt-in is required")
    validate_profile(profile)
    if type(cycles) is not int or not 1 <= cycles <= 10:
        raise DevelopmentError("cycles must be an integer in 1..10")
    route, catalog_hash = movement_route(profile)
    artifacts = Path(artifacts)
    artifacts.mkdir(parents=True, exist_ok=False)
    run_id = uuid.uuid4().hex
    timings, start = Timings(), time.monotonic()
    lease = AccountLease(profile, run_id, lease_root)
    report = {"version": 1, "run_id": run_id, "status": "failed",
              "scope": "shared-development-not-acceptance", "server_identity_verified": False,
              "server_processes_owned": False, "database_access": False,
              "account_reset_performed": False, "cycles": cycles,
              "protocol": profile["protocol"], "territory": profile["territory"],
              "worker_sha256": hashlib.sha256(Path(profile["worker"]).read_bytes()).hexdigest(),
              "catalog_sha256": catalog_hash, "movement_waypoints_per_cycle": len(route),
              "lease_retained": False, "worker_closed": False}
    acquired = False
    try:
        with timings.phase("account_lease"):
            lease.acquire()
            acquired = True
            report["lease_retained"] = True
        # Scope of this context includes worker cleanup; passing requires clean exit.
        with timings.phase("worker_session_including_close"):
            with worker_factory(Path(profile["worker"]), artifacts / "worker") as worker:
                bots = [Bot(worker, "mover"), Bot(worker, "witness")]
                states = []
                for index, (bot, account) in enumerate(zip(bots, profile["accounts"])):
                    with timings.phase(f"http_login_{index}"):
                        auth = login(profile, account)
                    with timings.phase(f"lobby_world_login_{index}"):
                        state = bot.login_via_lobby(auth, account["character"])
                        states.append(state)
                        if not idle_state(state, profile["territory"]):
                            raise DevelopmentError("bot is not idle in the configured public territory")
                mover, witness = bots
                actor, observer = [state["entity_id"] for state in states]
                if not actor or not observer or actor == observer:
                    raise DevelopmentError("bot identities must be distinct")
                report["entities"] = [actor, observer]
                names = [account["character"] for account in profile["accounts"]]
                with timings.phase("independent_initial_state"):
                    worker.wait_state(witness.name,
                        lambda s: idle_state(s, profile["territory"]) and witnessed(s, actor, names[0],
                            route[0] if route else states[0]["observed_position"]),
                        "exact mover identity and route-start position", timeout=10)
                    worker.wait_state(mover.name,
                        lambda s: idle_state(s, profile["territory"]) and witnessed(s, observer, names[1],
                            states[1]["observed_position"]), "exact witness identity", timeout=10)
                for cycle in range(cycles):
                    with timings.phase(f"say_round_trip_{cycle}"):
                        for sender, receiver, identity in ((mover, witness, actor), (witness, mover, observer)):
                            message = f"Sapphire dev {run_id[:8]} {cycle} {sender.name}"
                            sender.say(message)
                            receiver.expect_say(identity, message)
                    if route:
                        with timings.phase(f"observed_out_and_back_{cycle}"):
                            # No fabricated connecting segment, teleport or replan. A human
                            # viewer may remain nearby; the second bot proves each waypoint.
                            for point in [*route[1:], *reversed(route[:-1])]:
                                if not idle_state(worker.snapshot(mover.name), profile["territory"]):
                                    raise DevelopmentError("mover left the expected idle public state")
                                mover.walk_to(point, speed=2.0, timeout=10)
                                worker.wait_state(witness.name,
                                    lambda s: idle_state(s, profile["territory"])
                                    and witnessed(s, actor, names[0], point),
                                    "independently received waypoint", timeout=10)
                with timings.phase("logout_and_independent_despawn"):
                    mover.logout(wait_server_close=True)
                    worker.wait_state(witness.name, lambda s: str(actor) not in s["actors"],
                                      "mover despawn", timeout=10)
                    witness.logout(wait_server_close=True)
                    for bot in bots:
                        bot.close()
            report["worker_closed"] = True
        with timings.phase("release_accounts"):
            lease.release()
            report["lease_retained"] = False
        report["status"] = "passed"
    except (Exception, KeyboardInterrupt) as error:
        # Worker journals retain bounded semantic evidence. Exception strings may
        # contain received state; never echo them or the credential profile here.
        report["error_type"] = type(error).__name__
        report["failure_stage"] = next((row["phase"] for row in timings.rows
                                         if row["outcome"] == "failed"), "unknown")
        if acquired:
            report["recovery"] = "Verify both bots offline, then manually remove this run's local account leases. No automatic retry/reset."
    finally:
        report["elapsed_seconds"] = time.monotonic() - start
        report["timings"] = timings.rows
        (artifacts / "development-summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--artifacts", required=True, help="New private artifact directory (must not exist)")
    parser.add_argument("--allow-shared-development", action="store_true")
    parser.add_argument("--cycles", type=int, default=1)
    args = parser.parse_args(argv)
    try:
        profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
        result = run(profile, args.artifacts, confirmed=args.allow_shared_development, cycles=args.cycles)
    except (Exception, KeyboardInterrupt) as error:
        # In particular, do not let JSONDecodeError reproduce a credential line.
        print(json.dumps({"status": "failed", "stage": "preflight", "error_type": type(error).__name__}))
        return 1
    print(json.dumps({"status": result["status"], "scope": result["scope"],
                      "elapsed_seconds": result["elapsed_seconds"], "artifacts": args.artifacts}))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

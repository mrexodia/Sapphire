"""Fast, opt-in two-bot checks on an already-running LOCAL development server.

Never starts/stops servers, changes configuration, accesses a database or retries
mutations. This is explicitly non-isolated evidence, NOT an acceptance gate.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import time
import uuid

from .support.development import (AccountLease, DevelopmentError, Timings, authenticate, check_managed_host,
                                  idle_state, movement_route, validate_profile, witnessed)
from .support.worker import Bot, Worker
from .support.development_deadline import RunDeadline, DeadlineWorker
from .support.development_worker_exit import ObservedWorker
from .support.development_reconnect import verify_position_reconnect
from .support.development_party import require_bound_party_worker, verify_two_bot_party
from .support.development_viewer import validate_viewer_name, viewer_checkpoint
from .support.development_tell import require_visible_tell_worker, verify_visible_tells
from .support.development_decline import require_decline_worker, verify_party_decline
from .support.development_sprint import require_sprint_worker, verify_sprint as verify_self_sprint
from .support.development_equipment import (require_equipment_worker, begin_roundtrip,
                                            finish_roundtrip, observe_after_reconnect)


def run(profile, artifacts, *, confirmed=False, cycles=1, await_placement=False,
        verify_reconnect=False, verify_party=False, verify_tell=False, verify_decline=False,
        verify_inventory=False, verify_sprint=False, verify_equipment=False, viewer_name=None, max_seconds=None,
        worker_factory=Worker, login=authenticate, lease_root=None):
    if not confirmed:
        raise DevelopmentError("explicit --allow-shared-development opt-in is required")
    validate_profile(profile)
    check_managed_host(profile)
    validate_viewer_name(viewer_name, profile["accounts"])
    if max_seconds is not None and (type(max_seconds) is not int or not 1 <= max_seconds <= 900):
        raise DevelopmentError("max_seconds must be an integer in 1..900")
    if type(cycles) is not int or not 1 <= cycles <= 10:
        raise DevelopmentError("cycles must be an integer in 1..10")
    if any(type(flag) is not bool for flag in
           (verify_reconnect, verify_party, verify_tell, verify_decline, verify_inventory, verify_sprint, verify_equipment)):
        raise DevelopmentError("verification flags must be boolean")
    if verify_inventory and not verify_reconnect:
        raise DevelopmentError("inventory comparison requires explicit --verify-reconnect")
    if verify_equipment and not (verify_reconnect and verify_inventory):
        raise DevelopmentError("equipment round trip requires explicit --verify-reconnect and --verify-reconnect-inventory")
    if verify_decline and verify_party:
        raise DevelopmentError("decline and party-creation checks require separate fresh runs")
    route, catalog_hash = movement_route(profile)
    if type(await_placement) is not bool or (await_placement and not route):
        raise DevelopmentError("administrative placement wait requires a source-bound quest route")
    artifacts = Path(artifacts)
    artifacts.mkdir(parents=True, exist_ok=False)
    run_id = uuid.uuid4().hex
    timings, start = Timings(), time.monotonic()
    deadline = RunDeadline(max_seconds, started=start) if max_seconds is not None else None
    if deadline is not None:
        original_login = login
        def login(config, account):
            return deadline.call(original_login, config, account)
    lease = AccountLease(profile, run_id, lease_root)
    report = {"version": 1, "run_id": run_id, "status": "failed",
              "scope": "shared-development-not-acceptance", "server_identity_verified": False,
              "server_processes_owned": False, "database_access": False,
              "account_reset_performed_by_runner": False, "cycles": cycles,
              "administrative_preparation_wait_enabled": await_placement,
              "administrative_command_execution_attested": False,
              "reconnect_verification": {"requested": verify_reconnect, "verified": False},
              "inventory_verification": {"requested": verify_inventory, "verified": False},
              "party_verification": {"requested": verify_party, "verified": False},
              "tell_verification": {"requested": verify_tell, "verified": False},
              "decline_verification": {"requested": verify_decline, "verified": False},
              "sprint_verification": {"requested": verify_sprint, "verified": False},
              "equipment_verification": {"requested": verify_equipment, "verified": False},
              "viewer_verification": {"requested": viewer_name is not None, "verified": False,
                                      "scope": "two-checkpoint-presence-not-graphical-attestation",
                                      "viewer_login_or_control_performed": False},
              "world_restart_performed": False,
              "protocol": profile["protocol"], "territory": profile["territory"],
              "worker_sha256": hashlib.sha256(Path(profile["worker"]).read_bytes()).hexdigest(),
              "catalog_sha256": catalog_hash, "movement_waypoints_per_cycle": len(route),
              "lease_retained": False, "worker_closed": False,
              "worker_exit": {"context_entered": False, "context_exit_attempted": False,
                              "context_exit_completed": False, "process_exit_observed": False}}
    acquired = False
    try:
        with timings.phase("account_lease"):
            if deadline is not None:
                deadline.check()
            lease.acquire()
            acquired = True
            report["lease_retained"] = True
        # Scope of this context includes worker cleanup; passing requires clean exit.
        with timings.phase("worker_session_including_close"):
            if deadline is not None:
                deadline.check()
            with ObservedWorker(worker_factory(Path(profile["worker"]), artifacts / "worker"),
                                report["worker_exit"]) as raw_worker:
                if deadline is not None:
                    deadline.check()
                worker = DeadlineWorker(raw_worker, deadline) if deadline is not None else raw_worker
                if verify_party:
                    with timings.phase("party_worker_capability"):
                        require_bound_party_worker(worker)
                if verify_decline:
                    with timings.phase("decline_worker_capability"):
                        require_decline_worker(worker)
                if verify_tell:
                    with timings.phase("tell_worker_capability"):
                        require_visible_tell_worker(worker)
                if verify_sprint:
                    with timings.phase("sprint_worker_capability"):
                        require_sprint_worker(worker)
                if verify_equipment:
                    with timings.phase("equipment_worker_capability"):
                        require_equipment_worker(worker)
                bots = [Bot(worker, "mover"), Bot(worker, "witness")]
                states = []
                for index, (bot, account) in enumerate(zip(bots, profile["accounts"])):
                    with timings.phase(f"http_login_{index}"):
                        auth = login(profile, account)
                    with timings.phase(f"lobby_world_login_{index}"):
                        state = bot.login_via_lobby(auth, account["character"])
                        states.append(state)
                        initial_territory = state.get("territory") if await_placement else profile["territory"]
                        if (await_placement and initial_territory not in {130, 182}) or not idle_state(state, initial_territory):
                            raise DevelopmentError("bot is not idle in the expected territory")
                if await_placement:
                    with timings.phase("administrative_placement_wait_not_gameplay"):
                        deadline = time.monotonic() + 120
                        (artifacts / "placement-ready.json").write_text(json.dumps({
                            "scope": "administrative-preparation-not-gameplay", "run_id": run_id,
                            "wait_seconds": 120, "territory": profile["territory"], "position": route[0],
                            "bots": [{"entity_id": state["entity_id"], "name": account["character"]}
                                     for state, account in zip(states, profile["accounts"])],
                            "note": "Readiness only; a separate GM-approved registry command is required."
                        }, indent=2), encoding="utf-8")
                        for index, bot in enumerate(bots):
                            remaining = deadline - time.monotonic()
                            if remaining <= 0:
                                raise DevelopmentError("administrative placement observation deadline exceeded")
                            expected_entity = states[index]["entity_id"]
                            states[index] = worker.wait_state(bot.name,
                                lambda s: idle_state(s, profile["territory"])
                                and s["entity_id"] == expected_entity
                                and math.dist(s["observed_position"], route[0]) <= 0.15,
                                "operator-prepared public-world state (not gameplay)", timeout=remaining)
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
                if viewer_name is not None:
                    report["viewer_verification"]["start"] = viewer_checkpoint(
                        worker, [mover, witness], [actor, observer], profile["territory"],
                        viewer_name, run_id, "start", artifacts, timings)
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
                if verify_decline:
                    report["decline_verification"] = verify_party_decline(
                        profile, worker, mover, witness, states, timings)
                if verify_party:
                    report["party_verification"] = verify_two_bot_party(
                        profile, worker, mover, witness, states, run_id, timings)
                if verify_tell:
                    report["tell_verification"] = verify_visible_tells(
                        profile, worker, mover, witness, states, run_id, timings)
                if verify_sprint:
                    report["sprint_verification"] = verify_self_sprint(
                        profile, worker, mover, witness, states, timings)
                if verify_equipment:
                    equipment = report["equipment_verification"]
                    begin_roundtrip(profile, worker, mover, states[0], equipment, timings)
                    mover, equipment["unequip_reconnect"] = verify_position_reconnect(
                        profile, worker, mover, witness, states[0],
                        route[0] if route else states[0]["observed_position"], run_id, timings, login,
                        reconnected_name="mover-equipment-unequipped")
                    observe_after_reconnect(profile, worker, mover, equipment, timings)
                if verify_reconnect:
                    mover, report["reconnect_verification"] = verify_position_reconnect(
                        profile, worker, mover, witness, states[0],
                        route[0] if route else states[0]["observed_position"], run_id, timings, login,
                        inventory_report=report["inventory_verification"] if verify_inventory else None)
                    bots = [mover, witness]
                if verify_equipment:
                    finish_roundtrip(profile, worker, mover, equipment, timings)
                    mover, equipment["reequip_reconnect"] = verify_position_reconnect(
                        profile, worker, mover, witness, states[0],
                        route[0] if route else states[0]["observed_position"], run_id, timings, login,
                        reconnected_name="mover-equipment-reequipped")
                    observe_after_reconnect(profile, worker, mover, equipment, timings, reequipped=True)
                    bots = [mover, witness]
                if viewer_name is not None:
                    report["viewer_verification"]["finish"] = viewer_checkpoint(
                        worker, [mover, witness], [actor, observer], profile["territory"],
                        viewer_name, run_id, "finish", artifacts, timings,
                        expected=report["viewer_verification"]["start"]["identity"])
                    report["viewer_verification"]["verified"] = True
                with timings.phase("logout_and_independent_despawn"):
                    mover.logout(wait_server_close=True)
                    worker.wait_state(witness.name, lambda s: str(actor) not in s["actors"],
                                      "mover despawn", timeout=10)
                    witness.logout(wait_server_close=True)
                    for bot in bots:
                        bot.close()
            report["worker_closed"] = True
        if deadline is not None:
            with timings.phase("run_deadline_completion"):
                deadline.complete()
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
        report["run_deadline"] = deadline.report() if deadline is not None else {"enabled": False}
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
    parser.add_argument("--max-seconds", type=int, default=300,
                        help="Cooperative session budget 1..900 seconds (default 300); final lease/report cleanup excluded")
    parser.add_argument("--await-placement", action="store_true",
                        help="Allow up to 120s for separate GM-approved placement; requires quest_catalog")
    parser.add_argument("--verify-reconnect", action="store_true",
                        help="One explicit fresh-login identity/position check with the witness kept online; no restart")
    parser.add_argument("--verify-reconnect-inventory", dest="verify_inventory", action="store_true",
                        help="Compare complete received slot/catalog/count projections; requires --verify-reconnect")
    parser.add_argument("--verify-party", action="store_true",
                        help="One owned two-bot invite/chat/disband check; refuses existing social state")
    parser.add_argument("--verify-party-decline", dest="verify_decline", action="store_true",
                        help="Decline only the exact other bot's invitation; separate from --verify-party")
    parser.add_argument("--verify-tell", action="store_true",
                        help="Two fresh received direct Tells between visible non-GM bots; no remote fallback")
    parser.add_argument("--verify-sprint", action="store_true",
                        help="One ordinary self-Sprint with fresh independent effect/zero-TP observations; no retry")
    parser.add_argument("--verify-starter-equipment", dest="verify_equipment", action="store_true",
                        help="Starter-body round trip with three normal reconnects; also requires both inventory/reconnect flags")
    parser.add_argument("--viewer-name", help="Exact separate visible player name; requires unique Say replies at start/finish")
    args = parser.parse_args(argv)
    try:
        profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
        result = run(profile, args.artifacts, confirmed=args.allow_shared_development, cycles=args.cycles,
                     await_placement=args.await_placement, verify_reconnect=args.verify_reconnect,
                     verify_party=args.verify_party, verify_tell=args.verify_tell,
                     verify_decline=args.verify_decline, verify_inventory=args.verify_inventory,
                     verify_sprint=args.verify_sprint, verify_equipment=args.verify_equipment,
                     viewer_name=args.viewer_name, max_seconds=args.max_seconds)
    except (Exception, KeyboardInterrupt) as error:
        # In particular, do not let JSONDecodeError reproduce a credential line.
        print(json.dumps({"status": "failed", "stage": "preflight", "error_type": type(error).__name__}))
        return 1
    print(json.dumps({"status": result["status"], "scope": result["scope"],
                      "elapsed_seconds": result["elapsed_seconds"], "artifacts": args.artifacts}))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

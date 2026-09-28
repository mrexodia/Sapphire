"""Run bounded exploration/soak, or replay an allowlisted semantic action plan.

python -m tests.e2e.run_workload --profile .e2e-local.json --mode explore --seed 42 --bots 2 --steps 12
"""
import argparse
import json
import math
import os
from pathlib import Path
import time

from .support.catalog import load_quest_catalog
from .support.environment import Environment
from .support.metrics import ProcessMetrics
from .support.worker import Worker
from .support.workload import Workload, build_plan, resolve_plan, validate_plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--mode", choices=("explore", "soak", "replay"), default="explore")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--bots", type=int, default=2)
    parser.add_argument("--steps", type=int, default=12)
    parser.add_argument("--duration", type=float, help="workflow action budget, excluding setup/teardown (default 120s, or replayed limit)")
    parser.add_argument("--ramp-interval", type=float, help="population ramp delay (default 0.25s, or replayed limit)")
    parser.add_argument("--round-interval", type=float, help="minimum time between full soak round starts, 0..60s")
    parser.add_argument("--min-active-seconds", type=float, help="required first-to-last activity span, excluding setup/teardown")
    parser.add_argument("--plan", help="Recorded plan.json to replay (no raw packets or sessions)")
    args = parser.parse_args(argv)
    profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    catalog = load_quest_catalog(profile["quest_catalog"])
    if args.mode == "replay":
        if not args.plan or Path(args.plan).stat().st_size > 1024 * 1024:
            parser.error("replay requires a plan file <=1MiB")
        plan = validate_plan(json.loads(Path(args.plan).read_text(encoding="utf-8")), catalog)
    else:
        plan = build_plan(catalog, args.mode, args.seed, args.bots, args.steps)
    try:
        plan = resolve_plan(plan, catalog, duration=args.duration, ramp_interval=args.ramp_interval,
                            round_interval=args.round_interval, min_active_seconds=args.min_active_seconds)
    except ValueError as error:
        parser.error(str(error))
    environment = Environment(profile)
    result = {"status": "failed", "mode": args.mode, "plan_mode": plan["mode"], "bots": plan["bots"], "limits": plan["limits"]}
    stage = "setup"
    metrics, workload = None, None
    started = time.monotonic()
    try:
        (environment.artifacts / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
        environment.start()
        with Worker(environment.worker, environment.artifacts / "workload") as worker:
            workload = Workload(environment, worker, catalog, plan)
            metrics = ProcessMetrics({**{name: p.pid for name, p in environment.processes.items()},
                                      "worker": worker.process.pid, "runner": os.getpid()})
            metrics.start()
            workload.setup()
            result["peak_active_bots_verified"] = len(workload.bots)
            stage = "workflow"
            result.update(workload.run())
            stage = "shutdown"
            workload.shutdown()
            environment.check_alive()
            result["status"] = "passed"
    except KeyboardInterrupt:
        result["error"] = "workload interrupted"
        result["failure_stage"] = stage
    except Exception as error:
        result["error"] = str(error)
        result["failure_stage"] = stage
    finally:
        if metrics:
            metrics.stop()
            (environment.artifacts / "resources.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in metrics.samples), encoding="utf-8")
            result["process_resources"] = {}
            for name in metrics.processes:
                values = [row["processes"][name] for row in metrics.samples if "rss_bytes" in row["processes"][name]]
                if values:
                    result["process_resources"][name] = {"peak_rss_bytes": max(row["rss_bytes"] for row in values),
                        "cpu_seconds_delta": values[-1]["cpu_seconds"] - values[0]["cpu_seconds"]}
                    private = [row["private_commit_bytes"] for row in values if "private_commit_bytes" in row]
                    if private:
                        result["process_resources"][name]["peak_private_commit_bytes"] = max(private)
        if workload:
            (environment.artifacts / "checkpoints.json").write_text(json.dumps(workload.checkpoints, indent=2), encoding="utf-8")
            (environment.artifacts / "rounds.json").write_text(json.dumps(workload.rounds, indent=2), encoding="utf-8")
            outcomes = workload.outcomes
            (environment.artifacts / "outcomes.json").write_text(json.dumps(outcomes, indent=2), encoding="utf-8")
            elapsed = sorted(outcome["duration_seconds"] for outcome in outcomes)
            result["completed_actions"] = len(outcomes)
            result["failed_actions"] = sum(outcome["status"] != "passed" for outcome in outcomes)
            if elapsed:
                result["action_duration_seconds"] = {"p50": elapsed[len(elapsed)//2],
                    "p95": elapsed[math.ceil(len(elapsed)*0.95)-1], "max": elapsed[-1]}
        # Every normal failure path closes worker connections and all private processes.
        try:
            environment.close()
        except Exception as error:
            result["status"] = "failed"
            result["cleanup_error"] = str(error)
            result["failure_stage"] = "cleanup"
        result["elapsed_seconds"] = time.monotonic() - started
        (environment.artifacts / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"result": result, "artifacts": str(environment.artifacts)}, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

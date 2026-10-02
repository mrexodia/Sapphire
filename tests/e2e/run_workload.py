"""Run bounded exploration/soak, or replay an allowlisted semantic action plan.

python -m tests.e2e.run_workload --profile .e2e-local.json --mode explore --seed 42 --bots 2 --steps 12 --authorize-disposable-environment
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


def run(profile, catalog, plan, *, mode="replay", authorized=False):
    if authorized is not True:
        raise ValueError("workload requires explicit disposable-environment authorization")
    # Reject invalid semantics before allocating any private environment.
    plan = resolve_plan(plan, catalog)
    if mode not in {"explore", "soak", "replay"}:
        raise ValueError("unsupported workload mode")
    environment = Environment(profile)
    result = {"status": "failed", "mode": mode, "plan_mode": plan["mode"],
              "execution_authorized": True,
              "bots": plan["bots"], "limits": plan["limits"]}
    stage = "setup"
    metrics, workload = None, None
    started = time.monotonic()

    def message(error):
        text = "workload interrupted" if isinstance(error, KeyboardInterrupt) else str(error)
        for secret in environment.redactions:
            if secret:
                text = text.replace(secret, "<redacted>")
        return text

    def failed(key, error, failure_stage):
        result["status"] = "failed"
        result[key] = message(error)
        # Keep the original failure rather than hiding it behind a secondary
        # sampling/cleanup/diagnostic failure. Secondary errors have separate keys.
        result.setdefault("failure_stage", failure_stage)

    try:
        (environment.artifacts / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
        environment.start()
        with Worker(environment.worker, environment.artifacts / "workload",
                    getattr(environment, "deadline_scale", 1)) as worker:
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
    except (Exception, KeyboardInterrupt) as error:
        failed("error", error, stage)
    finally:
        # No report aggregation or artifact write may bypass environment cleanup.
        # Even an interrupted/broken sampler must not strand the owned servers.
        try:
            if metrics:
                try:
                    metrics.stop()
                except (Exception, KeyboardInterrupt) as error:
                    failed("sampling_error", error, "sampling")
        finally:
            try:
                environment.close()
                result["runtime_removed"] = not environment.root.exists()
                if not result["runtime_removed"]:
                    raise RuntimeError("private runtime remains after cleanup")
            except (Exception, KeyboardInterrupt) as error:
                failed("cleanup_error", error, "cleanup")

    def artifact(name, produce):
        try:
            text = produce()
            # Apply the same secrets registered by provisioning/authentication to
            # diagnostic exceptions as to environment logs. Plans have no secrets.
            for secret in environment.redactions:
                if secret:
                    text = text.replace(secret, "<redacted>")
            target = environment.artifacts / name
            temporary = target.with_name(name + ".tmp")
            temporary.write_text(text, encoding="utf-8")
            temporary.replace(target)
        except (Exception, KeyboardInterrupt) as error:
            result["status"] = "failed"
            result.setdefault("failure_stage", "artifacts")
            result.setdefault("artifact_errors", []).append({"artifact": name, "error": message(error)})

    # Independent best-effort writes: a full/broken destination must not mask all
    # other diagnostics. None of these failures may turn a failed run green.
    if metrics:
        artifact("resources.jsonl", lambda: "".join(json.dumps(row) + "\n" for row in metrics.samples))
        try:
            result["process_resources"] = {}
            for name in metrics.processes:
                values = [row["processes"][name] for row in metrics.samples if "rss_bytes" in row["processes"][name]]
                if values:
                    result["process_resources"][name] = {
                        "peak_rss_bytes": max(row["rss_bytes"] for row in values),
                        "cpu_seconds_delta": values[-1]["cpu_seconds"] - values[0]["cpu_seconds"]}
                    private = [row["private_commit_bytes"] for row in values if "private_commit_bytes" in row]
                    if private:
                        result["process_resources"][name]["peak_private_commit_bytes"] = max(private)
        except (Exception, KeyboardInterrupt) as error:
            failed("resource_summary_error", error, "artifacts")
    if workload:
        for name, attribute in (("checkpoints", "checkpoints"), ("rounds", "rounds"), ("outcomes", "outcomes")):
            artifact(name + ".json", lambda attribute=attribute: json.dumps(getattr(workload, attribute), indent=2))
        try:
            outcomes = workload.outcomes
            elapsed = sorted(outcome["duration_seconds"] for outcome in outcomes)
            result["completed_actions"] = len(outcomes)
            result["failed_actions"] = sum(outcome["status"] != "passed" for outcome in outcomes)
            if elapsed:
                result["action_duration_seconds"] = {"p50": elapsed[len(elapsed)//2],
                    "p95": elapsed[math.ceil(len(elapsed)*0.95)-1], "max": elapsed[-1]}
        except (Exception, KeyboardInterrupt) as error:
            failed("action_summary_error", error, "artifacts")
    result["elapsed_seconds"] = time.monotonic() - started
    # If this write itself fails, the returned/CLI result still records failure;
    # the absence of result.json is never treated as success.
    artifact("result.json", lambda: json.dumps(result, indent=2))
    return result, environment.artifacts


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
    parser.add_argument("--authorize-disposable-environment", action="store_true")
    args = parser.parse_args(argv)
    if not args.authorize_disposable_environment:
        parser.error("explicit disposable-environment authorization is required")
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
    result, artifacts = run(
        profile, catalog, plan, mode=args.mode, authorized=True)
    print(json.dumps({"result": result, "artifacts": str(artifacts)}, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

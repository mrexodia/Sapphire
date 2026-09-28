"""Bounded empty-server resource control. This is NOT gameplay/soak coverage.

No worker, account/character fixture or successful authentication is created.
python -m tests.e2e.run_idle_control --profile .e2e-local.json --duration 600
"""
import argparse
import json
import math
from pathlib import Path
import time

from .support.environment import Environment
from .support.metrics import ProcessMetrics


def run(profile, duration=600, *, clock=None, sleeper=None):
    if type(duration) not in (int, float) or not math.isfinite(duration) or not 10 <= duration <= 900:
        raise ValueError("empty-server duration must be a finite 10..900 seconds")
    clock, sleeper = clock or time.monotonic, sleeper or time.sleep
    environment = Environment(profile)
    metrics, sampling = None, False
    result = {"status": "failed", "kind": "empty-server-resource-control", "duration_seconds": duration,
              "note": "No successful authentication, fixtures, workers or gameplay actions; not gameplay coverage."}
    stage = "setup"
    try:
        environment.start()
        metrics = ProcessMetrics({name: process.pid for name, process in environment.processes.items()})
        stage = "sampling"
        result["started_monotonic"] = clock()
        deadline = result["started_monotonic"] + duration
        metrics.start()
        sampling = True
        while True:
            environment.check_alive()
            remaining = deadline - clock()
            if remaining <= 0:
                break
            sleeper(min(2, remaining))  # Diagnostic observation window, no gameplay assertions.
        result["finished_monotonic"] = clock()
        result["status"] = "observed"
    except (Exception, KeyboardInterrupt) as error:
        result["error"] = "interrupted" if isinstance(error, KeyboardInterrupt) else str(error)
        result["failure_stage"] = stage
    finally:
        if sampling:
            try:
                metrics.stop()
            except Exception as error:
                result.update(status="failed", sampling_error=str(error), failure_stage="sampling")
        samples = metrics.samples if metrics else []
        result["sample_count"] = len(samples)
        if result["status"] == "observed":
            times = [row["monotonic"] for row in samples]
            incomplete = (len(times) < 2 or times[0] - result["started_monotonic"] > 5
                          or result["finished_monotonic"] - times[-1] > 5
                          or any(b < a or b - a > 5 for a, b in zip(times, times[1:])))
            unavailable = any("rss_bytes" not in row["processes"].get(name, {})
                              for row in samples for name in environment.processes)
            if incomplete or unavailable:
                result.update(status="failed", error="resource sampling coverage incomplete or unavailable",
                              failure_stage="sampling")
        # Cleanup is independent of artifact writes; disk errors must not leave servers alive.
        try:
            environment.close()
        except Exception as error:
            result.update(status="failed", cleanup_error=str(error), failure_stage="cleanup")
        (environment.artifacts / "control-resources.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in samples), encoding="utf-8")
        (environment.artifacts / "control.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result, environment.artifacts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--duration", type=float, default=600)
    args = parser.parse_args(argv)
    profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    try:
        result, artifacts = run(profile, args.duration)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps({"result": result, "artifacts": str(artifacts)}, indent=2))
    return 0 if result["status"] == "observed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

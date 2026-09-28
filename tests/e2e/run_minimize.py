"""Reproduce and boundedly minimize a failed semantic workload plan.

Each candidate runs in a fresh disposable environment. Only an exact normalized
workflow/action failure with verified cleanup is accepted; passes, setup failures,
diagnostic failures and different assertions are rejected.
"""
import argparse
import json
from pathlib import Path

from .run_workload import run
from .support.catalog import load_quest_catalog
from .support.minimize import minimize_plan
from .support.workload import validate_plan


def _load_json(path, limit=1024 * 1024):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError(f"{path} must be a file no larger than {limit} bytes")
    return json.loads(path.read_text(encoding="utf-8"))


def _atomic_json(path, value):
    path = Path(path)
    if path.exists() or path.with_name(path.name + ".tmp").exists():
        raise ValueError(f"refusing to overwrite minimizer output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--plan", required=True, help="failed semantic plan.json, <=1MiB")
    parser.add_argument("--output", required=True, help="new minimized plan path; overwrite is refused")
    parser.add_argument("--max-attempts", type=int, default=32, help="isolated executions including baseline, 1..100")
    args = parser.parse_args(argv)
    try:
        profile = _load_json(args.profile)
        catalog = load_quest_catalog(profile["quest_catalog"])
        plan = validate_plan(_load_json(args.plan), catalog)
        output = Path(args.output)
        report_path = output.with_name(output.stem + "-report.json")
        if output.exists() or report_path.exists():
            raise ValueError("refusing to overwrite existing minimizer output/report")

        def evaluate(candidate):
            result, artifacts = run(profile, catalog, candidate, mode="replay")
            outcomes_path = artifacts / "outcomes.json"
            outcomes = _load_json(outcomes_path, 16 * 1024 * 1024) if outcomes_path.exists() else []
            return {"result": result, "outcomes": outcomes, "artifacts": str(artifacts)}

        minimized, report = minimize_plan(plan, catalog, evaluate, max_attempts=args.max_attempts)
        _atomic_json(output, minimized)
        _atomic_json(report_path, report)
    except (ValueError, KeyError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps({"status": "minimized", "plan": str(output), "report": str(report_path),
                      "original_actions": report["original_actions"],
                      "minimized_actions": report["minimized_actions"],
                      "one_minimal": report["one_minimal"],
                      "budget_exhausted": report["budget_exhausted"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Bounded semantic-plan reduction; never treats a different failure as equivalent."""
from copy import deepcopy
import hashlib
import json
import math

from .workload import validate_plan, validated_limits


def plan_digest(plan):
    return hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _stable_error(error):
    if not isinstance(error, str) or not error or len(error) > 64 * 1024:
        return None
    # Worker timeout snapshots contain ephemeral entity IDs, names, counters and
    # positions after this marker. The assertion identity before it is stable.
    return error.split("; state=", 1)[0][:512]


def workload_failure_signature(evaluation):
    """Return a strict workflow/action signature, or None for passes/unsafe failures."""
    if not isinstance(evaluation, dict) or set(evaluation) - {"result", "outcomes", "artifacts"}:
        raise ValueError("invalid minimizer evaluation")
    result, outcomes = evaluation.get("result"), evaluation.get("outcomes")
    if not isinstance(result, dict) or not isinstance(outcomes, list):
        raise ValueError("invalid minimizer result/outcomes")
    if (result.get("status") != "failed" or result.get("failure_stage") != "workflow"
            or result.get("runtime_removed") is not True or result.get("cleanup_error") is not None
            or result.get("artifact_errors")):
        return None
    failures = []
    for row in outcomes:
        if not isinstance(row, dict) or row.get("status") not in {"passed", "failed"}:
            raise ValueError("invalid minimizer outcome")
        if row["status"] == "failed":
            action, error = row.get("action"), _stable_error(row.get("error"))
            if not isinstance(action, dict) or error is None:
                return None
            failures.append({"action": deepcopy(action), "error": error})
    if not failures:
        return None
    failures.sort(key=lambda row: json.dumps(row, sort_keys=True, separators=(",", ":")))
    return {"failure_stage": "workflow", "failures": failures}


def _units(plan):
    actions = plan["actions"]
    if plan["mode"] == "soak":
        width = plan["bots"]
        return [[(index, deepcopy(actions[index])) for index in range(offset, offset + width)]
                for offset in range(0, len(actions), width)]
    return [[(index, deepcopy(action))] for index, action in enumerate(actions)]


def _candidate(plan, units):
    candidate = deepcopy(plan)
    candidate["actions"] = [deepcopy(action) for unit in units for _, action in unit]
    return candidate


def minimize_plan(plan, catalog, evaluate, *, max_attempts=32):
    """Delta-debug an unpaced plan using isolated evaluations and exact signatures.

    max_attempts bounds actual workload executions, including the baseline. Invalid
    semantic candidates are recorded but never executed or accepted.
    """
    if type(max_attempts) is not int or not 1 <= max_attempts <= 100:
        raise ValueError("max_attempts must be an integer from 1 to 100")
    original = validate_plan(plan, catalog)
    limits = validated_limits(original)
    if limits["round_interval"] or limits["min_active_seconds"]:
        raise ValueError("paced plans cannot be minimized without weakening sustained-work evidence")
    if not callable(evaluate):
        raise ValueError("minimizer evaluator must be callable")

    attempts = []
    evaluations = 0

    def execute(candidate, removed):
        nonlocal evaluations
        evaluation = evaluate(deepcopy(candidate))
        evaluations += 1
        signature = workload_failure_signature(evaluation)
        attempts.append({"plan_sha256": plan_digest(candidate), "actions": len(candidate["actions"]),
                         "removed_original_indices": sorted(removed), "signature": signature,
                         "artifacts": evaluation.get("artifacts")})
        return signature

    baseline_signature = execute(original, set())
    if baseline_signature is None:
        raise ValueError("baseline must fail in workflow actions with complete cleanup/artifacts")

    units = _units(original)
    all_indices = {index for unit in units for index, _ in unit}
    granularity = 2
    one_minimal = False
    while len(units) > 1 and evaluations < max_attempts:
        chunk_size = math.ceil(len(units) / granularity)
        reduced = False
        tested_single_removals = True
        for start in range(0, len(units), chunk_size):
            if evaluations >= max_attempts:
                tested_single_removals = False
                break
            complement = units[:start] + units[start + chunk_size:]
            if not complement:
                continue
            candidate = _candidate(original, complement)
            retained = {index for unit in complement for index, _ in unit}
            removed = all_indices - retained
            try:
                candidate = validate_plan(candidate, catalog)
            except ValueError as error:
                attempts.append({"plan_sha256": plan_digest(candidate), "actions": len(candidate["actions"]),
                                 "removed_original_indices": sorted(removed), "invalid": str(error)})
                continue
            signature = execute(candidate, removed)
            attempts[-1]["accepted"] = signature == baseline_signature
            if signature == baseline_signature:
                units = complement
                granularity = max(2, granularity - 1)
                reduced = True
                break
        if reduced:
            continue
        if granularity >= len(units):
            one_minimal = tested_single_removals
            break
        granularity = min(len(units), granularity * 2)

    minimized = validate_plan(_candidate(original, units), catalog)
    if len(units) == 1:
        # Removing the sole action/round would violate the validated minimum
        # action budget, so no further executable semantic candidate exists.
        one_minimal = True
    retained = [index for unit in units for index, _ in unit]
    report = {"version": 1, "status": "minimized", "baseline_signature": baseline_signature,
              "original_plan_sha256": plan_digest(original), "minimized_plan_sha256": plan_digest(minimized),
              "original_actions": len(original["actions"]), "minimized_actions": len(minimized["actions"]),
              "retained_original_indices": retained,
              "removed_original_indices": sorted(all_indices - set(retained)),
              "evaluations": evaluations, "max_attempts": max_attempts,
              "budget_exhausted": evaluations >= max_attempts and not one_minimal,
              "one_minimal": one_minimal, "attempts": attempts,
              "note": "semantic action reduction only; exact normalized action failure preserved"}
    return minimized, report

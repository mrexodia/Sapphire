"""Failure-reducer contracts; synthetic evaluations are not gameplay evidence."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from .support.minimize import minimize_plan, plan_digest, workload_failure_signature
from .support.workload import build_plan, validate_plan
from .test_policy import catalog


TRIGGER = {"kind": "walk", "bot": 0, "waypoint": 2}


def exploration_plan():
    plan = build_plan(catalog(), "explore", 7, 2, 6)
    plan["version"] = 1
    plan["actions"] = [
        {"kind": "heartbeat", "bot": 1},
        {"kind": "say", "bot": 0},
        {"kind": "walk", "bot": 0, "waypoint": 1},
        deepcopy(TRIGGER),
        {"kind": "heartbeat", "bot": 0},
        {"kind": "say", "bot": 1},
    ]
    plan["limits"] = {"duration": 30, "ramp_interval": 0}
    return validate_plan(plan, catalog())


def evaluation(plan, *, different_without_trigger=False, cleanup=True):
    has_trigger = TRIGGER in plan["actions"]
    if has_trigger or different_without_trigger:
        action = deepcopy(TRIGGER if has_trigger else plan["actions"][0])
        error = ("population-0: timeout waiting for waypoint sent; state={'ephemeral': 1}"
                 if has_trigger else "different invariant failed")
        outcomes = [{"status": "failed", "action": action, "error": error}]
        result = {"status": "failed", "failure_stage": "workflow", "runtime_removed": cleanup}
    else:
        outcomes = [{"status": "passed", "action": deepcopy(row)} for row in plan["actions"]]
        result = {"status": "passed", "runtime_removed": cleanup}
    return {"result": result, "outcomes": outcomes, "artifacts": "synthetic"}


def test_signature_removes_only_ephemeral_snapshot_and_requires_cleanup():
    first = workload_failure_signature(evaluation(exploration_plan()))
    changed = evaluation(exploration_plan())
    changed["outcomes"][0]["error"] = "population-0: timeout waiting for waypoint sent; state={'other': 2}"
    assert workload_failure_signature(changed) == first
    changed["outcomes"][0]["error"] = "population-0: another assertion; state={}"
    assert workload_failure_signature(changed) != first
    assert workload_failure_signature(evaluation(exploration_plan(), cleanup=False)) is None


def test_reducer_preserves_exact_failure_and_returns_valid_one_minimal_plan():
    original = exploration_plan()
    before = deepcopy(original)
    minimized, report = minimize_plan(original, catalog(), evaluation, max_attempts=32)
    assert original == before and validate_plan(minimized, catalog()) == minimized
    assert TRIGGER in minimized["actions"] and len(minimized["actions"]) == 2
    assert report["original_actions"] == 6 and report["minimized_actions"] == 2
    assert report["one_minimal"] and not report["budget_exhausted"]
    assert report["minimized_plan_sha256"] == plan_digest(minimized)
    assert set(report["retained_original_indices"]) | set(report["removed_original_indices"]) == set(range(6))
    assert all(row.get("accepted") is not True or row["signature"] == report["baseline_signature"]
               for row in report["attempts"])


def test_different_failure_is_never_accepted_as_equivalent():
    minimized, report = minimize_plan(exploration_plan(), catalog(),
        lambda plan: evaluation(plan, different_without_trigger=True), max_attempts=32)
    assert TRIGGER in minimized["actions"]
    assert all(not row.get("accepted") for row in report["attempts"]
               if row.get("signature") and row["signature"] != report["baseline_signature"])


def test_soak_reduction_removes_only_complete_rounds():
    plan = build_plan(catalog(), "soak", 9, 2, 6)
    plan["limits"] = {"duration": 30, "ramp_interval": 0,
                      "round_interval": 0, "min_active_seconds": 0}
    trigger = deepcopy(plan["actions"][2])
    def evaluate(candidate):
        failed = trigger in candidate["actions"]
        result = {"status": "failed" if failed else "passed", "runtime_removed": True}
        outcomes = []
        if failed:
            result["failure_stage"] = "workflow"
            outcomes = [{"status": "failed", "action": trigger, "error": "round assertion"}]
        return {"result": result, "outcomes": outcomes, "artifacts": "synthetic"}
    minimized, report = minimize_plan(plan, catalog(), evaluate, max_attempts=32)
    assert len(minimized["actions"]) == 2 and len(minimized["actions"]) % minimized["bots"] == 0
    assert [row["bot"] for row in minimized["actions"]] == [0, 1]
    assert report["one_minimal"]


def test_budget_bounds_actual_evaluations_and_does_not_overclaim_minimality():
    calls = []
    def evaluate(plan):
        calls.append(plan_digest(plan))
        return evaluation(plan)
    minimized, report = minimize_plan(exploration_plan(), catalog(), evaluate, max_attempts=2)
    assert len(calls) == report["evaluations"] == 2
    assert report["budget_exhausted"] and not report["one_minimal"]
    assert validate_plan(minimized, catalog()) == minimized


@pytest.mark.parametrize("attempts", [True, 0, 101, 1.5])
def test_invalid_attempt_budget_is_rejected(attempts):
    with pytest.raises(ValueError, match="max_attempts"):
        minimize_plan(exploration_plan(), catalog(), evaluation, max_attempts=attempts)


def test_paced_plan_is_rejected_before_evaluation():
    plan = build_plan(catalog(), "soak", 9, 2, 6)
    plan["limits"].update(round_interval=5, min_active_seconds=10, duration=30)
    called = []
    with pytest.raises(ValueError, match="Paced|paced"):
        minimize_plan(plan, catalog(), lambda candidate: called.append(candidate), max_attempts=10)
    assert not called


@pytest.mark.parametrize("kind", ["pass", "setup", "cleanup", "artifacts"])
def test_unsafe_baseline_cannot_be_minimized(kind):
    def unsafe(plan):
        result = {"status": "passed" if kind == "pass" else "failed", "runtime_removed": kind != "cleanup"}
        if kind != "pass": result["failure_stage"] = "setup" if kind == "setup" else "workflow"
        if kind == "artifacts": result["artifact_errors"] = [{"artifact": "outcomes.json"}]
        outcomes = [] if kind in {"pass", "setup"} else [{"status": "failed", "action": TRIGGER, "error": "x"}]
        return {"result": result, "outcomes": outcomes, "artifacts": "synthetic"}
    with pytest.raises(ValueError, match="baseline"):
        minimize_plan(exploration_plan(), catalog(), unsafe)


def test_cli_publishes_new_plan_and_report_without_overwrite(monkeypatch, tmp_path):
    from . import run_minimize as cli
    profile = tmp_path / "profile.json"
    plan_path = tmp_path / "failed-plan.json"
    output = tmp_path / "minimized.json"
    profile.write_text(json.dumps({"quest_catalog": "synthetic"}))
    plan_path.write_text(json.dumps(exploration_plan()))
    monkeypatch.setattr(cli, "load_quest_catalog", lambda path: catalog())
    counter = {"value": 0}
    def run(profile_data, loaded_catalog, candidate, mode, authorized):
        assert authorized is True
        counter["value"] += 1
        artifacts = tmp_path / f"attempt-{counter['value']}"
        artifacts.mkdir()
        current = evaluation(candidate)
        (artifacts / "outcomes.json").write_text(json.dumps(current["outcomes"]))
        return current["result"], artifacts
    monkeypatch.setattr(cli, "run", run)
    with pytest.raises(SystemExit):
        cli.main(["--profile", str(profile), "--plan", str(plan_path),
                  "--output", str(output)])
    assert counter["value"] == 0 and not output.exists()
    assert cli.main(["--profile", str(profile), "--plan", str(plan_path),
                     "--output", str(output), "--max-attempts", "32",
                     "--authorize-disposable-environment"]) == 0
    minimized = json.loads(output.read_text())
    report = json.loads((tmp_path / "minimized-report.json").read_text())
    assert validate_plan(minimized, catalog()) == minimized and report["one_minimal"]
    with pytest.raises(SystemExit):
        cli.main(["--profile", str(profile), "--plan", str(plan_path), "--output", str(output),
                  "--authorize-disposable-environment"])

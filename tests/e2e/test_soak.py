"""Synthetic clock/state contracts; these are not sustained gameplay evidence."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from .support.worker import WorkerError
from .support.workload import Workload, build_plan, resolve_plan, validate_plan, validated_limits
from .test_policy import catalog


def paced_plan(bots=2, steps=6, interval=10, minimum=20, duration=60):
    return resolve_plan(build_plan(catalog(), "soak", 19, bots, steps), catalog(),
                        round_interval=interval, min_active_seconds=minimum, duration=duration)


def test_v2_pacing_roundtrips_without_mutating_recorded_plan():
    plan = paced_plan()
    assert plan["version"] == 2
    assert resolve_plan(plan, catalog()) == plan
    before = deepcopy(plan)
    changed = resolve_plan(plan, catalog(), duration=90)
    assert changed["limits"]["duration"] == 90 and plan == before
    assert changed["limits"]["min_active_seconds"] == 20


def test_legacy_plans_replay_unpaced_and_require_upgrade_for_pacing():
    legacy = build_plan(catalog(), "soak", 19, 2, 6)
    legacy["version"] = 1
    legacy["limits"] = {"duration": 60, "ramp_interval": 0.25}
    assert validate_plan(legacy, catalog()) == legacy
    assert validated_limits(legacy)["round_interval"] == 0
    upgraded = resolve_plan(legacy, catalog(), round_interval=10, min_active_seconds=20)
    assert upgraded["version"] == 2 and legacy["version"] == 1
    legacy["limits"]["round_interval"] = 10
    with pytest.raises(ValueError, match="limits"):
        validate_plan(legacy, catalog())


@pytest.mark.parametrize("change", [
    {"round_interval": -1}, {"round_interval": 61}, {"round_interval": float("nan")},
    {"round_interval": float("inf")}, {"round_interval": True}, {"min_active_seconds": 21},
    {"min_active_seconds": 60}, {"duration": 20}, {"round_interval": 0}, {"ramp_interval": float("nan")},
])
def test_impossible_or_nonfinite_pacing_is_rejected(change):
    with pytest.raises(ValueError):
        resolve_plan(paced_plan(), catalog(), **change)


def test_pacing_requires_full_soak_rounds_and_rejects_unknown_metadata():
    partial = build_plan(catalog(), "soak", 1, 2, 5)
    with pytest.raises(ValueError, match="complete soak"):
        resolve_plan(partial, catalog(), round_interval=1)
    exploration = build_plan(catalog(), "explore", 1, 2, 6)
    with pytest.raises(ValueError, match="complete soak"):
        resolve_plan(exploration, catalog(), round_interval=1)
    for field in ("session", "host", "raw_packets"):
        bad = paced_plan(); bad[field] = "not-allowed"
        with pytest.raises(ValueError, match="fields"):
            validate_plan(bad, catalog())


def test_sustained_claim_cannot_use_only_heartbeats_or_noop_walks():
    plan = paced_plan()
    for action in plan["actions"]:
        action.clear(); action.update(kind="heartbeat", bot=0)
    for index, action in enumerate(plan["actions"]):
        action["bot"] = index % 2
    with pytest.raises(ValueError, match="walking and Say"):
        validate_plan(plan, catalog())
    plan = paced_plan(); plan["actions"][0]["waypoint"] = 0
    with pytest.raises(ValueError, match="change the waypoint"):
        validate_plan(plan, catalog())


class Clock:
    def __init__(self):
        self.now = 100.0
    def __call__(self):
        return self.now
    def sleep(self, seconds):
        self.now += seconds


def synthetic_workload(plan=None):
    clock = Clock()
    entities = [100, 101]
    def snapshot(name):
        return {"phase": "ready", "gm_rank": 0, "territory": 130, "between_areas": False,
                "event_id": None, "scene": None, "entity_id": entities[int(name)],
                "actors": {str(i): {} for i in entities},
                "heartbeats": {"zone": int(clock() // 3), "chat": int(clock() // 3)}}
    worker = SimpleNamespace(snapshot=snapshot)
    work = Workload(SimpleNamespace(check_alive=lambda: None), worker, catalog(), plan or paced_plan(),
                    clock=clock, sleeper=clock.sleep)
    work.entities = entities
    work.bots = [SimpleNamespace(name=str(i)) for i in range(2)]
    def execute(index, action, deadline):
        return {"index": index, "action": action, "status": "passed", "started_monotonic": clock(),
                "finished_monotonic": clock(), "duration_seconds": 0}
    work._execute = execute
    return work, clock


def test_sustained_span_is_between_actions_not_setup_or_postrun_sleep():
    work, clock = synthetic_workload()
    clock.sleep(500)  # Setup time must not count.
    result = work.run()
    assert result["activity_span_seconds"] == 20
    assert [r["first_action_monotonic"] for r in work.rounds] == [600, 610, 620]
    assert result["verified_rounds"] == 3 and result["liveness_checkpoints"] > 6
    assert clock() == 620  # No artificial idle padding after the final action.
    assert work.checkpoints[-1]["heartbeats"][0]["zone"] > work.checkpoints[0]["heartbeats"][0]["zone"]
    with pytest.raises(WorkerError, match="only once"):
        work.run()


def test_elapsed_waiting_alone_cannot_satisfy_minimum_activity():
    work, clock = synthetic_workload()
    original = work._execute
    def execute(index, action, deadline):
        row = original(index, action, deadline)
        row.update(started_monotonic=100, finished_monotonic=100)
        return row
    work._execute = execute
    with pytest.raises(WorkerError, match="minimum verified activity"):
        work.run()


def test_slow_round_does_not_trigger_catchup_bursts():
    work, clock = synthetic_workload(paced_plan(steps=8, interval=5, minimum=15))
    original = work._execute
    def execute(index, action, deadline):
        if index == 0:
            clock.sleep(10)
        return original(index, action, deadline)
    work._execute = execute
    work.run()
    for previous, current in zip(work.rounds, work.rounds[1:]):
        assert current["first_action_monotonic"] - previous["last_action_monotonic"] >= 5


@pytest.mark.parametrize("fault", ["zone", "chat", "actor", "scene", "server", "reset", "gap", "identity"])
def test_paced_idle_periods_are_actually_monitored(fault):
    work, clock = synthetic_workload(paced_plan(steps=4, interval=25, minimum=25))
    original = work.worker.snapshot
    def snapshot(name):
        state = original(name)
        if fault in {"zone", "chat"}:
            state["heartbeats"][fault] = 0
        if clock() > 100:
            if fault == "actor":
                state["actors"] = {}
            elif fault == "scene":
                state["scene"] = {"id": "unsupported"}
            elif fault == "reset":
                state["heartbeats"]["zone"] = 0
            elif fault == "identity":
                state["entity_id"] = 999
        return state
    work.worker.snapshot = snapshot
    if fault == "server":
        def alive():
            if clock() > 100:
                raise WorkerError("server exited")
        work.environment.check_alive = alive
    if fault == "gap":
        work._sleep = lambda seconds: clock.sleep(20)
    with pytest.raises(WorkerError):
        work.run()
    assert len(work.outcomes) == 2  # No second batch sent after the fault.


def test_population_claim_requires_all_distinct_actors():
    work, clock = synthetic_workload()
    work.entities[1] = work.entities[0]
    with pytest.raises(WorkerError, match="population"):
        work.run()
    assert not work.outcomes


def test_slow_monitoring_cannot_turn_budget_exhaustion_into_success():
    work, clock = synthetic_workload()
    original = work.worker.snapshot
    def slow(name):
        clock.sleep(61)
        return original(name)
    work.worker.snapshot = slow
    with pytest.raises(WorkerError, match="monitoring"):
        work.run()
    assert not work.outcomes

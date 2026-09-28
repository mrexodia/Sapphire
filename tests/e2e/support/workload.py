"""Bounded supported-action policies. Plans contain no sessions, packets, or endpoints."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import math
import random
import time

from .worker import Bot, WorkerError


KINDS = {"walk", "say", "heartbeat", "reconnect"}
DEFAULT_LIMITS = {"duration": 120, "ramp_interval": 0.25, "round_interval": 0, "min_active_seconds": 0}
MONITOR_INTERVAL = 2.0
LIVENESS_LIMIT = 15.0


def validated_limits(plan):
    supplied = plan.get("limits", {})
    allowed = set(DEFAULT_LIMITS) if plan["version"] == 2 else {"duration", "ramp_interval"}
    if not isinstance(supplied, dict) or set(supplied) - allowed:
        raise ValueError("unsupported plan limits")
    limits = {**DEFAULT_LIMITS, **supplied}
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in limits.values()):
        raise ValueError("plan limits must be finite numbers")
    duration, ramp, interval, minimum = (limits[key] for key in DEFAULT_LIMITS)
    if not 1 <= duration <= 3600 or not 0 <= ramp <= 10 or not 0 <= interval <= 60 or not 0 <= minimum < duration:
        raise ValueError("invalid duration, ramp, pacing or minimum activity limit")
    if interval or minimum:
        if plan["mode"] != "soak" or interval <= 0 or len(plan["actions"]) % plan["bots"]:
            raise ValueError("paced workloads require complete soak rounds and a positive interval")
        span = (len(plan["actions"]) // plan["bots"] - 1) * interval
        if span <= 0 or span >= duration or span < minimum:
            raise ValueError("scheduled activity span cannot satisfy the minimum within the budget")
        if minimum and any(not {"walk", "say"}.issubset(
                {a["kind"] for a in plan["actions"] if a["bot"] == bot}) for bot in range(plan["bots"])):
            raise ValueError("sustained activity requires walking and Say for every bot")
    return limits


def resolve_plan(plan, catalog, **overrides):
    result = validate_plan(plan, catalog)
    if set(overrides) - set(DEFAULT_LIMITS):
        raise ValueError("unsupported limit override")
    limits = validated_limits(result)
    limits.update({key: value for key, value in overrides.items() if value is not None})
    if result["version"] == 2 or limits["round_interval"] or limits["min_active_seconds"]:
        result["version"] = 2
        result["limits"] = limits
    else:
        result["limits"] = {key: limits[key] for key in ("duration", "ramp_interval")}
    return validate_plan(result, catalog)


def route_digest(catalog):
    return hashlib.sha256(json.dumps(catalog["route"], separators=(",", ":")).encode()).hexdigest()


def build_plan(catalog, mode, seed, bots, steps):
    if mode not in {"explore", "soak"} or not 2 <= bots <= 32 or not bots <= steps <= 1000:
        raise ValueError("workload requires explore/soak, 2..32 bots and bots..1000 total steps")
    rng = random.Random(seed)
    limit = min(8, len(catalog["route"]) - 1)
    positions = [0] * bots
    actions = []
    for index in range(steps):
        bot = rng.randrange(bots) if mode == "explore" else index % bots
        kinds = ["walk", "walk", "say", "heartbeat"] + (["reconnect"] if mode == "explore" else [])
        kind = rng.choice(kinds)
        if mode == "soak" and index < 2 * bots:
            kind = "walk" if index < bots else "say"
        action = {"kind": kind, "bot": bot}
        if kind == "walk":
            choices = [i for i in range(limit + 1) if i != positions[bot]]
            target = rng.choice(choices)
            action["waypoint"] = target
            positions[bot] = target
        actions.append(action)
    return {"version": 2, "profile": "sapphire-3.3", "mode": mode, "seed": seed,
            "bots": bots, "route_sha256": route_digest(catalog), "actions": actions, "limits": dict(DEFAULT_LIMITS)}


def validate_plan(plan, catalog):
    if set(plan) - {"version", "profile", "mode", "seed", "bots", "route_sha256", "actions", "limits"}:
        raise ValueError("unexpected plan fields")
    if type(plan.get("version")) is not int or plan["version"] not in (1, 2) or plan.get("profile") != "sapphire-3.3":
        raise ValueError("unsupported plan version/profile")
    if plan.get("mode") not in {"explore", "soak"} or type(plan.get("bots")) is not int or not 2 <= plan["bots"] <= 32:
        raise ValueError("invalid workload mode/population")
    if type(plan.get("seed")) is not int:
        raise ValueError("invalid plan seed")
    if plan.get("route_sha256") != route_digest(catalog):
        raise ValueError("replay route does not match the recorded plan")
    actions = plan.get("actions", [])
    if not isinstance(actions, list) or not plan["bots"] <= len(actions) <= 1000:
        raise ValueError("invalid action budget")
    positions = [0] * plan["bots"]
    for index, action in enumerate(actions):
        if not isinstance(action, dict) or action.get("kind") not in KINDS or type(action.get("bot")) is not int or not 0 <= action["bot"] < plan["bots"]:
            raise ValueError("unsupported action or bot index")
        expected = {"kind", "bot", "waypoint"} if action["kind"] == "walk" else {"kind", "bot"}
        if set(action) != expected:
            raise ValueError("unexpected action parameters")
        if action["kind"] == "walk" and (type(action.get("waypoint")) is not int or not 0 <= action["waypoint"] <= min(8, len(catalog["route"]) - 1)):
            raise ValueError("waypoint exceeds curated workload area")
        if action["kind"] == "walk":
            if action["waypoint"] == positions[action["bot"]]:
                raise ValueError("workload walking must change the waypoint")
            positions[action["bot"]] = action["waypoint"]
        if plan["mode"] == "soak" and (action["bot"] != index % plan["bots"] or action["kind"] == "reconnect"):
            raise ValueError("soak batches require distinct live actors; reconnect is serial only")
    validated_limits(plan)
    return deepcopy(plan)


class Workload:
    def __init__(self, environment, worker, catalog, plan, duration=None, ramp_interval=None, *, clock=None, sleeper=None):
        self.plan = resolve_plan(plan, catalog, duration=duration, ramp_interval=ramp_interval)
        limits = validated_limits(self.plan)
        self.environment, self.worker, self.catalog = environment, worker, catalog
        self.duration, self.ramp_interval = limits["duration"], limits["ramp_interval"]
        self.round_interval, self.min_active_seconds = limits["round_interval"], limits["min_active_seconds"]
        self._clock, self._sleep = clock or time.monotonic, sleeper or time.sleep
        self.checkpoints, self.rounds, self._progress = [], [], {}
        self._started, self._last_check = None, None
        self.bots, self.fixtures, self.entities = [], [], []
        self.positions = [0] * self.plan["bots"]
        self.outcomes = []
        self.coverage = set()

    def setup(self):
        for index in range(self.plan["bots"]):
            if index and self.ramp_interval:
                self._sleep(self.ramp_interval)  # Explicit population ramp, not gameplay synchronization.
            fixture = self.environment.fresh_character(self.catalog["route"][0])
            bot = Bot(self.worker, f"population-{index}")
            state = bot.login_via_lobby(fixture["auth"], fixture["name"])
            self.fixtures.append(fixture); self.bots.append(bot); self.entities.append(state["entity_id"])
        for index, entity in enumerate(self.entities):
            observer = self.bots[(index + 1) % len(self.bots)]
            self.worker.wait_state(observer.name, lambda s, key=str(entity): key in s["actors"], "population visible")

    def _check_invariants(self, deadline):
        now = self._clock()
        if now >= deadline:
            raise WorkerError("workload duration budget exhausted during monitoring")
        if self.round_interval and self._last_check is not None and now - self._last_check > LIVENESS_LIMIT:
            raise WorkerError("workload liveness monitoring coverage gap")
        self.environment.check_alive()
        if (len(self.bots) != self.plan["bots"] or len(self.entities) != self.plan["bots"]
                or len(set(self.entities)) != self.plan["bots"]):
            raise WorkerError("workload population is incomplete or identities are duplicated")
        heartbeats = []
        for index, bot in enumerate(self.bots):
            state = self.worker.snapshot(bot.name)
            if (state["phase"] != "ready" or state["gm_rank"] != 0 or state["territory"] != 130
                    or state["between_areas"] or state["entity_id"] != self.entities[index]):
                raise WorkerError(f"population invariant failed for bot {index}")
            if state["event_id"] is not None or state["scene"] is not None:
                raise WorkerError(f"unexpected event/scene for bot {index}")
            counts = state["heartbeats"]
            if any(type(counts.get(channel)) is not int or counts[channel] < 0 for channel in ("zone", "chat")):
                raise WorkerError("invalid received heartbeat counters")
            if self.round_interval:
                # Each bot is also a witness for its predecessor, throughout paced idle periods.
                if str(self.entities[(index - 1) % len(self.bots)]) not in state["actors"]:
                    raise WorkerError(f"population observer lost actor for bot {index}")
                for channel in ("zone", "chat"):
                    key = (index, channel)
                    count, seen = self._progress.get(key, (counts[channel], now))
                    if counts[channel] < count:
                        raise WorkerError("unexpected heartbeat counter reset")
                    if counts[channel] > count:
                        seen = now
                    elif now - seen > LIVENESS_LIMIT:
                        raise WorkerError(f"stale {channel} heartbeat for bot {index}")
                    self._progress[key] = (counts[channel], seen)
            heartbeats.append({channel: counts[channel] for channel in ("zone", "chat")})
        finished = self._clock()
        if finished >= deadline or (self.round_interval and finished - now > LIVENESS_LIMIT):
            raise WorkerError("workload monitoring exceeded its deadline or coverage window")
        self._last_check = now
        self.checkpoints.append({"elapsed_seconds": finished - self._started, "bots_verified": len(self.bots),
                                 "heartbeats": heartbeats})
        if len(self.checkpoints) > 7200:
            raise WorkerError("workload checkpoint budget exhausted")

    def _pace_until(self, due, deadline):
        while self._clock() < due:
            self._check_invariants(deadline)
            remaining = min(MONITOR_INTERVAL, due - self._clock(), deadline - self._clock())
            if remaining > 0:
                self._sleep(remaining)  # Deliberate workload think-time, not an outcome assertion.

    def _execute(self, index, action, deadline):
        started = self._clock()
        outcome = {"index": index, "action": action, "started_monotonic": started, "status": "failed"}
        try:
            remaining = deadline - self._clock()
            if remaining <= 0:
                raise WorkerError("workload duration budget exhausted")
            actor = action["bot"]
            bot, observer = self.bots[actor], self.bots[(actor + 1) % len(self.bots)]
            entity = self.entities[actor]
            kind = action["kind"]
            if kind == "walk":
                start, target = self.positions[actor], action["waypoint"]
                step = 1 if target >= start else -1
                route = [self.catalog["route"][i] for i in range(start + step, target + step, step)]
                if route:
                    bot.walk_route(route, speed=2, timeout=min(remaining, 30))
                self.worker.wait_state(observer.name,
                    lambda s: str(entity) in s["actors"] and math.dist(s["actors"][str(entity)]["position"], self.catalog["route"][target]) < 0.15,
                    "workload movement observed", min(10, max(0.01, deadline - self._clock())))
                self.positions[actor] = target
            elif kind == "say":
                message = f"E2E workload step {index} bot {actor}"
                bot.say(message)
                observer.expect_say(entity, message, min(10, remaining))
            elif kind == "heartbeat":
                before = self.worker.snapshot(bot.name)["heartbeats"]
                self.worker.wait_state(bot.name,
                    lambda s: all(s["heartbeats"][ch] > before[ch] for ch in ("zone", "chat")),
                    "both channels alive", min(10, remaining))
            elif kind == "reconnect":
                bot.logout(timeout=min(10, remaining))
                self.worker.wait_state(observer.name, lambda s: str(entity) not in s["actors"],
                                       "session removed before reconnect", min(30, max(0.01, deadline - self._clock())))
                bot.close()
                fixture = self.fixtures[actor]
                auth = self.environment.api("login", {"username": fixture["username"], "pass": fixture["password"]})
                state = bot.login_via_lobby(auth, fixture["name"], timeout=min(30, max(0.01, deadline - self._clock())))
                if state["entity_id"] != entity or math.dist(state["observed_position"], self.catalog["route"][self.positions[actor]]) > 0.15:
                    raise WorkerError("reconnect did not reload identity/position")
                self.worker.wait_state(observer.name, lambda s: str(entity) in s["actors"], "reconnected actor visible", min(10, remaining))
            if self._clock() > deadline:
                raise WorkerError("action exceeded the workload duration budget")
            outcome["status"] = "passed"
            return outcome
        except Exception as error:
            # No authentication data is included in workload exception messages.
            outcome["error"] = str(error)
            return outcome
        finally:
            outcome["finished_monotonic"] = self._clock()
            outcome["duration_seconds"] = outcome["finished_monotonic"] - started

    def run(self):
        if self._started is not None:
            raise WorkerError("a workload instance may run only once")
        self._started = self._clock()
        deadline, due = self._started + self.duration, self._started
        actions = self.plan["actions"]
        width = self.plan["bots"] if self.plan["mode"] == "soak" else 1
        with ThreadPoolExecutor(max_workers=width) as pool:
            for offset in range(0, len(actions), width):
                self._pace_until(due, deadline)
                self._check_invariants(deadline)
                futures = [pool.submit(self._execute, i, actions[i], deadline)
                           for i in range(offset, min(len(actions), offset + width))]
                results = [future.result() for future in futures]
                self.outcomes.extend(results)
                self.coverage.update(result["action"]["kind"] for result in results if result["status"] == "passed")
                if any(result["status"] != "passed" for result in results):
                    raise WorkerError("workload assertion failed; inspect outcomes.json")
                self.rounds.append({"offset": offset, "scheduled_monotonic": due,
                    "first_action_monotonic": min(r["started_monotonic"] for r in results),
                    "last_action_monotonic": max(r["started_monotonic"] for r in results),
                    "finished_monotonic": max(r["finished_monotonic"] for r in results)})
                # No catch-up burst after a slow round: anchor to actual action starts.
                due = self.rounds[-1]["last_action_monotonic"] + self.round_interval
                self._check_invariants(deadline)
        span = self.rounds[-1]["finished_monotonic"] - self.rounds[0]["first_action_monotonic"]
        if span < self.min_active_seconds:
            raise WorkerError("minimum verified activity duration was not reached")
        return {"passed_actions": len(self.outcomes), "action_kinds": sorted(self.coverage),
                "activity_span_seconds": span, "workflow_elapsed_seconds": self._clock() - self._started,
                "verified_rounds": len(self.rounds), "liveness_checkpoints": len(self.checkpoints),
                "minimum_activity_verified": span >= self.min_active_seconds,
                "note": "supported workflows only; seed does not reproduce server scheduling"}

    def shutdown(self):
        # Observe each session disappearing before considering teardown successful.
        for index, bot in enumerate(self.bots[:-1]):
            bot.logout()
            observer = self.bots[-1]
            entity = str(self.entities[index])
            self.worker.wait_state(observer.name, lambda s: entity not in s["actors"], "population cleanup", 30)
            bot.close()
        if self.bots:
            self.bots[-1].logout()
            self.bots[-1].close()

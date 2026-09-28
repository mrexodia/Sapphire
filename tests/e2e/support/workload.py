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
        action = {"kind": kind, "bot": bot}
        if kind == "walk":
            choices = [i for i in range(limit + 1) if i != positions[bot]]
            target = rng.choice(choices)
            action["waypoint"] = target
            positions[bot] = target
        actions.append(action)
    return {"version": 1, "profile": "sapphire-3.3", "mode": mode, "seed": seed,
            "bots": bots, "route_sha256": route_digest(catalog), "actions": actions}


def validate_plan(plan, catalog):
    if plan.get("version") != 1 or plan.get("profile") != "sapphire-3.3":
        raise ValueError("unsupported plan version/profile")
    if plan.get("mode") not in {"explore", "soak"} or type(plan.get("bots")) is not int or not 2 <= plan["bots"] <= 32:
        raise ValueError("invalid workload mode/population")
    if plan.get("route_sha256") != route_digest(catalog):
        raise ValueError("replay route does not match the recorded plan")
    actions = plan.get("actions", [])
    if not plan["bots"] <= len(actions) <= 1000:
        raise ValueError("invalid action budget")
    for index, action in enumerate(actions):
        if action.get("kind") not in KINDS or type(action.get("bot")) is not int or not 0 <= action["bot"] < plan["bots"]:
            raise ValueError("unsupported action or bot index")
        expected = {"kind", "bot", "waypoint"} if action["kind"] == "walk" else {"kind", "bot"}
        if set(action) != expected:
            raise ValueError("unexpected action parameters")
        if action["kind"] == "walk" and (type(action.get("waypoint")) is not int or not 0 <= action["waypoint"] <= min(8, len(catalog["route"]) - 1)):
            raise ValueError("waypoint exceeds curated workload area")
        if plan["mode"] == "soak" and (action["bot"] != index % plan["bots"] or action["kind"] == "reconnect"):
            raise ValueError("soak batches require distinct live actors; reconnect is serial only")
    return deepcopy(plan)


class Workload:
    def __init__(self, environment, worker, catalog, plan, duration=120, ramp_interval=0.25):
        self.plan = validate_plan(plan, catalog)
        if not 1 <= duration <= 3600 or not 0 <= ramp_interval <= 10:
            raise ValueError("duration must be 1..3600s and ramp interval 0..10s")
        self.environment, self.worker, self.catalog = environment, worker, catalog
        self.duration, self.ramp_interval = duration, ramp_interval
        self.bots, self.fixtures, self.entities = [], [], []
        self.positions = [0] * self.plan["bots"]
        self.outcomes = []
        self.coverage = set()

    def setup(self):
        for index in range(self.plan["bots"]):
            if index and self.ramp_interval:
                time.sleep(self.ramp_interval)  # Explicit population ramp, not gameplay synchronization.
            fixture = self.environment.fresh_character(self.catalog["route"][0])
            bot = Bot(self.worker, f"population-{index}")
            state = bot.login_via_lobby(fixture["auth"], fixture["name"])
            self.fixtures.append(fixture); self.bots.append(bot); self.entities.append(state["entity_id"])
        for index, entity in enumerate(self.entities):
            observer = self.bots[(index + 1) % len(self.bots)]
            self.worker.wait_state(observer.name, lambda s, key=str(entity): key in s["actors"], "population visible")

    def _check_invariants(self):
        self.environment.check_alive()
        for index, bot in enumerate(self.bots):
            state = self.worker.snapshot(bot.name)
            if state["phase"] != "ready" or state["gm_rank"] != 0 or state["territory"] != 130 or state["between_areas"]:
                raise WorkerError(f"population invariant failed for bot {index}")
            if state["event_id"] is not None or state["scene"] is not None:
                raise WorkerError(f"unexpected event/scene for bot {index}")

    def _execute(self, index, action, deadline):
        started = time.monotonic()
        outcome = {"index": index, "action": action, "started_monotonic": started, "status": "failed"}
        try:
            remaining = deadline - time.monotonic()
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
                    "workload movement observed", min(10, max(0.01, deadline - time.monotonic())))
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
                                       "session removed before reconnect", min(30, max(0.01, deadline - time.monotonic())))
                bot.close()
                fixture = self.fixtures[actor]
                auth = self.environment.api("login", {"username": fixture["username"], "pass": fixture["password"]})
                state = bot.login_via_lobby(auth, fixture["name"], timeout=min(30, max(0.01, deadline - time.monotonic())))
                if state["entity_id"] != entity or math.dist(state["observed_position"], self.catalog["route"][self.positions[actor]]) > 0.15:
                    raise WorkerError("reconnect did not reload identity/position")
                self.worker.wait_state(observer.name, lambda s: str(entity) in s["actors"], "reconnected actor visible", min(10, remaining))
            if time.monotonic() > deadline:
                raise WorkerError("action exceeded the workload duration budget")
            outcome["status"] = "passed"
            return outcome
        except Exception as error:
            # No authentication data is included in workload exception messages.
            outcome["error"] = str(error)
            return outcome
        finally:
            outcome["duration_seconds"] = time.monotonic() - started

    def run(self):
        deadline = time.monotonic() + self.duration
        actions = self.plan["actions"]
        width = self.plan["bots"] if self.plan["mode"] == "soak" else 1
        with ThreadPoolExecutor(max_workers=width) as pool:
            for offset in range(0, len(actions), width):
                self._check_invariants()
                futures = [pool.submit(self._execute, i, actions[i], deadline)
                           for i in range(offset, min(len(actions), offset + width))]
                results = [future.result() for future in futures]
                self.outcomes.extend(results)
                self.coverage.update(result["action"]["kind"] for result in results if result["status"] == "passed")
                if any(result["status"] != "passed" for result in results):
                    raise WorkerError("workload assertion failed; inspect outcomes.json")
                self._check_invariants()
        return {"passed_actions": len(self.outcomes), "action_kinds": sorted(self.coverage),
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

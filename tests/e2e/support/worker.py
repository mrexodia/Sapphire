"""Bounded JSON-lines controller. No packets or server objects exposed to scenarios."""
from __future__ import annotations

from collections import deque
from pathlib import Path
import json
import subprocess
import threading
import time

from .combat import fast_blade_ready


class WorkerError(RuntimeError):
    pass


class UnsupportedScene(WorkerError):
    pass


class Worker:
    def __init__(self, executable: Path, artifacts: Path):
        artifacts.mkdir(parents=True, exist_ok=True)
        self.artifacts = artifacts
        self._cv = threading.Condition()
        self._write_lock = threading.Lock()
        self._responses = {}
        self._pending = set()
        self._events = deque(maxlen=2048)
        self._actions = deque(maxlen=2048)
        self._stderr = deque(maxlen=128)
        self._counter = 0
        self._failure = None
        self._closed = False
        self._version = 0
        self._versions = {}
        self.process = subprocess.Popen(
            [str(executable.resolve())], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, bufsize=0,
        )
        self._threads = [threading.Thread(target=self._read, daemon=True),
                         threading.Thread(target=self._read_stderr, daemon=True)]
        for thread in self._threads:
            thread.start()
        try:
            caps = self.request("capabilities")
            if caps["control_version"] != 1 or caps["profile"] != "sapphire-3.3":
                raise WorkerError("unsupported worker version/profile")
        except BaseException:
            self.close()
            raise

    def _read(self):
        try:
            while True:
                line = self.process.stdout.readline(1024 * 1024 + 1)
                if not line:
                    raise WorkerError("worker output closed")
                if len(line) > 1024 * 1024 or not line.endswith(b"\n"):
                    raise WorkerError("worker response exceeds limit")
                message = json.loads(line)
                with self._cv:
                    if message["type"] == "response":
                        if message["id"] not in self._pending:
                            raise WorkerError("unexpected worker response id")
                        self._responses[message["id"]] = message
                    elif message["type"] == "event":
                        message["received_monotonic"] = time.monotonic()
                        self._events.append(message)
                        self._version += 1
                        self._versions[message["bot"]] = self._version
                    else:
                        raise WorkerError("unexpected worker message type")
                    self._cv.notify_all()
        except Exception as error:
            with self._cv:
                self._failure = str(error)
                self._cv.notify_all()

    def _read_stderr(self):
        while True:
            line = self.process.stderr.readline(4096)
            if not line:
                return
            with self._cv:
                self._stderr.append(line.decode("utf-8", errors="replace"))

    def request(self, method, bot=None, timeout=10, **args):
        deadline = time.monotonic() + timeout
        with self._write_lock:
            with self._cv:
                if self._closed or self._failure:
                    raise WorkerError(self._failure or "worker closed")
                self._counter += 1
                identifier = self._counter
            # Never record requests: login arguments contain an authentication session.
            data = json.dumps({"id": identifier, "method": method, "bot": bot,
                               "args": args}, allow_nan=False).encode() + b"\n"
            if len(data) > 65536:
                raise WorkerError("control request too large")
            with self._cv:
                self._pending.add(identifier)
                if method not in {"snapshot", "capabilities"}:
                    safe_args = args if method in {"walk_to", "interact", "choose_scene", "say", "discard_item", "fast_blade"} else {}
                    if method == "cross_exit":
                        safe_args = {"exit_id": args["exit"]["id"], "territory": args["exit"]["territory"]}
                    self._actions.append({"id": identifier, "method": method, "bot": bot,
                                          "args": safe_args, "monotonic": time.monotonic()})
            try:
                self.process.stdin.write(data)
                self.process.stdin.flush()
            except (OSError, ValueError) as error:
                with self._cv:
                    self._failure = "cannot write to worker"
                    self._cv.notify_all()
                raise WorkerError(self._failure) from error
        with self._cv:
            while identifier not in self._responses:
                if self._failure:
                    raise WorkerError(self._failure)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    # A timed-out operation might have succeeded. Do not retry it.
                    self._failure = f"worker deadline exceeded for {method}"
                    self._cv.notify_all()
                    raise WorkerError(self._failure)
                self._cv.wait(remaining)
            response = self._responses.pop(identifier)
            self._pending.remove(identifier)
        if not response["ok"]:
            raise WorkerError(f"{method}: {response['error']['kind']}: {response['error']['message']}")
        if method == "remove":
            with self._cv:
                self._versions.pop(bot, None)
                self._cv.notify_all()
        return response["result"]

    def snapshot(self, bot):
        return self.request("snapshot", bot)

    def wait_state(self, bot, predicate, description, timeout=30):
        deadline = time.monotonic() + timeout
        while True:
            with self._cv:
                version = self._versions.get(bot, 0)
            state = self.snapshot(bot)
            if state["phase"] == "failed":
                raise WorkerError(f"{bot}: {state.get('error', 'bot failed')}")
            if predicate(state):
                return state
            with self._cv:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise WorkerError(f"{bot}: timeout waiting for {description}; state={state}")
                changed = self._cv.wait_for(lambda: self._versions.get(bot, 0) != version or self._failure, remaining)
                if self._failure:
                    raise WorkerError(self._failure)
                if not changed:
                    raise WorkerError(f"{bot}: timeout waiting for {description}; state={state}")

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self.process.stdin.close()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        finally:
            for thread in self._threads:
                thread.join(timeout=2)
            with self._cv:
                (self.artifacts / "events.jsonl").write_text(
                    "".join(json.dumps(event) + "\n" for event in self._events), encoding="utf-8")
                (self.artifacts / "actions.jsonl").write_text(
                    "".join(json.dumps(action) + "\n" for action in self._actions), encoding="utf-8")
                (self.artifacts / "worker-stderr.log").write_text("".join(self._stderr), encoding="utf-8")
            self.process.stdout.close()
            self.process.stderr.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class Bot:
    def __init__(self, worker, name):
        self.worker, self.name = worker, name

    def login_via_lobby(self, auth, character, timeout=30):
        self.worker.request("login", self.name, host=auth["lobbyHost"], port=auth["lobbyPort"],
                            session=auth["sId"], character=character)
        return self.wait_world_ready(timeout)

    def wait_world_ready(self, timeout=30):
        state = self.worker.wait_state(self.name, lambda s: s["phase"] == "ready", "world ready", timeout)
        if state["gm_rank"] != 0:
            raise WorkerError("gameplay tests require a non-GM character")
        return state

    def walk_to(self, position, speed=2.0, timeout=60):
        self.worker.request("walk_to", self.name, position=position, speed=speed)
        return self.worker.wait_state(self.name, lambda s: not s["moving"], "waypoint sent", timeout)

    def walk_route(self, waypoints, speed=2.0, timeout=300):
        if not waypoints or len(waypoints) > 2048:
            raise WorkerError("route must contain 1..2048 waypoints")
        deadline = time.monotonic() + timeout
        for point in waypoints:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise WorkerError("route deadline exceeded")
            self.walk_to(point, speed, remaining)

    def interact(self, actor_id, event_id):
        self.worker.request("interact", self.name, actor_id=actor_id, event_id=event_id)

    def choose_dialogue(self, catalog, choice, timeout=10):
        state = self.worker.wait_state(self.name, lambda s: s["scene"] is not None, "scene", timeout)
        scene = state["scene"]
        key = f"{scene['event_id']}:{scene['scene_id']}"
        try:
            results = catalog["scenes"][key]["choices"][choice]
        except KeyError as error:
            raise UnsupportedScene(f"unsupported scene/choice: {key}/{choice}") from error
        if catalog.get("profile") != "sapphire-3.3":
            raise UnsupportedScene("scene catalog profile mismatch")
        self.worker.request("choose_scene", self.name, **scene_arguments(scene), results=results)

    def wait_fast_blade_ready(self, target, timeout=30):
        # Received TP/target plus the worker's LOCAL conservative pacing guard.
        # State notifications (including ordinary heartbeat replies) drive waits;
        # no fixed recast sleep, privileged replenishment or automatic retry.
        return self.worker.wait_state(self.name, lambda s: fast_blade_ready(s, target),
                                      "Fast Blade local guard, natural TP and estimated range", timeout)

    def fast_blade(self, target, timeout=10):
        request = self.worker.request("fast_blade", self.name, target=target)["request"]
        state = self.worker.wait_state(self.name,
            lambda s: any(e["source"] == s["entity_id"] and e["target"] == target and e["action"] == 9
                          and e["request"] == request for e in s["combat"]["effects"]),
            "received Fast Blade result", timeout)
        return next(e for e in state["combat"]["effects"] if e["source"] == state["entity_id"]
                    and e["target"] == target and e["action"] == 9 and e["request"] == request)

    def cross_exit(self, transition, timeout=30):
        self.worker.request("cross_exit", self.name, exit=transition)
        return self.worker.wait_state(self.name,
            lambda s: s["phase"] == "ready" and s["territory"] == transition["target_territory"]
                      and not s["between_areas"], "destination territory ready", timeout)

    def discard_item(self, storage, slot, expected_item, timeout=10):
        self.worker.request("discard_item", self.name, storage=storage, slot=slot, expected_item=expected_item)
        key = f"{storage}:{slot}"
        return self.worker.wait_state(self.name,
            lambda s: s["rewards"]["inventory_ready"] and key not in s["rewards"]["inventory"],
            "discarded stack absent in received inventory", timeout)

    def say(self, message):
        self.worker.request("say", self.name, message=message)

    def expect_say(self, actor, message, timeout=10):
        return self.worker.wait_state(self.name,
            lambda s: any(m["actor"] == actor and m["message"] == message for m in s["chat"]),
            "say received from expected actor", timeout)

    def wait_event_finished(self, timeout=10):
        return self.worker.wait_state(self.name, lambda s: s["event_id"] is None and s["scene"] is None,
                                      "event finished", timeout)

    def reward_snapshot(self, work_index, timeout=10):
        state = self.worker.wait_state(self.name,
            lambda s: s["rewards"]["inventory_ready"] and len(s["rewards"]["exp_by_index"]) > work_index,
            "inventory and experience snapshot", timeout)
        return reward_values(state["rewards"], work_index)

    def expect_rewards(self, expected, work_index, timeout=10):
        return self.worker.wait_state(self.name,
            lambda s: s["rewards"]["inventory_ready"] and reward_values(s["rewards"], work_index) == expected,
            "exact reward state", timeout)

    def expect_quest_active(self, quest, sequence=None, timeout=10):
        key = str(quest & 0xffff)
        return self.worker.wait_state(self.name,
            lambda s: key in s["quests"] and (sequence is None or s["quests"][key]["sequence"] == sequence),
            f"quest {quest} active at sequence {sequence}", timeout)

    def expect_quest_complete(self, quest, timeout=10):
        key = str(quest & 0xffff)
        return self.worker.wait_state(self.name, lambda s: s["complete_quests"].get(key) is True,
                                      f"quest {quest} complete", timeout)

    def logout(self, timeout=10):
        self.worker.request("logout", self.name)
        self.worker.wait_state(self.name, lambda s: s["phase"] == "logged_out", "logout acknowledgement", timeout)
        self.worker.request("close", self.name)

    def close(self):
        self.worker.request("remove", self.name)


def reward_values(state, work_index):
    if not state["inventory_ready"] or len(state["exp_by_index"]) <= work_index:
        raise WorkerError("reward baseline is not observed yet")
    items, currencies = {}, {}
    for slot in state["inventory"].values():
        if slot["storage"] not in {0, 1, 2, 3, 2000}:
            continue
        target = currencies if slot["storage"] == 2000 else items
        key = str(slot["id"])
        target[key] = target.get(key, 0) + slot["count"]
    job = str(state["class_job"])
    return {"items": items, "currencies": currencies,
            "exp": state["exp_by_class"].get(job, state["exp_by_index"][work_index]),
            "level": state["level"] if state["level"] is not None else state["level_by_index"][work_index]}


def scene_arguments(scene):
    return {key: scene[key] for key in ("event_id", "scene_id", "token")}

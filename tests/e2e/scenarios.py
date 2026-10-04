"""Watchable bot scenarios.

Each scenario drives bots against the running dev stack and returns the bots it
left logged in, so the caller decides what happens next: the pytest wrappers log
them out and assert the despawn, while `python -m tests.e2e.scenario` keeps them
standing in the world until you press Ctrl+C.

A scenario is a function `name(server, worker, log) -> list[Bot]`. `log` is a
callable taking one line of progress text.
"""
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor

from .support.catalog import load_shop_catalog
from .support.worker import Bot

SCENARIOS = {}


def scenario(fn):
    SCENARIOS[fn.__name__] = fn
    return fn


def _spawn(server, worker, name, log, **kwargs):
    fixture = server.fresh_character(**kwargs)
    bot = Bot(worker, name)
    state = bot.login_via_lobby(fixture["auth"], fixture["name"])
    log(f"{name}: {fixture['name']} is in territory {state['territory']} at "
        f"{[round(v, 1) for v in state['observed_position']]}")
    state["name"] = fixture["name"]
    return bot, state


@scenario
def say_and_walk(server, worker, log):
    """Two bots: one says a line and walks a short segment, the other confirms it saw both."""
    mover, mover_state = _spawn(server, worker, "mover", log)
    observer, _ = _spawn(server, worker, "observer", log)
    actor = str(mover_state["entity_id"])
    worker.wait_state(observer.name, lambda s: actor in s["actors"], "observer sees the mover")

    message = "Hello from the Sapphire bots"
    mover.say(message)
    observer.expect_say(mover_state["entity_id"], message)
    log("observer received the Say")

    destination = list(mover_state["observed_position"])
    destination[0] += 3.0
    mover.walk_to(destination)
    worker.wait_state(observer.name,
        lambda s: actor in s["actors"] and math.dist(s["actors"][actor]["position"], destination) < 0.1,
        "observer sees the mover arrive")
    log("observer saw the mover walk")
    mover.walk_to(mover_state["observed_position"])
    log("mover walked back")
    return [mover, observer]


@scenario
def party(server, worker, log):
    """Three bots form a party, chat in it, hand over leadership, and stay grouped."""
    leader, leader_state = _spawn(server, worker, "leader", log)
    member, member_state = _spawn(server, worker, "member", log)
    third, third_state = _spawn(server, worker, "third", log)
    for bot, state in ((member, member_state), (third, third_state)):
        actor = str(state["entity_id"])
        worker.wait_state(leader.name, lambda s, a=actor: a in s["actors"], f"leader sees {bot.name}")

    leader.invite_party(member_state["entity_id"], member_state["name"])
    member.accept_party(expected_count=2)
    log("member joined")
    leader.invite_party(third_state["entity_id"], third_state["name"])
    third.accept_party(expected_count=3)
    log("third joined")

    leader.party_chat("Party formed by the Sapphire bots")
    member.expect_party_chat(leader_state, "Party formed by the Sapphire bots")
    third.expect_party_chat(leader_state, "Party formed by the Sapphire bots")
    log("party chat delivered to both members")

    leader.change_party_leader(member_state["entity_id"], member_state["name"])
    log("leadership handed to the member")
    return [leader, member, third]


@scenario
def soak(server, worker, log, duration=600, bots=3):
    """Login churn, chat, walking and shop events in a loop while sampling the world's memory.

    Every cycle each bot logs in, says a line, walks a short segment, opens and closes the
    gil shop and logs out again; the next cycle logs the same characters back in. After each
    cycle the world process's resident memory (psutil, if installed), the login and shop
    round-trip times and any missing keepalive replies are logged and appended to soak.jsonl
    in the worker's artifacts directory. Run it for an hour with
    `python -m tests.e2e.scenario soak --duration 3600`; a world that grows without bound or
    stops answering events shows up in that file."""
    path = server.profile.get("shop_catalog")
    if not path:
        raise RuntimeError("the soak scenario needs profile.shop_catalog for its shop round trips")
    shop = load_shop_catalog(path)
    position = shop["route"][-1]
    fixtures = [server.fresh_character(position, shop["territory"]) for _ in range(bots)]
    log(f"{bots} bots created at the gil shop; starting memory "
        f"{_memory_text(server.world_memory())}")
    report = worker.artifacts / "soak.jsonl"
    started = time.monotonic()
    cycle = 0
    active = []
    while True:
        cycle += 1
        active = []
        sample = {"cycle": cycle, "elapsed_s": round(time.monotonic() - started, 1), "bots": []}
        for index, fixture in enumerate(fixtures):
            bot = Bot(worker, f"soak-{index}")
            auth = fixture["auth"] if cycle == 1 else server.relogin(fixture)
            began = time.monotonic()
            state = bot.login_via_lobby(auth, fixture["name"])
            login_s = time.monotonic() - began
            bot.say(f"soak cycle {cycle}")
            step = list(state["observed_position"])
            step[0] += 2.0
            bot.walk_to(step)
            bot.walk_to(state["observed_position"])
            began = time.monotonic()
            bot.open_gil_shop(shop["shop"]["layout_id"], shop["shop"]["event_id"])
            bot.exit_gil_shop(shop["shop"]["event_id"])
            shop_s = time.monotonic() - began
            active.append(bot)
            sample["bots"].append({"name": fixture["name"], "login_s": round(login_s, 2),
                                   "shop_s": round(shop_s, 2)})
        # Keepalives: every bot pings both channels every 3 s; a reply gap shows as sent > replies.
        time.sleep(4)
        gaps = 0
        for bot, row in zip(active, sample["bots"]):
            snapshot = worker.snapshot(bot.name)
            sent = sum(snapshot["heartbeats"].values())
            row["heartbeats_sent"] = sent
            row["heartbeat_replies"] = snapshot["heartbeat_replies"]
            gaps += max(0, sent - snapshot["heartbeat_replies"] - 2)
        sample["missing_heartbeat_replies"] = gaps
        sample["world_rss_mib"] = server.world_memory()
        with report.open("a", encoding="utf-8") as handle:
            print(json.dumps(sample), file=handle)
        slowest = max(sample["bots"], key=lambda row: row["shop_s"])
        log(f"cycle {cycle}: world {_memory_text(sample['world_rss_mib'])}, slowest login "
            f"{max(row['login_s'] for row in sample['bots']):.1f}s, slowest shop {slowest['shop_s']:.1f}s, "
            f"missing keepalive replies {gaps}")
        if time.monotonic() - started >= duration:
            break
        logout_all(active)
    return active


def _memory_text(mib):
    return "unknown (install psutil)" if mib is None else f"{mib:.0f} MiB"


def soak_report(worker):
    """The cycle samples the soak scenario wrote for this worker."""
    path = worker.artifacts / "soak.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def logout_all(bots, timeout=35):
    with ThreadPoolExecutor(max_workers=max(1, len(bots))) as pool:
        for future in [pool.submit(bot.logout) for bot in bots]:
            future.result(timeout=timeout)
    for bot in bots:
        bot.close()

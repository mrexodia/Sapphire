"""Watchable bot scenarios.

Each scenario drives bots against the running dev stack and returns the bots it
left logged in, so the caller decides what happens next: the pytest wrappers log
them out and assert the despawn, while `python -m tests.e2e.scenario` keeps them
standing in the world until you press Ctrl+C.

A scenario is a function `name(server, worker, log) -> list[Bot]`. `log` is a
callable taking one line of progress text.
"""
import math
from concurrent.futures import ThreadPoolExecutor

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


def logout_all(bots, timeout=35):
    with ThreadPoolExecutor(max_workers=max(1, len(bots))) as pool:
        for future in [pool.submit(bot.logout) for bot in bots]:
            future.result(timeout=timeout)
    for bot in bots:
        bot.close()

"""Normal-network journeys against disposable servers, never synthetic peers."""
import math
import pytest
from .support.worker import Bot

pytestmark = pytest.mark.live


def test_rejected_credentials(environment):
    environment.api("login", {"username": "absent_e2e_user", "pass": "invalid"}, expected=400)


def test_login_idle_logout(environment, live_worker):
    fixture = environment.fresh_character()
    bot = Bot(live_worker, "login")
    state = bot.login_via_lobby(fixture["auth"], fixture["name"])
    assert state["territory"] != 0
    assert str(state["entity_id"]) in state["actors"]
    counts = state["heartbeats"]
    live_worker.wait_state(bot.name,
        lambda s: all(s["heartbeats"][channel] >= counts[channel] + 2 for channel in ("zone", "chat")),
        "two rounds of keepalives on each channel", timeout=15)
    bot.logout()
    bot.close()


def test_observed_movement_and_position_persistence(environment, live_worker):
    mover_fixture = environment.fresh_character()
    observer_fixture = environment.fresh_character()
    mover, observer = Bot(live_worker, "mover"), Bot(live_worker, "observer")
    mover_state = mover.login_via_lobby(mover_fixture["auth"], mover_fixture["name"])
    observer.login_via_lobby(observer_fixture["auth"], observer_fixture["name"])
    actor = str(mover_state["entity_id"])
    live_worker.wait_state(observer.name, lambda s: actor in s["actors"], "mover spawn")
    mover.say("Sapphire E2E observer check")
    observer.expect_say(mover_state["entity_id"], "Sapphire E2E observer check")
    # Deliberately small starter-area segment, not a claim of general pathfinding.
    destination = list(mover_state["observed_position"])
    destination[0] += 1.0
    mover.walk_to(destination)
    live_worker.wait_state(observer.name,
        lambda s: actor in s["actors"] and math.dist(s["actors"][actor]["position"], destination) < 0.1,
        "movement received by observer")
    mover.logout()
    live_worker.wait_state(observer.name, lambda s: actor not in s["actors"], "mover despawn", timeout=30)
    observer.logout()
    mover.close()
    observer.close()
    environment.restart_world()
    auth = environment.api("login", {"username": mover_fixture["username"], "pass": mover_fixture["password"]})
    reconnected = Bot(live_worker, "reconnected")
    state = reconnected.login_via_lobby(auth, mover_fixture["name"])
    assert math.dist(state["observed_position"], destination) < 0.1
    reconnected.logout()
    reconnected.close()

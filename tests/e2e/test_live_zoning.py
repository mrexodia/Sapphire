"""A normal physical exit crossing, with independent observers on both sides."""
import math
from copy import deepcopy
import pytest

from .support.catalog import load_transition_catalog
from .support.worker import Bot

pytestmark = pytest.mark.live


def test_observed_exit_crossing_and_territory_persistence(environment, live_worker):
    path = environment.profile.get("transition_catalog")
    assert path, "zoning requires profile.transition_catalog generated from matching local assets"
    catalog = load_transition_catalog(path)
    transition = catalog["transition"]
    discovery = catalog["supported_discovery"]
    destination = transition["destinations"][0]
    fixture = environment.fresh_character(catalog["route"][0])
    source_fixture = environment.fresh_character(catalog["route"][0])
    target_fixture = environment.fresh_character(destination["position"], destination["territory"])
    player = Bot(live_worker, "traveler")
    source, target = Bot(live_worker, "source-observer"), Bot(live_worker, "target-observer")
    state = player.login_via_lobby(fixture["auth"], fixture["name"])
    assert state["territory"] == 130 and state["scene"] is None
    actor = str(state["entity_id"])
    source_state = source.login_via_lobby(source_fixture["auth"], source_fixture["name"])
    target_state = target.login_via_lobby(target_fixture["auth"], target_fixture["name"])
    assert target_state["territory"] == destination["territory"] and target_state["scene"] is None
    assert actor not in target_state["actors"]
    live_worker.wait_state(source.name, lambda s: actor in s["actors"], "traveler visible in source territory")
    live_worker.wait_state(player.name,
        lambda s: str(source_state["entity_id"]) in s["actors"]
                  and s["actors"][str(source_state["entity_id"])]["name"] == source_fixture["name"],
        "source observer visible by exact name")
    player.invite_party(source_state["entity_id"], source_fixture["name"])
    source.accept_party()
    live_worker.wait_state(player.name, lambda s: s["party"]["count"] == 2,
                           "traveler received source party membership")
    before = player.reward_snapshot(1)  # Gladiator fixture's observed class work index.
    # The source observer stays outside the trigger; it must not ignore its own
    # automatic-exit obligation merely to watch the traveler disappear.
    player.walk_route(catalog["route"], speed=2.0, timeout=60)
    live_worker.wait_state(source.name,
        lambda s: actor in s["actors"] and math.dist(s["actors"][actor]["position"], catalog["route"][-1]) < 0.15,
        "traveler physically reached exit")
    state = player.cross_exit(transition)
    assert state["scene"] is None and state["event_id"] is None and state["gm_rank"] == 0
    assert state["central_thanalan_discovery"] is False
    assert math.dist(state["observed_position"], destination["position"]) < 0.15
    live_worker.wait_state(source.name, lambda s: actor not in s["actors"], "traveler left source territory")
    live_worker.wait_state(target.name,
        lambda s: actor in s["actors"] and math.dist(s["actors"][actor]["position"], destination["position"]) < 0.15,
        "traveler arrived in destination territory")
    assert live_worker.snapshot(source.name)["territory"] == 130
    # UpdateParty redacts detailed fields for a remote-zone member (territory 0),
    # while retaining exact entity/name identity. Each side must receive its own
    # current territory and the other's explicitly redacted remote detail.
    expected_territories = {
        player.name: {state["entity_id"]: 141, source_state["entity_id"]: 0},
        source.name: {state["entity_id"]: 0, source_state["entity_id"]: 130}}
    for bot in (player, source):
        party_state = live_worker.wait_state(bot.name,
            lambda s: s["party"]["count"] == 2
                      and {member["entity_id"]: member["territory"] for member in s["party"]["members"]}
                          == expected_territories[bot.name],
            "cross-territory party roster update")
        assert party_state["party"]["leader_index"] == 0
    player.expect_rewards(before, 1)
    player.discover_central_thanalan(discovery)
    after_discovery = deepcopy(before)
    after_discovery["exp"] += discovery["level_one_exp_reward"]
    player.expect_rewards(after_discovery, 1)
    player.say("E2E destination chat after zoning")
    target.expect_say(state["entity_id"], "E2E destination chat after zoning")
    heartbeats = state["heartbeats"]
    live_worker.wait_state(player.name,
        lambda s: all(s["heartbeats"][channel] > heartbeats[channel] for channel in ("zone", "chat")),
        "both channels remain live after zoning")
    source.leave_party()
    live_worker.wait_state(player.name, lambda s: s["party"]["count"] == 0,
                           "traveler received cross-zone party disband")
    player.logout()
    live_worker.wait_state(target.name, lambda s: actor not in s["actors"], "destination session cleanup", 30)
    for bot in (source, target):
        bot.logout()
        bot.close()
    player.close()
    environment.restart_world()
    auth = environment.api("login", {"username": fixture["username"], "pass": fixture["password"]})
    reloaded = Bot(live_worker, "traveler-reloaded")
    state = reloaded.login_via_lobby(auth, fixture["name"])
    assert state["territory"] == destination["territory"]
    assert math.dist(state["observed_position"], destination["position"]) < 0.15
    assert state["central_thanalan_discovery"] is True
    reloaded.expect_rewards(after_discovery, 1)
    reloaded.logout()
    reloaded.close()

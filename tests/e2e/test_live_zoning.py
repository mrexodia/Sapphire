"""A normal physical exit crossing, with independent observers on both sides."""
import json
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
    discovery, second_discovery = catalog["supported_discoveries"]
    destination = transition["destinations"][0]
    fixture = environment.fresh_character(catalog["route"][0])
    source_fixture = environment.fresh_character(catalog["route"][0])
    target_fixture = environment.fresh_character(destination["position"], destination["territory"])
    discovery_observer_fixture = environment.fresh_character(second_discovery["route"][-1],
                                                              destination["territory"])
    player = Bot(live_worker, "traveler")
    source, target = Bot(live_worker, "source-observer"), Bot(live_worker, "target-observer")
    discovery_observer = Bot(live_worker, "discovery-observer")
    state = player.login_via_lobby(fixture["auth"], fixture["name"])
    assert state["territory"] == 130 and state["scene"] is None
    actor = str(state["entity_id"])
    source_state = source.login_via_lobby(source_fixture["auth"], source_fixture["name"])
    target_state = target.login_via_lobby(target_fixture["auth"], target_fixture["name"])
    discovery_observer.login_via_lobby(discovery_observer_fixture["auth"],
                                       discovery_observer_fixture["name"])
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
    target_arrival = live_worker.wait_state(target.name,
        lambda s: actor in s["actors"] and math.dist(s["actors"][actor]["position"], destination["position"]) < 0.15,
        "traveler arrived in destination territory")
    assert live_worker.snapshot(source.name)["territory"] == 130
    # UpdateParty redacts detailed fields for a remote-zone member (territory 0),
    # while retaining exact entity/name identity. Each side must receive its own
    # current territory and the other's explicitly redacted remote detail.
    expected_territories = {
        player.name: {state["entity_id"]: 141, source_state["entity_id"]: 0},
        source.name: {state["entity_id"]: 0, source_state["entity_id"]: 130}}
    party_states = {}
    for bot in (player, source):
        party_state = live_worker.wait_state(bot.name,
            lambda s: s["party"]["count"] == 2
                      and {member["entity_id"]: member["territory"] for member in s["party"]["members"]}
                          == expected_territories[bot.name],
            "cross-territory party roster update")
        assert party_state["party"]["leader_index"] == 0
        party_states[bot.name] = party_state
    assert party_states[player.name]["party"]["chat_channel"] == party_states[source.name]["party"]["chat_channel"]
    sent = source.party_chat("source to remote traveler party message")
    received = player.expect_party_chat(source_state, "source to remote traveler party message")
    assert (sent["party_id"], sent["channel"]) == (received["party_id"], received["channel"])
    sent = player.party_chat("traveler to remote source party message")
    received = source.expect_party_chat(state, "traveler to remote source party message")
    assert (sent["party_id"], sent["channel"]) == (received["party_id"], received["channel"])
    player.expect_rewards(before, 1)
    first_reply = player.discover_central_thanalan(
        discovery, target_arrival["actors"][actor]["position"])["discovery_reply"]
    after_discovery = deepcopy(before)
    after_discovery["exp"] += discovery["level_one_exp_reward"]
    player.expect_rewards(after_discovery, 1)
    player.walk_route(second_discovery["route"], speed=2.0, timeout=330)
    second_arrival = live_worker.wait_state(discovery_observer.name,
        lambda s: actor in s["actors"]
                  and math.dist(s["actors"][actor]["position"], second_discovery["route"][-1]) < 0.15,
        "traveler independently observed in second discovery box")
    second_reply = player.discover_central_thanalan(
        second_discovery, second_arrival["actors"][actor]["position"])["discovery_reply"]
    after_discovery["exp"] += second_discovery["level_one_exp_reward"]
    state = player.expect_rewards(after_discovery, 1)
    player.say("E2E destination chat after zoning")
    discovery_observer.expect_say(state["entity_id"], "E2E destination chat after zoning")
    heartbeats = state["heartbeats"]
    live_worker.wait_state(player.name,
        lambda s: all(s["heartbeats"][channel] > heartbeats[channel] for channel in ("zone", "chat")),
        "both channels remain live after zoning")
    source.leave_party()
    live_worker.wait_state(player.name, lambda s: s["party"]["count"] == 0,
                           "traveler received cross-zone party disband")
    player.logout()
    live_worker.wait_state(discovery_observer.name, lambda s: actor not in s["actors"],
                           "destination session cleanup", 30)
    for bot in (source, target, discovery_observer):
        bot.logout()
        bot.close()
    player.close()
    environment.restart_world()
    auth = environment.api("login", {"username": fixture["username"], "pass": fixture["password"]})
    reloaded = Bot(live_worker, "traveler-reloaded")
    state = reloaded.login_via_lobby(auth, fixture["name"])
    assert state["territory"] == destination["territory"]
    assert math.dist(state["observed_position"], second_discovery["route"][-1]) < 0.15
    assert state["central_thanalan_discovery"] is True
    assert state["central_thanalan_discoveries"] == [1, 3]
    reloaded.expect_rewards(after_discovery, 1)
    (environment.artifacts / "central-thanalan-discovery.json").write_text(json.dumps({
        "bindings": [{"layout_id": discovery["id"], "part_id": discovery["discovery_index"],
                      "shape": discovery["shape"], "witness_position": target_arrival["actors"][actor]["position"]},
                     {"layout_id": second_discovery["id"], "part_id": second_discovery["discovery_index"],
                      "shape": second_discovery["shape"], "witness_position": second_arrival["actors"][actor]["position"],
                      "route_points": len(second_discovery["route"]),
                      "route_length": second_discovery["route_length"]}],
        "received_replies": [first_reply, second_reply],
        "fresh_login_discoveries": state["central_thanalan_discoveries"],
        "expected_cumulative_exp": after_discovery["exp"],
        "reply_is_not_persistence_proof": True
    }, indent=2), encoding="utf-8")
    reloaded.logout()
    reloaded.close()

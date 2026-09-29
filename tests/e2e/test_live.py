"""Normal-network journeys against disposable servers, never synthetic peers."""
import math
import pytest
from .support.worker import Bot, WorkerError

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


def test_received_party_join_and_leave(environment, live_worker):
    leader_fixture = environment.fresh_character()
    member_fixture = environment.fresh_character()
    third_fixture = environment.fresh_character()
    leader, member = Bot(live_worker, "party-leader"), Bot(live_worker, "party-member")
    third = Bot(live_worker, "party-third")
    leader_state = leader.login_via_lobby(leader_fixture["auth"], leader_fixture["name"])
    member_state = member.login_via_lobby(member_fixture["auth"], member_fixture["name"])
    third_state = third.login_via_lobby(third_fixture["auth"], third_fixture["name"])
    leader_id, member_id, third_id = (leader_state["entity_id"], member_state["entity_id"],
                                      third_state["entity_id"])
    live_worker.wait_state(leader.name,
        lambda s: str(member_id) in s["actors"] and s["actors"][str(member_id)]["name"] == member_fixture["name"],
        "party target received by leader")
    live_worker.wait_state(member.name,
        lambda s: str(leader_id) in s["actors"] and s["actors"][str(leader_id)]["name"] == leader_fixture["name"],
        "party inviter received by member")
    live_worker.wait_state(leader.name,
        lambda s: str(third_id) in s["actors"] and s["actors"][str(third_id)]["name"] == third_fixture["name"],
        "third party target received by leader")
    leader.invite_party(member_id, member_fixture["name"])
    declined = member.decline_party()
    assert declined == {"result": 0, "auth_type": 1, "answer": 0, "name": leader_fixture["name"]}
    member_character_id = member_state["characters"][0]["character_id"]
    live_worker.wait_state(leader.name,
        lambda s: s["party_invite_update"] == {"character_id": member_character_id,
                                                "auth_type": 1, "result": 5,
                                                "name": member_fixture["name"]}
                  and s["party"]["count"] == 0,
        "leader received exact party decline")
    assert live_worker.snapshot(member.name)["party"]["count"] == 0
    leader.invite_party(member_id, member_fixture["name"])
    member_party = member.accept_party()
    leader_party = live_worker.wait_state(leader.name, lambda s: s["party"]["count"] == 2,
                                          "leader received two-member party state")
    expected = {(leader_id, leader_fixture["name"]), (member_id, member_fixture["name"])}
    for state in (leader_party, member_party):
        party = state["party"]
        assert party["id"] != 0 and party["chat_channel"] != 0 and party["leader_index"] == 0
        assert {(row["entity_id"], row["name"]) for row in party["members"]} == expected
    assert leader_party["party"]["chat_channel"] == member_party["party"]["chat_channel"]
    sent = leader.party_chat("leader to member party message")
    received = member.expect_party_chat(leader_party, "leader to member party message")
    assert (sent["party_id"], sent["channel"]) == (received["party_id"], received["channel"])
    sent = member.party_chat("member to leader party message")
    received = leader.expect_party_chat(member_party, "member to leader party message")
    assert (sent["party_id"], sent["channel"]) == (received["party_id"], received["channel"])

    original_party = (leader_party["party"]["id"], leader_party["party"]["chat_channel"])
    leader.invite_party(third_id, third_fixture["name"])
    third_party = third.accept_party(expected_count=3)
    expected_three = expected | {(third_id, third_fixture["name"])}
    for bot in (leader, member, third):
        joined = live_worker.wait_state(bot.name, lambda s: s["party"]["count"] == 3,
                                        "received three-member party state")
        assert (joined["party"]["id"], joined["party"]["chat_channel"]) == original_party
        assert {(row["entity_id"], row["name"]) for row in joined["party"]["members"]} == expected_three
    leader.change_party_leader(member_id, member_fixture["name"])
    for bot in (leader, member, third):
        changed = live_worker.wait_state(bot.name,
            lambda s: s["party"]["members"][s["party"]["leader_index"]]["entity_id"] == member_id,
            "received transferred party leadership")
        assert changed["party"]["members"][changed["party"]["leader_index"]]["name"] == member_fixture["name"]
    with pytest.raises(WorkerError, match="received party leadership"):
        leader.invite_party(third_id, third_fixture["name"])
    sent = third.party_chat("third member party message")
    for receiver in (leader, member):
        received = receiver.expect_party_chat(third_party, "third member party message")
        assert (sent["party_id"], sent["channel"]) == (received["party_id"], received["channel"])
    third.leave_party()
    for bot in (leader, member):
        remaining = live_worker.wait_state(bot.name, lambda s: s["party"]["count"] == 2,
                                            "received roster after third member leaves")
        assert (remaining["party"]["id"], remaining["party"]["chat_channel"]) == original_party
        assert {(row["entity_id"], row["name"]) for row in remaining["party"]["members"]} == expected
        assert remaining["party"]["members"][remaining["party"]["leader_index"]]["entity_id"] == member_id
    member.leave_party()
    live_worker.wait_state(leader.name, lambda s: s["party"]["count"] == 0,
                           "leader received party disband")
    for bot in (leader, member, third):
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

"""Normal-network journeys against the running dev stack."""
from concurrent.futures import ThreadPoolExecutor
import json
import math
import pytest
from .scenarios import logout_all, party, say_and_walk
from .support.worker import Bot, WorkerError

pytestmark = pytest.mark.live


def test_rejected_credentials(server):
    result = server.api("login", {"username": "absent_e2e_user", "pass": "invalid"}, expected=400)
    assert isinstance(result, dict) and "sId" not in result


def test_login_idle_logout(server, live_worker):
    fixture = server.fresh_character()
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


def test_received_party_join_and_leave(server, live_worker):
    leader_fixture = server.fresh_character()
    member_fixture = server.fresh_character()
    third_fixture = server.fresh_character()
    extra_fixtures = [server.fresh_character() for _ in range(5)]
    outsider_fixture = server.fresh_character()
    leader, member = Bot(live_worker, "party-leader"), Bot(live_worker, "party-member")
    third = Bot(live_worker, "party-third")
    extras = [Bot(live_worker, f"party-extra-{index}") for index in range(5)]
    outsider = Bot(live_worker, "party-outsider")
    leader_state = leader.login_via_lobby(leader_fixture["auth"], leader_fixture["name"])
    member_state = member.login_via_lobby(member_fixture["auth"], member_fixture["name"])
    third_state = third.login_via_lobby(third_fixture["auth"], third_fixture["name"])
    extra_states = [bot.login_via_lobby(fixture["auth"], fixture["name"])
                    for bot, fixture in zip(extras, extra_fixtures)]
    outsider_state = outsider.login_via_lobby(outsider_fixture["auth"], outsider_fixture["name"])
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
    leader.tell(member_id, member_fixture["name"], "leader to member exact tell")
    received_tell = member.expect_tell(leader_state, "leader to member exact tell")
    assert received_tell["party_id"] == 0
    member.tell(leader_id, leader_fixture["name"], "member to leader exact tell")
    received_tell = leader.expect_tell(member_state, "member to leader exact tell")
    assert received_tell["party_id"] == 0
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
    with pytest.raises(WorkerError, match="received leadership"):
        leader.kick_party_member(third_id, third_fixture["name"])
    member.kick_party_member(third_id, third_fixture["name"])
    live_worker.wait_state(third.name, lambda s: s["party"]["count"] == 0,
                           "kicked member received empty party state")
    for bot in (leader, member):
        remaining = live_worker.wait_state(bot.name, lambda s: s["party"]["count"] == 2,
                                            "received roster after third member leaves")
        assert (remaining["party"]["id"], remaining["party"]["chat_channel"]) == original_party
        assert {(row["entity_id"], row["name"]) for row in remaining["party"]["members"]} == expected
        assert remaining["party"]["members"][remaining["party"]["leader_index"]]["entity_id"] == member_id
    # Re-add the kicked client, then expand through the protocol's exact eight-member
    # roster limit. Every member independently receives the same identities and leader.
    expected_full = set(expected)
    expansion = [(third, third_fixture, third_state), *zip(extras, extra_fixtures, extra_states)]
    last_joined = None
    for expected_count, (bot, fixture, bot_state) in enumerate(expansion, start=3):
        member.invite_party(bot_state["entity_id"], fixture["name"])
        last_joined = bot.accept_party(expected_count=expected_count)
        expected_full.add((bot_state["entity_id"], fixture["name"]))
    party_bots = [leader, member, third, *extras]
    for bot in party_bots:
        full = live_worker.wait_state(bot.name, lambda s: s["party"]["count"] == 8,
                                      "received full eight-member party roster")
        assert (full["party"]["id"], full["party"]["chat_channel"]) == original_party
        assert {(row["entity_id"], row["name"]) for row in full["party"]["members"]} == expected_full
        assert full["party"]["members"][full["party"]["leader_index"]]["entity_id"] == member_id
    sent = extras[-1].party_chat("full roster party message")
    for receiver in party_bots[:-1]:
        received = receiver.expect_party_chat(last_joined, "full roster party message")
        assert (sent["party_id"], sent["channel"]) == (received["party_id"], received["channel"])

    # Ordinary logout retains exact offline membership, then a fresh HTTP/lobby/world
    # session restores the same member identity and party channel without a retry.
    rejoin_fixture, rejoin_before = extra_fixtures[-1], extra_states[-1]
    extras[-1].logout()
    extras[-1].close()
    for receiver in party_bots[:-1]:
        offline = live_worker.wait_state(receiver.name,
            lambda s: s["party"]["count"] == 8
                      and next(row for row in s["party"]["members"]
                               if row["entity_id"] == rejoin_before["entity_id"])["territory"] == 0,
            "received offline full-party member identity")
        assert {(row["entity_id"], row["name"]) for row in offline["party"]["members"]} == expected_full
    live_worker.wait_state(member.name,
        lambda s: str(rejoin_before["entity_id"]) not in s["actors"],
        "offline tell target despawned")
    assert member.tell_offline(rejoin_before["entity_id"], rejoin_fixture["name"],
                               "offline member exact tell") == {"name": rejoin_fixture["name"]}
    rejoin_auth = server.relogin(rejoin_fixture)
    rejoined = Bot(live_worker, "party-extra-rejoined")
    rejoined_state = rejoined.login_via_lobby(rejoin_auth, rejoin_fixture["name"])
    assert rejoined_state["entity_id"] == rejoin_before["entity_id"]
    rejoined_full = live_worker.wait_state(rejoined.name, lambda s: s["party"]["count"] == 8,
                                            "rejoined client received full party")
    assert (rejoined_full["party"]["id"], rejoined_full["party"]["chat_channel"]) == original_party
    assert {(row["entity_id"], row["name"]) for row in rejoined_full["party"]["members"]} == expected_full
    for receiver in party_bots[:-1]:
        live_worker.wait_state(receiver.name,
            lambda s: next(row for row in s["party"]["members"]
                           if row["entity_id"] == rejoined_state["entity_id"])["territory"] == 130,
            "received rejoined party member detail")
    party_bots[-1] = rejoined
    sent = rejoined.party_chat("rejoined full roster party message")
    for receiver in party_bots[:-1]:
        received = receiver.expect_party_chat(rejoined_full, "rejoined full roster party message")
        assert (sent["party_id"], sent["channel"]) == (received["party_id"], received["channel"])
    live_worker.wait_state(member.name,
        lambda s: str(outsider_state["entity_id"]) in s["actors"]
                  and s["actors"][str(outsider_state["entity_id"])]["name"] == outsider_fixture["name"],
        "ninth exact player received by full-party leader")
    with pytest.raises(WorkerError, match="party invite requires"):
        member.invite_party(outsider_state["entity_id"], outsider_fixture["name"])
    with pytest.raises(WorkerError, match="received leadership"):
        leader.disband_party()
    member.disband_party()
    for bot in party_bots:
        live_worker.wait_state(bot.name, lambda s: s["party"]["count"] == 0,
                               "received explicit full-party disband")
    # Publish every independent logout before waiting for acknowledgements. Serial
    # waits can leave later requests behind unrelated per-session server teardown.
    with ThreadPoolExecutor(max_workers=9) as pool:
        futures = [pool.submit(bot.logout) for bot in [*party_bots, outsider]]
        for future in futures:
            future.result(timeout=35)
        bot.close()


def test_observed_movement_and_position_persistence(server, live_worker):
    mover_fixture = server.fresh_character()
    observer_fixture = server.fresh_character()
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
    auth = server.relogin(mover_fixture)
    reconnected = Bot(live_worker, "reconnected")
    state = reconnected.login_via_lobby(auth, mover_fixture["name"])
    assert math.dist(state["observed_position"], destination) < 0.1
    reconnected.logout()
    reconnected.close()


# The watchable scenarios from `python -m tests.e2e.scenario`, run unattended.
@pytest.mark.parametrize("run", [say_and_walk, party], ids=lambda fn: fn.__name__)
def test_scenario(server, live_worker, run):
    bots = run(server, live_worker, lambda line: None)
    actors = [live_worker.snapshot(bot.name)["entity_id"] for bot in bots]
    logout_all(bots[:-1])
    witness = bots[-1]
    live_worker.wait_state(witness.name, lambda s: all(str(a) not in s["actors"] for a in actors[:-1]),
                           "witness sees the other bots despawn", timeout=30)
    logout_all([witness])

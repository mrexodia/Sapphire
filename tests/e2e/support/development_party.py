"""Bounded two-bot social check; never adopts or cleans up an unrelated party."""
from .development import DevelopmentError, idle_state, received_character_identity, witnessed

BOUND_METHODS = {"invite_party_bound", "accept_party_bound", "party_chat_bound", "disband_party_bound"}
EMPTY_PARTY = {"id": 0, "chat_channel": 0, "count": 0, "leader_index": 0, "members": []}


def require_bound_party_worker(worker):
    methods = worker.request("capabilities").get("methods", [])
    if not isinstance(methods, list) or not BOUND_METHODS <= set(methods):
        raise DevelopmentError("party check requires a worker with bound party-context methods")


def ungrouped(state, territory):
    return (idle_state(state, territory) and state.get("party") == EMPTY_PARTY
            and state.get("pending_party_invite") is None)


def owned_party(state, identities, territory):
    party = state.get("party", {})
    if (not idle_state(state, territory) or state.get("pending_party_invite") is not None
            or type(party.get("id")) is not int or party["id"] <= 0
            or type(party.get("chat_channel")) is not int or party["chat_channel"] <= 0
            or party.get("count") != 2 or party.get("leader_index") != 0
            or len(party.get("members", [])) != 2):
        return False
    return all({key: member.get(key) for key in ("entity_id", "character_id", "name")} == identity
               and member.get("territory") == territory
               for member, identity in zip(party["members"], identities))


def bound_request(worker, bot, method, state, **args):
    return worker.request(method, bot.name, expected_party=state["party"],
                          expected_invite=state["pending_party_invite"], **args)


def verify_two_bot_party(profile, worker, leader, member, baseline_states, run_id, timings):
    territory = profile["territory"]
    identities = [received_character_identity(state, account["character"])
                  for state, account in zip(baseline_states, profile["accounts"])]
    bots = [leader, member]
    with timings.phase("party_clean_preconditions"):
        before = [worker.snapshot(bot.name) for bot in bots]
        if not all(ungrouped(state, territory) and state.get("party_invite_result") is None
                   and state.get("party_invite_update") is None and state.get("party_invite_reply") is None
                   for state in before):
            raise DevelopmentError("party check refuses existing membership or a pending invite")
        for index, state in enumerate(before):
            peer = identities[1 - index]
            if not witnessed(state, peer["entity_id"], peer["name"]):
                raise DevelopmentError("party peer is not independently received")
    with timings.phase("party_exact_invitation"):
        bound_request(worker, leader, "invite_party_bound", before[0],
                      target=identities[1]["entity_id"], name=identities[1]["name"])
        receipt = worker.wait_state(leader.name,
            lambda s: s.get("party_invite_result") is not None,
            "party invitation result (not membership proof)", timeout=10)["party_invite_result"]
        if receipt != {"result": 0, "target": identities[1]["name"]}:
            raise DevelopmentError("unexpected party invitation receipt")
        pending = worker.wait_state(member.name,
            lambda s: s.get("pending_party_invite") is not None,
            "received party invitation", timeout=10)
        expected_invite = {"character_id": identities[0]["character_id"], "auth_type": 1,
                           "result": 1, "name": identities[0]["name"]}
        if (not idle_state(pending, territory) or pending.get("party") != EMPTY_PARTY
                or pending["pending_party_invite"] != expected_invite):
            raise DevelopmentError("party invitation does not bind the exact dedicated inviter")
        bound_request(worker, member, "accept_party_bound", pending)
    with timings.phase("party_independent_membership"):
        joined = worker.wait_state(leader.name, lambda s: owned_party(s, identities, territory),
                                   "exact owned two-bot party on leader", timeout=10)
        party = joined["party"]
        worker.wait_state(member.name,
            lambda s: owned_party(s, identities, territory) and s["party"] == party,
            "same exact owned party and channel on member", timeout=10)
    messages = []
    with timings.phase("party_bidirectional_chat"):
        for index, (sender, receiver) in enumerate(((leader, member), (member, leader))):
            current = worker.snapshot(sender.name)
            if not owned_party(current, identities, territory) or current["party"] != party:
                raise DevelopmentError("owned party changed before chat")
            message = f"Sapphire dev {run_id} party {index}"
            bound_request(worker, sender, "party_chat_bound", current, message=message)
            received = receiver.expect_party_chat(current, message)
            if (received["party_id"] != party["id"] or received["channel"] != party["chat_channel"]
                    or received["character_id"] != identities[index]["character_id"]
                    or received["name"] != identities[index]["name"]):
                raise DevelopmentError("party chat did not bind the owned channel and sender")
            messages.append(received)
    with timings.phase("party_owned_disband_and_empty_state"):
        current = [worker.snapshot(bot.name) for bot in bots]
        if not all(owned_party(state, identities, territory) and state["party"] == party for state in current):
            raise DevelopmentError("party ownership changed; refusing automatic cleanup")
        bound_request(worker, leader, "disband_party_bound", current[0])
        for bot in bots:
            worker.wait_state(bot.name, lambda s: ungrouped(s, territory),
                              "exact empty party after owned disband", timeout=10)
    return {"requested": True, "verified": True, "scope": "owned-two-bot-party-not-general-social",
            "identities": identities, "party": party, "invitation_receipt": receipt,
            "received_chat": messages, "both_empty_after_disband": True}

"""One exact dedicated-peer party decline; no foreign-invitation cleanup/retry."""
import time

from .development import DevelopmentError, idle_state, received_character_identity, witnessed
from .development_party import EMPTY_PARTY, bound_request

METHODS = {"invite_party_bound", "decline_party_bound"}
SCOPE = "dedicated-peer-decline-not-general-social"


def require_decline_worker(worker):
    methods = worker.request("capabilities").get("methods", [])
    if not isinstance(methods, list) or not METHODS <= set(methods):
        raise DevelopmentError("decline check requires bound invitation/decline methods")


def participant(state, identity, peer, territory):
    if (not idle_state(state, territory) or state.get("between_areas") is not False
            or received_character_identity(state, identity["name"]) != identity
            or state.get("party") != EMPTY_PARTY
            or type(state.get("seq")) is not int or state["seq"] < 0):
        raise DevelopmentError("decline participant identity/idle/empty-party state changed")
    matches = [key for key, actor in state.get("actors", {}).items()
               if actor.get("kind") == 1 and actor.get("name") == peer["name"]]
    if matches != [str(peer["entity_id"])] or not witnessed(state, peer["entity_id"], peer["name"]):
        raise DevelopmentError("decline peer must be one exact visible non-GM player")


def verify_party_decline(profile, worker, inviter, recipient, baseline_states, timings):
    identities = [received_character_identity(s, a["character"])
                  for s, a in zip(baseline_states, profile["accounts"])]
    if len(identities) != 2 or any(identities[0][k] == identities[1][k]
                                 for k in ("name", "entity_id", "character_id")):
        raise DevelopmentError("decline requires two distinct dedicated identities")
    territory, bots = profile["territory"], [inviter, recipient]
    with timings.phase("party_decline_exact_peer_round_trip"):
        before = [worker.snapshot(bot.name) for bot in bots]
        for i, state in enumerate(before):
            participant(state, identities[i], identities[1-i], territory)
            # No stale results, outgoing requests or arbitrary pending invitations.
            if any(state.get(key) is not None for key in
                   ("pending_party_invite", "party_invite_result", "party_invite_update", "party_invite_reply")):
                raise DevelopmentError("decline requires fresh empty invitation history")
        deadline = time.monotonic() + 10
        def wait(bot, index, predicate, description):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DevelopmentError("decline deadline exceeded; no retry")
            def checked(state):
                participant(state, identities[index], identities[1-index], territory)
                return state["seq"] > before[index]["seq"] and predicate(state)
            state = worker.wait_state(bot.name, checked, description, timeout=remaining)
            if time.monotonic() >= deadline or not checked(state):
                raise DevelopmentError("late or mismatched decline observation")
            return state
        bound_request(worker, inviter, "invite_party_bound", before[0],
                      target=identities[1]["entity_id"], name=identities[1]["name"])
        sent = wait(inviter, 0, lambda s: s.get("party_invite_result") is not None,
                    "exact invitation publication result, not decline proof")
        invitation_result = {"result": 0, "target": identities[1]["name"]}
        if sent["party_invite_result"] != invitation_result or sent.get("pending_party_invite") is not None:
            raise DevelopmentError("unexpected invitation result or incoming invitation")
        pending = wait(recipient, 1, lambda s: s.get("pending_party_invite") is not None,
                       "exact dedicated inviter received")
        expected = {"character_id": identities[0]["character_id"], "auth_type": 1,
                    "result": 1, "name": identities[0]["name"]}
        if pending["pending_party_invite"] != expected:
            raise DevelopmentError("refuse to decline another inviter")
        if time.monotonic() >= deadline:
            raise DevelopmentError("decline expired before publication")
        # Native guard rechecks both received contexts on the publication thread.
        bound_request(worker, recipient, "decline_party_bound", pending)
        reply = {"result": 0, "auth_type": 1, "answer": 0, "name": identities[0]["name"]}
        rejected = {"character_id": identities[1]["character_id"], "auth_type": 1,
                    "result": 5, "name": identities[1]["name"]}
        recipient_after = wait(recipient, 1, lambda s: s.get("party_invite_reply") == reply
                               and s.get("pending_party_invite") is None,
                               "recipient received exact decline reply")
        inviter_after = wait(inviter, 0, lambda s: s.get("party_invite_update") == rejected
                             and s.get("pending_party_invite") is None
                             and s.get("party_invite_result") == invitation_result,
                             "inviter independently received exact rejection")
    return {"requested": True, "verified": True, "scope": SCOPE,
            "identities": identities, "invitation_result": invitation_result,
            "received_reply": recipient_after["party_invite_reply"],
            "received_rejection": inviter_after["party_invite_update"],
            "baseline_sequences": [s["seq"] for s in before],
            "received_sequences": [inviter_after["seq"], recipient_after["seq"]],
            "both_empty_after_decline": True}

"""Two visible dedicated non-GM peers; no remote/offline fallback or retries."""
import secrets
import time

from .development import DevelopmentError, received_character_identity, witnessed
from .development_party import ungrouped


SCOPE = "visible-two-bot-tell-not-general-messaging"


def require_visible_tell_worker(worker):
    methods = worker.request("capabilities").get("methods", [])
    if not isinstance(methods, list) or "tell_visible" not in methods:
        raise DevelopmentError("Tell check requires the visible-only native method")


def participant(state, identity, peer, territory):
    if (not ungrouped(state, territory) or state.get("between_areas") is not False
            or type(state.get("entity_id")) is not int
            or received_character_identity(state, identity["name"]) != identity):
        raise DevelopmentError("Tell participant identity or idle nonparty state changed")
    actors = state.get("actors", {})
    matches = [key for key, row in actors.items()
               if row.get("kind") == 1 and row.get("name") == peer["name"]]
    if matches != [str(peer["entity_id"])] or not witnessed(state, peer["entity_id"], peer["name"]):
        raise DevelopmentError("Tell peer must be one exact visible non-GM player")
    seq = state.get("seq")
    if type(seq) is not int or seq < 0:
        raise DevelopmentError("Tell observation requires a received sequence")
    return seq


def fresh_tell(state, sender, message, baseline):
    expected = {"party_id": 0, "actor": sender["entity_id"], "character_id": sender["character_id"],
                "name": sender["name"], "message": message}
    rows = [row for row in state.get("tells", [])
            if all(type(row.get(key)) is int for key in ("party_id", "actor", "character_id"))
            and all(row.get(key) == value for key, value in expected.items())
            and type(row.get("token")) is int and baseline < row["token"] <= state["seq"]]
    return rows[0] if len(rows) == 1 else None


def verify_visible_tells(profile, worker, mover, witness, baseline_states, run_id, timings):
    identities = [received_character_identity(state, account["character"])
                  for state, account in zip(baseline_states, profile["accounts"])]
    if len(identities) != 2 or any(identities[0][key] == identities[1][key]
                                 for key in ("entity_id", "character_id", "name")):
        raise DevelopmentError("Tell check requires two distinct dedicated identities")
    bots, receipts = [mover, witness], []
    with timings.phase("tell_visible_bidirectional"):
        for index in (0, 1):
            other = 1 - index
            states = [worker.snapshot(bot.name) for bot in bots]
            tokens = [participant(state, identities[i], identities[1-i], profile["territory"])
                      for i, state in enumerate(states)]
            # Fresh after both baselines: old/prepopulated chat cannot prove delivery.
            message = f"Sapphire dev {run_id} tell {index} {secrets.token_hex(8)}"
            deadline = time.monotonic() + 10
            worker.request("tell_visible", bots[index].name, target=identities[other]["entity_id"],
                           name=identities[other]["name"], message=message)
            def received(state):
                participant(state, identities[other], identities[index], profile["territory"])
                return fresh_tell(state, identities[index], message, tokens[other]) is not None
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DevelopmentError("Tell delivery deadline exceeded after publication; no retry")
            state = worker.wait_state(bots[other].name, received, "fresh exact dedicated-peer Tell", timeout=remaining)
            if time.monotonic() >= deadline or not received(state):
                raise DevelopmentError("Tell delivery was late or did not bind the exact sender")
            receipts.append({"sender": identities[index], "recipient": identities[other],
                             "baseline_seq": tokens[other], "received_seq": state["seq"],
                             "received": fresh_tell(state, identities[index], message, tokens[other])})
    return {"requested": True, "verified": True, "scope": SCOPE,
            "received_tells": receipts}

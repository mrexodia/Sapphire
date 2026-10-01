"""One ordinary self-Sprint, with fresh independent received effects/TP evidence."""
import copy
import time

from .combat import sprint_ready
from .development import DevelopmentError, received_character_identity, witnessed
from .development_party import ungrouped

HISTORIES = ("effects", "starts", "hud_params")
SCOPE = "one-self-sprint-received-effect-and-zero-tp-not-speed-expiry-or-cooldown-readiness"


def require_sprint_worker(worker):
    methods = worker.request("capabilities").get("methods")
    if not isinstance(methods, list) or "sprint" not in methods:
        raise DevelopmentError("Sprint check requires the native semantic Sprint method")


def participant(state, identity, peer, territory):
    if (not ungrouped(state, territory) or state.get("between_areas") is not False
            or received_character_identity(state, identity["name"]) != identity):
        raise DevelopmentError("Sprint participant identity/idle nonparty state changed")
    matches = [key for key, row in state["actors"].items()
               if row.get("kind") == 1 and row.get("name") == peer["name"]]
    if matches != [str(peer["entity_id"])] or not witnessed(state, peer["entity_id"], peer["name"]):
        raise DevelopmentError("Sprint requires one exact visible non-GM peer")
    if type(state.get("seq")) is not int or state["seq"] < 0:
        raise DevelopmentError("Sprint requires a received sequence")


def histories(state):
    result = {}
    for key in HISTORIES:
        rows = state.get("combat", {}).get(key)
        if not isinstance(rows, list) or len(rows) > 128 or any(not isinstance(r, dict) for r in rows):
            raise DevelopmentError("invalid Sprint received history")
        result[key] = copy.deepcopy(rows)
    return result


def fresh_rows(state, baseline):
    result = histories(state)
    for key, old in baseline.items():
        if len(result[key]) == 128 or result[key][:len(old)] != old:
            raise DevelopmentError("Sprint history changed or saturated; no cache clearing/retry")
        result[key] = result[key][len(old):]
    return result


def receipt(state, baseline, entity, request, *, require_start):
    fresh = fresh_rows(state, baseline)
    effects = [row for row in fresh["effects"] if row.get("source") == entity
               and row.get("target") == entity and row.get("action") == 3
               and row.get("kind") == 1 and row.get("request") == request]
    if len(effects) > 1:
        raise DevelopmentError("ambiguous duplicate Sprint effect")
    if not effects:
        return None
    effect = effects[0]
    for key in ("source", "target", "action", "kind", "request", "result"):
        if type(effect.get(key)) is not int:
            raise DevelopmentError("malformed Sprint effect identity")
    expected = [{"type": 18, "value": 50, "flag": 128, "args": [0, 0, 30]}]
    if effect.get("effects") != expected or any(type(value) is not int for row in effect["effects"]
            for value in (row["type"], row["value"], row["flag"], *row["args"])):
        raise DevelopmentError("unexpected received Sprint status effect")
    zero = [row for row in fresh["hud_params"] if type(row.get("target")) is int
            and row["target"] == entity and type(row.get("tp")) is int and row["tp"] == 0]
    if not zero:
        return None
    starts = [row for row in fresh["starts"] if row.get("source") == entity and row.get("action") == 3]
    start = None
    if require_start:
        if len(starts) > 1:
            raise DevelopmentError("ambiguous Sprint start")
        if not starts:
            return None
        start = starts[0]
        if start != {"source": entity, "action": 3, "group": 56, "recast_centiseconds": 3000} or any(
                type(value) is not int for value in start.values()):
            raise DevelopmentError("unexpected Sprint recast metadata")
    return {"effect": copy.deepcopy(effect), "zero_tp": copy.deepcopy(zero[0]),
            "start": copy.deepcopy(start), "received_seq": state["seq"]}


def verify_sprint(profile, worker, mover, witness, initial_states, timings):
    identities = [received_character_identity(s, a["character"])
                  for s, a in zip(initial_states, profile["accounts"])]
    if len(identities) != 2 or any(identities[0][key] == identities[1][key]
                                 for key in ("name", "entity_id", "character_id")):
        raise DevelopmentError("Sprint requires two distinct dedicated identities")
    bots = [mover, witness]
    with timings.phase("sprint_natural_readiness"):
        readiness_deadline = time.monotonic() + 10
        def ready(state):
            participant(state, identities[0], identities[1], profile["territory"])
            return sprint_ready(state)
        worker.wait_state(mover.name, ready, "natural Sprint TP/pacing readiness", timeout=10)
        states = [worker.snapshot(bot.name) for bot in bots]
        for i, state in enumerate(states):
            participant(state, identities[i], identities[1-i], profile["territory"])
        if time.monotonic() >= readiness_deadline or not ready(states[0]):
            raise DevelopmentError("Sprint readiness changed or was late before publication")
        baselines = [histories(s) for s in states]
        if any(len(rows) == 128 for baseline in baselines for rows in baseline.values()):
            raise DevelopmentError("Sprint requires room in received histories")
        entity = identities[0]["entity_id"]
        if any(any(row.get("source") == entity and row.get("action") == 3
                   for row in b[key]) for b in baselines for key in ("effects", "starts")):
            raise DevelopmentError("Sprint requires fresh session action history")
    with timings.phase("sprint_independent_effect_and_tp"):
        deadline = time.monotonic() + 10
        request = worker.request("sprint", mover.name).get("request")
        if type(request) is not int or not 1 <= request <= 65535:
            raise DevelopmentError("invalid Sprint publication request identity; no retry")
        receipts = []
        for i, bot in enumerate(bots):
            def received(state):
                participant(state, identities[i], identities[1-i], profile["territory"])
                if state["seq"] <= states[i]["seq"]:
                    return False
                return receipt(state, baselines[i], entity, request, require_start=i == 0) is not None
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DevelopmentError("Sprint observation deadline exceeded; no retry")
            state = worker.wait_state(bot.name, received, "fresh exact Sprint effect and zero TP", timeout=remaining)
            if time.monotonic() >= deadline or not received(state):
                raise DevelopmentError("Sprint observation late or changed; no retry")
            receipts.append(receipt(state, baselines[i], entity, request, require_start=i == 0))
        if receipts[0]["effect"] != receipts[1]["effect"]:
            raise DevelopmentError("Sprint independently received effects disagree")
    return {"requested": True, "verified": True,
            "scope": SCOPE,
            "identities": identities, "request": request,
            "tp_before": states[0]["actors"][str(entity)]["tp"],
            "baselines": [{"seq": s["seq"], "histories": b} for s, b in zip(states, baselines)],
            "receipts": receipts}

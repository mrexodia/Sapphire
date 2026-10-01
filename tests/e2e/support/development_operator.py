"""Narrow GM fixture setup request, NEVER normal gameplay or mutation evidence.

The caller owns/authorizes the separate GM session. This helper does not log in,
look up arbitrary players, reset actors, or retry. Actual placement must be
observed independently by the normal non-GM runner.
"""
import json
import os
from pathlib import Path
import re

from .development import DevelopmentError, received_character_identity


def request_registered_placement(worker, operator, operator_name, registry, slot, artifacts, *, approved=False):
    if approved is not True:
        raise DevelopmentError("explicit administrative placement approval is required")
    if (type(slot) is not int or slot not in (0, 1) or not isinstance(registry, dict)
            or type(registry.get("version")) is not int or registry["version"] != 1
            or registry.get("purpose") != "development-bot-placement"
            or type(registry.get("territory")) is not int or registry["territory"] != 130
            or not isinstance(registry.get("approval_id"), str)
            or not re.fullmatch("[0-9a-f]{32}", registry["approval_id"])):
        raise DevelopmentError("invalid reviewed placement registry/slot")
    bindings = registry.get("bots")
    if not isinstance(bindings, list) or len(bindings) != 2:
        raise DevelopmentError("two registered bot identities required")
    for row in bindings:
        if not isinstance(row, dict) or not isinstance(row.get("name"), str) or not re.fullmatch(r"Tester [A-Z]{12}", row["name"]):
            raise DevelopmentError("registered generated bot names required")
        for key, maximum in (("entity_id", 2**32 - 1), ("character_id", 2**64 - 1)):
            if type(row.get(key)) is not int or not 0 < row[key] <= maximum:
                raise DevelopmentError("registered received bot identities required")
    if any(len({row[key] for row in bindings}) != 2 for key in ("name", "entity_id", "character_id")):
        raise DevelopmentError("ambiguous registered bot identities")
    if "development_place_registered" not in worker.request("capabilities").get("methods", []):
        raise DevelopmentError("worker lacks the distinct administrative placement capability")
    state = worker.snapshot(operator.name)
    identity = received_character_identity(state, operator_name)
    if (state.get("phase") != "ready" or type(state.get("gm_rank")) is not int
            or not 1 <= state["gm_rank"] <= 255 or state.get("territory") != 130
            or state.get("moving") is not False or state.get("between_areas") is not False
            or state.get("scene") is not None or state.get("event_id") is not None
            or state.get("party", {}).get("id") != 0 or state.get("party", {}).get("count") != 0
            or state.get("pending_party_invite") is not None
            or any(identity["character_id"] == row["character_id"] or identity["entity_id"] == row["entity_id"]
                   for row in bindings)):
        raise DevelopmentError("a separate ready, stationary, nonparty GM operator is required")
    report = {"scope": "administrative-preparation-not-gameplay", "approval_id": registry["approval_id"],
              "slot": slot, "operator": identity, "expected_target": bindings[slot],
              "status": "publication_outcome_unknown", "placement_verified": False,
              "note": "Never retry an uncertain request; require normal-client received-state evidence."}
    # Flushed exclusive intent before dispatch. Same journal path cannot be reused,
    # including after a request timeout. Not cross-host/crash-consistent exclusion.
    path = Path(artifacts) / f"placement-request-{registry['approval_id']}-{slot}.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    receipt = worker.request("development_place_registered", operator.name,
                            administrative_setup=True, approval_id=registry["approval_id"],
                            slot=slot, expected_operator=identity)
    if receipt != {"scope": "administrative-preparation-not-gameplay", "publication": "local-only", "placement_verified": False}:
        raise DevelopmentError("unexpected administrative publication receipt; do not retry")
    # Keep the pre-dispatch intent file unchanged, even on success. This receipt
    # is local publication only, not a server acknowledgement or mutation proof.
    return {**report, "status": "local_publication_only", "receipt": receipt, "intent_path": str(path)}

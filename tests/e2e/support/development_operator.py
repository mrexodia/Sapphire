"""Narrow GM fixture setup request, NEVER normal gameplay or mutation evidence.

The caller owns/authorizes the separate GM session. DevelopmentOperator provides
an explicit administrative login, not the ordinary non-GM Bot API. The placement
helper never logs in, discovers arbitrary targets or retries. Actual placement
must be observed independently by the normal non-GM runner.
"""
import json
import math
import os
from pathlib import Path
import re

from .development import DevelopmentError, received_character_identity
from .worker import Bot


def operator_identity(state, name):
    identity = received_character_identity(state, name)
    if (state.get("phase") != "ready" or type(state.get("gm_rank")) is not int
            or not 1 <= state["gm_rank"] <= 255 or state.get("territory") != 130
            or state.get("moving") is not False or state.get("between_areas") is not False
            or state.get("scene") is not None or state.get("event_id") is not None
            or state.get("party", {}).get("id") != 0 or state.get("party", {}).get("count") != 0
            or state.get("pending_party_invite") is not None):
        raise DevelopmentError("a ready, stationary, nonparty GM preparation operator is required")
    return identity


class DevelopmentOperator:
    """Separate administrative session API; does not expose gameplay actions.

    Ordinary Bot.login_via_lobby/wait_world_ready still require non-GM. Nothing
    here creates/promotes a character or changes server/DB configuration.
    """
    def __init__(self, worker, name):
        self.worker, self.name = worker, name
        self._identity = None
        self._login_started = False
        self._replies = set()

    def login_for_preparation(self, auth, character, *, approved=False, timeout=30):
        if approved is not True or self._login_started:
            raise DevelopmentError("explicit fresh preparation-operator login required")
        if "development_place_registered" not in self.worker.request("capabilities").get("methods", []):
            raise DevelopmentError("worker lacks administrative placement capability")
        self._login_started = True  # No second login after an uncertain first request.
        self.worker.request("login", self.name, host=auth["lobbyHost"], port=auth["lobbyPort"],
                            session=auth["sId"], character=character)
        state = self.worker.wait_state(self.name, lambda s: s.get("phase") == "ready",
                                       "separate GM preparation operator world ready", timeout)
        self._identity = operator_identity(state, character)
        return state

    def reply_to_viewer_challenge(self, challenge):
        if self._identity is None:
            raise DevelopmentError("preparation operator is not authenticated")
        state = self.worker.snapshot(self.name)
        identity = operator_identity(state, self._identity["name"])
        expected = {"entity_id": identity["entity_id"], "name": identity["name"], "gm_rank": state["gm_rank"]}
        run_id, stage = challenge.get("run_id"), challenge.get("stage")
        message = challenge.get("reply_in_say")
        if (identity != self._identity or challenge.get("viewer") != expected
                or challenge.get("scope") != "separate-player-presence-not-graphical-attestation"
                or not isinstance(run_id, str) or not re.fullmatch("[0-9a-f]{32}", run_id)
                or stage not in {"start", "finish"} or not isinstance(message, str)
                or not re.fullmatch(f"Sapphire viewer {run_id[:8]} {stage} [0-9a-f]{{32}}", message)
                or (run_id, stage) in self._replies or len(self._replies) >= 20):
            raise DevelopmentError("invalid/changed/consumed operator viewer challenge")
        self._replies.add((run_id, stage))  # Consume before publication; no retries.
        return self.worker.request("say", self.name, message=message)

    def logout(self):
        # Reuse only the ordinary logout/close lifecycle, never gameplay login or actions.
        Bot(self.worker, self.name).logout(wait_server_close=True)

    def close(self):
        Bot(self.worker, self.name).close()


def validate_placement_registry(registry):
    """Mirror the server's exact v2 schema before irreversible intent publication."""
    expected = {"version", "purpose", "approval_id", "provisioning_run_id", "territory",
                "position", "catalog_sha256", "bots"}
    if (not isinstance(registry, dict) or set(registry) != expected
            or type(registry.get("version")) is not int or registry["version"] != 2
            or registry.get("purpose") != "development-bot-placement"
            or type(registry.get("territory")) is not int or registry["territory"] != 130
            or not isinstance(registry.get("approval_id"), str)
            or not re.fullmatch("[0-9a-f]{32}", registry["approval_id"])
            or not isinstance(registry.get("provisioning_run_id"), str)
            or not re.fullmatch("[0-9a-f]{32}", registry["provisioning_run_id"])
            or not isinstance(registry.get("catalog_sha256"), str)
            or not re.fullmatch("[0-9a-f]{64}", registry["catalog_sha256"])):
        raise DevelopmentError("invalid reviewed placement registry schema")
    position = registry.get("position")

    def valid_coordinate(value):
        if type(value) is int:
            return abs(value) < 1000
        return type(value) is float and math.isfinite(value) and abs(value) < 1000

    if (not isinstance(position, list) or len(position) != 3
            or not all(valid_coordinate(value) for value in position)):
        raise DevelopmentError("invalid reviewed placement destination")
    bindings = registry.get("bots")
    if not isinstance(bindings, list) or len(bindings) != 2:
        raise DevelopmentError("two registered bot identities required")
    for row in bindings:
        if (not isinstance(row, dict) or set(row) != {"name", "entity_id", "character_id"}
                or not isinstance(row.get("name"), str)
                or not re.fullmatch(r"Tester [A-Z]{12}", row["name"])):
            raise DevelopmentError("registered generated bot binding required")
        for key, maximum in (("entity_id", 2**32 - 1), ("character_id", 2**64 - 1)):
            if type(row.get(key)) is not int or not 0 < row[key] <= maximum:
                raise DevelopmentError("registered received bot identities required")
    if any(len({row[key] for row in bindings}) != 2 for key in ("name", "entity_id", "character_id")):
        raise DevelopmentError("ambiguous registered bot identities")
    return bindings


def request_registered_placement(worker, operator, operator_name, registry, slot, artifacts, *, approved=False):
    if approved is not True:
        raise DevelopmentError("explicit administrative placement approval is required")
    if type(slot) is not int or slot not in (0, 1):
        raise DevelopmentError("invalid reviewed placement registry/slot")
    bindings = validate_placement_registry(registry)
    if "development_place_registered" not in worker.request("capabilities").get("methods", []):
        raise DevelopmentError("worker lacks the distinct administrative placement capability")
    state = worker.snapshot(operator.name)
    identity = operator_identity(state, operator_name)
    if any(identity["character_id"] == row["character_id"] or identity["entity_id"] == row["entity_id"]
           for row in bindings):
        raise DevelopmentError("operator must be separate from both registered targets")
    report = {"scope": "administrative-preparation-not-gameplay", "approval_id": registry["approval_id"],
              "provisioning_run_id": registry["provisioning_run_id"],
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

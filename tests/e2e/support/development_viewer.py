"""Read-only received-state confirmation of a separate named player.

A unique ordinary Say reply is required on BOTH bot clients at both endpoints.
One unchanged spawn-generation token on the persistent witness additionally rejects
any received viewer despawn/respawn between endpoints. None of this attests rendering.
"""
import json
from pathlib import Path
import time
import uuid

from .development import DevelopmentError, idle_state, position


VIEWER_SCOPE = "two-endpoint-say-and-persistent-witness-presence-not-rendering"
CONTINUITY_SCOPE = "unchanged-received-spawn-token-on-persistent-observer-not-server-session-proof"


def validate_viewer_name(name, accounts):
    if name is None:
        return
    if (not isinstance(name, str) or not 1 <= len(name) <= 31 or name != name.strip()
            or any(ord(c) < 32 or ord(c) > 126 for c in name)):
        raise DevelopmentError("viewer name must be an exact printable ASCII name of 1..31 characters")
    if name.casefold() in {account["character"].casefold() for account in accounts}:
        raise DevelopmentError("the viewer must not be either dedicated bot character")


def observe_viewer(state, name, territory, bot_actor, excluded):
    if not idle_state(state, territory) or state.get("entity_id") != bot_actor:
        return None
    matches = [(key, row) for key, row in state.get("actors", {}).items()
               if row.get("name") == name and type(row.get("kind")) is int and row["kind"] == 1]
    if len(matches) > 1:
        raise DevelopmentError("ambiguous received viewer identity")
    if not matches:
        return None
    key, row = matches[0]
    known_players, sequence = state.get("known_players"), state.get("seq")
    known = known_players.get(key) if isinstance(known_players, dict) else None
    if (not isinstance(key, str) or not key.isdecimal() or str(int(key)) != key
            or not 0 < int(key) <= 0xffffffff or int(key) in excluded
            or type(row.get("gm_rank")) is not int or not 0 <= row["gm_rank"] <= 255
            or not position(row.get("position")) or not isinstance(known, dict)
            or known.get("name") != name or known.get("spawned") is not True
            or type(sequence) is not int or sequence < 0
            or type(known.get("last_seen_token")) is not int
            or not 0 <= known["last_seen_token"] <= sequence):
        raise DevelopmentError("invalid received separate-viewer identity/state")
    return {"entity_id": int(key), "name": row["name"], "gm_rank": row["gm_rank"],
            "position": list(row["position"]), "presence_token": known["last_seen_token"]}


def viewer_checkpoint(worker, bots, bot_actors, territory, name, run_id, stage, artifacts,
                      timings, expected=None, continuity=None, *, clock=time.monotonic):
    if (stage not in {"start", "finish"}
            or (stage == "finish") != (expected is not None)
            or (stage == "finish") != (continuity is not None)):
        raise DevelopmentError("viewer checkpoints require an authored start/finish pair")
    if (not isinstance(run_id, str) or len(run_id) != 32
            or any(c not in "0123456789abcdef" for c in run_id)):
        raise DevelopmentError("viewer challenge requires a unique run identifier")
    if (len(bots) != 2 or len({bot.name for bot in bots}) != 2
            or len(bot_actors) != 2 or len(set(bot_actors)) != 2):
        raise DevelopmentError("viewer confirmation requires two distinct bot observers")
    observations, high_water = [], {}
    with timings.phase(f"viewer_{stage}_identity"):
        deadline = clock() + 10
        for bot, actor in zip(bots, bot_actors):
            remaining = deadline - clock()
            if remaining <= 0:
                raise DevelopmentError("viewer identity observation deadline exceeded")
            state = worker.wait_state(bot.name,
                lambda s, actor=actor: observe_viewer(s, name, territory, actor, bot_actors) is not None,
                "unambiguous separate viewer player spawn", timeout=remaining)
            if clock() >= deadline:
                raise DevelopmentError("viewer identity observation deadline exceeded")
            if type(state.get("seq")) is not int or state["seq"] < 0:
                raise DevelopmentError("viewer confirmation requires received event sequence numbers")
            high_water[bot.name] = state["seq"]
            observations.append(observe_viewer(state, name, territory, actor, bot_actors))
        identities = [{key: row[key] for key in ("entity_id", "name", "gm_rank")} for row in observations]
        if identities[0] != identities[1] or (expected is not None and identities[0] != expected):
            raise DevelopmentError("viewer identity differs between observers/checkpoints")
    identity = identities[0]
    presence_tokens = {bot.name: row["presence_token"] for bot, row in zip(bots, observations)}
    continuous_presence = None
    if continuity is not None:
        if (not isinstance(continuity, dict)
                or set(continuity) != {"observer", "observer_entity_id", "viewer_entity_id",
                                       "presence_token"}
                or continuity.get("observer") not in presence_tokens
                or type(continuity.get("observer_entity_id")) is not int
                or continuity["observer_entity_id"] != bot_actors[[bot.name for bot in bots].index(continuity["observer"])]
                or continuity.get("viewer_entity_id") != identity["entity_id"]
                or type(continuity.get("presence_token")) is not int
                or presence_tokens[continuity["observer"]] != continuity["presence_token"]):
            raise DevelopmentError("viewer received presence was interrupted or observer changed")
        continuous_presence = {
            "verified": True,
            "scope": CONTINUITY_SCOPE,
            **continuity,
        }
    # Generate only after both baseline snapshots, so a predictable finish reply
    # cannot be sent during the scenario and accepted as end-checkpoint liveness.
    reply = f"Sapphire viewer {run_id[:8]} {stage} {uuid.uuid4().hex}"
    with timings.phase(f"viewer_{stage}_unique_say_both_observers"):
        deadline = clock() + 60
        challenge = {"version": 1, "scope": "separate-player-presence-not-graphical-attestation",
                     "stage": stage, "run_id": run_id, "viewer": identity,
                     "reply_in_say": reply, "reply_deadline_seconds": 60,
                     "observer_sequence_baselines": high_water,
                     "note": "Send once from this viewer in ordinary Say; no runner login/control of that player."}
        with (Path(artifacts) / f"viewer-{stage}.json").open("x", encoding="utf-8") as stream:
            json.dump(challenge, stream, indent=2)
        replies = []
        for bot, actor in zip(bots, bot_actors):
            remaining = deadline - clock()
            if remaining <= 0:
                raise DevelopmentError("viewer reply observation deadline exceeded")
            def replied(state, actor=actor, observer=bot.name):
                row = observe_viewer(state, name, territory, actor, bot_actors)
                return (row is not None
                        and {key: row[key] for key in ("entity_id", "name", "gm_rank")} == identity
                        and row["presence_token"] == presence_tokens[observer]
                        and (continuity is None
                             or row["presence_token"] == continuity["presence_token"])
                        and type(state.get("seq")) is int
                        and any(message.get("kind") == 10 and type(message.get("actor")) is int
                                and message["actor"] == identity["entity_id"]
                                and type(message.get("token")) is int
                                and high_water[observer] < message["token"] <= state["seq"]
                                and message.get("message") == reply for message in state.get("chat", [])))
            state = worker.wait_state(bot.name, replied,
                "unique viewer Say received with matching visible identity", timeout=remaining)
            if clock() >= deadline:
                raise DevelopmentError("viewer reply observation deadline exceeded")
            replies.append({"observer": bot.name, "viewer": observe_viewer(state, name, territory, actor, bot_actors),
                            "message": reply, "received_sequence": state["seq"],
                            "baseline_sequence": high_water[bot.name]})
    result = {"verified": True, "stage": stage, "identity": identity,
              "presence_tokens": presence_tokens,
              "initial_observations": observations, "received_replies": replies}
    if continuous_presence is not None:
        result["continuous_presence"] = continuous_presence
    return result

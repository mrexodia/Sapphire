"""One explicitly requested fresh-login check, never recovery after a failure."""
import math

from .development import (DevelopmentError, authenticate, idle_state,
                          received_character_identity, witnessed)
from .worker import Bot


def verify_position_reconnect(profile, worker, mover, witness, baseline_state,
                              expected_position, run_id, timings, login=authenticate):
    account = profile["accounts"][0]
    identity = received_character_identity(baseline_state, account["character"])
    actor, name = identity["entity_id"], identity["name"]
    territory = profile["territory"]
    with timings.phase("reconnect_before_logout_observation"):
        before = worker.wait_state(witness.name,
            lambda s: idle_state(s, territory) and witnessed(s, actor, name, expected_position),
            "mover endpoint independently received before reconnect", timeout=10)
        received_before = list(before["actors"][str(actor)]["position"])
    with timings.phase("reconnect_logout_and_despawn"):
        # Server close is required, not merely its logout acknowledgement. Keep
        # the witness online and require absence before creating a new client.
        mover.logout(wait_server_close=True)
        worker.wait_state(witness.name,
            lambda s: idle_state(s, territory) and str(actor) not in s["actors"],
            "old mover despawn before fresh authentication", timeout=10)
        mover.close()
    with timings.phase("reconnect_fresh_http_login"):
        auth = login(profile, account)
    reloaded = Bot(worker, "mover-reconnected")
    with timings.phase("reconnect_lobby_world_identity_position"):
        state = reloaded.login_via_lobby(auth, name)
        after_identity = received_character_identity(state, name)
        if after_identity != identity:
            raise DevelopmentError("reconnect selected a different character identity")
        if (not idle_state(state, territory)
                or math.dist(state["observed_position"], expected_position) > 0.15
                or math.dist(state["observed_position"], received_before) > 0.15):
            raise DevelopmentError("fresh login did not receive the independently observed endpoint")
    with timings.phase("reconnect_independent_respawn_and_say"):
        after = worker.wait_state(witness.name,
            lambda s: idle_state(s, territory) and witnessed(s, actor, name, expected_position)
            and witnessed(s, actor, name, received_before),
            "same mover independently respawned at the saved endpoint", timeout=10)
        # A unique post-login message supplies fresh semantic liveness rather
        # than treating a previously cached actor row as successful reconnect.
        message = f"Sapphire dev {run_id[:8]} fresh login verified"
        reloaded.say(message)
        witness.expect_say(actor, message)
    evidence = {"requested": True, "verified": True,
                "scope": "fresh-login-position-not-world-restart",
                "identity_before": identity, "identity_after": after_identity,
                "territory": territory, "expected_position": list(expected_position),
                "witness_before": received_before,
                "received_after": list(state["observed_position"]),
                "witness_after": list(after["actors"][str(actor)]["position"]),
                "old_server_close_observed": True, "independent_despawn_observed": True,
                "post_login_say_observed": True, "world_restart_performed": False}
    return reloaded, evidence

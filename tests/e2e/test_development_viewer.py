"""Synthetic viewer-presence contracts; no graphical client or live server."""
import copy
import json
from types import SimpleNamespace

import pytest

from . import run_development
from .support.development import DevelopmentError, Timings
from .support.development_viewer import validate_viewer_name, viewer_checkpoint
from .test_development import FakeWorker, execute, profile


NAME = "Separate Viewer"
RUN = "a" * 32


class ViewerWorker(FakeWorker):
    def __init__(self, artifacts):
        super().__init__()
        self.artifacts = artifacts
        self.deliver = {"mover", "witness"}
        self.reply_kind, self.reply_actor, self.reply_text = 10, 3, None
        self.token_override = None
        self.waits = []
        for state in self.states.values():
            state["seq"] = 10
            state["actors"]["3"] = {"kind": 1, "name": NAME, "gm_rank": 90, "position": [1, 2, 3]}

    def wait_state(self, bot, predicate, description, timeout=30):
        self.waits.append(timeout)
        if description.startswith("unique viewer Say") and bot in self.deliver:
            stage = "finish" if (self.artifacts / "viewer-finish.json").exists() else "start"
            challenge = json.loads((self.artifacts / f"viewer-{stage}.json").read_text())
            self.states[bot]["seq"] += 1
            self.states[bot]["chat"].append({"kind": self.reply_kind, "actor": self.reply_actor,
                "message": self.reply_text or challenge["reply_in_say"],
                "token": self.states[bot]["seq"] if self.token_override is None else self.token_override})
        return super().wait_state(bot, predicate, description, timeout)


def checkpoint(worker, path, stage="start", expected=None, **kwargs):
    bots = [SimpleNamespace(name=name) for name in ("mover", "witness")]
    return viewer_checkpoint(worker, bots, [1, 2], 130, NAME, RUN, stage, path, Timings(), expected, **kwargs)


def test_two_observers_two_challenges_and_read_only_viewer(tmp_path):
    worker = ViewerWorker(tmp_path)
    start = checkpoint(worker, tmp_path)
    # The human is allowed to walk while watching. Positions are recorded, not
    # constrained or restored; no continuous presence claim is made.
    for state in worker.states.values(): state["actors"]["3"]["position"] = [4, 5, 6]
    finish = checkpoint(worker, tmp_path, "finish", start["identity"])
    assert start["verified"] and finish["verified"]
    assert start["identity"] == finish["identity"] == {"entity_id": 3, "name": NAME, "gm_rank": 90}
    assert start["received_replies"][0]["message"] != finish["received_replies"][0]["message"]
    assert len(start["received_replies"]) == len(finish["received_replies"]) == 2
    assert finish["received_replies"][0]["viewer"]["position"] == [4, 5, 6]
    assert not worker.commands and all(0 < timeout <= 60 for timeout in worker.waits)


@pytest.mark.parametrize("field,value", [("reply_kind", 11), ("reply_actor", 4),
    ("reply_actor", True), ("reply_text", "stale message"), ("deliver", {"mover"}), ("deliver", set())])
def test_wrong_channel_identity_stale_or_one_sided_reply_fails(tmp_path, field, value):
    worker = ViewerWorker(tmp_path)
    setattr(worker, field, value)
    with pytest.raises(DevelopmentError): checkpoint(worker, tmp_path)
    assert not worker.commands


@pytest.mark.parametrize("mutation", ["absent", "npc", "ambiguous", "different_observer_id", "bad_position",
                                    "gm_mismatch", "observer_changed", "viewer_is_bot", "noncanonical_id"])
def test_identity_fail_closed_before_challenge(tmp_path, mutation):
    worker = ViewerWorker(tmp_path)
    state = worker.states["mover"]
    if mutation == "absent": state["actors"].pop("3")
    if mutation == "npc": state["actors"]["3"]["kind"] = 3
    if mutation == "ambiguous": state["actors"]["4"] = copy.deepcopy(state["actors"]["3"])
    if mutation == "different_observer_id": state["actors"]["4"] = state["actors"].pop("3")
    if mutation == "bad_position": state["actors"]["3"]["position"][0] = float("nan")
    if mutation == "gm_mismatch": state["actors"]["3"]["gm_rank"] = 0
    if mutation == "observer_changed": state["entity_id"] = 99
    if mutation == "viewer_is_bot": state["actors"]["1"] = state["actors"].pop("3")
    if mutation == "noncanonical_id": state["actors"]["03"] = state["actors"].pop("3")
    with pytest.raises(DevelopmentError): checkpoint(worker, tmp_path)
    assert not (tmp_path / "viewer-start.json").exists() and not worker.commands


def test_viewer_identity_change_at_finish_fails_before_second_challenge(tmp_path):
    worker = ViewerWorker(tmp_path)
    start = checkpoint(worker, tmp_path)
    for state in worker.states.values(): state["actors"]["4"] = state["actors"].pop("3")
    with pytest.raises(DevelopmentError): checkpoint(worker, tmp_path, "finish", start["identity"])
    assert not (tmp_path / "viewer-finish.json").exists()


def test_finish_cannot_reuse_start_reply(tmp_path):
    worker = ViewerWorker(tmp_path)
    start = checkpoint(worker, tmp_path)
    worker.reply_text = start["received_replies"][0]["message"]
    with pytest.raises(DevelopmentError): checkpoint(worker, tmp_path, "finish", start["identity"])


@pytest.mark.parametrize("token", [0, 10, 999, True])
def test_matching_text_with_stale_or_invalid_event_token_is_rejected(tmp_path, token):
    worker = ViewerWorker(tmp_path)
    worker.token_override = token
    with pytest.raises(DevelopmentError): checkpoint(worker, tmp_path)


def test_late_successful_wait_is_not_accepted(tmp_path):
    worker = ViewerWorker(tmp_path)
    ticks = iter([0, 0, 0, 1, 1, 2, 2, 63])
    with pytest.raises(DevelopmentError, match="reply observation deadline"):
        checkpoint(worker, tmp_path, clock=lambda: next(ticks))


def test_reply_deadline_is_shared_not_sixty_seconds_per_observer(tmp_path):
    worker = ViewerWorker(tmp_path)
    ticks = iter([0, 0, 0, 1, 1, 2, 2, 2, 63])
    with pytest.raises(DevelopmentError, match="reply observation deadline"):
        checkpoint(worker, tmp_path, clock=lambda: next(ticks))
    assert not worker.commands


@pytest.mark.parametrize("name", ["", " name", "name ", "x" * 32, "bad\nname", "bad\x7fname", "é", True, "bot mover"])
def test_invalid_or_bot_viewer_name_before_auth_or_artifacts(profile, tmp_path, name):
    with pytest.raises(DevelopmentError):
        run_development.run(profile, tmp_path / "run", confirmed=True, viewer_name=name,
                            login=lambda *_: pytest.fail("authentication attempted"))
    assert not (tmp_path / "run").exists()


def test_runner_records_viewer_pair_without_login_or_mutation(profile, tmp_path):
    fake = ViewerWorker(tmp_path / "run")
    report, fake = execute(profile, tmp_path, fake, viewer_name=NAME)
    assert report["status"] == "passed" and report["viewer_verification"]["verified"]
    assert report["viewer_verification"]["viewer_login_or_control_performed"] is False
    assert fake.commands.count("login") == 2 and fake.commands.count("say") == 2
    assert not report["lease_retained"]


def test_unconfirmed_viewer_keeps_leases_and_does_not_start_gameplay(profile, tmp_path):
    fake = ViewerWorker(tmp_path / "run")
    fake.deliver = set()
    report, fake = execute(profile, tmp_path, fake, viewer_name=NAME)
    assert report["status"] == "failed" and report["lease_retained"] and fake.closed
    assert report["failure_stage"] == "viewer_start_unique_say_both_observers"
    assert "say" not in fake.commands and not report["viewer_verification"]["verified"]


def test_end_confirmation_follows_reconnected_bot_instance(profile, tmp_path, monkeypatch):
    fake = ViewerWorker(tmp_path / "run")
    calls = []
    def check(worker, bots, *args, **kwargs):
        calls.append([bot.name for bot in bots])
        return {"verified": True, "identity": {"entity_id": 3, "name": NAME, "gm_rank": 90}}
    class Replacement:
        name = "mover-reconnected"
        def logout(self, **kwargs): fake.states["witness"]["actors"].pop("1")
        def close(self): pass
    monkeypatch.setattr(run_development, "viewer_checkpoint", check)
    monkeypatch.setattr(run_development, "verify_position_reconnect", lambda *a: (Replacement(), {"verified": True}))
    report, _ = execute(profile, tmp_path, fake, viewer_name=NAME, verify_reconnect=True)
    assert report["status"] == "passed"
    assert calls == [["mover", "witness"], ["mover-reconnected", "witness"]]

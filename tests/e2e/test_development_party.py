"""Synthetic shared-party lifecycle and foreign-state rejection contracts."""
import copy

import pytest

from . import run_development
from .support.development import DevelopmentError
from .support.development_party import BOUND_METHODS, EMPTY_PARTY
from .test_development import profile
from .test_development_reconnect import ReconnectWorker


class PartyWorker(ReconnectWorker):
    def __init__(self, failure=None):
        super().__init__()
        self.party_failure = failure
        self.published = []
        for state in self.states.values():
            state.update(party=copy.deepcopy(EMPTY_PARTY), pending_party_invite=None,
                         party_invite_result=None, party_chat=[])
        self.original = copy.deepcopy(self.states["mover"])
        if failure == "existing_party":
            self.states["mover"]["party"]["id"] = 123
        if failure == "existing_invite":
            self.states["witness"]["pending_party_invite"] = {"character_id": 999}
        if failure == "existing_outgoing_invite":
            self.states["mover"]["party_invite_result"] = {"result": 0, "target": "Somebody Else"}

    def snapshot(self, bot):
        return copy.deepcopy(self.states[bot])

    def request(self, method, bot=None, **args):
        if method == "capabilities":
            return {"methods": [] if self.party_failure == "old_worker" else sorted(BOUND_METHODS)}
        if method not in BOUND_METHODS:
            return super().request(method, bot, **args)
        state = self.states[bot]
        if method == "accept_party_bound" and self.party_failure == "raced_invite":
            state["pending_party_invite"]["character_id"] = 999
        if method == "disband_party_bound" and self.party_failure == "raced_roster":
            state["party"]["members"][1]["character_id"] = 999
        # Model the native guard: expected context was serialized earlier, and
        # must still match immediately before command publication.
        if args["expected_party"] != state["party"] or args["expected_invite"] != state["pending_party_invite"]:
            raise DevelopmentError("native party context changed")
        self.published.append(method)
        if method == "invite_party_bound":
            assert bot == "mover" and args["target"] == 2 and args["name"] == "Bot Witness"
            state["party_invite_result"] = {"result": 0, "target": "Bot Witness"}
            self.states["witness"]["pending_party_invite"] = {
                "character_id": 999 if self.party_failure == "foreign_invite" else 101,
                "auth_type": 1, "result": 1, "name": "Bot Mover"}
            if self.party_failure == "invite_rejected":
                state["party_invite_result"]["result"] = 99
        elif method == "accept_party_bound":
            assert bot == "witness"
            state["pending_party_invite"] = None
            party = {"id": 900, "chat_channel": 600, "count": 2, "leader_index": 0,
                     "members": [{"entity_id": entity, "character_id": entity + 100, "name": name,
                                  "territory": 130, "level": 1, "class_job": 1}
                                 for entity, name in ((1, "Bot Mover"), (2, "Bot Witness"))]}
            for value in self.states.values():
                value["party"] = copy.deepcopy(party)
            if self.party_failure == "foreign_member":
                self.states["mover"]["party"]["members"][1]["character_id"] = 999
            if self.party_failure == "different_party":
                self.states["witness"]["party"]["id"] = 901
            if self.party_failure == "different_channel":
                self.states["witness"]["party"]["chat_channel"] = 601
            if self.party_failure == "wrong_leader":
                self.states["mover"]["party"]["leader_index"] = 1
        elif method == "party_chat_bound":
            peer = "witness" if bot == "mover" else "mover"
            entity = state["entity_id"]
            name = "Bot Mover" if bot == "mover" else "Bot Witness"
            row = {"actor": entity, "character_id": entity + 100, "name": name,
                   "party_id": 900, "channel": 600, "message": args["message"]}
            if self.party_failure == "wrong_chat_channel":
                row["channel"] = 999
            if self.party_failure == "wrong_chat_character":
                row["character_id"] = 999
            if self.party_failure != "missing_chat":
                self.states[peer]["party_chat"].append(row)
            if self.party_failure == "membership_changed_before_disband" and bot == "witness":
                # The receipt still matches current membership for its sender,
                # but ownership must be rechecked before any disband is sent.
                self.states["witness"]["party"]["members"][0]["character_id"] = 999
        elif method == "disband_party_bound":
            self.states["mover"]["party"] = copy.deepcopy(EMPTY_PARTY)
            if self.party_failure != "missing_disband_state":
                self.states["witness"]["party"] = copy.deepcopy(EMPTY_PARTY)
        return {}  # Receipts alone never prove membership/chat/disband effects.


def execute(profile, tmp_path, failure=None, reconnect=False, enabled=True):
    fake = PartyWorker(failure)
    logins = []
    def login(*args):
        logins.append(1)
        return {"lobbyHost": "127.0.0.1", "lobbyPort": 54994, "sId": "private"}
    result = run_development.run(profile, tmp_path / "run", confirmed=True,
        verify_party=enabled, verify_reconnect=reconnect,
        worker_factory=lambda *_: fake, login=login, lease_root=tmp_path / "leases")
    return result, fake, logins


def test_owned_party_requires_real_state_and_restores_empty_membership(profile, tmp_path):
    report, fake, _ = execute(profile, tmp_path)
    assert report["status"] == "passed" and fake.closed and not report["lease_retained"]
    proof = report["party_verification"]
    assert proof["verified"] and proof["both_empty_after_disband"]
    assert proof["party"]["id"] == 900 and proof["party"]["chat_channel"] == 600
    assert [row["character_id"] for row in proof["received_chat"]] == [101, 102]
    assert fake.published == ["invite_party_bound", "accept_party_bound", "party_chat_bound",
                              "party_chat_bound", "disband_party_bound"]
    assert not list((tmp_path / "leases").iterdir())


@pytest.mark.parametrize("failure", ["old_worker", "existing_party", "existing_invite", "existing_outgoing_invite", "foreign_invite",
    "raced_invite", "invite_rejected", "foreign_member", "different_party", "different_channel",
    "wrong_leader", "missing_chat", "wrong_chat_channel", "wrong_chat_character",
    "membership_changed_before_disband", "raced_roster", "missing_disband_state"])
def test_uncertain_or_foreign_social_state_is_never_cleaned_up_automatically(profile, tmp_path, failure):
    report, fake, logins = execute(profile, tmp_path, failure)
    assert report["status"] == "failed" and report["lease_retained"] and fake.closed
    assert report["party_verification"] == {"requested": True, "verified": False}
    assert len(list((tmp_path / "leases").glob("*.lock"))) == 2
    if failure != "missing_disband_state":
        assert "disband_party_bound" not in fake.published
    if failure in {"old_worker", "existing_party", "existing_invite", "existing_outgoing_invite"}:
        assert not fake.published
    if failure == "old_worker":
        assert not logins  # Capability failure must precede authentication.
    if failure in {"foreign_invite", "raced_invite", "invite_rejected"}:
        assert fake.published == ["invite_party_bound"]
    assert fake.published.count("invite_party_bound") <= 1
    assert fake.published.count("disband_party_bound") <= 1


def test_party_flag_is_opt_in_and_strict_boolean(profile, tmp_path):
    report, fake, _ = execute(profile, tmp_path, enabled=False)
    assert report["status"] == "passed" and not fake.published
    assert report["party_verification"] == {"requested": False, "verified": False}
    with pytest.raises(DevelopmentError):
        run_development.run(profile, tmp_path / "invalid", confirmed=True, verify_party=1)
    assert not (tmp_path / "invalid").exists()


def test_party_cleanup_precedes_optional_reconnect(profile, tmp_path):
    report, fake, logins = execute(profile, tmp_path, reconnect=True)
    assert report["status"] == "passed" and len(logins) == 3
    assert report["party_verification"]["verified"] and report["reconnect_verification"]["verified"]
    phases = [row["phase"] for row in report["timings"]]
    assert phases.index("party_owned_disband_and_empty_state") < phases.index("reconnect_fresh_http_login")

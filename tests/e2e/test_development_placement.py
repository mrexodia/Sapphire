"""Synthetic administrative-placement guards; not live warp/reset evidence."""
import copy
import json

import pytest

from . import prepare_development, run_development
from .provision_development import new_profile
from .support.development import DevelopmentError, received_character_identity
from .test_development import FakeWorker, profile, execute


@pytest.fixture
def preparation(tmp_path, monkeypatch):
    worker = tmp_path / "worker"
    worker.write_bytes(b"synthetic-worker")
    private = new_profile({"version": 1, "mode": "shared-development", "protocol": "sapphire-3.3",
                           "worker": str(worker), "api_port": 5000, "lobby_port": 54994, "territory": 130})
    report = {"scope": "shared-development-provisioning-not-gameplay", "status": "provisioned",
              "lease_retained": False, "worker_closed": True,
              "accounts": [{"slot": index, "character": account["character"], "entity_id": index + 1,
                            "character_id": index + 100, "gm_rank": 0,
                            "account_creation": "fresh_login_verified",
                            "character_creation": "refreshed_lobby_and_world_verified",
                            "logout_server_close_verified": True}
                           for index, account in enumerate(private["accounts"])]}
    monkeypatch.setattr(prepare_development, "movement_route", lambda _: ([[1, 2, 3], [2, 2, 3]], "a" * 64))
    return private, report


def test_registry_binds_exact_observed_characters_and_source_destination(preparation):
    private, report = preparation
    registry = prepare_development.placement_registry(private, report)
    assert registry["position"] == [1, 2, 3] and registry["territory"] == 130
    assert registry["catalog_sha256"] == "a" * 64 and len(registry["approval_id"]) == 32
    assert [row["character_id"] for row in registry["bots"]] == [100, 101]
    for account in private["accounts"]:
        assert account["password"] not in json.dumps(registry)
        assert account["username"] not in json.dumps(registry)


@pytest.mark.parametrize("patch", [{"status": "failed"}, {"lease_retained": True},
    {"worker_closed": False}, {"scope": "headless-live-not-real-client"}])
def test_registry_requires_complete_provisioning(preparation, patch):
    private, report = preparation
    report.update(patch)
    with pytest.raises(DevelopmentError):
        prepare_development.placement_registry(private, report)


@pytest.mark.parametrize("patch", [{"character_id": None}, {"character_id": True}, {"entity_id": 0},
    {"entity_id": 2**32}, {"character_id": 2**64}, {"character": "Human Viewer"},
    {"logout_server_close_verified": False}, {"gm_rank": 1}, {"gm_rank": False}, {"slot": 1}, {"slot": False},
    {"character_creation": "requested_outcome_unknown"}])
def test_registry_rejects_missing_legacy_or_unowned_identities(preparation, patch):
    private, report = preparation
    report["accounts"][0].update(patch)
    with pytest.raises(DevelopmentError):
        prepare_development.placement_registry(private, report)


def test_registry_requires_unique_bindings(preparation):
    private, report = preparation
    report["accounts"][1]["character_id"] = report["accounts"][0]["character_id"]
    with pytest.raises(DevelopmentError):
        prepare_development.placement_registry(private, report)


def test_registry_cli_requires_approval_and_never_overwrites(preparation, tmp_path):
    private, report = preparation
    pp, rp, out = [tmp_path / name for name in ("profile.json", "report.json", "registry.json")]
    pp.write_text(json.dumps(private))
    rp.write_text(json.dumps(report))
    args = ["--profile", str(pp), "--provisioning-report", str(rp), "--registry", str(out)]
    assert prepare_development.main(args) == 1 and not out.exists()
    assert prepare_development.main([*args, "--approve-fixture-placement"]) == 0
    original = out.read_bytes()
    assert prepare_development.main([*args, "--approve-fixture-placement"]) == 1
    assert out.read_bytes() == original


def test_received_lobby_and_world_identity_must_match():
    state = {"entity_id": 1, "characters": [{"name": "Tester ABCDEFGHIJKL", "entity_id": 1, "character_id": 100}]}
    assert received_character_identity(state, "Tester ABCDEFGHIJKL")["character_id"] == 100
    for mutate in (lambda s: s.update(entity_id=2), lambda s: s["characters"].append(s["characters"][0]),
                   lambda s: s["characters"][0].update(character_id=-1)):
        wrong = copy.deepcopy(state)
        mutate(wrong)
        with pytest.raises(DevelopmentError):
            received_character_identity(wrong, "Tester ABCDEFGHIJKL")


def test_placement_wait_is_explicit_and_requires_route(profile, tmp_path):
    with pytest.raises(DevelopmentError, match="source-bound"):
        run_development.run(profile, tmp_path / "run", confirmed=True, await_placement=True)
    assert not (tmp_path / "run").exists()


def test_placement_wait_is_separate_from_normal_actions(profile, tmp_path, monkeypatch):
    monkeypatch.setattr(run_development, "movement_route", lambda _: ([[0, 0, 0], [1, 0, 0]], "a" * 64))
    class PlacedByOperator(FakeWorker):
        def __init__(self):
            super().__init__()
            for state in self.states.values():
                state["territory"] = 182
        def wait_state(self, bot, predicate, description, timeout=30):
            if description.startswith("operator-prepared"):
                assert 0 < timeout <= 120
                self.states[bot]["territory"] = 130
            return super().wait_state(bot, predicate, description, timeout)
    result, fake = execute(profile, tmp_path, PlacedByOperator(), await_placement=True)
    assert result["status"] == "passed" and result["administrative_preparation_wait_enabled"]
    assert not result["administrative_command_execution_attested"]
    assert "administrative_placement_wait_not_gameplay" in {row["phase"] for row in result["timings"]}
    ready = json.loads((tmp_path / "run" / "placement-ready.json").read_text())
    assert ready["scope"] == "administrative-preparation-not-gameplay" and ready["wait_seconds"] == 120
    assert [row["entity_id"] for row in ready["bots"]] == [1, 2]
    assert set(fake.commands) == {"login", "say", "walk_to", "logout", "close", "remove"}


def test_placement_timeout_preserves_lease_without_mutations(profile, tmp_path, monkeypatch):
    monkeypatch.setattr(run_development, "movement_route", lambda _: ([[0, 0, 0], [1, 0, 0]], "a" * 64))
    fake = FakeWorker()
    for state in fake.states.values():
        state["territory"] = 182
    result, fake = execute(profile, tmp_path, fake, await_placement=True)
    assert result["status"] == "failed" and result["lease_retained"] and fake.closed
    assert set(fake.commands) == {"login"}

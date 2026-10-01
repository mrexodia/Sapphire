"""Synthetic administrative-placement guards; not live warp/reset evidence."""
import copy
import json
import os

import pytest

from . import prepare_development, run_development
from .provision_development import new_profile
from .support.development import DevelopmentError, received_character_identity
from .support.development_binding import provisioning_binding
from .support.development_result import inspect_development_result
from .test_development import FakeWorker, profile, execute


def runner_registry(profile, tmp_path, fake):
    names = ["Tester AAAAAAAAAAAA", "Tester BBBBBBBBBBBB"]
    for index, name in enumerate(names):
        profile["accounts"][index]["character"] = name
        state = fake.states[("mover", "witness")[index]]
        state["characters"][0]["name"] = name
    fake.states["witness"]["actors"]["1"]["name"] = names[0]
    fake.states["mover"]["actors"]["2"]["name"] = names[1]
    if hasattr(fake, "original"):
        fake.original["characters"][0]["name"] = names[0]
    if hasattr(fake, "actor_row"):
        fake.actor_row["name"] = names[0]
    registry = {"version":2,"purpose":"development-bot-placement",
        "approval_id":"d" * 32,"provisioning_run_id":"c" * 32,
        "territory":130,"position":[0,0,0],"catalog_sha256":"a" * 64,
        "bots":[{"name":names[index],"entity_id":index + 1,
                 "character_id":fake.states[("mover", "witness")[index]]["characters"][0]["character_id"]}
                for index in range(2)]}
    path = tmp_path / "placement-registry.json"
    path.write_text(json.dumps(registry))
    return path


@pytest.fixture
def preparation(tmp_path, monkeypatch):
    worker = tmp_path / "worker"
    worker.write_bytes(b"synthetic-worker")
    private = new_profile({"version": 1, "mode": "shared-development", "protocol": "sapphire-3.3",
                           "worker": str(worker), "api_port": 5000, "lobby_port": 54994, "territory": 130})
    report = {"scope": "shared-development-provisioning-not-gameplay", "run_id": "c" * 32,
              "status": "provisioned", "lease_retained": False, "worker_closed": True,
              "credential_profile_saved": True,
              "worker_exit": {"scope": "owned-native-worker-exit-not-server-session-closure",
                              "context_entered": True, "context_exit_attempted": True,
                              "context_exit_completed": True, "process_exit_observed": True,
                              "process_id": 12345, "returncode": 0},
              "lease_snapshot": {"version": 1,
                  "scope": "exact-local-account-lease-snapshot-not-server-session-or-offline-proof",
                  "state": "clear", "expected_lease_count": 2, "present_lease_count": 0,
                  "records": [{"lease_index": 0, "state": "absent"},
                              {"lease_index": 1, "state": "absent"}],
                  "retained_run_id": None, "profile_or_account_values_disclosed": False,
                  "lease_paths_or_keys_disclosed": False, "unrelated_entries_inspected": False,
                  "filesystem_mutation_performed": False, "server_or_database_contacted": False,
                  "active_session_checked": False, "offline_verified": False,
                  "release_authorized": False, "cross_file_snapshot_atomic": False,
                  "retained_receipts_match_run": False},
              "lease_snapshot_matches_run_state": True,
              "accounts": [{"slot": index, "character": account["character"], "entity_id": index + 1,
                            "character_id": index + 100, "gm_rank": 0,
                            "account_creation": "fresh_login_verified",
                            "character_creation": "refreshed_lobby_and_world_verified",
                            "logout_server_close_verified": True}
                           for index, account in enumerate(private["accounts"])]}
    report["provisioning_binding"] = provisioning_binding(private, report["accounts"])
    monkeypatch.setattr(prepare_development, "movement_route", lambda _: ([[1, 2, 3], [2, 2, 3]], "a" * 64))
    return private, report


def test_registry_binds_exact_observed_characters_and_source_destination(preparation):
    private, report = preparation
    registry = prepare_development.placement_registry(private, report)
    assert registry["version"] == 2 and registry["position"] == [1, 2, 3] and registry["territory"] == 130
    assert registry["provisioning_run_id"] == report["run_id"]
    assert registry["catalog_sha256"] == "a" * 64 and len(registry["approval_id"]) == 32
    assert [row["character_id"] for row in registry["bots"]] == [100, 101]
    for account in private["accounts"]:
        assert account["password"] not in json.dumps(registry)
        assert account["username"] not in json.dumps(registry)


@pytest.mark.parametrize("patch", [{"status": "failed"}, {"lease_retained": True},
    {"worker_closed": False}, {"worker_exit": None}, {"credential_profile_saved": False},
    {"lease_snapshot": None}, {"lease_snapshot_matches_run_state": False},
    {"run_id": None}, {"run_id": True}, {"run_id": "C" * 32}, {"run_id": "c" * 31},
    {"scope": "headless-live-not-real-client"}])
def test_registry_requires_complete_provisioning(preparation, patch):
    private, report = preparation
    report.update(patch)
    with pytest.raises(DevelopmentError):
        prepare_development.placement_registry(private, report)


@pytest.mark.parametrize("field,value", [
    ("context_entered", False), ("context_exit_attempted", False),
    ("context_exit_completed", False), ("process_exit_observed", False),
    ("process_id", 0), ("process_id", True), ("returncode", 1), ("returncode", True),
    ("scope", "server-session-closed")])
def test_registry_rejects_malformed_or_failed_worker_exit(preparation, field, value):
    private, report = preparation
    report["worker_exit"][field] = value
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
    report["provisioning_binding"] = provisioning_binding(private, report["accounts"])
    with pytest.raises(DevelopmentError):
        prepare_development.placement_registry(private, report)


def test_registry_cli_requires_approval_and_never_overwrites(
        preparation, tmp_path, monkeypatch):
    private, report = preparation
    calls = []
    def validated(report_path, profile_path, *, managed):
        calls.append((report_path, profile_path, managed))
        return {"profile":private,"report":report}
    monkeypatch.setattr(prepare_development, "validate_provisioning_evidence", validated)
    pp, rp, out = [tmp_path / name for name in ("profile.json", "report.json", "registry.json")]
    pp.write_text(json.dumps(private))
    rp.write_text(json.dumps(report))
    args = ["--profile", str(pp), "--provisioning-report", str(rp), "--registry", str(out)]
    assert prepare_development.main(args) == 1 and not out.exists()
    assert prepare_development.main([*args, "--approve-fixture-placement"]) == 0
    original = out.read_bytes()
    assert prepare_development.main([*args, "--approve-fixture-placement"]) == 1
    assert out.read_bytes() == original
    assert calls == [(str(rp),str(pp),None),(str(rp),str(pp),None)]


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


@pytest.mark.parametrize("mutation", ["catalog","name","duplicate","hardlink"])
def test_placement_registry_is_exact_and_validated_before_login(
        profile, tmp_path, monkeypatch, mutation):
    monkeypatch.setattr(run_development, "movement_route",
                        lambda _: ([[0, 0, 0], [1, 0, 0]], "a" * 64))
    fake = FakeWorker()
    registry = runner_registry(profile, tmp_path, fake)
    value = json.loads(registry.read_text())
    if mutation == "catalog": value["catalog_sha256"] = "b" * 64
    elif mutation == "name": value["bots"][0]["name"] = "Tester CCCCCCCCCCCC"
    elif mutation == "duplicate":
        registry.write_text(registry.read_text().replace(
            '{"version": 2,', '{"version": 2, "version": 2,', 1))
    else:
        os.link(registry, tmp_path / "registry-alias.json")
    if mutation not in {"duplicate","hardlink"}: registry.write_text(json.dumps(value))
    with pytest.raises(DevelopmentError):
        run_development.run(profile, tmp_path / "run", confirmed=True,
            await_placement=True, placement_registry=registry,
            worker_factory=lambda *_: fake, lease_root=tmp_path / "leases")
    assert not (tmp_path / "run").exists() and fake.commands == []


def test_placement_registry_and_wait_must_be_selected_together(
        profile, tmp_path, monkeypatch):
    monkeypatch.setattr(run_development, "movement_route",
                        lambda _: ([[0, 0, 0], [1, 0, 0]], "a" * 64))
    fake = FakeWorker(); registry = runner_registry(profile, tmp_path, fake)
    with pytest.raises(DevelopmentError):
        run_development.run(profile, tmp_path / "missing", confirmed=True,
                            await_placement=True)
    with pytest.raises(DevelopmentError):
        run_development.run(profile, tmp_path / "foreign", confirmed=True,
                            placement_registry=registry)
    assert not (tmp_path / "missing").exists() and not (tmp_path / "foreign").exists()


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
                self.states[bot]["seq"] += 1
            return super().wait_state(bot, predicate, description, timeout)
    fake = PlacedByOperator()
    registry = runner_registry(profile, tmp_path, fake)
    result, fake = execute(profile, tmp_path, fake, await_placement=True,
                           placement_registry=registry, max_seconds=60)
    assert result["status"] == "passed" and result["administrative_preparation_wait_enabled"]
    assert not result["administrative_command_execution_attested"]
    assert "administrative_placement_wait_not_gameplay" in {row["phase"] for row in result["timings"]}
    ready = json.loads((tmp_path / "run" / "placement-ready.json").read_text())
    assert ready["scope"] == "administrative-preparation-not-gameplay" and ready["wait_seconds"] == 120
    assert [row["entity_id"] for row in ready["bots"]] == [1, 2]
    assert ready["registry_sha256"] == result["placement_verification"]["registry_sha256"]
    assert result["placement_verification"]["verified"] is True
    assert result["placement_verification"]["state_transition_observed"] is True
    proof = inspect_development_result(tmp_path / "run/development-summary.json")
    assert set(proof["verified_checks"]) == {"say","movement","placement"}
    assert set(fake.commands) == {"login", "say", "walk_to", "logout", "close", "remove"}


@pytest.mark.parametrize("mutation", ["target","stale","transition","catalog"])
def test_placement_result_inspector_rejects_foreign_or_stale_registry_receipt(
        profile, tmp_path, monkeypatch, mutation):
    monkeypatch.setattr(run_development, "movement_route",
                        lambda _: ([[0, 0, 0], [1, 0, 0]], "a" * 64))
    class Placed(FakeWorker):
        def __init__(self):
            super().__init__()
            for state in self.states.values(): state["territory"] = 182
        def wait_state(self, bot, predicate, description, timeout=30):
            if description.startswith("operator-prepared"):
                self.states[bot]["territory"] = 130
                self.states[bot]["seq"] += 1
            return super().wait_state(bot, predicate, description, timeout)
    fake = Placed(); registry = runner_registry(profile, tmp_path, fake)
    execute(profile, tmp_path, fake, await_placement=True,
            placement_registry=registry, max_seconds=60)
    summary = tmp_path / "run/development-summary.json"
    report = json.loads(summary.read_text())
    placement = report["placement_verification"]
    if mutation == "target": placement["targets"][0]["name"] = "Tester CCCCCCCCCCCC"
    elif mutation == "stale":
        placement["received"][0]["received_sequence"] = placement["initial"][0]["baseline_sequence"]
    elif mutation == "transition": placement["state_transition_observed"] = False
    else: placement["catalog_sha256"] = "b" * 64
    summary.write_text(json.dumps(report))
    with pytest.raises(DevelopmentError): inspect_development_result(summary)


def test_placement_timeout_preserves_lease_without_mutations(profile, tmp_path, monkeypatch):
    monkeypatch.setattr(run_development, "movement_route", lambda _: ([[0, 0, 0], [1, 0, 0]], "a" * 64))
    fake = FakeWorker()
    for state in fake.states.values():
        state["territory"] = 182
    registry = runner_registry(profile, tmp_path, fake)
    result, fake = execute(profile, tmp_path, fake, await_placement=True,
                           placement_registry=registry)
    assert result["status"] == "failed" and result["lease_retained"] and fake.closed
    assert set(fake.commands) == {"login"}

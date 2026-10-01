"""Synthetic policy only: no client launch, pixel review, gameplay, or disposal."""
import copy
import hashlib
import json

import pytest

from .inspect_client_development_result import main as inspect_main
from .support.client_development import (require_graphical_check,
                                         require_graphical_decline_check,
                                         require_graphical_run_pair)
from .support.client_result import inspect_client_development_result, RESULT_SCOPE
from .support.client_smoke import (CLIENT_SHA256, INTERACTION_CAPTURE_SCOPE,
                                   INTERACTION_REVIEW_CHECKS, LOGOUT_CAPTURE_SCOPE,
                                   LOGOUT_REVIEW_CHECKS, REVIEW_CHECKS,
                                   witness_say_challenge)
from .support.client_snapshot import git
from .support.development import DevelopmentError
from .support.environment import REPO
from .test_client_development import completed, declined


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def json_file(path, mutate):
    value = json.loads(path.read_text(encoding="utf-8"))
    mutate(value)
    write_json(path, value)


def environment_file(root, report, mutate):
    path = root / "artifacts/sapphire-e2e-synthetic/manifest.json"
    json_file(path, mutate)
    report["environment_manifest"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()


def outer_state(position, sequence, chat=None, *, viewer=True):
    actors = ({"3":{"kind":1,"name":"Tester Viewer","gm_rank":0,"level":1,
                    "hp":94,"position":position}} if viewer else {})
    return {"phase":"ready","gm_rank":0,"territory":130,"between_areas":False,
            "scene":None,"entity_id":1,"seq":sequence,"chat":chat or [],
            "characters":[{"name":"bot mover","entity_id":1,"character_id":11}],
            "actors":actors}


def build_output(root, source_revision="1" * 40):
    combat_hashes = {"data/actions/player.json":"1" * 64,
        "data/bnpcs/w1f2/w1f2.json":"2" * 64,
        "data/bnpcs/w1f2/w1f2_paths.json":"3" * 64}
    source_manifest = {"version":1,
        "scope":"committed-coordinator-source-not-native-build-attestation",
        "revision":source_revision,"dirty":False,
        "sha256":{"tests/e2e/synthetic.py":"a" * 64, **combat_hashes},"gitlinks":[],
        "submodule_fetch_performed":False,"remote_configured":False}
    input_root = root.parent / "input"
    source_path = input_root / "source.json"
    write_json(source_path, source_manifest)
    staged = {
        "profile.json":b'{"synthetic":true}',
        "bin/api.exe":b"synthetic api", "bin/lobby.exe":b"synthetic lobby",
        "bin/server.exe":b"synthetic world", "bin/dbm.exe":b"synthetic dbm",
        "bin/sapphire_test_client.exe":b"synthetic worker",
        "bin/compiledscripts/script.dll":b"synthetic script",
        "quest_catalog.json":b'{"synthetic":"catalog"}',
        "catalog-mesh.nav":b"synthetic navigation",
    }
    for relative, contents in staged.items():
        path = input_root / relative; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
    input_hashes = {relative:hashlib.sha256((input_root / relative).read_bytes()).hexdigest()
                    for relative in staged}
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    input_hashes["source.json"] = source_hash
    write_json(root.parent / "inputs.json", {"version":1,
        "status":"prepared_not_executed","client_sha256":CLIENT_SHA256,
        "config_sha256":"e" * 64,"source_revision":source_revision,
        "source_manifest_sha256":source_hash,"working_tree_changes_included":False,
        "inputs":input_hashes})
    main, decline = completed(), declined()
    main["worker_sha256"] = decline["worker_sha256"] = input_hashes["bin/sapphire_test_client.exe"]
    main["catalog_sha256"] = input_hashes["quest_catalog.json"]
    main["elapsed_seconds"], decline["elapsed_seconds"] = 12.5, 4.5
    decline["run_id"] = "b" * 32
    for stage in ("start", "finish"):
        for reply in decline["viewer_verification"][stage]["received_replies"]:
            reply["message"] = reply["message"].replace("viewer aaaaaaaa", "viewer bbbbbbbb")
    write_json(root / "development/development-summary.json", main)
    write_json(root / "development-decline/development-summary.json", decline)
    main_path = root / "development/development-summary.json"
    decline_path = root / "development-decline/development-summary.json"
    main_hash = hashlib.sha256(main_path.read_bytes()).hexdigest()
    decline_hash = hashlib.sha256(decline_path.read_bytes()).hexdigest()
    main_proof = require_graphical_check(main, "Tester Viewer", 3)
    decline_proof = require_graphical_decline_check(decline, "Tester Viewer", 3)
    pair = require_graphical_run_pair(
        main, decline, ["bot mover", "bot witness"], main["worker_sha256"])
    run_id = "f" * 32
    frame = b"synthetic frame bytes, not reviewed pixels"
    (root / "review.png").write_bytes(frame)
    frame_hash = hashlib.sha256(frame).hexdigest()
    challenge = witness_say_challenge(run_id)
    ticket = {"run": run_id, "frame_sha256": frame_hash,
              "witness_say_challenge": challenge}
    review = {"version": 1, **ticket, "checks": REVIEW_CHECKS, "manual_review": True}
    write_json(root / "review-ticket.json", ticket)
    write_json(root / "review.json", review)
    (root / "interaction.png").write_bytes(b"synthetic nonempty interaction frame")
    interaction_hash = hashlib.sha256((root / "interaction.png").read_bytes()).hexdigest()
    interaction_ticket = {"run":run_id,"development_run":decline["run_id"],
        "bots":["bot mover", "bot witness"], "frame_sha256":interaction_hash,
        "viewer_say_challenge":decline["viewer_verification"]["finish"]["received_replies"][0]["message"],
        "scope":INTERACTION_CAPTURE_SCOPE}
    interaction_review = {"version":1, **interaction_ticket,
        "checks":INTERACTION_REVIEW_CHECKS,"manual_review":True}
    write_json(root / "interaction-ticket.json", interaction_ticket)
    write_json(root / "interaction-review.json", interaction_review)
    (root / "logout.png").write_bytes(b"synthetic nonempty logout frame")
    logout_hash = hashlib.sha256((root / "logout.png").read_bytes()).hexdigest()
    logout_ticket = {"run":run_id,"frame_sha256":logout_hash,"scope":LOGOUT_CAPTURE_SCOPE}
    write_json(root / "logout-ticket.json", logout_ticket)
    write_json(root / "logout-review.json", {"version":1, **logout_ticket,
        "checks":LOGOUT_REVIEW_CHECKS,"manual_review":True})
    starts = [{"process":name,"generation":1,"pid":index + 20}
              for index, name in enumerate(("database","api","lobby","world"))]
    teardowns = [{**row,"was_running_before_cleanup":True,
        "terminate_requested":True,"kill_requested":False,"exit_observed":True,
        "returncode":-15,
        "scope":"exact-owned-isolated-process-teardown-not-graceful-server-exit"}
        for row in reversed(starts)]
    lifecycle_path = root / "artifacts/sapphire-e2e-synthetic/process-lifecycle.json"
    write_json(lifecycle_path, {"version":1,
        "scope":"exact-owned-isolated-process-teardown-not-graceful-server-exit",
        "starts":starts,"teardowns":teardowns})
    lifecycle_hash = hashlib.sha256(lifecycle_path.read_bytes()).hexdigest()
    environment_path = root / "artifacts/sapphire-e2e-synthetic/manifest.json"
    write_json(environment_path, {"revision":source_revision,"dirty":False,
        "profile":"sapphire-3.3","fixture_version":2,"deadline_scale":1,
        "database":"sapphire_e2e_" + "a" * 32,"runtime":"C:/synthetic-runtime",
        "game_data":"C:/e2e-sqpack","navmesh":"C:/e2e-navigation",
        "ports":{"database":3307,"api":8081,"lobby":54994,"world":55000},
        "binaries":{name:input_hashes[f"bin/{name}.exe"]
                    for name in ("api","lobby","server","dbm")},
        "worker_sha256":input_hashes["bin/sapphire_test_client.exe"],
        "scripts":{"script.dll":input_hashes["bin/compiledscripts/script.dll"]},
        "server_navigation":{"w1t1/w1t1.nav":"4" * 64},
        "combat_data":{relative.removeprefix("data/"):digest
                       for relative,digest in combat_hashes.items()},
        "quest_catalog":{"path":"C:/e2e-input/quest_catalog.json",
                         "sha256":input_hashes["quest_catalog.json"]},
        "quest_catalog_navigation":{"path":"C:/e2e-input/catalog-mesh.nav",
                                    "sha256":input_hashes["catalog-mesh.nav"]}})
    environment_hash = hashlib.sha256(environment_path.read_bytes()).hexdigest()
    retire = {"server_close_observed": True, "native_bot_removed": True,
              "scope": "normal-witness-session-retirement-not-offline-exclusion"}
    phases = ["setup", "spawn", "movement", "say", "review", "development",
              "interaction_review", "logout", "witness_retirement", "cleanup"]
    report = {
        "version": 1, "run": run_id, "status": "passed",
        "scope": "manual-real-client-login-movement-say-logout",
        "source_revision": source_revision, "source_manifest_sha256": source_hash,
        "real_name": "Tester Viewer", "real_entity": 3,
        "witness_name": "bot mover", "witness_say_challenge": challenge,
        "client_sha256": CLIENT_SHA256, "client_pid": 1234,
        "client_teardown": {"version":1,"pid":1234,
            "was_running_before_cleanup":True,"forced_termination_requested":True,
            "exit_observed":True,"returncode":1,
            "scope":"exact-owned-title-screen-client-forced-cleanup-not-ui-exit-proof"},
        "environment_manifest":{"verified":True,
            "scope":"exact-graphical-environment-input-identities-not-native-build-provenance",
            "relative_path":"artifacts/sapphire-e2e-synthetic/manifest.json",
            "sha256":environment_hash},
        "environment_process_teardown": {"verified":True,
            "scope":"exact-graphical-isolated-service-teardown-before-result-publication",
            "relative_path":"artifacts/sapphire-e2e-synthetic/process-lifecycle.json",
            "sha256":lifecycle_hash,"evidence":{"verified":True,
                "scope":"all-exact-owned-isolated-process-generations-observed-terminated",
                "process_count":4,
                "generations":{"api":1,"database":1,"lobby":1,"world":1}}},
        "sandbox_disposal": "operator_required", "runtime_removed": True,
        "fixture": {"position": [0, 0, 0], "territory": 130,
                    "catalog_sha256": input_hashes["quest_catalog.json"], "placement_is_travel": False,
                    "development_check": True},
        "development_check": {"requested": True, "status": "passed",
            "summary_sha256": main_hash, "elapsed_seconds": 12.5,
            "evidence": main_proof},
        "decline_check": {"requested": True, "status": "passed",
            "summary_sha256": decline_hash, "elapsed_seconds": 4.5,
            "evidence": decline_proof},
        "development_run_pair": pair,
        "development_witness_handoff": {"verified": True,
            "scope": "same-dedicated-witness-across-normal-handoff-not-offline-exclusion",
            "identity": copy.deepcopy(pair["identities"][0]),
            "retirement_scope": "normal-witness-session-retirement-not-offline-exclusion",
            "comprehensive_run_id": "a" * 32, "decline_run_id": "b" * 32},
        "logout_witness_restoration": {"verified": True,
            "scope": "fresh-paired-witness-login-and-viewer-presence-not-offline-exclusion",
            "identity": copy.deepcopy(pair["identities"][0]),
            "viewer": {"entity_id": 3, "name": "Tester Viewer", "gm_rank": 0,
                       "position": [1, 0, 0], "presence_token": 19},
            "received_sequence": 20},
        "witness_retirements": [{"bot": "witness", **retire},
                                {"bot": "witness-after-development", **retire}],
        "observer_worker_exit": {
            "scope": "owned-native-worker-exit-not-server-session-closure",
            "context_entered": True, "context_exit_attempted": True,
            "context_exit_completed": True, "process_exit_observed": True,
            "process_id": 12345, "returncode": 0},
        "activity_deadline": {"enabled": True, "limit_seconds": 1200,
            "expired": False, "activity_and_worker_exit_completed_within_budget": True,
            "scope": "cooperative-manual-activity-success-deadline-not-hard-cleanup-limit",
            "environment_cleanup_may_exceed_deadline": True},
        "timing": {"version": 1, "scope": "manual-client-phase-wall-time-not-coverage",
            "elapsed_seconds": 10.0,
            "phases": [{"phase": phase, "seconds": 1.0} for phase in phases],
            "note": "Includes operator waits and worker unwinding; cleanup is client/environment teardown. Not gameplay CPU time."},
        "pre_client_state": outer_state([0,0,0], 6, viewer=False),
        "spawn": outer_state([0,0,0], 7),
        "real_spawn_receipt": {"verified":True,
            "scope":"fresh-exact-fixture-real-client-spawn-not-client-provenance",
            "entity_id":3,"name":"Tester Viewer","gm_rank":0,"level":1,
            "position":[0,0,0],"baseline_sequence":6,"received_sequence":7},
        "movement_baseline": outer_state([0,0,0], 8),
        "movement": outer_state([1,0,0], 9),
        "real_movement_receipt": {"verified":True,
            "scope":"fresh-bounded-real-client-movement-received-by-independent-witness",
            "actor":3,"origin":[0,0,0],"baseline_position":[0,0,0],
            "received_position":[1,0,0],"baseline_sequence":8,
            "received_sequence":9,"movement_metres":1.0},
        "observed_movement_metres": 1.0,
        "say_baseline": outer_state([1,0,0], 10),
        "say": outer_state([1,0,0], 11,
            [{"actor":3,"kind":10,"message":"E2E real client verified","token":11}]),
        "real_say_receipt": {"verified":True,
            "scope":"fresh-ordinary-real-client-say-received-by-independent-witness",
            "actor":3,"message":"E2E real client verified","kind":10,
            "baseline_sequence":10,"message_token":11,"received_sequence":11},
        "review": outer_state([1,0,0], 12,
            [{"actor":3,"kind":10,"message":"E2E real client verified","token":11}]),
        "interaction_review": outer_state([1,0,0], 13),
        "logout_baseline": outer_state([1,0,0], 13),
        "logout": outer_state([1,0,0], 14, viewer=False),
        "real_logout_receipt": {"verified":True,
            "scope":"fresh-real-client-absence-after-logout-phase-not-server-logout-proof",
            "entity_id":3,"baseline_position":[1,0,0],
            "baseline_sequence":13,"received_sequence":14},
        "manual_review": review,
        "manual_interaction_review": interaction_review,
        "logout_request": "[3] Zone IPC : StartLogoutCountdown",
        "logout_frame_sha256": logout_hash,
    }
    write_json(root / "result.json", report)
    write_json(root / "status.json", {"run": run_id, "phase": "finished",
                                      "status": "passed", "instruction": "synthetic"})
    return report


def build_output_challenge(root):
    return json.loads((root / "interaction-ticket.json").read_text())["viewer_say_challenge"]


def report_source_hash(root):
    return hashlib.sha256((root.parent / "input/source.json").read_bytes()).hexdigest()


def test_read_only_inspector_revalidates_current_nested_and_outer_evidence(tmp_path):
    root = tmp_path / "output"; root.mkdir(); build_output(root)
    before = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in root.rglob("*") if path.is_file()}
    proof = inspect_client_development_result(root, "1" * 40)
    after = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in root.rglob("*") if path.is_file()}
    assert before == after
    assert proof["status"] == "accepted" and proof["scope"] == RESULT_SCOPE
    assert proof["prepared_inputs"] == {"verified":True,
        "scope":"all-exact-staged-graphical-input-files-match-preparation-manifest",
        "file_count":10,
        "source":{"verified":True,
            "scope":"exact-prepared-source-manifest-bytes-and-revision-not-native-build-attestation",
            "revision":"1" * 40,"source_manifest_sha256":report_source_hash(root),
            "tracked_source_files":4,"unmaterialized_gitlinks":0},
        "note":"External readonly mappings and native-build provenance are out of scope."}
    assert proof["sandbox_disposal_verified"] is False
    assert proof["bot_interaction_review"] == {"verified":True,
        "frame_sha256":hashlib.sha256((root / "interaction.png").read_bytes()).hexdigest(),
        "scope":INTERACTION_CAPTURE_SCOPE, "development_run":"b" * 32,
        "bots":["bot mover", "bot witness"],
        "viewer_say_challenge":build_output_challenge(root)}
    assert proof["title_screen_review"] == {"verified":True,
        "frame_sha256":hashlib.sha256((root / "logout.png").read_bytes()).hexdigest(),
        "scope":LOGOUT_CAPTURE_SCOPE}
    assert proof["environment_manifest"]["evidence"]["script_count"] == 1
    assert proof["environment_manifest"]["evidence"]["server_navigation_file_count"] == 1
    assert proof["environment_manifest"]["evidence"]["worker_sha256"] == proof["worker_sha256"]
    assert proof["environment_process_teardown"]["evidence"]["process_count"] == 4
    assert proof["activity_deadline"]["activity_and_worker_exit_completed_within_budget"] is True


def test_inspector_cli_prints_summary_without_writing_output(tmp_path, capsys):
    root = tmp_path / "output"; root.mkdir()
    revision = git(REPO, "rev-parse", "--verify", "HEAD^{commit}").decode().strip()
    build_output(root, revision)
    assert inspect_main(["--output", str(root)]) == 0
    value = json.loads(capsys.readouterr().out)
    assert value["scope"] == RESULT_SCOPE and value["sandbox_disposal_verified"] is False


@pytest.mark.parametrize("mutation", [
    lambda root, report: report.update(status="failed"),
    lambda root, report: report.update(source_revision="0" * 40),
    lambda root, report: report.pop("source_manifest_sha256"),
    lambda root, report: report.update(source_manifest_sha256="0" * 64),
    lambda root, report: json_file(root.parent / "inputs.json",
        lambda value:value.update(source_revision="0" * 40)),
    lambda root, report: json_file(root.parent / "inputs.json",
        lambda value:value["inputs"].update({"source.json":"0" * 64})),
    lambda root, report: json_file(root.parent / "input/source.json",
        lambda value:value.update(dirty=True)),
    lambda root, report: (root.parent / "input/profile.json").write_bytes(b"changed"),
    lambda root, report: (root.parent / "input/extra.bin").write_bytes(b"untracked input"),
    lambda root, report: report.update(runtime_removed=False),
    lambda root, report: report.update(sandbox_disposal="verified"),
    lambda root, report: report.update(client_pid=True),
    lambda root, report: report["client_teardown"].update(pid=4321),
    lambda root, report: report["client_teardown"].update(was_running_before_cleanup=1),
    lambda root, report: report["client_teardown"].update(forced_termination_requested=False),
    lambda root, report: report["client_teardown"].update(exit_observed=False),
    lambda root, report: report["client_teardown"].update(returncode=True),
    lambda root, report: report["environment_manifest"].update(
        relative_path="../foreign/manifest.json"),
    lambda root, report: report["environment_manifest"].update(sha256="0" * 64),
    lambda root, report: environment_file(root, report,
        lambda value:value.update(dirty=True)),
    lambda root, report: environment_file(root, report,
        lambda value:value["binaries"].update(api=True)),
    lambda root, report: environment_file(root, report,
        lambda value:value["scripts"].update({"script.dll":"0" * 64})),
    lambda root, report: environment_file(root, report,
        lambda value:value["server_navigation"].update({"../foreign.nav":"0" * 64})),
    lambda root, report: environment_file(root, report,
        lambda value:value["combat_data"].update({"actions/player.json":"0" * 64})),
    lambda root, report: environment_file(root, report,
        lambda value:value["quest_catalog"].update(sha256="0" * 64)),
    lambda root, report: report["environment_process_teardown"].update(
        relative_path="../foreign/process-lifecycle.json"),
    lambda root, report: report["environment_process_teardown"].update(sha256="0" * 64),
    lambda root, report: report["environment_process_teardown"]["evidence"].update(
        process_count=True),
    lambda root, report: json_file(root /
        "artifacts/sapphire-e2e-synthetic/process-lifecycle.json",
        lambda value:value["teardowns"][0].update(returncode=True)),
    lambda root, report: write_json(root /
        "artifacts/sapphire-e2e-synthetic/retained/Cleanup-Failure.JSON", {}),
    lambda root, report: report["fixture"].update(catalog_sha256="e" * 64),
    lambda root, report: report["development_check"].update(summary_sha256="0" * 64),
    lambda root, report: report["development_run_pair"]["identities"][0].update(entity_id=True),
    lambda root, report: report["development_run_pair"]["identities"][0].update(character_id=99),
    lambda root, report: report["development_check"].update(elapsed_seconds=True),
    lambda root, report: report["development_witness_handoff"].update(identity={}),
    lambda root, report: report["logout_witness_restoration"]["viewer"].update(entity_id=4),
    lambda root, report: report["witness_retirements"][0].update(server_close_observed=1),
    lambda root, report: report["observer_worker_exit"].update(returncode=1),
    lambda root, report: report["activity_deadline"].update(
        activity_and_worker_exit_completed_within_budget=False),
    lambda root, report: report["timing"]["phases"][0].update(seconds=float("nan")),
    lambda root, report: report.update(observed_movement_metres=True),
    lambda root, report: report.update(witness_say_challenge="stale challenge"),
    lambda root, report: write_json(root / "review-ticket.json",
        {"run":"f"*32,"frame_sha256":hashlib.sha256((root / "review.png").read_bytes()).hexdigest(),
         "witness_say_challenge":witness_say_challenge("e"*32)}),
    lambda root, report: report["pre_client_state"]["actors"].update(
        {"4":{"kind":1,"name":"foreign","gm_rank":0,"level":1,"hp":94,"position":[0,0,0]}}),
    lambda root, report: report["pre_client_state"].update(entity_id=True),
    lambda root, report: report["spawn"].update(seq=6),
    lambda root, report: report["real_spawn_receipt"].update(name="foreign"),
    lambda root, report: report["movement_baseline"]["actors"]["3"].update(position=[0.2,0,0]),
    lambda root, report: report["real_movement_receipt"].update(baseline_sequence=True),
    lambda root, report: report["movement"].update(seq=8),
    lambda root, report: report["spawn"]["characters"][0].update(character_id=99),
    lambda root, report: report["movement"].update(entity_id=True),
    lambda root, report: report["say_baseline"]["chat"].append(
        {"actor":3,"kind":10,"message":"E2E real client verified","token":10}),
    lambda root, report: report["say"]["chat"][0].update(token=10),
    lambda root, report: report["real_say_receipt"].update(actor=True),
    lambda root, report: report["review"]["actors"]["3"].update(name="foreign"),
    lambda root, report: report["logout_baseline"]["actors"]["3"].update(name="foreign"),
    lambda root, report: report["real_logout_receipt"].update(received_sequence=13),
    lambda root, report: report["logout"].update(seq=13),
    lambda root, report: report["logout"]["actors"].update(
        {"3":{"kind":1,"name":"Tester Viewer","gm_rank":0,"level":1,
              "hp":94,"position":[1,0,0]}}),
    lambda root, report: report["manual_review"].update(manual_review=False),
    lambda root, report: report["interaction_review"]["actors"]["3"].update(name="foreign"),
    lambda root, report: report["manual_interaction_review"].update(manual_review=1),
    lambda root, report: write_json(root / "interaction-ticket.json",
        {**json.loads((root / "interaction-ticket.json").read_text()),
         "development_run":"e" * 32}),
    lambda root, report: write_json(root / "interaction-ticket.json",
        {**json.loads((root / "interaction-ticket.json").read_text()),
         "bots":["bot mover", "foreign"]}),
    lambda root, report: write_json(root / "interaction-review.json",
        {**json.loads((root / "interaction-review.json").read_text()),
         "viewer_say_challenge":"stale"}),
    lambda root, report: (root / "interaction.png").write_bytes(b"changed interaction frame"),
    lambda root, report: report.update(logout_request="foreign"),
    lambda root, report: report.update(logout_frame_sha256="0" * 64),
    lambda root, report: write_json(root / "logout-review.json",
        {"version":1,"run":"f"*32,"frame_sha256":report["logout_frame_sha256"],
         "scope":LOGOUT_CAPTURE_SCOPE,"checks":[],"manual_review":True}),
    lambda root, report: (root / "logout.png").write_bytes(b"changed logout frame"),
    lambda root, report: write_json(root / "status.json",
        {"run": "0" * 32, "phase": "finished", "status": "passed"}),
])
def test_inspector_rejects_partial_foreign_or_type_confused_results(tmp_path, mutation):
    root = tmp_path / "output"; root.mkdir(); report = build_output(root)
    mutation(root, report)
    write_json(root / "result.json", report)
    with pytest.raises(DevelopmentError):
        inspect_client_development_result(root, "1" * 40)

"""Asset-independent contracts, NOT real-client execution or rendering evidence."""
import copy
import json
import xml.etree.ElementTree as ET

import pytest

from .prepare_client_smoke import (approve, approve_interaction, approve_logout,
                                   sandbox_xml)
from .support.client_smoke import (INTERACTION_CAPTURE_SCOPE, INTERACTION_REVIEW_CHECKS,
                                   LOGOUT_CAPTURE_SCOPE, LOGOUT_REVIEW_CHECKS,
                                   REAL_SAY, REVIEW_CHECKS, moved, other_player, position,
                                   real_logout_baseline, real_movement_baseline,
                                   real_say_baseline, real_spawn_baseline,
                                   received_real_logout, received_real_movement,
                                   received_real_say, received_real_spawn,
                                   validate_interaction_review, validate_logout_review,
                                   validate_review, witness_say_challenge)
from .support.environment import sha256


def state():
    return {"phase": "ready", "gm_rank": 0, "territory": 130, "between_areas": False,
            "scene": None, "entity_id": 11, "seq": 10, "chat": [],
            "actors": {"12": {"kind": 1, "name": "Tester Viewer", "gm_rank": 0,
                              "level": 1, "hp": 94, "position": [1, 2, 3]},
                       "19": {"kind": 2}}}


def test_peer_identity_and_absence_are_phase_specific():
    received = state()
    assert other_player(received)[0] == 12
    assert other_player(received, 12)[0] == 12
    with pytest.raises(ValueError, match="identity changed"):
        other_player(received, 13)
    received["actors"].pop("12")
    assert other_player(received) is None
    assert other_player(received, 12, allow_absent=True) is None
    with pytest.raises(ValueError, match="disappeared"):
        other_player(received, 12)


@pytest.mark.parametrize("key,value", [("phase", "failed"), ("gm_rank", 1), ("territory", 141),
                                       ("between_areas", True), ("scene", {})])
def test_unready_witness_cannot_supply_evidence(key, value):
    received = state()
    received[key] = value
    with pytest.raises(ValueError):
        other_player(received)


@pytest.mark.parametrize("key,value", [("gm_rank", 1), ("level", 2), ("hp", 0)])
def test_unexpected_real_player_rejected(key, value):
    received = state()
    received["actors"]["12"][key] = value
    with pytest.raises(ValueError):
        other_player(received)


def test_multiple_peers_never_select_arbitrarily():
    received = state()
    received["actors"]["13"] = copy.deepcopy(received["actors"]["12"])
    with pytest.raises(ValueError, match="ambiguous"):
        other_player(received)


@pytest.mark.parametrize("value", [[True, 0, 0], [float("nan"), 0, 0], [float("inf"), 0, 0],
                                   [1000, 0, 0], [0, 0], "123"])
def test_received_position_is_bounded_finite_numeric(value):
    with pytest.raises(ValueError):
        position(value)


def test_fixture_placement_and_excess_movement_are_not_success():
    assert not moved([0, 0, 0], [0, 0, 0])
    assert not moved([0, 0, 0], [0.99, 0, 0])
    assert moved([0, 0, 0], [1, 0, 0])
    assert moved([0, 0, 0], [3, 4, 0])
    with pytest.raises(ValueError):
        moved([0, 0, 0], [5.01, 0, 0])


def test_real_spawn_requires_empty_baseline_exact_name_and_advancing_sequence():
    empty = state(); empty["actors"].pop("12")
    baseline = real_spawn_baseline(empty)
    assert baseline == 10 and received_real_spawn(
        empty, "Tester Viewer", [1,2,3], baseline) is None
    spawned = state(); spawned["seq"] = 11
    assert received_real_spawn(spawned, "Tester Viewer", [1,2,3], baseline) == {
        "verified":True,
        "scope":"fresh-exact-fixture-real-client-spawn-not-client-provenance",
        "entity_id":12,"name":"Tester Viewer","gm_rank":0,"level":1,
        "position":[1,2,3],"baseline_sequence":10,"received_sequence":11}


def test_real_spawn_rejects_preexisting_stale_foreign_or_distant_player():
    with pytest.raises(ValueError, match="unexpected player"):
        real_spawn_baseline(state())
    mutations = (
        lambda value: value.update(seq=10),
        lambda value: value["actors"]["12"].update(name="foreign"),
        lambda value: value["actors"]["12"].update(position=[3,2,3]),
        lambda value: value.update(seq=True),
    )
    for mutate in mutations:
        spawned = state(); spawned["seq"] = 11; mutate(spawned)
        with pytest.raises(ValueError):
            received_real_spawn(spawned, "Tester Viewer", [1,2,3], 10)


def test_real_movement_requires_post_phase_baseline_and_advancing_received_state():
    baseline_state = state(); baseline_state["actors"]["12"]["position"] = [0,0,0]
    baseline = real_movement_baseline(baseline_state, 12, [0,0,0])
    waiting = copy.deepcopy(baseline_state)
    assert received_real_movement(waiting, 12, [0,0,0], baseline) is None
    received = copy.deepcopy(baseline_state); received["seq"] = 11
    received["actors"]["12"]["position"] = [1,0,0]
    assert received_real_movement(received, 12, [0,0,0], baseline) == {
        "verified":True,
        "scope":"fresh-bounded-real-client-movement-received-by-independent-witness",
        "actor":12,"origin":[0,0,0],"baseline_position":[0,0,0],
        "received_position":[1,0,0],"baseline_sequence":10,
        "received_sequence":11,"movement_metres":1.0}


def test_real_movement_rejects_stale_displaced_or_excessive_evidence():
    displaced = state(); displaced["actors"]["12"]["position"] = [0.16,0,0]
    with pytest.raises(ValueError, match="baseline"):
        real_movement_baseline(displaced, 12, [0,0,0])
    baseline = {"sequence":10,"position":[0,0,0]}
    for sequence, point in ((10,[1,0,0]), (11,[5.01,0,0])):
        received = state(); received["seq"] = sequence
        received["actors"]["12"]["position"] = point
        with pytest.raises(ValueError):
            received_real_movement(received, 12, [0,0,0], baseline)
    with pytest.raises(ValueError):
        received_real_movement(state(), 12, [0,0,0], {"sequence":True,"position":[0,0,0]})


def test_real_logout_requires_visible_post_phase_baseline_then_fresh_absence():
    baseline = real_logout_baseline(state(), 12, "Tester Viewer")
    assert baseline == {"sequence":10,"position":[1,2,3]}
    still_present = state(); still_present["seq"] = 11
    assert received_real_logout(still_present, 12, baseline) is None
    absent = state(); absent["seq"] = 11; absent["actors"].pop("12")
    assert received_real_logout(absent, 12, baseline) == {
        "verified":True,
        "scope":"fresh-real-client-absence-after-logout-phase-not-server-logout-proof",
        "entity_id":12,"baseline_position":[1,2,3],
        "baseline_sequence":10,"received_sequence":11}


def test_real_logout_rejects_foreign_malformed_or_stale_absence():
    with pytest.raises(ValueError):
        real_logout_baseline(state(), 12, "foreign")
    absent = state(); absent["actors"].pop("12")
    with pytest.raises(ValueError, match="stale"):
        received_real_logout(absent, 12, {"sequence":10,"position":[1,2,3]})
    absent["seq"] = 11
    with pytest.raises(ValueError):
        received_real_logout(absent, 12, {"sequence":True,"position":[1,2,3]})


def test_real_say_requires_one_fresh_sequence_bound_ordinary_message():
    baseline_state = state()
    baseline = real_say_baseline(baseline_state, 12)
    assert baseline == 10 and received_real_say(baseline_state, 12, baseline) is None
    received = state(); received.update(seq=12)
    received["chat"] = [{"actor":12,"kind":10,"message":REAL_SAY,"token":11}]
    assert received_real_say(received, 12, baseline) == {
        "verified":True,
        "scope":"fresh-ordinary-real-client-say-received-by-independent-witness",
        "actor":12,"message":REAL_SAY,"kind":10,
        "baseline_sequence":10,"message_token":11,"received_sequence":12}


def test_real_say_rejects_stale_malformed_or_ambiguous_receipts():
    stale = state(); stale["chat"] = [{"actor":12,"kind":10,"message":REAL_SAY,"token":10}]
    with pytest.raises(ValueError, match="already present"):
        real_say_baseline(stale, 12)
    mutations = (
        lambda row, received: row.update(token=10),
        lambda row, received: row.update(token=True),
        lambda row, received: row.update(kind=11),
        lambda row, received: row.update(actor=12.0),
        lambda row, received: row.update(extra=True),
        lambda row, received: received["chat"].append(copy.deepcopy(row)),
    )
    for mutate in mutations:
        received = state(); received.update(seq=12)
        row = {"actor":12,"kind":10,"message":REAL_SAY,"token":11}
        received["chat"] = [row]; mutate(row, received)
        with pytest.raises(ValueError):
            received_real_say(received, 12, 10)


def review_files(tmp_path):
    (tmp_path / "review.png").write_bytes(b"synthetic contract input, not an image")
    run_id = "a" * 32
    ticket = {"run": run_id, "frame_sha256": sha256(tmp_path / "review.png"),
              "witness_say_challenge": witness_say_challenge(run_id)}
    (tmp_path / "review-ticket.json").write_text(json.dumps(ticket))
    (tmp_path / "status.json").write_text(json.dumps({"run": run_id, "phase": "review"}))
    return ticket


def test_explicit_review_bound_to_active_run_and_exact_frame(tmp_path):
    ticket = review_files(tmp_path)
    assert not (tmp_path / "review.json").exists()
    approve(tmp_path)  # Represents an explicit operator action, not image recognition.
    receipt = json.loads((tmp_path / "review.json").read_text())
    assert validate_review(receipt, ticket)["checks"] == REVIEW_CHECKS
    for key, value in [("run", "b" * 32), ("frame_sha256", "0" * 64),
                       ("witness_say_challenge", "stale challenge"),
                       ("manual_review", False), ("manual_review", 1), ("version", True),
                       ("checks", []), ("extra", True)]:
        invalid = {**receipt, key: value}
        with pytest.raises(ValueError):
            validate_review(invalid, ticket)
    (tmp_path / "review.png").write_bytes(b"changed")
    with pytest.raises(ValueError, match="frame changed"):
        approve(tmp_path)


def test_review_rejects_foreign_run_bound_witness_challenge(tmp_path):
    ticket = review_files(tmp_path)
    ticket["witness_say_challenge"] = witness_say_challenge("b" * 32)
    (tmp_path / "review-ticket.json").write_text(json.dumps(ticket))
    with pytest.raises(ValueError, match="foreign Say challenge"):
        approve(tmp_path)
    for value in (True, "g" * 32, "a" * 31, "A" * 32):
        with pytest.raises(ValueError):
            witness_say_challenge(value)


def test_explicit_interaction_review_binds_active_bots_fresh_say_and_exact_frame(tmp_path):
    run_id, development_run = "c" * 32, "d" * 32
    (tmp_path / "interaction.png").write_bytes(b"synthetic interaction frame, not reviewed pixels")
    ticket = {"run":run_id, "development_run":development_run,
              "bots":["bot mover", "bot witness"],
              "frame_sha256":sha256(tmp_path / "interaction.png"),
              "viewer_say_challenge":f"Sapphire viewer {development_run[:8]} finish {'e' * 32}",
              "scope":INTERACTION_CAPTURE_SCOPE}
    (tmp_path / "interaction-ticket.json").write_text(json.dumps(ticket))
    (tmp_path / "status.json").write_text(json.dumps(
        {"run":run_id,"phase":"interaction_review"}))
    approve_interaction(tmp_path)
    receipt = json.loads((tmp_path / "interaction-review.json").read_text())
    assert validate_interaction_review(receipt, ticket)["checks"] == INTERACTION_REVIEW_CHECKS
    for key, value in (("run", "f" * 32), ("development_run", "f" * 32),
                       ("bots", ["same", "SAME"]), ("bots", ["one"]),
                       ("frame_sha256", "0" * 64), ("viewer_say_challenge", "stale"),
                       ("scope", "foreign"), ("manual_review", 1),
                       ("version", True), ("checks", []), ("extra", True)):
        with pytest.raises(ValueError):
            validate_interaction_review({**receipt, key:value}, ticket)
    (tmp_path / "interaction.png").write_bytes(b"changed")
    with pytest.raises(ValueError, match="frame changed"):
        approve_interaction(tmp_path)


def test_explicit_logout_review_is_bound_to_finished_run_and_exact_frame(tmp_path):
    run_id = "c" * 32
    (tmp_path / "logout.png").write_bytes(b"synthetic title frame, not reviewed pixels")
    ticket = {"run":run_id,"frame_sha256":sha256(tmp_path / "logout.png"),
              "scope":LOGOUT_CAPTURE_SCOPE}
    (tmp_path / "logout-ticket.json").write_text(json.dumps(ticket))
    (tmp_path / "status.json").write_text(json.dumps(
        {"run":run_id,"phase":"finished","status":"passed"}))
    approve_logout(tmp_path)
    receipt = json.loads((tmp_path / "logout-review.json").read_text())
    assert validate_logout_review(receipt, ticket)["checks"] == LOGOUT_REVIEW_CHECKS
    for key, value in (("run", "d" * 32), ("frame_sha256", "0" * 64),
                       ("scope", "foreign"), ("manual_review", False),
                       ("version", True), ("checks", []), ("extra", True)):
        with pytest.raises(ValueError):
            validate_logout_review({**receipt, key:value}, ticket)
    (tmp_path / "logout.png").write_bytes(b"changed")
    with pytest.raises(ValueError, match="frame changed"):
        approve_logout(tmp_path)


@pytest.mark.parametrize("status", [{"run": "b" * 32, "phase": "review"},
                                    {"run": "a" * 32, "phase": "logout"}])
def test_stale_or_wrong_phase_review_rejected(tmp_path, status):
    review_files(tmp_path)
    (tmp_path / "status.json").write_text(json.dumps(status))
    with pytest.raises(ValueError, match="no active review"):
        approve(tmp_path)


def test_sandbox_has_one_writable_output_and_no_network_or_redirection():
    xml = sandbox_xml([("C:/source&private", "C:/sapphire-repo", True),
                       ("C:/output", "C:/e2e-output", False)])
    tree = ET.fromstring(xml)
    for name in ("Networking", "ClipboardRedirection", "AudioInput", "VideoInput", "PrinterRedirection"):
        assert tree.findtext(name) == "Disable"
    assert tree.findtext("vGPU") == "Enable"
    folders = tree.findall("MappedFolders/MappedFolder")
    assert folders[0].findtext("HostFolder") == "C:/source&private"
    assert [f.findtext("ReadOnly") for f in folders] == ["true", "false"]
    assert folders[1].findtext("SandboxFolder") == "C:\\e2e-output"


@pytest.mark.parametrize("mappings", [[], [("C:/source", "C:/source", False)],
    [("C:/output", "C:/e2e-output", False), ("C:/other", "C:/other", False)]])
def test_rejects_unsafe_writable_mappings(mappings):
    with pytest.raises(ValueError):
        sandbox_xml(mappings)

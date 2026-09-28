"""Asset-independent contracts, NOT real-client execution or rendering evidence."""
import copy
import json
import xml.etree.ElementTree as ET

import pytest

from .prepare_client_smoke import approve, sandbox_xml
from .support.client_smoke import REVIEW_CHECKS, moved, other_player, position, validate_review
from .support.environment import sha256


def state():
    return {"phase": "ready", "gm_rank": 0, "territory": 130, "between_areas": False,
            "scene": None, "entity_id": 11,
            "actors": {"12": {"kind": 1, "gm_rank": 0, "level": 1, "hp": 94,
                              "position": [1, 2, 3]},
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


def review_files(tmp_path):
    (tmp_path / "review.png").write_bytes(b"synthetic contract input, not an image")
    ticket = {"run": "run-a", "frame_sha256": sha256(tmp_path / "review.png")}
    (tmp_path / "review-ticket.json").write_text(json.dumps(ticket))
    (tmp_path / "status.json").write_text(json.dumps({"run": "run-a", "phase": "review"}))
    return ticket


def test_explicit_review_bound_to_active_run_and_exact_frame(tmp_path):
    ticket = review_files(tmp_path)
    assert not (tmp_path / "review.json").exists()
    approve(tmp_path)  # Represents an explicit operator action, not image recognition.
    receipt = json.loads((tmp_path / "review.json").read_text())
    assert validate_review(receipt, ticket)["checks"] == REVIEW_CHECKS
    for key, value in [("run", "other-run"), ("frame_sha256", "different-frame"),
                       ("manual_review", False), ("manual_review", 1), ("version", True),
                       ("checks", []), ("extra", True)]:
        invalid = {**receipt, key: value}
        with pytest.raises(ValueError):
            validate_review(invalid, ticket)
    (tmp_path / "review.png").write_bytes(b"changed")
    with pytest.raises(ValueError, match="frame changed"):
        approve(tmp_path)


@pytest.mark.parametrize("status", [{"run": "run-b", "phase": "review"},
                                    {"run": "run-a", "phase": "logout"}])
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

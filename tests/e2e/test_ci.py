"""CI gate contracts use synthetic files/reports, not gameplay evidence."""
import json
import struct
from types import SimpleNamespace

import pytest

from . import run_ci


@pytest.fixture
def profile(tmp_path):
    p = {key: str(tmp_path / key) for key in run_ci.PATH_KEYS}
    for key in ("binaries", "mariadb_bin", "navigation", "game_data"):
        (tmp_path / key).mkdir()
    from pathlib import Path
    for name in ("api", "lobby", "server", "dbm"):
        (Path(p["binaries"]) / (name + ".exe")).write_bytes(b"synthetic executable")
    scripts = Path(p["binaries"]) / "compiledscripts"
    scripts.mkdir()
    (scripts / "fixture.dll").write_bytes(b"synthetic module")
    for name in ("mariadbd", "mariadb-install-db", "mariadb"):
        (Path(p["mariadb_bin"]) / (name + ".exe")).write_bytes(b"synthetic executable")
    Path(p["worker"]).write_bytes(b"synthetic worker")
    (tmp_path / "ffxivgame.ver").write_text(run_ci.VERSION)
    (Path(p["game_data"]) / "ffxiv").mkdir()
    (Path(p["game_data"]) / "ffxiv/fixture.index").write_bytes(b"synthetic archive")
    for name in ("w1t1", "w1f2"):
        root = Path(p["navigation"]) / name
        root.mkdir()
        (root / (name + ".nav")).write_bytes(struct.pack("<III", 0x54534554, 1, 1) + b"synthetic mesh")
    nav = {"mesh": str(Path(p["navigation"]) / "w1t1/w1t1.nav")}
    quest = {"profile": "sapphire-3.3", "version": 1, "quest": 65686, "level": 1,
             "previous_quests": [0, 0, 0], "client": 1, "finish": 2, "navigation": nav,
             "route": [[0, 0, 0], [1, 0, 0]], "route_length": 1,
             "actors": [{"base_id": i + 1, "layout_id": i, "territory": 130, "position": [i, 0, 0]}
                        for i in (0, 1)]}
    Path(p["quest_catalog"]).write_text(json.dumps(quest))
    Path(p["follow_up_catalog"]).write_text(json.dumps({**quest, "quest": 65687, "previous_quests": [65686, 0, 0]}))
    transition = {"profile": "sapphire-3.3", "version": 1, "territory": 130, "navigation": nav,
                  "route": [[2, 0, 0], [0, 0, 0]], "route_length": 2,
                  "transition": {"territory": 130, "enabled": True, "shape": 1, "exit_type": 1,
                                 "target_territory": 141, "target_pop": 1,
                                 "position": [0, 0, 0], "scale": [1, 1, 1], "rotation": [0, 0, 0],
                                 "destinations": [{"id": 1, "territory": 141,
                                                   "position": [-113.490196, 17.62882, 329.058105]}]},
                  "supported_discovery": {"id": 3643706, "territory": 141, "kind": "map_range",
                      "enabled": True, "discovery_enabled": True, "shape": 3, "discovery_index": 1,
                      "map_id": 21, "map_discovery_index": 8, "uint16_storage": True,
                      "map_discovery_flag": 16382, "level_one_exp_reward": 15,
                      "position": [-90.424652, 16.765249, 297.362396], "scale": [140, 23.227831, 140],
                      "rotation": [0, -0.048542, 0]}}
    transition["supported_discoveries"] = [transition["supported_discovery"].copy(),
        {"id": 4204061, "territory": 141, "kind": "map_range", "enabled": True,
         "discovery_enabled": True, "shape": 1, "discovery_index": 3, "map_id": 21,
         "map_discovery_index": 8, "uint16_storage": True, "map_discovery_flag": 16382,
         "level_one_exp_reward": 15, "position": [37.696751, 13.38007, 99.489952],
         "scale": [10, 10, 35], "rotation": [0, 0.3573853, 0],
         "navigation": {"mesh": "navi/w1f2/w1f2.nav", "format": "TSET-v1", "polyref_bits": 64},
         "route": [[-113.490196, 17.62882, 329.058105], [37.696751, 13.38007, 99.489952]],
         "route_length": 274.9128619973513}]
    Path(p["transition_catalog"]).write_text(json.dumps(transition))
    combat = {"version": 1, "profile": "sapphire-3.3", "action": 9, "class_job": 1,
              "work_index": 1, "level": 1, "base_exp": 50,
              "category": 3, "cost_type": 5, "cost": 60, "range": -1, "cast_ms": 0,
              "recast_ms": 2500, "recast_group": 58, "effect_type": 1, "target_enemy": True,
              "sprint": {"action": 3, "class_job": 0, "work_index": -1, "level": 0,
                         "base_exp": 45, "category": 0, "cost_type": 18, "cost": 0,
                         "range": 0, "cast_ms": 0, "recast_ms": 30000,
                         "recast_group": 56, "effect_type": 1, "target_enemy": False},
              "return": {"action": 6, "class_job": 0, "work_index": -1, "level": 0,
                         "base_exp": 45, "category": 10, "cost_type": 0, "cost": 0,
                         "range": 0, "cast_ms": 5000, "recast_ms": 900000,
                         "recast_group": 57, "effect_type": 1, "target_enemy": False},
              "bootshine": {"action": 53, "class_job": 2, "work_index": 0, "level": 1,
                            "base_exp": 50, "category": 3, "cost_type": 5, "cost": 60,
                            "range": -1, "cast_ms": 0, "recast_ms": 2500,
                            "recast_group": 58, "effect_type": 1, "target_enemy": True},
              "blizzard": {"action": 142, "class_job": 7, "work_index": 5, "level": 1,
                           "base_exp": 50, "category": 2, "cost_type": 3, "cost": 4,
                           "range": 25, "cast_ms": 2500, "recast_ms": 2500,
                           "recast_group": 58, "effect_type": 1, "target_enemy": True}}
    Path(p["combat_catalog"]).write_text(json.dumps(combat))
    shop = {"version": 1, "profile": "sapphire-3.3", "territory": 130,
            "start_actor": 1001289, "navigation": nav,
            "route": [[0, 0, 0], [1, 0, 0]], "route_length": 1,
            "shop": {"layout_id": 3, "base_id": 4, "event_id": 262468, "position": [1, 0, 0]},
            "sale": {"item": 4551, "quantity": 1, "gil": 28},
            "starter_liquidation": {"item": 3296, "quantity": 1, "gil": 45},
            "starter_body_liquidation": {"item": 2983, "quantity": 1, "gil": 59},
            "starter_feet_liquidation": {"item": 3750, "quantity": 1, "gil": 48},
            "purchase": {"shop_id": 262468, "index": 0, "item": 5890, "quantity": 3, "unit_gil": 8, "gil": 24,
                         "item_action": {"row": 232, "type": 852, "arg": 235}},
            "equipment_purchase": {"shop_id": 262468, "index": 11, "item": 3286,
                                   "quantity": 1, "gil": 39, "resale_gil": 39,
                                   "source_slot": 7, "gear_slot": 6},
            "second_equipment_purchase": {"shop_id": 262468, "index": 9, "item": 3748,
                                          "quantity": 1, "gil": 54, "resale_gil": 54,
                                          "source_slot": 8, "gear_slot": 7},
            "third_equipment_purchase": {"shop_id": 262468, "index": 3, "item": 2967,
                                         "quantity": 1, "gil": 59,
                                         "source_slot": 4, "gear_slot": 3},
            "head_purchase": {"shop": {"layout_id": 4393619, "base_id": 1005495,
                                          "event_id": 262415, "position": [2, 0, 0]},
                              "index": 0, "item": 2638, "quantity": 1, "gil": 47,
                              "source_slot": 3, "gear_slot": 2,
                              "route": [[1, 0, 0], [2, 0, 0]], "route_length": 1},
            "ear_purchase": {"shop": {"layout_id": 4614930, "base_id": 1005900,
                                         "event_id": 262425, "position": [3, 0, 0]},
                             "index": 0, "item": 4200, "quantity": 1, "gil": 66,
                             "source_slot": 9, "gear_slot": 8,
                             "route": [[2, 0, 0], [3, 0, 0]], "route_length": 1},
            "neck_purchase": {"shop": {"layout_id": 4067692, "base_id": 1004417,
                                          "event_id": 262640, "position": [4, 0, 0]},
                              "index": 1, "item": 15130, "quantity": 1, "gil": 168,
                              "source_slot": 10, "gear_slot": 9,
                              "route": [[3, 0, 0], [4, 0, 0]], "route_length": 1}}
    Path(p["shop_catalog"]).write_text(json.dumps(shop))
    respawn = {"version": 1, "profile": "sapphire-3.3", "homepoint": 9, "territory": 130,
               "pop_range": {"id": 1, "position": [0, 0, 0], "rotation": [0, 0, 0]}}
    Path(p["respawn_catalog"]).write_text(json.dumps(respawn))
    pursuit = {"version": 1, "profile": "sapphire-3.3", "territory": 141,
               "enemy": {"layout_id": 3749193, "base_id": 302, "level": 14, "position": [0, 0, 0]},
               "navigation": {"mesh": str(Path(p["navigation"]) / "w1f2/w1f2.nav")},
               "route": [[1, 0, 0], [2.5, 0, 0], [4, 0, 0], [5.5, 0, 0], [7, 0, 0], [8, 0, 0]],
               "route_length": 7,
               "leash_route": [[1 + index * 1.5, 0, 0] for index in range(31)],
               "leash_route_length": 45}
    Path(p["pursuit_catalog"]).write_text(json.dumps(pursuit))
    opening_route = [[42 - index * 0.9, 4 + index * 0.01, -157.6 + index * 0.56]
                     for index in range(11)]
    opening_route[-1] = [33.375702, 4.1, -151.994003]
    import math
    opening = {"version": 1, "profile": "sapphire-3.3", "territory": 182, "quest": 66130,
               "giver": {"layout_id": 3969639, "base_id": 1003987,
                         "position": [33.375702, 4.1, -151.994003]},
               "recipient": {"layout_id": 3969632, "base_id": 1003988,
                             "position": [21.077101, 7.45, -78.8134]},
               "reward": {"exp": 50, "gil": 103},
               "approach_route": opening_route,
               "approach_route_length": sum(math.dist(a, b) for a, b in zip(opening_route, opening_route[1:])),
               "completion_route_supported": False,
               "completion_route_blocker": "incomplete navigation corridor",
               "starter_ring_items": [{"item": item, "equip_slot_category": 12, "stack_max": 1}
                                      for item in (4423, 4424, 4425, 4426)],
               "opening_event_ranges": [
                   {"id": 4101525, "enabled": False, "shape": 1, "position": [91.77615, 4, -108.8433]},
                   {"id": 4101535, "enabled": False, "shape": 1, "position": [8.53425, 4, -143.5217]},
                   {"id": 4101537, "enabled": False, "shape": 1, "position": [42.22482, 4.1983, -160.709]}],
               "supported_range": {"event_id": 1245187, "param": 4101537, "expected_scene": 20,
                                   "route": [[42, 4.337, -157.6], [42.11241, 4.26765, -159.1545],
                                             [42.22482, 4.1983, -160.709]], "route_length": 3.12},
               "navigation": nav}
    Path(p["opening_quest_catalog"]).write_text(json.dumps(opening))
    return p


def test_preflight_checks_all_inputs_without_gameplay(profile):
    result, identities = run_ci.preflight(profile, suffix=".exe")
    assert result == profile
    assert set(identities["binaries"]) == {"api", "lobby", "server", "dbm"}
    assert set(identities["meshes"]) == {"w1t1", "w1f2"}


@pytest.mark.parametrize("mutation", ["missing", "version", "mesh", "route_mesh", "chain", "unknown"])
def test_preflight_rejects_mismatches(profile, mutation):
    from pathlib import Path
    if mutation == "missing":
        Path(profile["worker"]).unlink()
    elif mutation == "version":
        (Path(profile["game_data"]).parent / "ffxivgame.ver").write_text("wrong version")
    elif mutation == "mesh":
        (Path(profile["navigation"]) / "w1f2/w1f2.nav").write_bytes(b"MSET")
    elif mutation in {"route_mesh", "chain"}:
        path = Path(profile["follow_up_catalog"])
        data = json.loads(path.read_text())
        if mutation == "chain":
            data["previous_quests"] = [0, 0, 0]
        else:
            different = path.parent / "different.nav"
            different.write_bytes(b"different mesh")
            data["navigation"]["mesh"] = str(different)
        path.write_text(json.dumps(data))
    else:
        profile["database_password"] = "PRIVATE_MARKER"
    with pytest.raises((run_ci.PreflightError, FileNotFoundError)):
        run_ci.preflight(profile, suffix=".exe")


@pytest.mark.parametrize("field", [None, "worker", "binaries", "scripts", "catalog", "mesh", "missing"])
def test_public_identities_must_match_staged_inputs(profile, field):
    _, expected = run_ci.preflight(profile, suffix=".exe")
    manifest = {"worker_sha256": expected["worker"], "binaries": dict(expected["binaries"]),
                "scripts": {"fixture.dll": expected["script_modules"][0]},
                "server_navigation": {f"{name}/{name}.nav": digest for name, digest in expected["meshes"].items()},
                **{key: {"sha256": digest} for key, digest in expected["catalogs"].items()}}
    if field == "worker":
        manifest["worker_sha256"] = "changed"
    elif field == "binaries":
        manifest["binaries"]["server"] = "changed"
    elif field == "scripts":
        manifest["scripts"]["fixture.dll"] = "changed"
    elif field == "catalog":
        manifest["quest_catalog"]["sha256"] = "changed"
    elif field == "mesh":
        manifest["server_navigation"]["w1t1/w1t1.nav"] = "changed"
    elif field == "missing":
        manifest = {}
    assert run_ci.inputs_match(expected, manifest) is (field is None)


def complete_gate(tmp_path):
    gate = run_ci.EvidenceGate()
    gate.collected = list(run_ci.CASES)
    gate.environment = SimpleNamespace(_closed=True, root=tmp_path / "removed", processes={})
    for case in run_ci.CASES:
        for when in ("setup", "call", "teardown"):
            gate.pytest_runtest_logreport(SimpleNamespace(nodeid=case, when=when, outcome="passed",
                                                        longrepr="PRIVATE_MARKER"))
    return gate


def test_report_is_allowlisted_and_requires_actual_reports(tmp_path):
    gate = complete_gate(tmp_path)
    report = gate.summary(0)
    assert report["status"] == "passed" and all(report["cases"].values())
    assert "PRIVATE_MARKER" not in json.dumps(report)
    assert run_ci.EvidenceGate().summary(0)["status"] == "failed"


@pytest.mark.parametrize("mutation", ["skip", "missing", "duplicate", "foreign", "collection", "cleanup", "process", "exit"])
def test_green_exit_is_not_sufficient(tmp_path, mutation):
    gate = complete_gate(tmp_path)
    code = 0
    if mutation in {"skip", "missing", "duplicate"}:
        gate.reports[run_ci.CASES[0]]["call"] = {"skip": ["skipped"], "missing": [], "duplicate": ["passed", "passed"]}[mutation]
    elif mutation == "foreign":
        gate.pytest_runtest_logreport(SimpleNamespace(nodeid="PRIVATE_MARKER", when="call", outcome="passed"))
    elif mutation == "collection":
        gate.collected.pop()
    elif mutation == "cleanup":
        gate.environment.root.mkdir()
    elif mutation == "process":
        gate.environment.processes["world"] = SimpleNamespace(poll=lambda: None)
    else:
        code = 1
    report = gate.summary(code)
    assert report["status"] == "failed"
    assert "PRIVATE_MARKER" not in json.dumps(report)


def test_entry_point_isolates_pytest_options_and_output(profile, tmp_path, monkeypatch):
    from pathlib import Path
    original = run_ci.preflight
    _, identities = original(profile, suffix=".exe")
    monkeypatch.setattr(run_ci, "preflight", lambda p: original(p, suffix=".exe"))
    monkeypatch.setattr(run_ci, "REPO", tmp_path)
    monkeypatch.setattr(run_ci.subprocess, "check_output", lambda args, **kwargs: "a" * 40 if args[-1] == "HEAD" else "")
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k PRIVATE_MARKER")
    monkeypatch.setenv("PYTEST_PLUGINS", "PRIVATE_MARKER")
    def fake_pytest(args, plugins):
        import os
        assert "PYTEST_ADDOPTS" not in os.environ and "PYTEST_PLUGINS" not in os.environ
        assert os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
        assert all(suite in args for suite in run_ci.SUITES)
        assert not any("::" in arg for arg in args)
        gate = complete_gate(tmp_path)
        artifacts = tmp_path / "staged-evidence"
        artifacts.mkdir()
        manifest = {"worker_sha256": identities["worker"], "binaries": identities["binaries"],
                    "scripts": {"fixture.dll": identities["script_modules"][0]},
                    "server_navigation": {f"{key}/{key}.nav": value for key, value in identities["meshes"].items()},
                    **{key: {"sha256": value} for key, value in identities["catalogs"].items()}}
        (artifacts / "manifest.json").write_text(json.dumps(manifest))
        gate.environment.artifacts = artifacts
        plugins[0].__dict__.update(gate.__dict__)
        print("PRIVATE_MARKER")
        return 0
    monkeypatch.setattr(pytest, "main", fake_pytest)
    source = tmp_path / "input.json"
    source.write_text(json.dumps(profile))
    public = tmp_path / "summary.json"
    cwd = Path.cwd()
    assert run_ci.run(source, tmp_path / "private", public, require_clean=True) == 0
    assert Path.cwd() == cwd
    assert run_ci.os.environ["PYTEST_ADDOPTS"] == "-k PRIVATE_MARKER"
    assert run_ci.os.environ["PYTEST_PLUGINS"] == "PRIVATE_MARKER"
    assert "PRIVATE_MARKER" not in public.read_text()
    assert "PRIVATE_MARKER" in next((tmp_path / "private").glob("*/pytest.log")).read_text()
    assert json.loads(public.read_text())["inputs_verified"]


def test_preflight_exception_is_only_in_private_diagnostics(tmp_path, monkeypatch):
    source = tmp_path / "profile.json"
    source.write_text('{"example": "PRIVATE_MARKER"}')
    def fail(profile):
        raise ValueError("PRIVATE_MARKER")
    monkeypatch.setattr(run_ci, "preflight", fail)
    public = tmp_path / "summary.json"
    private = tmp_path / "private"
    assert run_ci.run(source, private, public) == 1
    assert "PRIVATE_MARKER" not in public.read_text()
    assert json.loads(public.read_text())["stage"] == "preflight"
    assert "PRIVATE_MARKER" in next(private.glob("*/entry-error.log")).read_text()
    assert source.read_text() == '{"example": "PRIVATE_MARKER"}'
    with pytest.raises(run_ci.PreflightError, match="fresh"):
        run_ci.run(source, private, public)

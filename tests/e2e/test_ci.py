"""CI gate contracts use synthetic files/reports, not gameplay evidence."""
import hashlib
import json
from pathlib import Path
import struct
from types import SimpleNamespace

import pytest

from . import run_ci
from .inspect_ci_result import main as inspect_ci_main
from .support.ci_profile_result import (SCOPE as CI_PROFILE_SCOPE,
                                        inspect_ci_profile)
from .support.ci_staging_result import (SCOPE as CI_STAGING_SCOPE,
                                        stage_ci_profile)
from .support import environment as environment_support
from .inspect_ci_private_evidence import main as inspect_ci_private_main
from .inspect_ci_failure_result import main as inspect_ci_failure_main
from .inspect_isolated_fault import main as inspect_isolated_fault_main
from .inspect_isolated_case import main as inspect_isolated_case_main
from .inspect_cleanup_failure import main as inspect_cleanup_failure_main
from .support.cleanup_failure_result import inspect_cleanup_failure
from .support.ci_result import (EXPECTED_CASES, EXPECTED_CATALOGS,
                                SCOPE as CI_RESULT_SCOPE, inspect_ci_result)
from .support.ci_private_result import (FAULT_CASE,
                                        FAULT_CLASSIFICATION as PRIVATE_FAULT_CLASSIFICATION,
                                        FAULT_SCOPE as PRIVATE_FAULT_SCOPE,
                                        HTTP_RECEIPT_SCOPE as PRIVATE_HTTP_RECEIPT_SCOPE,
                                        SCOPE as CI_PRIVATE_SCOPE,
                                        inspect_ci_private_evidence)
from .support.ci_failure_result import (SCOPE as CI_FAILURE_SCOPE,
                                        inspect_ci_failure_result)
from .support.environment import (HTTP_RECEIPT_SCOPE as PRODUCER_HTTP_RECEIPT_SCOPE,
                                  ISOLATED_FAULT_CLASSIFICATION as PRODUCER_FAULT_CLASSIFICATION,
                                  ISOLATED_FAULT_SCOPE as PRODUCER_FAULT_SCOPE,
                                  SetupError, artifact_tree_sha256)
from .support.isolated_case_result import (HTTP_RECEIPT_SCOPE as STANDALONE_HTTP_RECEIPT_SCOPE,
                                           REJECTED_CREDENTIALS_CASE,
                                           SCOPE as ISOLATED_CASE_SCOPE,
                                           inspect_isolated_case)
from .support.isolated_fault_result import (FAULT_CLASSIFICATION as STANDALONE_FAULT_CLASSIFICATION,
                                            FAULT_SCOPE as STANDALONE_FAULT_SCOPE,
                                            SCOPE as ISOLATED_FAULT_SCOPE,
                                            inspect_isolated_fault)


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
                  "transition": {"id": 2377056, "territory": 130, "enabled": True, "shape": 1, "exit_type": 1,
                                 "target_territory": 141, "target_pop": 2372271,
                                 "position": [0, 0, 0], "scale": [1, 1, 1], "rotation": [0, 0, 0],
                                 "destinations": [{"id": 2372271, "territory": 141,
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
    transition["return_transition"] = {
        "id": 2372269, "territory": 141, "enabled": True, "shape": 1, "exit_type": 1,
        "target_territory": 130, "target_pop": 2377058,
        "position": [39, 13.38007, 99.489952], "scale": [4, 4, 4], "rotation": [0, 0, 0],
        "destinations": [{"id": 2377058, "territory": 130, "position": [40, 4, -149]}]}
    transition["return_route"] = [[37.696751, 13.38007, 99.489952], [39, 13.38007, 99.489952]]
    transition["return_route_length"] = 1.303249
    transition["return_navigation"] = {"mesh": "navi/w1f2/w1f2.nav", "format": "TSET-v1",
                                       "polyref_bits": 64}
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
              "true_strike": {"action": 54, "class_job": 2, "work_index": 0, "level": 2,
                              "base_exp": 55, "category": 3, "cost_type": 5, "cost": 50,
                              "range": -1, "cast_ms": 0, "recast_ms": 2500,
                              "recast_group": 58, "effect_type": 1, "target_enemy": True},
              "blizzard": {"action": 142, "class_job": 7, "work_index": 5, "level": 1,
                           "base_exp": 50, "category": 2, "cost_type": 3, "cost": 4,
                           "range": 25, "cast_ms": 2500, "recast_ms": 2500,
                           "recast_group": 58, "effect_type": 1, "target_enemy": True},
              "first_fast_blade_combo": {"action": 11, "class_job": 1, "work_index": 1,
                           "level": 4, "base_exp": 65, "category": 3, "cost_type": 5,
                           "cost": 60, "range": -1, "cast_ms": 0, "recast_ms": 2500,
                           "recast_group": 58, "effect_type": 1, "target_enemy": True,
                           "required_cumulative_exp": 2000, "level_thresholds": [300, 600, 1100],
                           "level_one_enemy_exp": 50,
                           "minimum_level_one_defeats": 40, "level_fourteen_enemy_exp": 115,
                           "minimum_level_fourteen_defeats": 18},
              "representative_high_level_enemy": {"level": 14, "base_exp": 115}}
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
                              "route": [[3, 0, 0], [4, 0, 0]], "route_length": 1},
            "wrist_purchase": {"shop_id": 262640, "index": 2, "item": 15132,
                                "quantity": 1, "gil": 168,
                                "source_slot": 11, "gear_slot": 10},
            "equipment_gap_scan": {"available_gil": 208, "maximum_equip_level": 1,
                                    "off_hand": {"source_slot": 2, "listed_candidates": 0,
                                                   "routed_candidates": 0},
                                    "waist": {"source_slot": 6, "listed_candidates": 0,
                                                "routed_candidates": 0},
                                    "overflow_merge": {"required_units": "stack_max_plus_one",
                                                        "listed_candidates": 0,
                                                        "routed_candidates": 0},
                                    "consuming_item": {"supported_actions": [853, 1322, 5845],
                                                       "listed_candidates": 0,
                                                       "routed_candidates": 0}}}
    Path(p["shop_catalog"]).write_text(json.dumps(shop))
    respawn = {"version": 1, "profile": "sapphire-3.3", "homepoint": 9, "territory": 130,
               "pop_range": {"id": 1, "position": [0, 0, 0], "rotation": [0, 0, 0]}}
    Path(p["respawn_catalog"]).write_text(json.dumps(respawn))
    proximity_origin = [47.837039947509766, 20.88382911682129, -297.4685974121094]
    proximity_route = [[proximity_origin[0], proximity_origin[1], proximity_origin[2] + distance]
                       for distance in range(20, 2, -1)]
    pursuit = {"version": 2, "profile": "sapphire-3.3", "territory": 141,
               "enemy": {"layout_id": 3749193, "base_id": 302, "level": 14, "position": [0, 0, 0]},
               "navigation": {"mesh": str(Path(p["navigation"]) / "w1f2/w1f2.nav")},
               "route": [[1, 0, 0], [2.5, 0, 0], [4, 0, 0], [5.5, 0, 0], [7, 0, 0], [8, 0, 0]],
               "route_length": 7,
               "leash_route": [[1 + index * 1.5, 0, 0] for index in range(31)],
               "leash_route_length": 45,
               "proximity_enemy": {"layout_id": 3746983, "base_id": 735, "level": 6,
                   "position": proximity_origin, "rotation": 0.26782724261283875,
                   "active_type": 0, "sense": 1, "sense_range": 14, "wandering_range": 6,
                   "level_adjusted_range": 14.0 - 1.53 ** 3.0},
               "proximity_route": proximity_route, "proximity_route_length": 17,
               "proximity_witness_position": [proximity_origin[0] + 30,
                                                proximity_origin[1], proximity_origin[2]]}
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


@pytest.mark.parametrize("patch", [{"action": 10}, {"level": 3}, {"base_exp": 50},
    {"required_cumulative_exp": 1999}, {"level_thresholds": [300, 600, 1099]},
    {"level_one_enemy_exp": 49},
    {"minimum_level_one_defeats": 39}, {"level_fourteen_enemy_exp": 114},
    {"minimum_level_fourteen_defeats": 17}])
def test_combat_catalog_rejects_combo_prerequisite_mismatch(profile, patch):
    from pathlib import Path
    from .support.catalog import validate_combat_catalog
    from .support.worker import WorkerError
    path = Path(profile["combat_catalog"])
    data = json.loads(path.read_text())
    data["first_fast_blade_combo"] = {**data["first_fast_blade_combo"], **patch}
    with pytest.raises(WorkerError, match="combo prerequisite"):
        validate_combat_catalog(data)


def test_combat_catalog_rejects_high_level_enemy_reward_mismatch(profile):
    from pathlib import Path
    from .support.catalog import validate_combat_catalog
    from .support.worker import WorkerError
    data = json.loads(Path(profile["combat_catalog"]).read_text())
    data["representative_high_level_enemy"]["base_exp"] = 114
    with pytest.raises(WorkerError, match="high-level enemy reward"):
        validate_combat_catalog(data)


def test_preflight_checks_all_inputs_without_gameplay(profile):
    result, identities = run_ci.preflight(profile, suffix=".exe")
    assert result == profile
    assert set(identities["binaries"]) == {"api", "lobby", "server", "dbm"}
    assert set(identities["meshes"]) == {"w1t1", "w1f2"}


def test_private_profile_inspector_is_read_only_and_discloses_no_paths(profile, tmp_path):
    path = tmp_path / "profile.json"; path.write_text(json.dumps(profile))
    before = path.read_bytes()
    proof = inspect_ci_profile(path, suffix=".exe")
    assert path.read_bytes() == before and proof["scope"] == CI_PROFILE_SCOPE
    assert proof["required_path_key_count"] == len(run_ci.PATH_KEYS)
    assert proof["catalog_count"] == len(run_ci.CATALOGS)
    assert proof["services_accounts_or_gameplay_started"] is False
    text = json.dumps(proof)
    assert str(tmp_path) not in text and proof["private_paths_disclosed"] is False


@pytest.mark.parametrize("mutation", ["unknown","missing","deadline","unavailable"])
def test_private_profile_inspector_rejects_unsafe_or_incomplete_input(profile, tmp_path, mutation):
    if mutation == "unknown": profile["database_password"] = "PRIVATE_MARKER"
    elif mutation == "missing": profile.pop("opening_quest_catalog")
    elif mutation == "deadline": profile["deadline_scale"] = True
    else: profile["worker"] = str(tmp_path / "PRIVATE_MARKER-missing-worker")
    path = tmp_path / "profile.json"; path.write_text(json.dumps(profile))
    with pytest.raises(SetupError) as raised:
        inspect_ci_profile(path, suffix=".exe")
    if mutation in {"unknown","unavailable"}:
        assert "PRIVATE_MARKER" not in str(raised.value)


def test_private_profile_inspector_rejects_duplicate_keys(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text('{"worker":"first","worker":"second"}')
    with pytest.raises(SetupError, match="cannot read"):
        inspect_ci_profile(path, suffix=".exe")


def test_private_profile_inspector_rejects_symlink(profile, tmp_path):
    target = tmp_path / "target.json"; target.write_text(json.dumps(profile))
    link = tmp_path / "profile.json"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("profile symlinks are unavailable on this host")
    with pytest.raises(SetupError, match="cannot read"):
        inspect_ci_profile(link, suffix=".exe")


def _clean_staging_git(monkeypatch, revision="a" * 40, dirty=False):
    def check_output(args, **_):
        if args[1:] == ["rev-parse", "HEAD"]: return revision + "\n"
        if args[1:] == ["status", "--porcelain"]: return " M private\n" if dirty else ""
        raise AssertionError(args)
    monkeypatch.setattr(environment_support.subprocess, "check_output", check_output)


def test_service_free_profile_staging_binds_manifest_and_removes_runtime(
        profile, tmp_path, monkeypatch):
    revision = "a" * 40; _clean_staging_git(monkeypatch, revision)
    path = tmp_path / "profile.json"; path.write_text(json.dumps(profile))
    private = (tmp_path / "private-stage").resolve()
    proof = stage_ci_profile(path, private, revision, suffix=".exe")
    assert proof["scope"] == CI_STAGING_SCOPE
    assert proof["process_start_count"] == proof["process_teardown_count"] == 0
    assert proof["runtime_and_disposable_root_absent"] is True
    assert proof["services_database_accounts_or_gameplay_started"] is False
    assert len(list(private.iterdir())) == 1 and str(tmp_path) not in json.dumps(proof)


def test_service_free_profile_staging_rejects_preexisting_private_root(profile, tmp_path):
    path = tmp_path / "profile.json"; path.write_text(json.dumps(profile))
    private = tmp_path / "existing"; private.mkdir()
    with pytest.raises(SetupError, match="new absolute"):
        stage_ci_profile(path, private.resolve(), "a" * 40, suffix=".exe")


def test_service_free_profile_staging_rejects_dirty_source_and_still_removes_runtime(
        profile, tmp_path, monkeypatch):
    _clean_staging_git(monkeypatch, dirty=True)
    path = tmp_path / "profile.json"; path.write_text(json.dumps(profile))
    private = (tmp_path / "private-stage").resolve()
    with pytest.raises(SetupError, match="clean source/profile"):
        stage_ci_profile(path, private, "a" * 40, suffix=".exe")
    artifact = next(private.iterdir())
    runtime = Path(json.loads((artifact / "manifest.json").read_text())["runtime"])
    assert not runtime.exists() and not runtime.parent.exists()


def test_service_free_profile_staging_rejects_terminal_cleanup_marker(
        profile, tmp_path, monkeypatch):
    _clean_staging_git(monkeypatch)
    original = environment_support.Environment.close
    def close_with_terminal_marker(environment):
        original(environment)
        retained = environment.artifacts / "retained"; retained.mkdir()
        (retained / "Cleanup-Failure.JSON").write_text("{}")
    monkeypatch.setattr(environment_support.Environment, "close", close_with_terminal_marker)
    path = tmp_path / "profile.json"; path.write_text(json.dumps(profile))
    private = (tmp_path / "private-stage").resolve()
    with pytest.raises(SetupError, match="terminal cleanup failure"):
        stage_ci_profile(path, private, "a" * 40, suffix=".exe")


def test_service_free_profile_staging_rejects_foreign_sibling_after_cleanup(
        profile, tmp_path, monkeypatch):
    _clean_staging_git(monkeypatch)
    original = environment_support.Environment.stage
    def stage_with_foreign_sibling(environment):
        original(environment)
        (environment.artifacts.parent / "foreign").write_text("not owned")
    monkeypatch.setattr(environment_support.Environment, "stage", stage_with_foreign_sibling)
    path = tmp_path / "profile.json"; path.write_text(json.dumps(profile))
    private = (tmp_path / "private-stage").resolve()
    with pytest.raises(SetupError, match="ambiguous or foreign"):
        stage_ci_profile(path, private, "a" * 40, suffix=".exe")
    artifact = next(entry for entry in private.iterdir() if entry.is_dir())
    runtime = Path(json.loads((artifact / "manifest.json").read_text())["runtime"])
    assert not runtime.exists() and not runtime.parent.exists()


@pytest.mark.parametrize("scale", [True, 0, 4, 1.5])
def test_preflight_rejects_unbounded_deadline_scale(profile, scale):
    profile["deadline_scale"] = scale
    with pytest.raises(run_ci.PreflightError, match="deadline_scale"):
        run_ci.preflight(profile, suffix=".exe")


def test_preflight_accepts_bounded_deadline_scale(profile):
    profile["deadline_scale"] = 3
    result, _ = run_ci.preflight(profile, suffix=".exe")
    assert result["deadline_scale"] == 3


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


@pytest.mark.parametrize("field", [None, "revision", "dirty", "fixture", "profile", "deadline",
    "worker", "binaries", "scripts", "catalog", "mesh", "missing"])
def test_public_identities_must_match_staged_inputs(profile, field):
    _, expected = run_ci.preflight(profile, suffix=".exe")
    manifest = {"revision":"a" * 40,"dirty":False,"profile":"sapphire-3.3",
                "fixture_version":2,"deadline_scale":1,
                "worker_sha256": expected["worker"], "binaries": dict(expected["binaries"]),
                "scripts": {"fixture.dll": expected["script_modules"][0]},
                "server_navigation": {f"{name}/{name}.nav": digest for name, digest in expected["meshes"].items()},
                **{key: {"sha256": digest} for key, digest in expected["catalogs"].items()}}
    if field == "revision": manifest["revision"] = "b" * 40
    elif field == "dirty": manifest["dirty"] = 0
    elif field == "fixture": manifest["fixture_version"] = True
    elif field == "profile": manifest["profile"] = "foreign"
    elif field == "deadline": manifest["deadline_scale"] = True
    elif field == "worker":
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
    assert run_ci.inputs_match(expected, manifest, "a" * 40, False, 1) is (field is None)


def lifecycle_rows():
    starts = [{"process":name,"generation":1,"pid":index + 10}
              for index, name in enumerate(("database", "api", "lobby", "world"))]
    teardowns = [{**row,"was_running_before_cleanup":True,
        "terminate_requested":True,"kill_requested":False,"exit_observed":True,
        "returncode":0,
        "scope":"exact-owned-isolated-process-teardown-not-graceful-server-exit"}
        for row in reversed(starts)]
    return starts, teardowns


def write_lifecycle(environment):
    environment.artifacts.mkdir(parents=True, exist_ok=True)
    (environment.artifacts / "process-lifecycle.json").write_text(json.dumps({
        "version":1,
        "scope":"exact-owned-isolated-process-teardown-not-graceful-server-exit",
        "starts":environment.process_starts,"teardowns":environment.process_teardowns}))


def write_environment_identity(environment):
    environment.artifacts.mkdir(parents=True, exist_ok=True)
    (environment.artifacts / "manifest.json").write_text(json.dumps({
        "database":environment.db_name,"runtime":str(environment.runtime),
        "ports":{"database":environment.db_port,"api":environment.api_port,
                 "lobby":environment.lobby_port,"world":environment.zone_port}}))


def complete_gate(tmp_path):
    gate = run_ci.EvidenceGate()
    gate.collected = list(run_ci.CASES)
    for index, case in enumerate(run_ci.CASES):
        starts, teardowns = lifecycle_rows()
        root = tmp_path / f"removed-{index}"
        environment = SimpleNamespace(_closed=True, root=root, runtime=root / "runtime", processes={},
            artifacts=tmp_path / f"process-evidence-{index}",
            db_name="sapphire_e2e_" + format(index,"032x"), db_port=10000 + index * 4,
            api_port=10001 + index * 4, lobby_port=10002 + index * 4,
            zone_port=10003 + index * 4, process_starts=starts, process_teardowns=teardowns)
        write_lifecycle(environment)
        write_environment_identity(environment)
        gate.environments.append(environment)
        gate.case_environments[case] = environment
        gate.environment = environment
        for when in ("setup", "call", "teardown"):
            gate.pytest_runtest_logreport(SimpleNamespace(nodeid=case, when=when, outcome="passed",
                                                        longrepr="PRIVATE_MARKER"))
    return gate


def test_report_is_allowlisted_and_requires_actual_reports(tmp_path):
    gate = complete_gate(tmp_path)
    report = gate.summary(0)
    assert report["status"] == "passed" and all(report["cases"].values())
    assert report["environment_isolation_verified"]
    assert [row["case"] for row in report["environment_evidence"]] == list(run_ci.CASES)
    assert len({row["manifest_sha256"] for row in report["environment_evidence"]}) == len(run_ci.CASES)
    assert report["cleanup_verified"] and report["process_cleanup_verified"]
    assert "PRIVATE_MARKER" not in json.dumps(report)
    assert run_ci.EvidenceGate().summary(0)["status"] == "failed"


def test_report_requires_cleanup_of_every_case_environment(tmp_path):
    gate = complete_gate(tmp_path)
    retained = tmp_path / "retained"
    retained.mkdir()
    gate.environments[0].root = retained
    assert gate.summary(0)["cleanup_verified"] is False
    retained.rmdir()
    assert gate.summary(0)["cleanup_verified"] is True


def test_report_requires_one_distinct_environment_per_exact_case(tmp_path):
    gate = complete_gate(tmp_path)
    first, second = run_ci.CASES[:2]
    gate.case_environments[second] = gate.case_environments[first]
    report = gate.summary(0)
    assert report["status"] == "failed"
    assert report["environment_isolation_verified"] is False
    gate = complete_gate(tmp_path / "missing")
    gate.case_environments.pop(first)
    assert gate.summary(0)["environment_isolation_verified"] is False


@pytest.mark.parametrize("mutation", ["root","artifacts","nested","database","runtime","ports","manifest"])
def test_report_rejects_shared_or_mismatched_private_fixture_identity(tmp_path, mutation):
    gate = complete_gate(tmp_path)
    first, second = gate.environments[:2]
    if mutation == "root": second.root = first.root
    elif mutation == "artifacts": second.artifacts = first.artifacts
    elif mutation == "nested": second.artifacts = second.root / "evidence"
    elif mutation == "database": second.db_name = first.db_name
    elif mutation == "runtime": second.runtime = second.root / "other"
    elif mutation == "ports": second.api_port = second.db_port
    else:
        manifest = json.loads((second.artifacts / "manifest.json").read_text())
        manifest["ports"]["world"] += 1
        (second.artifacts / "manifest.json").write_text(json.dumps(manifest))
    report = gate.summary(0)
    assert report["status"] == "failed"
    assert report["environment_isolation_verified"] is False


@pytest.mark.parametrize("mutation", ["skip", "missing", "duplicate", "foreign",
    "collection", "cleanup", "process", "teardown", "typed_teardown", "exit"])
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
    elif mutation == "teardown":
        gate.environment.process_teardowns.pop()
    elif mutation == "typed_teardown":
        gate.environment.process_teardowns[0]["returncode"] = True
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
        manifest = {"revision":"a" * 40,"dirty":False,"profile":"sapphire-3.3",
                    "fixture_version":2,"deadline_scale":1,
                    "worker_sha256": identities["worker"], "binaries": identities["binaries"],
                    "scripts": {"fixture.dll": identities["script_modules"][0]},
                    "server_navigation": {f"{key}/{key}.nav": value for key, value in identities["meshes"].items()},
                    **{key: {"sha256": value} for key, value in identities["catalogs"].items()}}
        for index, environment in enumerate(gate.environments):
            artifacts = tmp_path / f"staged-evidence-{index}"
            artifacts.mkdir()
            (artifacts / "manifest.json").write_text(json.dumps({**manifest,
                "database":environment.db_name,"runtime":str(environment.runtime),
                "ports":{"database":environment.db_port,"api":environment.api_port,
                         "lobby":environment.lobby_port,"world":environment.zone_port}}))
            environment.artifacts = artifacts
            write_lifecycle(environment)
        plugins[0].__dict__.update(gate.__dict__)
        junit_index = args.index("--junitxml")
        Path(args[junit_index + 1]).write_text(junit_document(run_ci.CASES))
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
    proof = inspect_ci_failure_result(public, "a" * 40)
    assert proof["gate_status"] == "failed" and proof["success_evidence_accepted"] is False
    assert "PRIVATE_MARKER" in next(private.glob("*/entry-error.log")).read_text()
    assert source.read_text() == '{"example": "PRIVATE_MARKER"}'
    with pytest.raises(run_ci.PreflightError, match="fresh"):
        run_ci.run(source, private, public)


def junit_document(cases, *, failing=False, foreign_first=False):
    rows = []
    for index, case in enumerate(cases):
        path, name = case.split("::", 1)
        if index == 0 and foreign_first:
            name += "_foreign"
        failure = "<failure />" if index == 0 and failing else ""
        rows.append(f'<testcase classname="{path[:-3].replace("/", ".")}" name="{name}">{failure}</testcase>')
    return "<testsuites><testsuite>" + "".join(rows) + "</testsuite></testsuites>"


def current_public_summary(revision="a" * 40):
    identities = {"worker":"1" * 64,
        "binaries":{key:str(index) * 64 for index,key in enumerate(("api","lobby","server","dbm"),2)},
        "catalogs":{key:format(index + 6,"x") * 64 for index,key in enumerate(run_ci.CATALOGS)},
        "meshes":{"w1t1":"e" * 64,"w1f2":"f" * 64},
        "script_modules":["0" * 64,"a" * 64]}
    evidence = [{"case":case,"manifest_sha256":format(index + 1,"064x"),
                 "lifecycle_sha256":"f" * 64,
                 "artifact_tree_sha256":format(index + 32,"064x")}
                for index,case in enumerate(run_ci.CASES)]
    return {"version":1,"status":"passed","stage":"verified",
        "scope":"headless-live-not-real-client","revision":revision,"source_dirty":False,
        "identities":identities,"deadline_scale":1,"collection_verified":True,
        "environment_isolation_verified":True,"environment_evidence":evidence,
        "gate_diagnostics_sha256":"e" * 64,
        "private_test_artifacts":{"profile_sha256":"b" * 64,
                                  "pytest_log_sha256":"c" * 64,"junit_sha256":"d" * 64},
        "cleanup_verified":True,"process_cleanup_verified":True,
        "cases":{case:True for case in run_ci.CASES},"pytest_exit_code":0,
        "inputs_verified":True}


def private_gate_evidence(tmp_path, report):
    root = tmp_path / "private-run"; artifacts = root / "artifacts"; artifacts.mkdir(parents=True)
    rows, directories = [], []
    for index, case in enumerate(run_ci.CASES):
        directory = artifacts / f"sapphire-e2e-{index:02d}"; directory.mkdir(); directories.append(directory)
        manifest = {"revision":report["revision"],"dirty":False,"profile":"sapphire-3.3",
            "fixture_version":2,"deadline_scale":report["deadline_scale"],
            "database":"sapphire_e2e_" + format(index,"032x"),
            "runtime":str((tmp_path / f"owned-{index}" / "runtime").resolve()),
            "ports":{"database":10000 + index*4,"api":10001 + index*4,
                     "lobby":10002 + index*4,"world":10003 + index*4},
            "worker_sha256":report["identities"]["worker"],
            "binaries":report["identities"]["binaries"],
            "scripts":{f"module-{offset}":digest for offset,digest in enumerate(
                report["identities"]["script_modules"])},
            "server_navigation":{f"{name}/{name}.nav":digest
                for name,digest in report["identities"]["meshes"].items()},
            **{key:{"sha256":digest} for key,digest in report["identities"]["catalogs"].items()}}
        starts, teardowns = lifecycle_rows()
        lifecycle = {"version":1,
            "scope":"exact-owned-isolated-process-teardown-not-graceful-server-exit",
            "starts":starts,"teardowns":teardowns}
        manifest_path = directory / "manifest.json"
        lifecycle_path = directory / "process-lifecycle.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))
        lifecycle_path.write_text(json.dumps(lifecycle, indent=2))
        if case == REJECTED_CREDENTIALS_CASE:
            (directory / "rejected-credentials.json").write_text(json.dumps({
                "version":1,"scope":PRODUCER_HTTP_RECEIPT_SCOPE,"method":"login",
                "expected_status":400,"received_status":400,"response_bytes":24,
                "response_sha256":"9" * 64,"session_returned":False}, indent=2))
        if case == FAULT_CASE:
            world = next(row for row in teardowns if row["process"] == "world")
            world_path = directory / "world.log"; world_path.write_text("redacted world fault log\n")
            failure = {"version":1,"classification":"intentional_owned_process_exit",
                "process":"world","generation":world["generation"],"pid":world["pid"],
                "returncode":world["returncode"],"log":"world.log","cleanup_required":True}
            (directory / "process-failure.json").write_text(json.dumps(failure, indent=2))
            proof = {key:failure[key] for key in
                     ("classification","process","generation","pid","returncode")}
            proof.update(world_log_sha256=hashlib.sha256(world_path.read_bytes()).hexdigest(),
                manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                lifecycle_sha256=hashlib.sha256(lifecycle_path.read_bytes()).hexdigest(),
                runtime_removed=True,secrets_absent_from_published_logs=True,
                scope=PRODUCER_FAULT_SCOPE)
            (directory / "fault-diagnostics-verification.json").write_text(
                json.dumps(proof, indent=2))
        rows.append({"case":case,
            "manifest_sha256":hashlib.sha256((directory / "manifest.json").read_bytes()).hexdigest(),
            "lifecycle_sha256":hashlib.sha256((directory / "process-lifecycle.json").read_bytes()).hexdigest(),
            "artifact_tree_sha256":artifact_tree_sha256(directory)})
    report["environment_evidence"] = rows
    diagnostics = {"collected":list(run_ci.CASES),
        "reports":{case:{phase:["passed"] for phase in ("setup","call","teardown")}
                   for case in run_ci.CASES},
        "unexpected":0,"environment_count":len(run_ci.CASES),
        "case_environment_count":len(run_ci.CASES),"environment_evidence":rows}
    profile = {key:str((tmp_path / "inputs" / key).resolve()) for key in run_ci.PATH_KEYS}
    profile.update(artifacts=str(artifacts.resolve()), deadline_scale=report["deadline_scale"])
    profile_path = root / "profile.json"; profile_path.write_text(json.dumps(profile))
    diagnostics_path = root / "gate-diagnostics.json"
    diagnostics_path.write_text(json.dumps(diagnostics, indent=2))
    report["gate_diagnostics_sha256"] = hashlib.sha256(diagnostics_path.read_bytes()).hexdigest()
    pytest_path = root / "pytest.log"; pytest_path.write_text(f"{len(run_ci.CASES)} passed\n")
    junit_path = root / "live.xml"
    junit_path.write_text(junit_document(run_ci.CASES))
    report["private_test_artifacts"] = {
        "profile_sha256":hashlib.sha256(profile_path.read_bytes()).hexdigest(),
        "pytest_log_sha256":hashlib.sha256(pytest_path.read_bytes()).hexdigest(),
        "junit_sha256":hashlib.sha256(junit_path.read_bytes()).hexdigest()}
    return root, directories


def rehash_private_row(report, directory, index):
    report["environment_evidence"][index].update(
        manifest_sha256=hashlib.sha256((directory / "manifest.json").read_bytes()).hexdigest(),
        lifecycle_sha256=hashlib.sha256((directory / "process-lifecycle.json").read_bytes()).hexdigest(),
        artifact_tree_sha256=artifact_tree_sha256(directory))


def sync_private_diagnostics(report, private):
    path = private / "gate-diagnostics.json"
    value = json.loads(path.read_text())
    value["environment_evidence"] = report["environment_evidence"]
    path.write_text(json.dumps(value, indent=2))
    report["gate_diagnostics_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()


def test_public_result_consumer_allowlists_require_explicit_producer_sync():
    assert EXPECTED_CASES == run_ci.CASES
    assert EXPECTED_CATALOGS == run_ci.CATALOGS


def test_fault_producer_and_independent_consumers_require_explicit_schema_sync():
    assert PRODUCER_FAULT_CLASSIFICATION == PRIVATE_FAULT_CLASSIFICATION \
        == STANDALONE_FAULT_CLASSIFICATION
    assert PRODUCER_FAULT_SCOPE == PRIVATE_FAULT_SCOPE == STANDALONE_FAULT_SCOPE
    assert PRODUCER_HTTP_RECEIPT_SCOPE == PRIVATE_HTTP_RECEIPT_SCOPE \
        == STANDALONE_HTTP_RECEIPT_SCOPE
    assert FAULT_CASE in run_ci.CASES and REJECTED_CREDENTIALS_CASE in run_ci.CASES


def test_current_public_result_inspector_is_strict_read_only_and_cli_matches(tmp_path, capsys):
    revision = "a" * 40
    path = tmp_path / "summary.json"
    path.write_text(json.dumps(current_public_summary(revision), indent=2))
    before = path.read_bytes()
    proof = inspect_ci_result(path, revision)
    assert path.read_bytes() == before
    assert proof["scope"] == CI_RESULT_SCOPE and proof["case_count"] == len(run_ci.CASES)
    assert inspect_ci_main(["--summary",str(path),"--expected-revision",revision]) == 0
    assert json.loads(capsys.readouterr().out) == proof


@pytest.mark.parametrize("shape", ["preflight","preflight-source","suite","verification"])
def test_failed_publication_inspector_accepts_only_sanitized_failure_shapes(tmp_path, capsys, shape):
    revision = "a" * 40
    full = current_public_summary(revision)
    full.update(status="failed", stage="verification", cleanup_verified=False)
    if shape == "verification":
        report = full
    elif shape == "suite":
        report = {key:full[key] for key in
                  ("version","status","scope","revision","source_dirty","identities","deadline_scale")}
        report["stage"] = "suite"
    elif shape == "preflight-source":
        report = {key:full[key] for key in
                  ("version","status","scope","revision","source_dirty","identities","deadline_scale")}
        report["stage"] = "preflight"
    else:
        report = {"version":1,"status":"failed","stage":"preflight",
                  "scope":"headless-live-not-real-client"}
    path = tmp_path / f"{shape}.json"; path.write_text(json.dumps(report))
    before = path.read_bytes()
    proof = inspect_ci_failure_result(path, revision)
    assert path.read_bytes() == before and proof["scope"] == CI_FAILURE_SCOPE
    assert proof["success_evidence_accepted"] is False and proof["gate_status"] == "failed"
    assert inspect_ci_failure_main(["--summary",str(path),"--expected-revision",revision]) == 0
    assert json.loads(capsys.readouterr().out) == proof


@pytest.mark.parametrize("mutation", ["passed","foreign","secret","dirty","partial-gate",
                                      "partial-artifacts","no-failed-outcome","bad-revision"])
def test_failed_publication_inspector_rejects_unsafe_or_success_shapes(tmp_path, mutation):
    report = current_public_summary(); report.update(status="failed", stage="verification",
                                                      cleanup_verified=False)
    expected = "a" * 40
    if mutation == "passed": report["status"] = "passed"
    elif mutation == "foreign": report["stage"] = "unknown"
    elif mutation == "secret": report["private_path"] = "C:/private/credential"
    elif mutation == "dirty": report["source_dirty"] = True
    elif mutation == "partial-gate": report.pop("cases")
    elif mutation == "partial-artifacts": report["private_test_artifacts"].pop("profile_sha256")
    elif mutation == "no-failed-outcome": report["cleanup_verified"] = True
    else: expected = "b" * 40
    path = tmp_path / "failed.json"; path.write_text(json.dumps(report))
    with pytest.raises(SetupError):
        inspect_ci_failure_result(path, expected)


def test_private_gate_evidence_inspector_correlates_all_cases_read_only(tmp_path, capsys):
    revision = "a" * 40
    report = current_public_summary(revision)
    private, directories = private_gate_evidence(tmp_path, report)
    summary = tmp_path / "summary.json"; summary.write_text(json.dumps(report, indent=2))
    files = [summary, private / "profile.json", private / "gate-diagnostics.json", private / "pytest.log",
             private / "live.xml", *[file for path in directories
                                      for file in path.rglob("*") if file.is_file()]]
    before = {path:hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    proof = inspect_ci_private_evidence(summary, private, revision)
    assert before == {path:hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    assert proof["scope"] == CI_PRIVATE_SCOPE and proof["case_count"] == len(run_ci.CASES)
    assert proof["fault_evidence_verified"] is True
    assert proof["rejected_credentials_evidence_verified"] is True
    assert proof["runtime_absence_verified"] is True
    assert proof["profile_schema_verified"] is True
    text = json.dumps(proof)
    assert str(private) not in text and "sapphire_e2e_" not in text
    assert inspect_ci_private_main(["--summary",str(summary),"--private-run-dir",str(private),
                                    "--expected-revision",revision]) == 0
    assert json.loads(capsys.readouterr().out) == proof


def standalone_case_files(tmp_path, report):
    _, directories = private_gate_evidence(tmp_path, report)
    case = run_ci.CASES[0]
    junit = tmp_path / "standalone.xml"; junit.write_text(junit_document([case]))
    log = tmp_path / "standalone.log"; log.write_text("1 passed\n")
    return case, directories[0], junit, log


def test_standalone_isolated_case_inspector_binds_runner_fixture_and_cleanup(tmp_path, capsys):
    revision = "a" * 40
    case, artifact, junit, log = standalone_case_files(tmp_path, current_public_summary(revision))
    files = [junit,log,*[path for path in artifact.rglob("*") if path.is_file()]]
    before = {path:hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    proof = inspect_isolated_case(artifact, junit, log, case, revision)
    assert before == {path:hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    assert proof["scope"] == ISOLATED_CASE_SCOPE and proof["case"] == case
    assert proof["sanitized_scenario_receipt_verified"] is True
    assert proof["scenario_semantics_independently_verified"] is False
    assert proof["private_paths_ports_database_or_pids_disclosed"] is False
    text = json.dumps(proof)
    assert str(artifact) not in text and "sapphire_e2e_" not in text
    assert inspect_isolated_case_main(["--artifact-dir",str(artifact),"--junit",str(junit),
        "--pytest-log",str(log),"--expected-case",case,"--expected-revision",revision]) == 0
    assert json.loads(capsys.readouterr().out) == proof


@pytest.mark.parametrize("mutation", ["foreign-case","junit-case","junit-failure","runtime",
                                      "lifecycle","revision","http-receipt","cleanup-failure",
                                      "nested-cleanup-failure","missing-log"])
def test_standalone_isolated_case_inspector_rejects_foreign_or_incomplete_evidence(
        tmp_path, mutation):
    case, artifact, junit, log = standalone_case_files(tmp_path, current_public_summary())
    expected = case
    if mutation == "foreign-case": expected = "tests/e2e/test_live.py::foreign"
    elif mutation == "junit-case": junit.write_text(junit_document([case], foreign_first=True))
    elif mutation == "junit-failure": junit.write_text(junit_document([case], failing=True))
    elif mutation == "runtime":
        Path(json.loads((artifact / "manifest.json").read_text())["runtime"]).mkdir(parents=True)
    elif mutation == "lifecycle":
        path = artifact / "process-lifecycle.json"; value = json.loads(path.read_text())
        value["teardowns"][0]["returncode"] = True; path.write_text(json.dumps(value))
    elif mutation == "revision":
        path = artifact / "manifest.json"; value = json.loads(path.read_text())
        value["revision"] = "b" * 40; path.write_text(json.dumps(value))
    elif mutation == "http-receipt":
        path = artifact / "rejected-credentials.json"; value = json.loads(path.read_text())
        value["session_returned"] = True; path.write_text(json.dumps(value))
    elif mutation == "cleanup-failure":
        (artifact / "cleanup-failure.json").write_text("{}")
    elif mutation == "nested-cleanup-failure":
        nested = artifact / "retained"; nested.mkdir()
        (nested / "Cleanup-Failure.JSON").write_text("{}")
    else: log.unlink()
    with pytest.raises(SetupError):
        inspect_isolated_case(artifact, junit, log, expected, "a" * 40)


def cleanup_failure_files(tmp_path):
    root = tmp_path / "cleanup-artifact"; root.mkdir()
    marker = {
        "version":1,"classification":"owned_process_cleanup_incomplete",
        "services":["world"],"runtime_retained":True,
        "retry_policy":"exact-process-poll-only-no-second-termination"}
    starts = [{"process":name,"generation":1,"pid":pid}
              for name,pid in zip(("database","api","lobby","world"), range(41,45))]
    teardowns = []
    for row in starts:
        unresolved = row["process"] == "world"
        teardowns.append({**row,"was_running_before_cleanup":True,
            "terminate_requested":True,"kill_requested":False,
            "exit_observed":not unresolved,"returncode":None if unresolved else -15,
            "scope":"exact-owned-isolated-process-teardown-not-graceful-server-exit"})
    lifecycle = {"version":1,
        "scope":"exact-owned-isolated-process-teardown-not-graceful-server-exit",
        "starts":starts,"teardowns":teardowns}
    (root / "cleanup-failure.json").write_text(json.dumps(marker))
    (root / "process-lifecycle.json").write_text(json.dumps(lifecycle))
    return root


def test_cleanup_failure_inspector_is_terminal_sanitized_and_read_only(tmp_path, capsys):
    root = cleanup_failure_files(tmp_path)
    proof = inspect_cleanup_failure(root)
    assert proof["status"] == "terminal-cleanup-failure"
    assert proof["services"] == ["world"]
    assert proof["current_lifecycle_complete"] is False
    assert proof["current_unresolved_generation_count"] == 1
    assert proof["success_evidence"] is False
    rendered = json.dumps(proof)
    assert str(root) not in rendered and '"pid"' not in rendered
    lifecycle = json.loads((root / "process-lifecycle.json").read_text())
    world = next(row for row in lifecycle["teardowns"] if row["process"] == "world")
    world.update(exit_observed=True, returncode=-1)
    (root / "process-lifecycle.json").write_text(json.dumps(lifecycle))
    recovered = inspect_cleanup_failure(root)
    assert recovered["current_lifecycle_complete"] is True
    assert recovered["current_unresolved_generation_count"] == 0
    assert recovered["status"] == "terminal-cleanup-failure"
    assert inspect_cleanup_failure_main(["--artifact-dir",str(root)]) == 0
    assert json.loads(capsys.readouterr().out) == recovered


def test_cleanup_failure_inspector_accepts_evidence_only_failure_without_lifecycle(tmp_path):
    root = tmp_path / "cleanup-artifact"; root.mkdir()
    marker = {"version":1,
        "classification":"owned_process_cleanup_evidence_incomplete",
        "services":[],"runtime_retained":True,
        "retry_policy":"exact-process-poll-only-no-second-termination"}
    (root / "cleanup-failure.json").write_text(json.dumps(marker))
    proof = inspect_cleanup_failure(root)
    assert proof["lifecycle_present"] is False
    assert proof["current_lifecycle_complete"] is None
    assert proof["owned_process_generation_count"] == 0
    assert proof["success_evidence"] is False


@pytest.mark.parametrize("mutation", ["classification","services","foreign-service","retry",
                                      "private-field","duplicate-key","foreign-teardown",
                                      "undeclared-uncertainty","typed-pid","relative-root"])
def test_cleanup_failure_inspector_rejects_malformed_or_foreign_evidence(tmp_path, mutation):
    root = cleanup_failure_files(tmp_path)
    marker_path = root / "cleanup-failure.json"
    lifecycle_path = root / "process-lifecycle.json"
    marker = json.loads(marker_path.read_text())
    lifecycle = json.loads(lifecycle_path.read_text())
    supplied = root
    if mutation == "classification": marker["classification"] = "success"
    elif mutation == "services": marker["services"] = []
    elif mutation == "foreign-service": marker["services"] = ["shell"]
    elif mutation == "retry": marker["retry_policy"] = "terminate-again"
    elif mutation == "private-field": marker["private_path"] = str(root)
    elif mutation == "duplicate-key":
        marker_path.write_text('{"version":1,"version":1}')
    elif mutation == "foreign-teardown": lifecycle["teardowns"][0]["pid"] += 100
    elif mutation == "undeclared-uncertainty":
        lifecycle["teardowns"][0].update(exit_observed=False, returncode=None)
    elif mutation == "typed-pid": lifecycle["starts"][0]["pid"] = True
    else: supplied = Path("cleanup-artifact")
    if mutation not in {"duplicate-key","relative-root"}:
        marker_path.write_text(json.dumps(marker))
        lifecycle_path.write_text(json.dumps(lifecycle))
    with pytest.raises(SetupError):
        inspect_cleanup_failure(supplied)


def test_standalone_isolated_fault_inspector_is_strict_sanitized_and_read_only(tmp_path, capsys):
    revision = "a" * 40
    report = current_public_summary(revision)
    _, directories = private_gate_evidence(tmp_path, report)
    artifact = directories[run_ci.CASES.index(FAULT_CASE)]
    junit = tmp_path / "fault.xml"; junit.write_text(junit_document([FAULT_CASE]))
    log = tmp_path / "pytest.log"; log.write_text("one fault case passed\n")
    files = [path for path in artifact.rglob("*") if path.is_file()]
    before = {path:hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    proof = inspect_isolated_fault(artifact, junit, log, revision)
    assert before == {path:hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    assert proof["scope"] == ISOLATED_FAULT_SCOPE
    assert proof["exact_world_teardown_correlated"] is True
    assert proof["exact_single_passing_junit_case"] is True
    assert proof["private_paths_ports_database_or_pids_disclosed"] is False
    text = json.dumps(proof)
    assert str(artifact) not in text and "sapphire_e2e_" not in text
    assert inspect_isolated_fault_main(
        ["--artifact-dir",str(artifact),"--junit",str(junit),
         "--pytest-log",str(log),"--expected-revision",revision]) == 0
    assert json.loads(capsys.readouterr().out) == proof


@pytest.mark.parametrize("mutation", ["classification","world-pid","runtime","proof-hash",
                                      "revision","foreign-field","junit-case",
                                      "junit-failure","cleanup-failure","pytest-log"])
def test_standalone_isolated_fault_inspector_rejects_foreign_or_incomplete_evidence(
        tmp_path, mutation):
    report = current_public_summary(); _, directories = private_gate_evidence(tmp_path, report)
    artifact = directories[run_ci.CASES.index(FAULT_CASE)]
    junit = tmp_path / "fault.xml"; junit.write_text(junit_document([FAULT_CASE]))
    log = tmp_path / "pytest.log"; log.write_text("one fault case passed\n")
    if mutation == "classification":
        path = artifact / "process-failure.json"
        value = json.loads(path.read_text()); value["classification"] = "organic_crash"
        path.write_text(json.dumps(value))
    elif mutation == "world-pid":
        path = artifact / "process-lifecycle.json"
        value = json.loads(path.read_text())
        next(row for row in value["teardowns"] if row["process"] == "world")["pid"] += 1
        path.write_text(json.dumps(value))
    elif mutation == "runtime":
        runtime = Path(json.loads((artifact / "manifest.json").read_text())["runtime"])
        runtime.mkdir(parents=True)
    elif mutation == "proof-hash":
        path = artifact / "fault-diagnostics-verification.json"
        value = json.loads(path.read_text()); value["world_log_sha256"] = "0" * 64
        path.write_text(json.dumps(value))
    elif mutation == "revision":
        path = artifact / "manifest.json"
        value = json.loads(path.read_text()); value["revision"] = "b" * 40
        path.write_text(json.dumps(value))
    elif mutation == "junit-case":
        junit.write_text(junit_document([FAULT_CASE], foreign_first=True))
    elif mutation == "junit-failure":
        junit.write_text(junit_document([FAULT_CASE], failing=True))
    elif mutation == "cleanup-failure":
        (artifact / "cleanup-failure.json").write_text("{}")
    elif mutation == "pytest-log":
        log.unlink()
    else:
        path = artifact / "process-failure.json"
        value = json.loads(path.read_text()); value["private_path"] = "C:/private"
        path.write_text(json.dumps(value))
    with pytest.raises(SetupError):
        inspect_isolated_fault(artifact, junit, log, "a" * 40)


@pytest.mark.parametrize("mutation", ["changed-bytes","missing","profile","pytest-log","junit","junit-case","diagnostics","lifecycle","inputs","database","fault-evidence","rejected-receipt","cleanup-failure","nested-cleanup-failure","runtime-retained"])
def test_private_gate_evidence_inspector_rejects_missing_foreign_or_invalid_private_bytes(
        tmp_path, mutation):
    report = current_public_summary(); private, directories = private_gate_evidence(tmp_path, report)
    target = directories[0]
    if mutation == "changed-bytes":
        with (target / "manifest.json").open("a") as stream: stream.write(" ")
    elif mutation == "missing":
        import shutil; shutil.rmtree(target)
    elif mutation == "profile":
        path = private / "profile.json"
        value = json.loads(path.read_text()); value["artifacts"] = str(tmp_path / "foreign")
        path.write_text(json.dumps(value))
        report["private_test_artifacts"]["profile_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    elif mutation == "pytest-log":
        with (private / "pytest.log").open("a") as stream: stream.write("changed")
    elif mutation in {"junit","junit-case"}:
        path = private / "live.xml"
        path.write_text(junit_document(run_ci.CASES, failing=mutation == "junit",
                                       foreign_first=mutation == "junit-case"))
        report["private_test_artifacts"]["junit_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    elif mutation == "diagnostics":
        path = private / "gate-diagnostics.json"
        value = json.loads(path.read_text()); value["reports"][run_ci.CASES[0]]["call"] = []
        path.write_text(json.dumps(value))
        report["gate_diagnostics_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    elif mutation == "lifecycle":
        value = json.loads((target / "process-lifecycle.json").read_text())
        value["teardowns"][0]["returncode"] = True
        (target / "process-lifecycle.json").write_text(json.dumps(value))
        rehash_private_row(report, target, 0)
    elif mutation == "inputs":
        value = json.loads((target / "manifest.json").read_text())
        value["worker_sha256"] = "0" * 64
        (target / "manifest.json").write_text(json.dumps(value))
        rehash_private_row(report, target, 0)
    elif mutation == "database":
        first = json.loads((directories[0] / "manifest.json").read_text())
        second = json.loads((directories[1] / "manifest.json").read_text())
        second["database"] = first["database"]
        (directories[1] / "manifest.json").write_text(json.dumps(second))
        rehash_private_row(report, directories[1], 1)
    elif mutation == "fault-evidence":
        index = run_ci.CASES.index(FAULT_CASE); target = directories[index]
        path = target / "fault-diagnostics-verification.json"
        value = json.loads(path.read_text()); value["scope"] = "forged scope"
        path.write_text(json.dumps(value))
        rehash_private_row(report, target, index)
    elif mutation == "rejected-receipt":
        index = run_ci.CASES.index(REJECTED_CREDENTIALS_CASE); target = directories[index]
        path = target / "rejected-credentials.json"
        value = json.loads(path.read_text()); value["received_status"] = 200
        path.write_text(json.dumps(value)); rehash_private_row(report, target, index)
    elif mutation in {"cleanup-failure","nested-cleanup-failure"}:
        marker_parent = target if mutation == "cleanup-failure" else target / "retained"
        marker_parent.mkdir(exist_ok=True)
        marker_name = "cleanup-failure.json" if mutation == "cleanup-failure" else "Cleanup-Failure.JSON"
        (marker_parent / marker_name).write_text("{}")
        rehash_private_row(report, target, 0)
    else:
        runtime = Path(json.loads((target / "manifest.json").read_text())["runtime"])
        runtime.mkdir(parents=True)
    if mutation in {"lifecycle","inputs","database","fault-evidence","rejected-receipt",
                    "cleanup-failure","nested-cleanup-failure"}:
        sync_private_diagnostics(report, private)
    summary = tmp_path / "summary.json"; summary.write_text(json.dumps(report))
    with pytest.raises(SetupError):
        inspect_ci_private_evidence(summary, private, "a" * 40)


@pytest.mark.parametrize("mutate", [
    lambda report:report.update(status="failed"),
    lambda report:report.update(stage="verification"),
    lambda report:report.update(source_dirty=0),
    lambda report:report.update(process_cleanup_verified=1),
    lambda report:report.update(environment_isolation_verified=1),
    lambda report:report.update(gate_diagnostics_sha256="g" * 64),
    lambda report:report.update(private_test_artifacts={"pytest_log_sha256":"a" * 64}),
    lambda report:report["private_test_artifacts"].update(profile_sha256="g" * 64),
    lambda report:report["private_test_artifacts"].update(junit_sha256="g" * 64),
    lambda report:report["environment_evidence"].pop(),
    lambda report:report["environment_evidence"].reverse(),
    lambda report:report["environment_evidence"][0].update(manifest_sha256="g" * 64),
    lambda report:report["environment_evidence"][0].update(artifact_tree_sha256="g" * 64),
    lambda report:report["environment_evidence"][1].update(
        manifest_sha256=report["environment_evidence"][0]["manifest_sha256"]),
    lambda report:report["environment_evidence"][1].update(
        artifact_tree_sha256=report["environment_evidence"][0]["artifact_tree_sha256"]),
    lambda report:report.update(cleanup_verified=False),
    lambda report:report.update(deadline_scale=True),
    lambda report:report["cases"].pop(run_ci.CASES[0]),
    lambda report:report.update(cases=dict(reversed(list(report["cases"].items())))),
    lambda report:report["cases"].update({run_ci.CASES[0]:1}),
    lambda report:report["identities"]["binaries"].update(api="g" * 64),
    lambda report:report["identities"]["catalogs"].update(foreign="f" * 64),
    lambda report:report["identities"].update(script_modules=["a" * 64,"0" * 64]),
    lambda report:report.update(extra=True),
])
def test_current_public_result_inspector_rejects_partial_foreign_or_type_confused(
        tmp_path, mutate):
    report = current_public_summary(); mutate(report)
    path = tmp_path / "summary.json"; path.write_text(json.dumps(report))
    with pytest.raises(SetupError):
        inspect_ci_result(path, "a" * 40)


def test_current_public_result_inspector_rejects_wrong_revision_and_legacy_summary(tmp_path):
    path = tmp_path / "summary.json"
    report = current_public_summary()
    path.write_text(json.dumps(report))
    with pytest.raises(SetupError, match="incomplete, foreign or failed"):
        inspect_ci_result(path, "b" * 40)
    report.pop("process_cleanup_verified")
    path.write_text(json.dumps(report))
    with pytest.raises(SetupError, match="incomplete, foreign or failed"):
        inspect_ci_result(path, "a" * 40)

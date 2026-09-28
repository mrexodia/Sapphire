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
                                 "destinations": [{"id": 1, "territory": 141, "position": [0, 0, 0]}]}}
    Path(p["transition_catalog"]).write_text(json.dumps(transition))
    combat = {"version": 1, "profile": "sapphire-3.3", "action": 9, "class_job": 1,
              "work_index": 1, "level": 1, "base_exp": 50,
              "category": 3, "cost_type": 5, "cost": 60, "range": -1, "cast_ms": 0,
              "recast_ms": 2500, "recast_group": 58, "effect_type": 1, "target_enemy": True}
    Path(p["combat_catalog"]).write_text(json.dumps(combat))
    shop = {"version": 1, "profile": "sapphire-3.3", "territory": 130,
            "start_actor": 1001289, "navigation": nav,
            "route": [[0, 0, 0], [1, 0, 0]], "route_length": 1,
            "shop": {"layout_id": 3, "base_id": 4, "event_id": 262468, "position": [1, 0, 0]},
            "sale": {"item": 4551, "quantity": 1, "gil": 28},
            "purchase": {"shop_id": 262468, "index": 0, "item": 5890, "quantity": 1, "gil": 8}}
    Path(p["shop_catalog"]).write_text(json.dumps(shop))
    respawn = {"version": 1, "profile": "sapphire-3.3", "homepoint": 9, "territory": 130,
               "pop_range": {"id": 1, "position": [0, 0, 0], "rotation": [0, 0, 0]}}
    Path(p["respawn_catalog"]).write_text(json.dumps(respawn))
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

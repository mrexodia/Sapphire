import contextlib
import json
import sys
import types

import pytest

from .support.client_timing import ClientPhaseTiming


def test_phase_times_include_waits_and_cleanup_without_claiming_coverage():
    now = [100.0]
    timing = ClientPhaseTiming(clock=lambda: now[0])
    now[0] = 119.5
    timing.transition("spawn")
    now[0] = 1319.5  # Manual inactivity is wall time, not 20 minutes of gameplay.
    timing.transition("cleanup")
    now[0] = 1320
    result = timing.finish()
    assert result["elapsed_seconds"] == 1220
    assert result["phases"] == [dict(phase="setup", seconds=19.5),
                                dict(phase="spawn", seconds=1200),
                                dict(phase="cleanup", seconds=.5)]
    assert result["scope"].endswith("not-coverage")
    assert "status" not in result
    now[0] += 100
    assert timing.finish() == result  # No growth after finish.
    result["phases"][0]["seconds"] = -1
    assert timing.finish()["phases"][0]["seconds"] == 19.5
    with pytest.raises(RuntimeError, match="already finished"):
        timing.transition("development")


def test_optional_development_and_zero_length_phases():
    now = [0.0]
    timing = ClientPhaseTiming(clock=lambda: now[0])
    for phase in ("spawn", "movement", "say", "review", "development", "logout", "cleanup"):
        timing.transition(phase)
        now[0] += 1
    result = timing.finish()
    assert result["phases"][0] == dict(phase="setup", seconds=0)
    assert result["elapsed_seconds"] == sum(row["seconds"] for row in result["phases"]) == 7


@pytest.mark.parametrize("cleanup_failure", [False, True])
def test_guest_startup_failure_records_cleanup_time_and_terminal_status(tmp_path, monkeypatch, cleanup_failure):
    from . import run_client_smoke as guest
    inputs, output = tmp_path / "input", tmp_path / "output"
    inputs.mkdir(); output.mkdir()
    for name, value in (("source", {}), ("profile", {}), ("fixture", {"development_check": False})):
        (inputs / (name + ".json")).write_text(json.dumps(value))
    now = [100.0]
    closed = []
    class Environment:
        redactions = []
        root = tmp_path / "removed-runtime"
        process_starts = []
        process_teardowns = []
        def __init__(self, profile):
            self.artifacts = output / "environment"
            self.artifacts.mkdir()
        def start(self):
            now[0] = 105
            raise RuntimeError("synthetic startup failure")
        def close(self):
            closed.append(True)
            now[0] = 108
            if cleanup_failure:
                raise RuntimeError("synthetic cleanup failure")
            (self.artifacts / "process-lifecycle.json").write_text(json.dumps({
                "version": 1,
                "scope": "exact-owned-isolated-process-teardown-not-graceful-server-exit",
                "starts": [], "teardowns": []}))
    monkeypatch.setattr(guest, "INPUT", inputs); monkeypatch.setattr(guest, "OUTPUT", output)
    monkeypatch.setattr(guest, "require_guest", lambda: "synthetic guest")
    monkeypatch.setattr(guest, "verify_source", lambda *args: "synthetic revision")
    monkeypatch.setattr(guest, "sha256", lambda *args: guest.CLIENT_SHA256)
    monkeypatch.setattr(guest, "ClientPhaseTiming", lambda: ClientPhaseTiming(clock=lambda: now[0]))
    monkeypatch.setattr(guest, "Environment", Environment)
    monkeypatch.setattr(guest.shutil, "copytree", lambda *args: None)
    monkeypatch.setattr(guest.shutil, "copy2", lambda *args: None)
    monkeypatch.setattr(guest.subprocess, "run", lambda *args, **kwargs: None)
    monkeypatch.setitem(sys.modules, "PIL", types.SimpleNamespace(ImageGrab=None))
    monkeypatch.setitem(sys.modules, "winreg", types.SimpleNamespace(
        CreateKey=lambda *args: contextlib.nullcontext(), HKEY_CURRENT_USER=0, REG_DWORD=0,
        SetValueEx=lambda *args: None))
    assert guest.run() == 1 and closed == [True]
    result = json.loads((output / "result.json").read_text())
    status = json.loads((output / "status.json").read_text())
    assert result["failure_stage"] == "setup" and result["status"] == "failed"
    assert result["timing"]["phases"] == [dict(phase="setup", seconds=5), dict(phase="cleanup", seconds=3)]
    assert result["timing"]["elapsed_seconds"] == 8
    # A setup failure before all four exact process starts has no complete teardown
    # proof, even when the synthetic close call itself returns normally.
    assert result["cleanup_errors"] == ["isolated environment cleanup failed"]
    assert status["phase"] == "finished" and status["status"] == "failed"
    assert status["run"] == result["run"]

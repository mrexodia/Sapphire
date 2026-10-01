"""Guest-only manual real-client lane. Start via prepare_client_smoke, not on the host."""
from __future__ import annotations

import ctypes
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid

from .support.client_smoke import (CLIENT_SHA256, REAL_SAY, WITNESS_SAY, other_player,
                                   moved, validate_review)
from .support.environment import Environment, sha256, REPO
from .support.client_snapshot import verify_source
from .support.client_timing import ClientPhaseTiming
from .support.client_lifecycle import retire_witness
from .support.worker import Worker, Bot
from .support.development_worker_exit import ObservedWorker, unobserved_worker_exit
from .support.client_development import (development_profile, require_graphical_check,
                                         require_graphical_decline_check,
                                         require_graphical_logout_witness,
                                         require_graphical_run_pair,
                                         require_graphical_witness_handoff,
                                         run_graphical_development, run_graphical_decline)
from .support.development import authenticate, movement_route
from .run_development import run as run_development

INPUT = Path("C:/e2e-input")
OUTPUT = Path("C:/e2e-output")


def publish(name, value):
    temporary = OUTPUT / (name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temporary.replace(OUTPUT / (name + ".json"))


def require_guest():
    if os.name != "nt":
        raise RuntimeError("Windows Sandbox guest required")
    documents = ctypes.create_unicode_buffer(32768)
    if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, documents) != 0:
        raise RuntimeError("cannot resolve guest Documents")
    if not documents.value.startswith("C:\\Users\\WDAGUtilityAccount\\"):
        raise RuntimeError("refuse use of a host user's game settings")
    # This guard prevents accidents, not a security boundary. Use the generated WSB.
    return documents.value


def run():
    documents = require_guest()  # Before registry, files, processes or fixture setup.
    from PIL import ImageGrab
    import winreg

    report = {"version": 1, "run": uuid.uuid4().hex, "status": "failed",
              "scope": "manual-real-client-login-movement-say-logout",
              "documents": documents, "sandbox_disposal": "operator_required",
              "witness_retirements": [], "observer_worker_exit": unobserved_worker_exit()}
    env = client = None
    deadline = None
    timing = ClientPhaseTiming()
    stage = "setup"
    root = Path("C:/e2e-client")
    try:
        source_manifest = json.loads((INPUT / "source.json").read_text(encoding="utf-8"))
        report["source_revision"] = verify_source(REPO, source_manifest)
        report["source_manifest_sha256"] = sha256(INPUT / "source.json")
        if sha256(INPUT / "client" / "ffxiv_dx11.exe") != CLIENT_SHA256:
            raise ValueError("unsupported or modified client executable")
        report["client_sha256"] = CLIENT_SHA256
        # Guest-only prerequisites; no installed host executable/settings are edited.
        for path, name in [(r"Software\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled"),
                           (r"System\GameConfigStore", "GameDVR_Enabled")]:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as handle:
                winreg.SetValueEx(handle, name, 0, winreg.REG_DWORD, 0)
        shutil.copytree(INPUT / "client", root)  # Refuse reuse of an existing client root.
        if sha256(root / "ffxiv_dx11.exe") != CLIENT_SHA256:
            raise ValueError("guest client copy differs from verified input")
        shutil.copy2(root / "ffxivgame.ver", "C:/ffxivgame.ver")
        for name in ("sqpack", "movie"):
            subprocess.run(["cmd", "/c", "mklink", "/J", str(root / name), f"C:\\e2e-{name}"],
                           check=True, capture_output=True, timeout=10)
        for name in ("XAudio2_7.dll", "XactEngine3_7.dll"):
            subprocess.run(["C:/Windows/System32/regsvr32.exe", "/s", str(root / name)],
                           check=True, timeout=20)
        profile = json.loads((INPUT / "profile.json").read_text(encoding="utf-8"))
        profile["artifacts"] = str(OUTPUT / "artifacts")
        fixture = json.loads((INPUT / "fixture.json").read_text(encoding="utf-8"))
        development_enabled = fixture.get("development_check", False)
        if type(development_enabled) is not bool:
            raise ValueError("invalid graphical development opt-in")
        if development_enabled and sha256(Path(profile["quest_catalog"])) != fixture["catalog_sha256"]:
            raise ValueError("development corridor differs from prepared fixture catalog")
        env = Environment(profile)
        env.start()
        report["artifacts"] = str(env.artifacts)
        report["fixture"] = fixture
        report["development_check"] = {"requested": development_enabled, "status": "not_run"}
        report["decline_check"] = {"requested": development_enabled, "status": "not_run"}
        report["development_run_pair"] = {"requested": development_enabled, "verified": False}
        report["development_witness_handoff"] = {"requested": development_enabled,
                                                   "verified": False}
        report["logout_witness_restoration"] = {"requested": development_enabled,
                                                  "verified": False}
        with ObservedWorker(Worker(env.worker, env.artifacts / "observer", env.deadline_scale),
                            report["observer_worker_exit"]) as worker:
            witness = env.fresh_character(fixture["position"])
            real = env.fresh_character(fixture["position"])
            bot = Bot(worker, "witness")
            initial = bot.login_via_lobby(witness["auth"], witness["name"])
            if other_player(initial) is not None:
                raise ValueError("unexpected player before real-client launch")
            args = [str(root / "ffxiv_dx11.exe"), "DEV.TestSID=" + real["auth"]["sId"],
                    "DEV.UseSqPack=1", "DEV.DataPathType=1"]
            for i in range(1, 9):
                args += [f"DEV.LobbyHost0{i}=127.0.0.1", f"DEV.LobbyPort0{i}={env.lobby_port}"]
            args += ["SYS.Region=3", "language=1", "version=1.0.0.0",
                     "DEV.MaxEntitledExpansionID=1", "DEV.GMServerHost=127.0.0.1"]
            with (env.runtime / "real-client.log").open("w") as stream:
                client = subprocess.Popen(args, cwd=root, stdout=stream, stderr=subprocess.STDOUT)
            report.update(real_name=real["name"], witness_name=witness["name"], client_pid=client.pid)
            deadline = time.monotonic() + 1200
            report["activity_deadline"] = {
                "enabled": True, "limit_seconds": 1200, "expired": False,
                "activity_and_worker_exit_completed_within_budget": False,
                "scope": "cooperative-manual-activity-success-deadline-not-hard-cleanup-limit",
                "environment_cleanup_may_exceed_deadline": True}

            def phase(name, instruction):
                nonlocal stage
                stage = name
                timing.transition(name)
                publish("status", {"run": report["run"], "phase": name, "instruction": instruction,
                                   "real_name": real["name"], "client_pid": client.pid,
                                   "activity_budget_seconds": 1200,
                                   "activity_remaining_seconds_at_publication": max(0, deadline - time.monotonic())})

            def wait(predicate):
                while time.monotonic() < deadline:
                    env.check_alive()
                    if client.poll() is not None:
                        raise RuntimeError("real client exited before scenario completion")
                    state = worker.snapshot(bot.name)
                    if predicate(state):
                        report[stage] = state
                        return state
                    time.sleep(0.5)  # Manual-input polling, never an assertion of success.
                raise TimeoutError("manual scenario exceeded twenty-minute activity deadline")

            phase("spawn", "In the game, select the named fixture character and enter the world.")
            spawned = wait(lambda s: other_player(s) is not None)
            entity, actor = other_player(spawned)
            origin = actor["position"]
            if math.dist(origin, fixture["position"]) > 1:
                raise ValueError("unexpected fixture spawn position")
            report["real_entity"] = entity
            phase("movement", "Move the real character 1 to 5 metres using normal movement keys.")
            arrived = wait(lambda s: moved(origin, other_player(s, entity)[1]["position"]))
            report["observed_movement_metres"] = math.dist(origin, arrived["actors"][str(entity)]["position"])
            phase("say", f"Send this exact Say message in the real client: {REAL_SAY}")

            def said(state):
                other_player(state, entity)
                return any(row["actor"] == entity and row["message"] == REAL_SAY for row in state["chat"])

            wait(said)
            bot.say(WITNESS_SAY)
            time.sleep(2)  # Allow drawing; only the following MANUAL review certifies rendering.
            frame = OUTPUT / "review.png"
            ImageGrab.grab(all_screens=True).save(frame)
            ticket = {"run": report["run"], "frame_sha256": sha256(frame)}
            publish("review-ticket", ticket)
            phase("review", "Review fixture in world and rendered witness Say; see REAL_CLIENT.md.")

            def reviewed(state):
                other_player(state, entity)
                path = OUTPUT / "review.json"
                if not path.exists():
                    return False
                review = validate_review(json.loads(path.read_text(encoding="utf-8")), ticket)
                report["manual_review"] = review
                return True

            wait(reviewed)
            if development_enabled:
                phase("development", "Keep this graphical character in-world. For development and then development-decline, read each viewer-start.json/viewer-finish.json and send its reply_in_say manually. Do not logout until instructed.")
                if client.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError("graphical process/activity unavailable before bot scenario")
                # Reuse only the owned headless witness account, after ordinary closure.
                # The graphical viewer account is never passed to the normal runner.
                initial_witness_retirement = retire_witness(bot)
                report["witness_retirements"].append(initial_witness_retirement)
                # Read the validated prefix, never invent an offset for the second bot.
                route, _ = movement_route({"territory": 130, "quest_catalog": profile["quest_catalog"]})
                if time.monotonic() >= deadline:
                    raise TimeoutError("graphical activity expired before peer fixture setup")
                peer = env.fresh_character(route[-1])  # Administrative pre-connection fixture, not progression.
                shared = development_profile(env, witness, peer, real, profile["quest_catalog"])
                def bounded_login(config, account):
                    if time.monotonic() >= deadline:
                        raise TimeoutError("graphical activity expired before authentication")
                    auth = authenticate(config, account)
                    if time.monotonic() >= deadline:
                        raise TimeoutError("graphical activity expired during authentication")
                    return auth
                result = run_graphical_development(
                    run_development, shared, OUTPUT / "development", viewer_name=real["name"],
                    activity_deadline=deadline, login=bounded_login)
                report["development_check"] = {"requested": True, "status": result["status"],
                    "summary_sha256": sha256(OUTPUT / "development/development-summary.json"),
                    "elapsed_seconds": result["elapsed_seconds"]}
                proof = require_graphical_check(result, real["name"], entity)
                if client.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError("graphical process/activity unavailable after bot scenario")
                report["development_check"]["evidence"] = proof
                decline = run_graphical_decline(
                    run_development, shared, OUTPUT / "development-decline",
                    viewer_name=real["name"], activity_deadline=deadline, login=bounded_login)
                report["decline_check"] = {"requested": True, "status": decline["status"],
                    "summary_sha256": sha256(OUTPUT / "development-decline/development-summary.json"),
                    "elapsed_seconds": decline["elapsed_seconds"]}
                decline_proof = require_graphical_decline_check(
                    decline, real["name"], entity)
                if client.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError("graphical process/activity unavailable after decline scenario")
                report["decline_check"]["evidence"] = decline_proof
                run_pair = require_graphical_run_pair(
                    result, decline, [account["character"] for account in shared["accounts"]],
                    sha256(env.worker))
                report["development_run_pair"] = run_pair
                report["development_witness_handoff"] = require_graphical_witness_handoff(
                    spawned, initial_witness_retirement, run_pair, witness["name"])
                # Restore the exact paired mover as an independent final logout witness.
                bot = Bot(worker, "witness-after-development")
                state = bot.login_via_lobby(bounded_login(shared, shared["accounts"][0]), witness["name"])
                report["logout_witness_restoration"] = require_graphical_logout_witness(
                    state, run_pair, real["name"], entity)
            phase("logout", "Use /logout and confirm normally. Leave the client running at its title screen.")
            wait(lambda s: other_player(s, entity, allow_absent=True) is None)
            # Despawn alone could mean an abnormal disconnect. Also require the real
            # actor's ordinary logout request and a still-running graphical process.
            marker = f"[{entity}] Zone IPC : StartLogoutCountdown"
            if marker not in (env.runtime / "world.log").read_text(encoding="utf-8", errors="replace"):
                raise ValueError("despawn without ordinary logout request")
            report["logout_request"] = marker
            ImageGrab.grab(all_screens=True).save(OUTPUT / "logout.png")
            if client.poll() is not None:
                raise RuntimeError("client exited during logout verification")
            phase("witness_retirement", "Leave the client at its title screen; waiting for normal headless witness closure.")
            if time.monotonic() >= deadline:
                raise TimeoutError("manual activity deadline exceeded before witness retirement")
            report["witness_retirements"].append(retire_witness(bot))
            if time.monotonic() >= deadline:
                raise TimeoutError("manual activity deadline exceeded during witness retirement")
            report["status"] = "passed"
            # The context exit after this line must also observe a normal exact-
            # owned native process exit or the terminal result is changed to failed.
            stage = "observer_worker_exit"
        # Exact outer-worker exit is part of activity success, not post-success cleanup.
        if time.monotonic() >= deadline:
            report["activity_deadline"]["expired"] = True
            raise TimeoutError("manual activity deadline exceeded during observer worker exit")
        report["activity_deadline"]["activity_and_worker_exit_completed_within_budget"] = True
    except BaseException as error:
        if deadline is not None and not report["activity_deadline"][
                "activity_and_worker_exit_completed_within_budget"]:
            report["activity_deadline"]["expired"] = time.monotonic() >= deadline
        message = str(error)
        for secret in env.redactions if env else ():
            message = message.replace(secret, "<redacted>")
        report.update(status="failed", failure_stage=stage, error=f"{type(error).__name__}: {message}")
    finally:
        # Teardown may terminate the title-screen process; process-exit UI is not tested.
        timing.transition("cleanup")
        errors = []
        if client and client.poll() is None:
            try:
                client.kill()
                client.wait(timeout=10)
            except BaseException:
                errors.append("client termination failed")
        if env:
            try:
                env.close()
                report["runtime_removed"] = not env.root.exists()
            except BaseException:
                errors.append("isolated environment cleanup failed")
        if errors:
            report.update(status="failed", cleanup_errors=errors)
        # Artifact-write failures cannot skip process/environment cleanup.
        report["timing"] = timing.finish()
        publish("result", report)
        publish("status", {"run": report["run"], "phase": "finished", "status": report["status"],
                           "instruction": "Read result.json and discard the owned Sandbox. Do not send game input."})
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(run())

"""Disposable local Sapphire environment; never imports an existing DB/config."""
from __future__ import annotations

import base64
import configparser
import hashlib
import json
import math
import os
import re
from pathlib import Path
import secrets
import shutil
import socket
import stat
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid

REPO = Path(__file__).resolve().parents[3]
ISOLATED_FAULT_CLASSIFICATION = "intentional_owned_process_exit"
HTTP_RECEIPT_SCOPE = "genuine-http-response-metadata-no-request-or-response-content"
ISOLATED_FAULT_SCOPE = (
    "one intentional termination of the exact owned disposable world process; "
    "proves bounded exit classification, generation-correlated teardown, "
    "redacted text-log publication and cleanup, not crash-dump retention, "
    "cancellation cleanup or server crash behavior")


class SetupError(RuntimeError):
    pass


def allocate_ports(count):
    if type(count) is not int or not 1 <= count <= 32:
        raise ValueError("port reservation count must be 1..32")
    # Hold all reservations together to avoid selecting the same port twice.
    sockets = []
    try:
        for _ in range(count):
            sock = socket.socket()
            sock.bind(("127.0.0.1", 0))
            sockets.append(sock)
        return [s.getsockname()[1] for s in sockets]
    finally:
        for sock in sockets:
            sock.close()


def write_config(path, values):
    config = configparser.ConfigParser(interpolation=None)
    config.optionxform = str
    config.read_dict(values)
    with path.open("w", encoding="utf-8") as stream:
        config.write(stream)


def remove_runtime(root, timeout=5):
    # Windows image scanners can briefly retain executable handles after wait().
    # Retry only permission/sharing failures, with a bounded deadline, never ignore them.
    deadline = time.monotonic() + timeout
    def writable_retry(function, path, error):
        if not isinstance(error[1], PermissionError):
            raise error[1]
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
        function(path)
    while root.exists():
        try:
            shutil.rmtree(root, onerror=writable_retry)
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.1)


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def artifact_tree_sha256(root):
    """Hash exact private artifact names/sizes/bytes without disclosing names."""
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise SetupError("private artifact tree is missing or unsafe")
    paths = sorted(root.rglob("*"), key=lambda path:path.relative_to(root).as_posix())
    if len(paths) > 16384:
        raise SetupError("private artifact tree contains too many entries")
    digest, file_count, total = hashlib.sha256(), 0, 0
    for path in paths:
        if path.is_symlink():
            raise SetupError("private artifact tree contains a symlink")
        relative = path.relative_to(root).as_posix().encode("utf-8")
        if path.is_dir():
            digest.update(b"D"); digest.update(len(relative).to_bytes(4, "big")); digest.update(relative)
            continue
        if not path.is_file():
            raise SetupError("private artifact tree contains a non-file entry")
        size = path.stat().st_size
        if size > 512 * 1024 * 1024:
            raise SetupError("private artifact file exceeds evidence bound")
        total += size
        if total > 2 * 1024 * 1024 * 1024:
            raise SetupError("private artifact tree exceeds evidence bound")
        digest.update(b"F"); digest.update(len(relative).to_bytes(4, "big")); digest.update(relative)
        digest.update(size.to_bytes(8, "big")); digest.update(bytes.fromhex(sha256(path)))
        file_count += 1
    if not file_count:
        raise SetupError("private artifact tree is empty")
    return digest.hexdigest()


def redact_runtime_log(text, secrets=()):
    for value in sorted((value for value in secrets if value), key=len, reverse=True):
        text = text.replace(value, "<redacted>")
    # Warm worlds admit independently authenticated controllers/viewers. Their
    # sessions are not necessarily known to this Environment's API wrapper.
    # These exact production lobby log shapes must never publish session values.
    return re.sub(r"((?:Login request from session|Allowed connection with no session|Could not retrieve session): )[^\r\n]*",
                  r"\1<redacted>", text)


def require_process_teardowns(starts, teardowns):
    """Require one exact observed teardown for every isolated process generation."""
    if not isinstance(starts, list) or not isinstance(teardowns, list) or not starts:
        raise SetupError("isolated process lifecycle evidence is missing")
    start_keys, generations = [], {}
    for row in starts:
        if (not isinstance(row, dict) or set(row) != {"process", "generation", "pid"}
                or row.get("process") not in {"database", "api", "lobby", "world"}
                or type(row.get("generation")) is not int or row["generation"] <= 0
                or type(row.get("pid")) is not int or row["pid"] <= 0):
            raise SetupError("invalid isolated process start identity")
        key = (row["process"], row["generation"], row["pid"])
        if key in start_keys:
            raise SetupError("duplicate isolated process start identity")
        start_keys.append(key)
        generations.setdefault(row["process"], []).append(row["generation"])
    if set(generations) != {"database", "api", "lobby", "world"}:
        raise SetupError("isolated process lifecycle lacks a required service")
    if any(values != list(range(1, len(values) + 1)) for values in generations.values()):
        raise SetupError("isolated process generations are not contiguous")

    teardown_keys = []
    for row in teardowns:
        if (not isinstance(row, dict)
                or set(row) != {"process", "generation", "pid",
                                "was_running_before_cleanup", "terminate_requested",
                                "kill_requested", "exit_observed", "returncode", "scope"}
                or row.get("process") not in {"database", "api", "lobby", "world"}
                or type(row.get("generation")) is not int or row["generation"] <= 0
                or type(row.get("pid")) is not int or row["pid"] <= 0
                or row.get("scope") !=
                    "exact-owned-isolated-process-teardown-not-graceful-server-exit"
                or type(row.get("was_running_before_cleanup")) is not bool
                or row["was_running_before_cleanup"] is not True
                or type(row.get("terminate_requested")) is not bool
                or row["terminate_requested"] is not True
                or type(row.get("kill_requested")) is not bool
                or type(row.get("exit_observed")) is not bool
                or row["exit_observed"] is not True
                or type(row.get("returncode")) is not int):
            raise SetupError("invalid isolated process teardown receipt")
        teardown_keys.append((row.get("process"), row.get("generation"), row.get("pid")))
    if len(teardown_keys) != len(set(teardown_keys)) or set(teardown_keys) != set(start_keys):
        raise SetupError("isolated process starts and teardowns do not match")
    return {"verified": True,
            "scope": "all-exact-owned-isolated-process-generations-observed-terminated",
            "process_count": len(start_keys),
            "generations": {name: len(values) for name, values in sorted(generations.items())}}


class Environment:
    def __init__(self, profile):
        self.profile = profile
        self.binaries = Path(profile["binaries"]).resolve()
        self.game_data = Path(profile["game_data"]).resolve()
        self.mariadb = Path(profile["mariadb_bin"]).resolve()
        self.worker = Path(profile["worker"]).resolve()
        self.navigation = Path(profile.get("navigation", self.binaries / "navi")).resolve()
        self.deadline_scale = profile.get("deadline_scale", 1)
        if type(self.deadline_scale) is not int or not 1 <= self.deadline_scale <= 3:
            raise SetupError("deadline_scale must be an integer from 1 through 3")
        self.suffix = ".exe" if os.name == "nt" else ""
        required = [self.worker, self.game_data,
                    self.mariadb / ("mariadbd" + self.suffix),
                    self.mariadb / ("mariadb-install-db" + self.suffix)]
        required += [self.binaries / (name + self.suffix) for name in ("api", "lobby", "server", "dbm")]
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            raise SetupError("missing required assets/binaries: " + ", ".join(missing))
        if profile.get("navigation") and not self.navigation.is_dir():
            raise SetupError("configured navigation root must exist")
        # Complete fallible non-filesystem setup before allocating a disposable root;
        # a constructor exception has no owner available to call close().
        self.db_port, self.api_port, self.lobby_port, self.zone_port = allocate_ports(4)
        self.db_name = "sapphire_e2e_" + uuid.uuid4().hex
        self.secret = secrets.token_hex(24)
        self.db_password = secrets.token_hex(24)
        self.redactions = {self.secret, self.db_password}
        self.processes = {}
        self._process_generations = {}
        self._process_metadata = {}
        self.process_starts = []
        self.process_teardowns = []
        self.streams = []
        self._closed = False
        self._cleanup_evidence_failed = False
        self._cleanup_failure_services = set()
        self.last_api_receipt = None
        self._http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.root = Path(tempfile.mkdtemp(prefix="sapphire-e2e-"))
        self.runtime = self.root / "runtime"
        self.artifacts = Path(profile.get("artifacts", REPO / ".e2e-artifacts")) / self.root.name
        artifact_preexisting = self.artifacts.exists()
        try:
            self.runtime.mkdir()
            self.artifacts.mkdir(parents=True)
        except BaseException:
            # Remove only directories allocated by this constructor; never remove a
            # pre-existing ambiguous artifact path.
            try:
                if (not artifact_preexisting and self.artifacts.is_dir()
                        and not any(self.artifacts.iterdir())):
                    self.artifacts.rmdir()
            finally:
                remove_runtime(self.root)
            raise

    def stage(self):
        for name in ("api", "lobby", "server", "dbm"):
            shutil.copy2(self.binaries / (name + self.suffix), self.runtime)
        # Copy instead of symlinking executables: ConfigMgr uses executableDir()/config.
        for pattern in ("*.dll", "*.so", "*.so.*", "*.dylib"):
            for library in self.binaries.glob(pattern):
                if library.is_file():
                    shutil.copy2(library, self.runtime / library.name)
        for directory in ("sql", "web", "data"):
            shutil.copytree(REPO / directory, self.runtime / directory)
        shutil.copytree(self.binaries / "compiledscripts", self.runtime / "compiledscripts",
                        ignore=shutil.ignore_patterns("cache", "*.pdb", "*_LOCK"))
        config = self.runtime / "config"
        config.mkdir()
        write_config(config / "global.ini", {
            "Database": {"Host": "127.0.0.1", "Port": self.db_port, "Database": self.db_name,
                         "Username": "root", "Password": self.db_password, "SyncThreads": 2, "AsyncThreads": 2},
            "General": {"ServerSecret": self.secret, "DataPath": self.game_data.as_posix(),
                        "DataVersion": "2016.07.05.0000.0001", "WorldID": 67,
                        "DefaultGMRank": 0, "LogLevel": 1, "LogFilter": 0},
            "Network": {"ZoneHost": "127.0.0.1", "ZonePort": self.zone_port,
                        "LobbyHost": "127.0.0.1", "LobbyPort": self.lobby_port,
                        "RestHost": "127.0.0.1", "RestPort": self.api_port},
        })
        write_config(config / "mysql-client.ini", {
            "client": {"host": "127.0.0.1", "port": self.db_port, "user": "root",
                       "password": self.db_password, "protocol": "tcp"},
        })
        write_config(config / "world.ini", {
            "Scripts": {"Path": "./compiledscripts/", "CachePath": "./cache/", "HotSwap": "false"},
            "Network": {"ListenIp": "127.0.0.1", "ListenPort": self.zone_port, "DisconnectTimeout": 20},
            "General": {"SkipOpening": "false", "MotD": "Sapphire isolated E2E"},
            "Navigation": {"MeshPath": self.navigation.as_posix()},
            "Map": {"EagerENpcEObjCache": "false"},
        })
        write_config(config / "lobby.ini", {
            "Lobby": {"AllowNoSessionConnect": "false", "WorldName": "Sapphire E2E"},
            "Network": {"ListenIp": "127.0.0.1", "ListenPort": self.lobby_port},
        })
        write_config(config / "api.ini", {
            "Network": {"ListenIp": "127.0.0.1", "ListenPort": self.api_port},
        })
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO, text=True))
        manifest = {"revision": revision, "dirty": dirty, "profile": "sapphire-3.3",
                    "fixture_version": 2, "deadline_scale": self.deadline_scale,
                    "database": self.db_name, "runtime": str(self.runtime),
                    "game_data": str(self.game_data), "navmesh": str(self.navigation),
                    "ports": {"database": self.db_port, "api": self.api_port,
                              "lobby": self.lobby_port, "world": self.zone_port},
                    "binaries": {name: sha256(self.runtime / (name + self.suffix))
                                 for name in ("api", "lobby", "server", "dbm")},
                    "worker_sha256": sha256(self.worker),
                    "scripts": {p.name: sha256(p) for p in (self.runtime / "compiledscripts").glob("*") if p.is_file()}}
        if self.profile.get("navigation"):
            manifest["server_navigation"] = {p.relative_to(self.navigation).as_posix(): sha256(p)
                                             for p in sorted(self.navigation.rglob("*.nav"))}
        manifest["combat_data"] = {name: sha256(self.runtime / "data" / name) for name in
            ("actions/player.json", "bnpcs/w1f2/w1f2.json", "bnpcs/w1f2/w1f2_paths.json")}
        for key in ("quest_catalog", "follow_up_catalog", "transition_catalog", "combat_catalog", "shop_catalog", "respawn_catalog", "pursuit_catalog", "opening_quest_catalog"):
            if self.profile.get(key):
                path = Path(self.profile[key]).resolve()
                manifest[key] = {"path": str(path), "sha256": sha256(path)}
                catalog = json.loads(path.read_text(encoding="utf-8"))
                if catalog.get("navigation", {}).get("mesh"):
                    mesh = Path(catalog["navigation"]["mesh"])
                    manifest[key + "_navigation"] = {"path": str(mesh), "sha256": sha256(mesh)}
        (self.artifacts / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def _run(self, name, args, timeout=120):
        with (self.runtime / f"{name}.log").open("wb") as stream:
            try:
                result = subprocess.run([str(x) for x in args], cwd=self.runtime,
                                        stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
            except subprocess.TimeoutExpired:
                # TimeoutExpired renders argv, which can contain initial DB credentials.
                raise SetupError(f"{name} timed out; inspect isolated logs") from None
        if result.returncode:
            raise SetupError(f"{name} exited {result.returncode}; inspect isolated logs")

    def _start(self, name, args):
        if name in self.processes:
            raise SetupError(f"refuse to replace active owned process: {name}")
        stream = (self.runtime / f"{name}.log").open("ab")
        self.streams.append(stream)
        process = subprocess.Popen([str(x) for x in args], cwd=self.runtime,
            stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
        if type(process.pid) is not int or process.pid <= 0:
            raise SetupError(f"owned process lacks a valid PID: {name}")
        generation = self._process_generations.get(name, 0) + 1
        self._process_generations[name] = generation
        self._process_metadata[name] = {"process": name, "generation": generation,
                                        "pid": process.pid}
        self.process_starts.append(dict(self._process_metadata[name]))
        self.processes[name] = process

    def check_alive(self):
        for name, process in self.processes.items():
            if process.poll() is not None:
                failure = self.artifacts / "process-failure.json"
                if not failure.exists():
                    failure.write_text(json.dumps({
                        "version": 1,
                        "classification": "unexpected_process_exit",
                        "process": name,
                        "returncode": process.returncode,
                        "log": f"{name}.log",
                        "cleanup_required": True,
                    }, indent=2), encoding="utf-8")
                raise SetupError(f"{name} exited unexpectedly ({process.returncode}); see {self.artifacts}")

    def _wait_port(self, port, timeout=120):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.check_alive()
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    return
            except OSError:
                time.sleep(0.1)  # Bounded readiness polling, not a gameplay assertion.
        raise SetupError(f"port {port} not ready within {timeout}s")

    def start(self):
        try:
            self.stage()
            data = self.root / "database"
            if os.name == "nt":
                self._run("db-install", [self.mariadb / "mariadb-install-db.exe", f"--datadir={data}",
                          f"--password={self.db_password}", f"--port={self.db_port}"])
            else:
                # Install into a private data directory; never use system service configuration.
                self._run("db-install", [self.mariadb / "mariadb-install-db", f"--datadir={data}",
                          "--auth-root-authentication-method=normal", "--skip-test-db"])
            args = [self.mariadb / ("mariadbd" + self.suffix), "--no-defaults", f"--datadir={data}",
                    "--bind-address=127.0.0.1", f"--port={self.db_port}", "--max-connections=64"]
            if os.name != "nt":
                args += [f"--socket={self.root / 'mysql.sock'}", f"--pid-file={self.root / 'mysql.pid'}"]
            self._start("database", args)
            self._wait_port(self.db_port)
            if os.name != "nt":
                client = self.mariadb / "mariadb"
                # Password generated internally from hex; no user-supplied SQL fragments.
                self._run("db-password", [client, "--no-defaults", "--host=127.0.0.1", f"--port={self.db_port}",
                          "--user=root", "--execute", f"ALTER USER 'root'@'localhost' IDENTIFIED BY '{self.db_password}'"], timeout=10)
            for mode in ("initialize", "migrate", "check"):
                self._run(f"db-{mode}", [self.runtime / ("dbm" + self.suffix), "--mode", mode, "--force", "yes"])
            for name, executable, port in (("api", "api", self.api_port), ("lobby", "lobby", self.lobby_port),
                                          ("world", "server", self.zone_port)):
                self._start(name, [self.runtime / (executable + self.suffix)])
                self._wait_port(port)
            # A socket alone does not prove API readiness: exercise expected credential rejection.
            self.api("login", {"username": "missing_e2e_account", "pass": "invalid"}, expected=400)
            return self
        except BaseException:
            self.close()
            raise

    def api(self, method, payload, expected=200):
        if method not in {"login", "createAccount", "createCharacter"}:
            raise ValueError("unsupported fixture API method")
        request = urllib.request.Request(f"http://127.0.0.1:{self.api_port}/sapphire-api/lobby/{method}",
            data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        try:
            with self._http.open(request, timeout=10) as response:
                status, body = response.status, response.read(1024 * 1024)
        except urllib.error.HTTPError as error:
            status, body = error.code, error.read(1024 * 1024)
        if status != expected:
            raise SetupError(f"{method}: expected HTTP {expected}, received {status}")
        result = json.loads(body) if body else {}
        self.last_api_receipt = {
            "version": 1,
            "scope": HTTP_RECEIPT_SCOPE,
            "method": method,
            "expected_status": expected,
            "received_status": status,
            "response_bytes": len(body),
            "response_sha256": hashlib.sha256(body).hexdigest(),
            "session_returned": isinstance(result, dict) and "sId" in result,
        }
        if "sId" in result:
            self.redactions.add(result["sId"])
        return result

    def fresh_account(self):
        username = "e2e_" + uuid.uuid4().hex
        password = secrets.token_hex(16)
        self.redactions.add(password)
        name = "Tester " + "".join(chr(65 + int(c, 16)) for c in uuid.uuid4().hex[:10])
        auth = self.api("createAccount", {"username": username, "pass": password})
        return {"username": username, "password": password, "name": name, "auth": auth}

    def fresh_character(self, position=None, territory=130, class_job=1):
        if type(territory) is not int or territory not in {130, 131, 140, 141}:
            raise SetupError("unsupported public fixture territory")
        if class_job not in {1, 2, 7}:
            raise SetupError("unsupported source-defined Ul'dah fixture class")
        if territory != 130 and position is None:
            raise SetupError("nondefault fixture territory requires an explicit position")
        if position is not None and (len(position) != 3 or not all(math.isfinite(v) and abs(v) < 1000 for v in position)):
            raise SetupError("invalid fixture start position")
        account = self.fresh_account()
        username, password, name, auth = (account[key] for key in ("username", "password", "name", "auth"))
        # Alphabetic fixture names, valid starter class, 26 customization bytes.
        appearance = [1, 0, 1, 50, 1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0]
        content = [[str(v) for v in appearance], "1", "1", "1", "1", str(class_job), "1"]
        info = json.dumps({"content": content}, separators=(",", ":"))
        # The fixture API accepts the same base64-encoded character description as the lobby.
        result = self.api("createCharacter", {"sId": auth["sId"], "secret": self.secret, "name": name,
                          "infoJson": base64.b64encode(info.encode()).decode()})
        if not str(result.get("result", "")).isdigit() or int(result["result"]) <= 0:
            raise SetupError("character fixture creation was not acknowledged")
        # Fixture setup ONLY, before this character's first world connection. Opening
        # territories are private; replication tests start in the public counterpart.
        # Never mutate this state once the tested journey has begun.
        coordinates = ""
        if position is not None:
            coordinates = ", " + ", ".join(f"{column}={float(value):.9g}" for column, value in zip(("PosX", "PosY", "PosZ"), position))
        sql = (f"UPDATE charainfo SET TerritoryType={territory}, TerritoryId=0, "
               f"IsNewGame=0, OpeningSequence=2{coordinates} WHERE Name='{name}';")
        self._run("fixture-seed", [self.mariadb / ("mariadb" + self.suffix),
                  f"--defaults-extra-file={self.runtime / 'config' / 'mysql-client.ini'}",
                  f"--database={self.db_name}", "--execute", sql])
        # Exercise genuine HTTP login even though provisioning also returns a session.
        auth = self.api("login", {"username": username, "pass": password})
        return {"name": name, "username": username, "password": password, "auth": auth}

    def restart_world(self):
        self._stop("world")
        self._start("world", [self.runtime / ("server" + self.suffix)])
        self._wait_port(self.zone_port)

    def terminate_world_for_fault_test(self):
        """Intentionally stop this fixture's exact world and retain classification."""
        process = self.processes.get("world")
        metadata = self._process_metadata.get("world")
        if (process is None or not isinstance(metadata, dict)
                or metadata.get("process") != "world" or process.poll() is not None):
            raise SetupError("refuse ambiguous or inactive owned world fault target")
        self._stop("world")
        receipt = self.process_teardowns[-1]
        if (receipt.get("pid") != metadata.get("pid")
                or receipt.get("generation") != metadata.get("generation")
                or type(receipt.get("returncode")) is not int):
            raise SetupError("owned world fault exit receipt is incomplete")
        diagnostic = {
            "version": 1,
            "classification": ISOLATED_FAULT_CLASSIFICATION,
            "process": "world",
            "generation": metadata["generation"],
            "pid": metadata["pid"],
            "returncode": receipt["returncode"],
            "log": "world.log",
            "cleanup_required": True,
        }
        (self.artifacts / "process-failure.json").write_text(
            json.dumps(diagnostic, indent=2), encoding="utf-8")
        raise SetupError(
            f"world generation {metadata['generation']} exited intentionally for fault test "
            f"({receipt['returncode']}); see {self.artifacts}")

    def _stop(self, name):
        process = self.processes.get(name)
        metadata = self._process_metadata.get(name)
        if process is None:
            return
        if not isinstance(metadata, dict):
            raise SetupError(f"owned process metadata is missing: {name}")
        prior = next((row for row in self.process_teardowns
                      if all(row.get(key) == metadata.get(key)
                             for key in ("process","generation","pid"))
                      and row.get("exit_observed") is False), None)
        if prior is not None:
            # Never issue a second uncertain terminate/kill request. A later close
            # may only observe that the exact retained process has exited.
            returncode = process.poll()
            if type(returncode) is not int:
                raise SetupError(f"owned process cleanup remains uncertain: {name}")
            prior.update(exit_observed=True, returncode=returncode)
            self.processes.pop(name, None)
            self._process_metadata.pop(name, None)
            return
        before = process.poll()
        receipt = {**metadata, "was_running_before_cleanup": before is None,
                   "terminate_requested": False, "kill_requested": False,
                   "exit_observed": before is not None, "returncode": before,
                   "scope": "exact-owned-isolated-process-teardown-not-graceful-server-exit"}
        try:
            if before is None:
                receipt["terminate_requested"] = True
                process.terminate()
                try:
                    returncode = process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    receipt["kill_requested"] = True
                    process.kill()
                    returncode = process.wait(timeout=5)
                if type(returncode) is not int:
                    raise SetupError(f"owned process exit code is unavailable: {name}")
                receipt.update(exit_observed=True, returncode=returncode)
        finally:
            self.process_teardowns.append(receipt)
        self.processes.pop(name, None)
        self._process_metadata.pop(name, None)

    def _write_lifecycle(self):
        lifecycle = {"version": 1,
                     "scope": "exact-owned-isolated-process-teardown-not-graceful-server-exit",
                     "starts": getattr(self, "process_starts", []),
                     "teardowns": getattr(self, "process_teardowns", [])}
        (self.artifacts / "process-lifecycle.json").write_text(
            json.dumps(lifecycle, indent=2), encoding="utf-8")

    def close(self):
        if self._closed:
            return
        failures = []
        for name in reversed(list(self.processes)):
            try:
                self._stop(name)
            except BaseException:
                failures.append(name)
        if failures:
            self._cleanup_evidence_failed = True
            services = getattr(self, "_cleanup_failure_services", set())
            services.update(failures)
            self._cleanup_failure_services = services
        publication_failed = False
        try:
            self._write_lifecycle()
        except BaseException:
            # A missing lifecycle is itself terminal evidence uncertainty, even
            # when every exact exit was observed.
            self._cleanup_evidence_failed = True
            publication_failed = True
        if getattr(self, "_cleanup_evidence_failed", False):
            services = sorted(getattr(self, "_cleanup_failure_services", set()))
            classification = ("owned_process_cleanup_incomplete" if services else
                              "owned_process_cleanup_evidence_incomplete")
            try:
                # Retry publication, never process termination, on a later close.
                (self.artifacts / "cleanup-failure.json").write_text(json.dumps({
                    "version":1,"classification":classification,
                    "services":services,"runtime_retained":True,
                    "retry_policy":"exact-process-poll-only-no-second-termination",
                }, indent=2), encoding="utf-8")
            except BaseException:
                publication_failed = True
        if failures or publication_failed:
            # Keep streams, logs and runtime for exact retained-process diagnosis.
            names = ", ".join(failures) if failures else "evidence publication"
            raise SetupError("owned process cleanup incomplete; inspect private lifecycle: " + names)
        for stream in self.streams:
            stream.close()
        # Only publish redacted text logs, never DB files, game assets or credentials/configs.
        for path in self.runtime.rglob("*.log"):
            text = path.read_text(encoding="utf-8", errors="replace")
            text = redact_runtime_log(text, self.redactions)
            target = self.artifacts / path.relative_to(self.runtime)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        remove_runtime(self.root)
        self._closed = True

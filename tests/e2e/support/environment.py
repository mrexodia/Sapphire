"""Disposable local Sapphire environment; never imports an existing DB/config."""
from __future__ import annotations

import base64
import configparser
import hashlib
import json
import math
import os
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


class SetupError(RuntimeError):
    pass


def allocate_ports(count):
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


class Environment:
    def __init__(self, profile):
        self.profile = profile
        self.binaries = Path(profile["binaries"]).resolve()
        self.game_data = Path(profile["game_data"]).resolve()
        self.mariadb = Path(profile["mariadb_bin"]).resolve()
        self.worker = Path(profile["worker"]).resolve()
        self.navigation = Path(profile.get("navigation", self.binaries / "navi")).resolve()
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
        self.root = Path(tempfile.mkdtemp(prefix="sapphire-e2e-"))
        self.runtime = self.root / "runtime"
        self.runtime.mkdir()
        self.artifacts = Path(profile.get("artifacts", REPO / ".e2e-artifacts")) / self.root.name
        self.artifacts.mkdir(parents=True)
        self.db_port, self.api_port, self.lobby_port, self.zone_port = allocate_ports(4)
        self.db_name = "sapphire_e2e_" + uuid.uuid4().hex
        self.secret = secrets.token_hex(24)
        self.db_password = secrets.token_hex(24)
        self.redactions = {self.secret, self.db_password}
        self.processes = {}
        self.streams = []
        self._closed = False
        self._http = urllib.request.build_opener(urllib.request.ProxyHandler({}))

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
                    "fixture_version": 2, "database": self.db_name, "runtime": str(self.runtime),
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
        stream = (self.runtime / f"{name}.log").open("ab")
        self.streams.append(stream)
        self.processes[name] = subprocess.Popen([str(x) for x in args], cwd=self.runtime,
            stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)

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

    def _stop(self, name):
        process = self.processes.pop(name, None)
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    def close(self):
        if self._closed:
            return
        for name in reversed(list(self.processes)):
            self._stop(name)
        for stream in self.streams:
            stream.close()
        # Only publish redacted text logs, never DB files, game assets or credentials/configs.
        for path in self.runtime.rglob("*.log"):
            text = path.read_text(encoding="utf-8", errors="replace")
            for value in self.redactions:
                if value:
                    text = text.replace(value, "<redacted>")
            target = self.artifacts / path.relative_to(self.runtime)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        remove_runtime(self.root)
        self._closed = True

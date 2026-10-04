"""Attach the headless bots to an already-running local Sapphire stack.

The tests never start, stop or configure MariaDB or the Sapphire services. They
only need the API endpoint, the server secret and the built worker. Throwaway
accounts and characters come from the API's development bot fixtures
(/sapphire-api/dev/*), which must be enabled in api.ini:

    [Development]
    BotApi = true
"""
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path


class SetupError(RuntimeError):
    pass


LOBBY_METHODS = {"login", "createAccount", "createCharacter", "deleteCharacter", "getCharacterList"}
DEV_METHODS = {"createBot", "listBots", "purgeBots"}


class DevServer:
    def __init__(self, profile):
        self.profile = profile
        self.api_url = str(profile.get("api", "http://127.0.0.1:80")).rstrip("/")
        self.secret = str(profile.get("secret", "default"))
        self.worker = Path(profile["worker"]).resolve()
        if not self.worker.is_file():
            raise SetupError(f"worker executable does not exist: {self.worker}")
        # The server's working directory (bin/): data/ and config/ live here.
        self.runtime = Path(profile.get("server_dir", self.worker.parent)).resolve()
        self.deadline_scale = profile.get("deadline_scale", 1)
        if type(self.deadline_scale) is not int or not 1 <= self.deadline_scale <= 3:
            raise SetupError("deadline_scale must be an integer from 1 through 3")
        root = Path(profile.get("artifacts", ".e2e-artifacts")).resolve()
        self.artifacts = root / time.strftime("%Y%m%d-%H%M%S")
        self.artifacts.mkdir(parents=True, exist_ok=True)
        self._opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())

    # -- HTTP ---------------------------------------------------------------

    def api(self, method, payload=None, expected=200, timeout=10):
        if method in LOBBY_METHODS:
            path = f"/sapphire-api/lobby/{method}"
        elif method in DEV_METHODS:
            path = f"/sapphire-api/dev/{method}"
        else:
            raise ValueError(f"unknown API method: {method}")
        body = dict(payload or {})
        if method in DEV_METHODS:
            body.setdefault("secret", self.secret)
        request = urllib.request.Request(self.api_url + path, data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json"})
        try:
            with self._opener.open(request, timeout=timeout) as response:
                status, text = response.status, response.read(1024 * 1024)
        except urllib.error.HTTPError as error:
            status, text = error.code, error.read(1024 * 1024)
        except urllib.error.URLError as error:
            raise SetupError(f"API {self.api_url} is unreachable ({error.reason}); is the dev stack running?") from None
        if status != expected:
            detail = text.decode(errors="replace")[:300]
            if status == 404 and method in DEV_METHODS:
                detail += " (enable [Development] BotApi = true in api.ini and restart the API)"
            raise SetupError(f"{method}: expected HTTP {expected}, received {status}: {detail}")
        return json.loads(text) if text else {}

    def check_alive(self):
        self.api("listBots")

    # -- fixtures -----------------------------------------------------------

    def fresh_account(self):
        """A bot account with no character, for lobby character-creation tests."""
        result = self.api("createBot", {"character": False})
        auth = self.api("login", {"username": result["username"], "pass": result["password"]})
        name = "Bot " + "".join(chr(65 + int(c, 16)) for c in result["username"][4:14])
        return {"username": result["username"], "password": result["password"], "name": name, "auth": auth}

    def fresh_character(self, position=None, territory=130, class_job=1, level=1):
        """A fresh non-GM bot character, already past the opening, logged in over HTTP."""
        if position is not None and len(position) != 3:
            raise SetupError("position must be [x, y, z]")
        request = {"class": class_job, "territory": territory, "level": level}
        if position is not None:
            request["position"] = [float(v) for v in position]
        result = self.api("createBot", request)
        # Exercise a genuine HTTP login even though creation also returned a session.
        auth = self.api("login", {"username": result["username"], "pass": result["password"]})
        return {"name": result["name"], "username": result["username"], "password": result["password"],
                "auth": auth, "character_id": result["character_id"], "entity_id": result["entity_id"]}

    def login(self, fixture):
        return self.api("login", {"username": fixture["username"], "pass": fixture["password"]})

    def wait_offline(self, name, timeout=30):
        """Wait until the world has dropped the character's session (charainfo.Online = 0)."""
        deadline = time.monotonic() + timeout
        while True:
            online = [character for account in self.list_bots() for character in account["characters"]
                      if character["name"] == name and character["online"]]
            if not online:
                return
            if time.monotonic() > deadline:
                raise SetupError(f"{name} is still online after {timeout}s")
            time.sleep(0.25)

    def relogin(self, fixture, timeout=30):
        """Fresh HTTP login for a character that just logged out."""
        self.wait_offline(fixture["name"], timeout)
        return self.login(fixture)

    def world_log(self):
        """Text of the newest world log under <server_dir>/log, or '' if unavailable."""
        logs = sorted((self.runtime / "log").glob("world_*.log"), key=lambda path: path.stat().st_mtime)
        return logs[-1].read_text(errors="replace") if logs else ""

    def require_navmesh(self, territory, internal_name):
        """Fail fast when the running world loaded no navmesh for the territory.

        Enemies cannot move without one, which otherwise shows up as a confusing
        combat timeout. The world prints one row per territory at startup, with a
        NAVI column when a mesh loaded; the latest row for this zone is checked."""
        rows = re.findall(rf"^.*{territory}\s+\d+\s+\d+\s+{re.escape(internal_name)}\s+\S+\s+(NAVI)?.*$",
                          self.world_log(), re.M)
        if rows and not rows[-1]:
            raise SetupError(f"the world loaded no navmesh for territory {territory} ({internal_name}); "
                             f"enemies there cannot move. Check MeshPath in world.ini.")

    def world_memory(self):
        """Resident set size in MiB of the world process running from <server_dir>, or None.

        Needs psutil; the soak scenario reports memory growth from this."""
        try:
            import psutil
        except ImportError:
            return None
        candidates = []
        for process in psutil.process_iter(["name", "exe", "memory_info"]):
            try:
                exe = process.info["exe"]
                if exe and Path(exe).parent.resolve() == self.runtime and process.info["name"]                         and process.info["name"].lower().startswith("server"):
                    candidates.append(process.info["memory_info"].rss)
            except (psutil.Error, OSError):
                continue
        return max(candidates) / (1024 * 1024) if candidates else None

    def list_bots(self):
        return self.api("listBots")["accounts"]

    def purge_bots(self):
        """Delete every bot account whose characters are offline. Returns the API summary."""
        return self.api("purgeBots")


def load_profile(path):
    profile = json.loads(Path(path).read_text(encoding="utf-8"))
    base = Path(path).resolve().parent
    for key in ("worker", "server_dir", "artifacts", "quest_catalog", "follow_up_catalog", "transition_catalog",
                "combat_catalog", "shop_catalog", "respawn_catalog", "pursuit_catalog", "opening_quest_catalog"):
        if key in profile and not Path(profile[key]).is_absolute():
            profile[key] = str((base / profile[key]).resolve())
    return profile

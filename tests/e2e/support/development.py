"""Opt-in, non-isolated development sessions. No DB or server process ownership."""
from contextlib import contextmanager
import hashlib
import json
import math
import psutil
from pathlib import Path
import tempfile
import time
import urllib.request

from .catalog import load_quest_catalog


class DevelopmentError(RuntimeError):
    pass


WORKER_EXIT_SCOPE = "owned-native-worker-exit-not-server-session-closure"


def require_normal_worker_exit(report, key="worker_exit"):
    """Reject legacy, malformed, failed or unbound exact-worker receipts."""
    receipt = report.get(key)
    if (not isinstance(receipt, dict) or receipt.get("scope") != WORKER_EXIT_SCOPE
            or receipt.get("context_entered") is not True
            or receipt.get("context_exit_attempted") is not True
            or receipt.get("context_exit_completed") is not True
            or receipt.get("process_exit_observed") is not True
            or type(receipt.get("process_id")) is not int or receipt["process_id"] <= 0
            or type(receipt.get("returncode")) is not int or receipt["returncode"] != 0
            or "context_exit_error_type" in receipt or receipt.get("process_observation_error") is True):
        raise DevelopmentError("normal owned native worker exit was not observed")
    return receipt


class Timings:
    def __init__(self):
        self.rows = []

    @contextmanager
    def phase(self, name):
        start = time.monotonic()
        outcome = "failed"
        try:
            yield
            outcome = "passed"
        finally:
            self.rows.append({"phase": name, "seconds": time.monotonic() - start,
                              "outcome": outcome})


def validate_profile(profile):
    # No arbitrary URLs, redirects, DB credentials, server secrets or lifecycle options.
    required = {"version", "mode", "protocol", "worker", "api_port", "lobby_port",
                "territory", "accounts"}
    allowed = required | {"quest_catalog", "host_session"}
    if not isinstance(profile, dict) or not required <= profile.keys() or profile.keys() - allowed:
        raise DevelopmentError("invalid development profile fields")
    if (type(profile["version"]) is not int or profile["version"] != 1
            or profile["mode"] != "shared-development" or profile["protocol"] != "sapphire-3.3"):
        raise DevelopmentError("unsupported development profile")
    for key in ("api_port", "lobby_port"):
        if type(profile[key]) is not int or not 1 <= profile[key] <= 65535:
            raise DevelopmentError("ports must be integers in 1..65535")
    if type(profile["territory"]) is not int or profile["territory"] not in {130, 131, 140, 141}:
        raise DevelopmentError("a supported public territory is required")
    if not isinstance(profile["worker"], str) or not Path(profile["worker"]).is_file():
        raise DevelopmentError("worker executable is missing")
    if "host_session" in profile:
        session = profile["host_session"]
        if (not isinstance(session, dict) or set(session) != {"path", "id"}
                or not isinstance(session["path"], str) or not Path(session["path"]).is_absolute()
                or not isinstance(session["id"], str) or len(session["id"]) != 32
                or any(c not in "0123456789abcdef" for c in session["id"])):
            raise DevelopmentError("invalid managed development session binding")
    accounts = profile["accounts"]
    if not isinstance(accounts, list) or len(accounts) != 2:
        raise DevelopmentError("exactly two dedicated bot accounts are required")
    for account in accounts:
        if not isinstance(account, dict) or set(account) != {"username", "password", "character"}:
            raise DevelopmentError("invalid bot account fields")
        if any(not isinstance(value, str) or not value or len(value) > 128 for value in account.values()):
            raise DevelopmentError("invalid bot account values")
        if not account["username"].startswith("e2e_"):
            raise DevelopmentError("only explicitly dedicated e2e_ accounts are allowed")
        if len(account["character"]) >= 32:
            raise DevelopmentError("invalid character name length")
    for key in ("username", "character"):
        if len({account[key].casefold() for account in accounts}) != 2:
            raise DevelopmentError("bot accounts and characters must be distinct")
    return profile


def check_managed_host(profile, *, clock=time.monotonic, process=psutil.Process):
    """Reject expired/stopped/orphaned managed profiles without contacting a server."""
    binding = profile.get("host_session")
    if binding is None:
        return
    try:
        status_path = Path(binding["path"])
        if status_path.with_name("stop").exists():
            raise ValueError()
        with status_path.open("rb") as stream:
            raw = stream.read(16385)
        if len(raw) > 16384:
            raise ValueError()
        status = json.loads(raw)
        pid, created, deadline = (status[key] for key in ("owner_pid", "owner_created", "deadline_monotonic"))
        owner = process(pid)
        if (type(status.get("version")) is not int or status["version"] != 1
                or status.get("kind") != "owned-development-host"
                or status.get("session_id") != binding["id"] or status.get("status") != "ready"
                or type(pid) is not int or pid <= 0
                or type(created) not in (int, float) or not math.isfinite(created)
                or type(deadline) not in (int, float) or not math.isfinite(deadline) or clock() >= deadline
                or type(status.get("api_port")) is not int or status["api_port"] != profile["api_port"]
                or type(status.get("lobby_port")) is not int or status["lobby_port"] != profile["lobby_port"]
                or status.get("protocol") != profile["protocol"]
                or not owner.is_running() or owner.status() in {psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD}
                or owner.create_time() != created):
            raise ValueError()
        if hashlib.sha256(Path(profile["worker"]).read_bytes()).hexdigest() != status.get("worker_sha256"):
            raise ValueError()
        require_normal_worker_exit(status, "worker_preflight_exit")
    except Exception:
        raise DevelopmentError("managed development host is unavailable, expired or does not match this profile") from None


class AccountLease:
    """Local cooperating-runner exclusion, NOT a server-side online-session lock.

    Failed/interrupted sessions retain the lease: cleanup must be verified manually.
    The fixed per-user directory prevents bypass via alternate artifact/profile paths.
    """
    def __init__(self, profile, run_id, root=None):
        self.root = Path(root) if root is not None else Path(tempfile.gettempdir()) / "sapphire-dev-bot-leases-v1"
        self.paths = []
        self.keys = sorted(hashlib.sha256(
            ("127.0.0.1:" + str(profile["api_port"]) + ":" + account["username"].casefold()).encode()
        ).hexdigest() for account in profile["accounts"])
        self.run_id = run_id

    def acquire(self):
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            for key in self.keys:
                path = self.root / (key + ".lock")
                with path.open("x", encoding="utf-8") as stream:
                    self.paths.append(path)
                    json.dump({"run_id": self.run_id, "recovery": "verify bots offline before removing lease"}, stream)
        except BaseException:
            self.release()
            raise DevelopmentError("bot account is leased or lease creation failed; inspect local lease directory") from None

    def release(self):
        for path in self.paths:
            path.unlink()
        self.paths.clear()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _account_session(profile, account, method):
    check_managed_host(profile)
    if method not in {"login", "createAccount"}:
        raise DevelopmentError("unsupported development account operation")
    request = urllib.request.Request(
        f"http://127.0.0.1:{profile['api_port']}/sapphire-api/lobby/{method}",
        data=json.dumps({"username": account["username"], "pass": account["password"]}).encode(),
        headers={"Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=10) as response:
            body = response.read(1024 * 1024 + 1)
            if response.status != 200 or len(body) > 1024 * 1024:
                raise ValueError()
            auth = json.loads(body)
        if (auth["lobbyHost"] != "127.0.0.1" or type(auth["lobbyPort"]) is not int
                or auth["lobbyPort"] != profile["lobby_port"]
                or not isinstance(auth["sId"], str) or not auth["sId"] or len(auth["sId"]) > 256):
            raise ValueError()
        return auth
    except Exception:
        # Never publish response bodies, request data, passwords or session tokens.
        raise DevelopmentError("HTTP account operation failed or lobby endpoint differs from configured loopback endpoint") from None


def authenticate(profile, account):
    return _account_session(profile, account, "login")


def create_account(profile, account):
    # Fresh login is still required separately; a creation response is not proof
    # of a usable persisted account or of any character/world state.
    return _account_session(profile, account, "createAccount")


def received_character_identity(state, name):
    rows = [row for row in state.get("characters", []) if row.get("name") == name]
    if len(rows) != 1:
        raise DevelopmentError("expected exactly one received lobby character identity")
    row = rows[0]
    for key, maximum in (("entity_id", 2**32 - 1), ("character_id", 2**64 - 1)):
        if type(row.get(key)) is not int or not 0 < row[key] <= maximum:
            raise DevelopmentError("invalid received character identity")
    if row["entity_id"] != state.get("entity_id"):
        raise DevelopmentError("lobby and world identities differ")
    return {key: row[key] for key in ("name", "entity_id", "character_id")}


def position(value):
    return (isinstance(value, list) and len(value) == 3
            and all(type(x) in (int, float) and math.isfinite(x) and abs(x) < 1000 for x in value))


def idle_state(state, territory):
    return (state.get("phase") == "ready" and state.get("territory") == territory
            and state.get("gm_rank") == 0 and not state.get("moving", True)
            and state.get("scene") is None and state.get("event_id") is None
            and position(state.get("observed_position")))


def witnessed(state, actor, name, target=None):
    row = state.get("actors", {}).get(str(actor), {})
    return (row.get("name") == name and row.get("gm_rank") == 0
            and position(row.get("position"))
            and (target is None or math.dist(row["position"], target) <= 0.15))


def movement_route(profile):
    """Only an out-and-back prefix of an existing validated quest corridor."""
    if "quest_catalog" not in profile:
        return [], None
    if profile["territory"] != 130:
        raise DevelopmentError("quest-prefix movement requires territory 130")
    path = Path(profile["quest_catalog"])
    catalog = load_quest_catalog(path)
    if catalog["quest"] != 65686:
        raise DevelopmentError("development movement supports Motivational Speaking only")
    route, distance = [catalog["route"][0]], 0.0
    for point in catalog["route"][1:]:
        step = math.dist(route[-1], point)
        if distance + step > 5 or len(route) >= 16:
            break
        route.append(point)
        distance += step
    if len(route) < 2 or distance < 0.1:
        raise DevelopmentError("no useful bounded movement prefix")
    return route, hashlib.sha256(path.read_bytes()).hexdigest()

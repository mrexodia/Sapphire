"""Read-only availability/identity inspection for a private isolated-gate profile."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..run_ci import CATALOGS, PATH_KEYS, preflight
from .environment import SetupError

SCOPE = "isolated-gate-private-profile-availability-and-byte-identities-only"


def inspect_ci_profile(profile_path, *, worker=None, binaries=None, suffix=None):
    path = Path(profile_path).resolve()
    try:
        if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 1024 * 1024:
            raise OSError()
        raw = path.read_bytes()
        profile = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SetupError("cannot read isolated-gate private profile") from error
    if not isinstance(profile, dict):
        raise SetupError("isolated-gate private profile is not an object")
    allowed = {*PATH_KEYS,"artifacts","deadline_scale"}
    unknown = sorted(set(profile) - allowed)
    missing = sorted(key for key in PATH_KEYS if not profile.get(key))
    if unknown:
        raise SetupError("isolated-gate private profile has unsupported keys: " + ", ".join(unknown))
    if missing:
        raise SetupError("isolated-gate private profile is missing keys: " + ", ".join(missing))
    effective = dict(profile)
    if worker is not None:
        effective["worker"] = str(Path(worker).resolve())
    if binaries is not None:
        effective["binaries"] = str(Path(binaries).resolve())
    try:
        _, identities = preflight(effective, suffix=suffix)
    except Exception as error:
        raise SetupError("isolated-gate private profile preflight failed; inspect private inputs") from error
    return {"version":1,"status":"accepted","scope":SCOPE,
            "profile_sha256":hashlib.sha256(raw).hexdigest(),
            "deadline_scale":effective.get("deadline_scale", 1),
            "required_path_key_count":len(PATH_KEYS),"catalog_count":len(CATALOGS),
            "worker_overridden":worker is not None,"binaries_overridden":binaries is not None,
            "identities":identities,"private_paths_disclosed":False,
            "services_accounts_or_gameplay_started":False,
            "note":"Static availability and exact byte identities only; not build provenance, compatibility, execution or gameplay evidence."}

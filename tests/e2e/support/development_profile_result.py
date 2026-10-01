"""Bind one strict external shared-development result to its private bot profile."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import stat

from .development import DevelopmentError, validate_profile
from .development_binding import require_development_run_binding
from .development_result import validate_development_evidence

SCOPE = "external-shared-run-private-profile-association-not-authentication-or-exclusion"


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise DevelopmentError("development profile contains a duplicate JSON key")
        value[key] = item
    return value


def _read_profile(path):
    try:
        path = Path(path)
        metadata = path.lstat()
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if (path.is_symlink() or not stat.S_ISREG(metadata.st_mode)
                or getattr(metadata, "st_file_attributes", 0) & reparse
                or metadata.st_nlink != 1 or not 0 < metadata.st_size <= 64 * 1024):
            raise OSError()
        raw = path.read_bytes()
        if not 0 < len(raw) <= 64 * 1024:
            raise OSError()
        profile = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DevelopmentError("cannot read private development profile") from error
    validate_profile(profile)
    return raw, profile


def inspect_development_profile_result(summary_path, profile_path):
    evidence = validate_development_evidence(summary_path)
    profile_raw, profile = _read_profile(profile_path)
    identities, binding = require_development_run_binding(evidence["report"], profile)
    return {"version":1,"status":"accepted","scope":SCOPE,
            "run_id":evidence["run_id"],
            "summary_sha256":hashlib.sha256(evidence["raw"]).hexdigest(),
            "profile_sha256":hashlib.sha256(profile_raw).hexdigest(),
            "development_profile_binding":binding,
            "received_identities":identities,
            "worker_sha256":evidence["report"]["worker_sha256"],
            "verified_checks":evidence["checks"],
            "managed_host":False,"credentials_disclosed":False,
            "authentication_currentness_verified":False,"offline_exclusion_verified":False,
            "note":"Exact retained private-profile/run association only; not current authentication, exclusive use, server identity, reset or acceptance proof."}

"""Artifact association only: not authentication, a signature or an offline lock."""
import hashlib
import json

from .development import DevelopmentError, validate_profile


def provisioning_binding(profile, accounts):
    """Bind configured realm/account slots and received identities, excluding secrets.

    Worker/catalog/password changes are allowed: these do not select another
    account. Host-session binding is included when supplied. Anyone able to edit
    both files can recompute this digest; operator review and server guards remain
    mandatory. It neither probes endpoints nor authorizes resets.
    """
    validate_profile(profile)
    if not isinstance(accounts, list) or len(accounts) != 2:
        raise DevelopmentError("binding requires exactly two provisioning identity rows")
    slots = []
    for index, (account, row) in enumerate(zip(profile["accounts"], accounts)):
        if type(row.get("slot")) is not int or row["slot"] != index or row.get("character") != account["character"]:
            raise DevelopmentError("binding account-slot/character mismatch")
        for key, maximum in (("entity_id", 2**32 - 1), ("character_id", 2**64 - 1)):
            if type(row.get(key)) is not int or not 0 < row[key] <= maximum:
                raise DevelopmentError("binding requires received positive character/entity IDs")
        slots.append({"slot": index, "username": account["username"].casefold(),
                      "character": account["character"], "entity_id": row["entity_id"],
                      "character_id": row["character_id"]})
    document = {"schema": "development-provisioning-association-v1",
                "version": profile["version"], "mode": profile["mode"], "protocol": profile["protocol"],
                "api_host": "127.0.0.1", "api_port": profile["api_port"], "lobby_port": profile["lobby_port"],
                "host_session": profile.get("host_session"), "accounts": slots}
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return {"schema": document["schema"], "sha256": hashlib.sha256(encoded).hexdigest()}


def require_provisioning_binding(profile, report):
    expected = provisioning_binding(profile, report.get("accounts"))
    if report.get("provisioning_binding") != expected:
        raise DevelopmentError("provisioning association missing or mismatched; do not synthesize legacy approval")

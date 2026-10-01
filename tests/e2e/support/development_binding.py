"""Artifact association only: not authentication, a signature or an offline lock."""
import hashlib
import json
from pathlib import Path

from .development import (DevelopmentError, require_managed_host_binding,
                          validate_profile)


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


def development_run_account_association(profile, *, require_worker=True):
    """Retain binding inputs without retaining passwords or worker paths."""
    validate_profile(profile, require_worker=require_worker)
    return {"schema":"development-run-account-input-v1","version":profile["version"],
            "mode":profile["mode"],"protocol":profile["protocol"],
            "api_host":"127.0.0.1","api_port":profile["api_port"],
            "lobby_port":profile["lobby_port"],"host_session":profile.get("host_session"),
            "accounts":[{"username":row["username"].casefold(),
                         "character":row["character"]} for row in profile["accounts"]]}


def validate_development_run_account_association(value):
    fields = {"schema","version","mode","protocol","api_host","api_port",
              "lobby_port","host_session","accounts"}
    if (not isinstance(value, dict) or set(value) != fields
            or value.get("schema") != "development-run-account-input-v1"
            or type(value.get("version")) is not int or value["version"] != 1
            or value.get("mode") != "shared-development"
            or value.get("protocol") != "sapphire-3.3"
            or value.get("api_host") != "127.0.0.1"
            or any(type(value.get(key)) is not int or not 1 <= value[key] <= 65535
                   for key in ("api_port","lobby_port"))
            or not isinstance(value.get("accounts"), list) or len(value["accounts"]) != 2):
        raise DevelopmentError("development run account association is malformed")
    session = value["host_session"]
    if session is not None and (not isinstance(session, dict)
            or set(session) != {"path","id"}
            or not isinstance(session.get("path"), str) or not Path(session["path"]).is_absolute()
            or not isinstance(session.get("id"), str) or len(session["id"]) != 32
            or any(char not in "0123456789abcdef" for char in session["id"])):
        raise DevelopmentError("development run account association is malformed")
    for account in value["accounts"]:
        if (not isinstance(account, dict) or set(account) != {"username","character"}
                or not isinstance(account["username"], str)
                or not account["username"].startswith("e2e_")
                or account["username"] != account["username"].casefold()
                or not isinstance(account["character"], str)
                or not 1 <= len(account["character"]) <= 31):
            raise DevelopmentError("development run account association is malformed")
    if any(len({row[key].casefold() for row in value["accounts"]}) != 2
           for key in ("username","character")):
        raise DevelopmentError("development run account association is ambiguous")
    return value


def development_run_binding_from_association(association, identities):
    association = validate_development_run_account_association(association)
    if not isinstance(identities, list) or len(identities) != 2:
        raise DevelopmentError("development binding requires two received identities")
    rows = []
    for index, (account, identity) in enumerate(zip(association["accounts"], identities)):
        if (not isinstance(identity, dict)
                or set(identity) != {"slot","name","entity_id","character_id"}
                or type(identity.get("slot")) is not int or identity["slot"] != index
                or identity.get("name") != account["character"]):
            raise DevelopmentError("development binding identity differs from profile")
        for key, maximum in (("entity_id",2**32 - 1),("character_id",2**64 - 1)):
            if type(identity.get(key)) is not int or not 0 < identity[key] <= maximum:
                raise DevelopmentError("development binding requires positive received IDs")
        rows.append({"slot":index,"username":account["username"],
                     "character":account["character"],"entity_id":identity["entity_id"],
                     "character_id":identity["character_id"]})
    if any(len({row[key] for row in rows}) != 2
           for key in ("username","character","entity_id","character_id")):
        raise DevelopmentError("development binding identities are ambiguous")
    document = {"schema":"development-run-profile-association-v1",
                "version":association["version"],"mode":association["mode"],
                "protocol":association["protocol"],"api_host":association["api_host"],
                "api_port":association["api_port"],"lobby_port":association["lobby_port"],
                "host_session":association["host_session"],"accounts":rows}
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"),
                         allow_nan=False).encode("utf-8")
    return {"schema":document["schema"],"sha256":hashlib.sha256(encoded).hexdigest()}


def development_run_binding(profile, identities, *, require_worker=True):
    """Bind one shared run to its ordered private accounts and received identities."""
    association = development_run_account_association(
        profile, require_worker=require_worker)
    return development_run_binding_from_association(association, identities)


def require_development_run_binding(report, profile=None, *, require_worker=True,
                                    account_association=None):
    identities = report.get("received_identities")
    binding = report.get("development_profile_binding")
    if (not isinstance(identities, list) or len(identities) != 2
            or not isinstance(binding, dict)
            or set(binding) != {"schema","sha256"}
            or binding.get("schema") != "development-run-profile-association-v1"
            or not isinstance(binding.get("sha256"), str) or len(binding["sha256"]) != 64
            or any(char not in "0123456789abcdef" for char in binding["sha256"])):
        raise DevelopmentError("development run profile association is missing")
    fields = {"slot","name","entity_id","character_id"}
    for index, identity in enumerate(identities):
        if (not isinstance(identity, dict) or set(identity) != fields
                or type(identity.get("slot")) is not int or identity["slot"] != index
                or not isinstance(identity.get("name"), str) or not 1 <= len(identity["name"]) <= 31
                or type(identity.get("entity_id")) is not int
                or not 0 < identity["entity_id"] < 2**32
                or type(identity.get("character_id")) is not int
                or not 0 < identity["character_id"] < 2**64):
            raise DevelopmentError("development run received identity is malformed")
    if (any(len({row[key] for row in identities}) != 2
            for key in ("name","entity_id","character_id"))
            or report.get("entities") != [row["entity_id"] for row in identities]):
        raise DevelopmentError("development run received identities are ambiguous or changed")
    if profile is not None and account_association is not None:
        raise DevelopmentError("development run association input is ambiguous")
    expected = None
    if profile is not None:
        expected = development_run_binding(profile, identities, require_worker=require_worker)
    elif account_association is not None:
        expected = development_run_binding_from_association(account_association, identities)
    if expected is not None and binding != expected:
        raise DevelopmentError("development run differs from exact private profile")
    return identities, binding


def require_provisioning_binding(profile, report):
    if profile.get("host_session") is not None:
        require_managed_host_binding(report.get("managed_host_binding"), True)
    expected = provisioning_binding(profile, report.get("accounts"))
    if report.get("provisioning_binding") != expected:
        raise DevelopmentError("provisioning association missing or mismatched; do not synthesize legacy approval")

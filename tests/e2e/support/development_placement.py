"""Strict private registry binding and retained received placement evidence."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import stat

from .development import DevelopmentError
from .development_operator import validate_placement_registry

SCOPE = "registered-administrative-placement-received-state-not-gameplay-or-command-attestation"


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise DevelopmentError("placement registry contains a duplicate JSON key")
        value[key] = item
    return value


def load_placement_registry(path, profile, catalog_sha256, route):
    try:
        path = Path(path)
        metadata = path.lstat()
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if (path.is_symlink() or not stat.S_ISREG(metadata.st_mode)
                or getattr(metadata, "st_file_attributes", 0) & reparse
                or metadata.st_nlink != 1 or not 0 < metadata.st_size <= 64 * 1024):
            raise OSError()
        raw = path.read_bytes()
        if len(raw) > 64 * 1024:
            raise OSError()
        registry = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DevelopmentError("cannot read private placement registry") from error
    bindings = validate_placement_registry(registry)
    names = [account["character"] for account in profile["accounts"]]
    if ([row["name"] for row in bindings] != names
            or registry["territory"] != profile["territory"]
            or registry["catalog_sha256"] != catalog_sha256
            or not route or registry["position"] != route[0]):
        raise DevelopmentError("placement registry differs from exact profile/catalog route")
    return {"requested":True,"verified":False,"scope":SCOPE,
            "registry_sha256":hashlib.sha256(raw).hexdigest(),
            "approval_id":registry["approval_id"],
            "provisioning_run_id":registry["provisioning_run_id"],
            "catalog_sha256":registry["catalog_sha256"],
            "territory":registry["territory"],"position":registry["position"],
            "targets":bindings,"initial":[],"received":[],
            "state_transition_observed":False,
            "administrative_command_execution_attested":False}


def require_placement_receipt(value, entities, catalog_sha256, route, requested):
    if requested is False:
        if value != {"requested":False,"verified":False}:
            raise DevelopmentError("unrequested placement has retained evidence")
        return None
    fields = {"requested","verified","scope","registry_sha256","approval_id",
              "provisioning_run_id","catalog_sha256","territory","position","targets",
              "initial","received","state_transition_observed",
              "administrative_command_execution_attested"}
    if (requested is not True or not isinstance(value, dict) or set(value) != fields
            or value.get("requested") is not True or value.get("verified") is not True
            or value.get("scope") != SCOPE
            or value.get("administrative_command_execution_attested") is not False
            or value.get("catalog_sha256") != catalog_sha256
            or type(value.get("territory")) is not int or value["territory"] != 130
            or not route or value.get("position") != route[0]):
        raise DevelopmentError("registered placement receipt is missing or changed")
    for key, length in (("registry_sha256",64),("approval_id",32),("provisioning_run_id",32)):
        item = value.get(key)
        if (not isinstance(item, str) or len(item) != length
                or any(char not in "0123456789abcdef" for char in item)):
            raise DevelopmentError("registered placement identity is invalid")
    targets, initial, received = value.get("targets"), value.get("initial"), value.get("received")
    if (not isinstance(targets, list) or len(targets) != 2
            or not isinstance(initial, list) or len(initial) != 2
            or not isinstance(received, list) or len(received) != 2):
        raise DevelopmentError("registered placement requires two exact observations")
    target_fields = {"name","entity_id","character_id"}
    for index, target in enumerate(targets):
        if (not isinstance(target, dict) or set(target) != target_fields
                or type(target.get("entity_id")) is not int
                or target["entity_id"] != entities[index]
                or type(target.get("character_id")) is not int
                or not 0 < target["character_id"] < 2**64
                or not isinstance(target.get("name"), str)
                or not re.fullmatch(r"Tester [A-Z]{12}", target["name"])):
            raise DevelopmentError("registered placement target differs from run identity")
    if any(len({row[key] for row in targets}) != 2 for key in target_fields):
        raise DevelopmentError("registered placement targets are ambiguous")
    transitioned = True
    for index, (before, after, target) in enumerate(zip(initial, received, targets)):
        if (not isinstance(before, dict)
                or set(before) != {"slot","identity","territory","baseline_sequence"}
                or type(before.get("slot")) is not int or before["slot"] != index
                or before.get("identity") != target
                or type(before.get("territory")) is not int or before["territory"] not in {130,182}
                or type(before.get("baseline_sequence")) is not int
                or not 0 <= before["baseline_sequence"] < 2**64
                or not isinstance(after, dict)
                or set(after) != {"slot","identity","territory","position","received_sequence"}
                or type(after.get("slot")) is not int or after["slot"] != index
                or after.get("identity") != target
                or type(after.get("territory")) is not int or after["territory"] != 130
                or type(after.get("received_sequence")) is not int
                or not before["baseline_sequence"] <= after["received_sequence"] < 2**64
                or not isinstance(after.get("position"), list) or len(after["position"]) != 3
                or any(type(item) not in {int,float} or isinstance(item, bool)
                       or not math.isfinite(item) for item in after["position"])
                or math.dist(after["position"], route[0]) > 0.15):
            raise DevelopmentError("registered placement received observation is malformed")
        changed = before["territory"] != 130
        if changed and after["received_sequence"] <= before["baseline_sequence"]:
            raise DevelopmentError("registered placement transition did not advance received state")
        transitioned = transitioned and changed
    if type(value.get("state_transition_observed")) is not bool or value["state_transition_observed"] is not transitioned:
        raise DevelopmentError("registered placement transition classification is invalid")
    return value

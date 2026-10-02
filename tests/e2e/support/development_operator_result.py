"""Strict diagnosis of two scripted local GM placement publications.

Accepted evidence proves only local worker publication after immutable intent. It
is not a server acknowledgement, received placement, gameplay, or retry authority.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import stat

from .development import DevelopmentError
from .development_placement import read_placement_registry

SCOPE = "two-scripted-local-placement-publications-not-server-or-mutation-proof"


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise DevelopmentError("operator evidence contains a duplicate JSON key")
        value[key] = item
    return value


def _read(path, label):
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
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DevelopmentError(f"cannot read operator {label}") from error
    if not isinstance(value, dict):
        raise DevelopmentError(f"operator {label} is not an object")
    return raw, value


def _typed_equal(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return (set(left) == set(right)
                and all(_typed_equal(left[key], right[key]) for key in left))
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _typed_equal(left[index], right[index]) for index in range(len(left)))
    return left == right


def _operator(value):
    if (not isinstance(value, dict) or set(value) != {"name","entity_id","character_id"}
            or not isinstance(value.get("name"), str) or not 1 <= len(value["name"]) <= 31
            or type(value.get("entity_id")) is not int or not 0 < value["entity_id"] < 2**32
            or type(value.get("character_id")) is not int
            or not 0 < value["character_id"] < 2**64):
        raise DevelopmentError("operator identity is malformed")
    return value


def inspect_development_operator_publications(registry_path, artifact_dir):
    registry_raw, registry, targets = read_placement_registry(registry_path)
    artifact_dir = Path(artifact_dir)
    try:
        metadata = artifact_dir.lstat()
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if (artifact_dir.is_symlink() or not stat.S_ISDIR(metadata.st_mode)
                or getattr(metadata, "st_file_attributes", 0) & reparse):
            raise OSError()
    except OSError as error:
        raise DevelopmentError("operator artifact directory is unsafe") from error
    approval = registry["approval_id"]
    expected_names = {
        *(f"placement-request-{approval}-{slot}.json" for slot in range(2)),
        *(f"placement-publication-{approval}-{slot}.json" for slot in range(2)),
    }
    try:
        relevant = {entry.name for entry in artifact_dir.iterdir()
                    if entry.name.casefold().startswith(("placement-request-","placement-publication-"))
                    and entry.name.casefold().endswith(".json")}
    except OSError as error:
        raise DevelopmentError("cannot enumerate operator artifacts") from error
    if relevant != expected_names:
        raise DevelopmentError("operator artifact set is missing or foreign")
    intent_fields = {"version","scope","execution_authorized","approval_id",
        "provisioning_run_id","slot",
        "operator","operator_gm_rank","operator_received_sequence","expected_target",
        "status","placement_verified","note"}
    publication_fields = {"version","scope","execution_authorized","approval_id",
        "provisioning_run_id","slot",
        "intent_sha256","operator","operator_gm_rank","operator_received_sequence",
        "expected_target","status","receipt","placement_verified","note"}
    receipt = {"scope":"administrative-preparation-not-gameplay",
               "publication":"local-only","placement_verified":False}
    operator = None
    sequences, rows = [], []
    for slot in range(2):
        intent_raw, intent = _read(
            artifact_dir / f"placement-request-{approval}-{slot}.json", "intent")
        publication_raw, publication = _read(
            artifact_dir / f"placement-publication-{approval}-{slot}.json", "publication")
        common = (intent.get("version") == 1
            and intent.get("scope") == "administrative-preparation-not-gameplay"
            and intent.get("execution_authorized") is True
            and intent.get("approval_id") == approval
            and intent.get("provisioning_run_id") == registry["provisioning_run_id"]
            and type(intent.get("slot")) is int and intent["slot"] == slot
            and _typed_equal(intent.get("expected_target"), targets[slot])
            and type(intent.get("operator_gm_rank")) is int
            and 1 <= intent["operator_gm_rank"] <= 255
            and type(intent.get("operator_received_sequence")) is int
            and 0 <= intent["operator_received_sequence"] < 2**64
            and intent.get("placement_verified") is False)
        if (set(intent) != intent_fields or not common
                or intent.get("status") != "publication_outcome_unknown"
                or intent.get("note") != "Never retry an uncertain request; require normal-client received-state evidence."):
            raise DevelopmentError("operator pre-dispatch intent is malformed")
        identity = _operator(intent.get("operator"))
        if any(identity[key] == target[key] for target in targets
               for key in ("entity_id","character_id")):
            raise DevelopmentError("operator identity aliases a registered target")
        if operator is None:
            operator = {"identity":identity,"gm_rank":intent["operator_gm_rank"]}
        elif operator != {"identity":identity,"gm_rank":intent["operator_gm_rank"]}:
            raise DevelopmentError("operator identity changed between publications")
        sequences.append(intent["operator_received_sequence"])
        publication_identity = _operator(publication.get("operator"))
        if (set(publication) != publication_fields
                or publication.get("version") != 1
                or publication.get("scope") != intent["scope"]
                or publication.get("execution_authorized") is not True
                or publication.get("approval_id") != approval
                or publication.get("provisioning_run_id") != registry["provisioning_run_id"]
                or type(publication.get("slot")) is not int or publication["slot"] != slot
                or publication.get("intent_sha256") != hashlib.sha256(intent_raw).hexdigest()
                or not _typed_equal(publication_identity, identity)
                or type(publication.get("operator_gm_rank")) is not int
                or publication["operator_gm_rank"] != intent["operator_gm_rank"]
                or type(publication.get("operator_received_sequence")) is not int
                or publication["operator_received_sequence"] != intent["operator_received_sequence"]
                or not _typed_equal(publication.get("expected_target"), targets[slot])
                or publication.get("status") != "local_publication_only"
                or not _typed_equal(publication.get("receipt"), receipt)
                or publication.get("placement_verified") is not False
                or publication.get("note") != "Local worker publication only; require normal-client received-state evidence."):
            raise DevelopmentError("operator terminal local-publication evidence is malformed")
        rows.append({"slot":slot,"intent_sha256":hashlib.sha256(intent_raw).hexdigest(),
                     "publication_sha256":hashlib.sha256(publication_raw).hexdigest()})
    if sequences != sorted(sequences):
        raise DevelopmentError("operator received sequences moved backwards")
    encoded_operator = json.dumps(operator, sort_keys=True, separators=(",", ":")).encode()
    return {"version":1,"status":"accepted_local_publication_only","scope":SCOPE,
            "execution_authorized":True,
            "approval_id":approval,"provisioning_run_id":registry["provisioning_run_id"],
            "registry_sha256":hashlib.sha256(registry_raw).hexdigest(),
            "operator_identity_sha256":hashlib.sha256(encoded_operator).hexdigest(),
            "targets":targets,"publications":rows,
            "server_acknowledgement_verified":False,"placement_verified":False,
            "retry_authorized":False,
            "note":"Two immutable intents reached local worker publication only; require independent normal-client received placement evidence."}

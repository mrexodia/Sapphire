"""Strict external provisioning→registry→received-placement correlation."""
from __future__ import annotations

import hashlib

from .development import DevelopmentError, movement_route
from .development_placement import load_placement_registry
from .development_result import validate_development_evidence
from .managed_provisioning_result import validate_provisioning_evidence

SCOPE = "external-provisioning-registry-received-placement-chain-not-command-or-reset-proof"


def inspect_development_placement_chain(profile_path, provisioning_summary,
                                        registry_path, development_summary):
    provisioning = validate_provisioning_evidence(
        provisioning_summary, profile_path, managed=False)
    profile, provision_report = provisioning["profile"], provisioning["report"]
    route, catalog_sha256 = movement_route(profile)
    if not route:
        raise DevelopmentError("placement chain requires one source-bound movement route")
    registry = load_placement_registry(registry_path, profile, catalog_sha256, route)
    development = validate_development_evidence(development_summary)
    run_report = development["report"]
    placement = run_report.get("placement_verification")
    if (run_report.get("administrative_preparation_wait_enabled") is not True
            or not isinstance(placement, dict) or placement.get("verified") is not True):
        raise DevelopmentError("development run lacks verified registered placement evidence")
    keys = ("registry_sha256","approval_id","provisioning_run_id","catalog_sha256",
            "territory","position","targets")
    if any(placement.get(key) != registry.get(key) for key in keys):
        raise DevelopmentError("development placement differs from reviewed registry bytes")
    if registry["provisioning_run_id"] != provisioning["run_id"]:
        raise DevelopmentError("placement registry differs from exact provisioning run")
    expected_targets = [{"name":row["character"],"entity_id":row["entity_id"],
                         "character_id":row["character_id"]}
                        for row in provisioning["accounts"]]
    if registry["targets"] != expected_targets:
        raise DevelopmentError("placement registry differs from provisioned identities")
    return {"version":1,"status":"accepted","scope":SCOPE,
            "provisioning_run_id":provisioning["run_id"],
            "development_run_id":development["run_id"],
            "provisioning_summary_sha256":hashlib.sha256(
                provisioning["summary_raw"]).hexdigest(),
            "registry_sha256":registry["registry_sha256"],
            "development_summary_sha256":hashlib.sha256(development["raw"]).hexdigest(),
            "catalog_sha256":registry["catalog_sha256"],
            "approval_id":registry["approval_id"],
            "received_targets":expected_targets,
            "state_transition_observed":placement["state_transition_observed"],
            "verified_checks":development["checks"],
            "managed_host":False,"administrative_command_execution_attested":False,
            "note":"Exact external provisioning/registry/received-state correlation only; not command causation, gameplay, reset, offline exclusion or server identity."}

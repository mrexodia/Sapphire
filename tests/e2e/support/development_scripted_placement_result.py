"""Correlate scripted local publication with external received placement evidence."""
from __future__ import annotations

from .development import DevelopmentError
from .development_operator_result import inspect_development_operator_publications
from .development_placement_result import inspect_development_placement_chain

SCOPE = "scripted-local-publication-and-received-placement-correlation-not-command-causation"


def inspect_development_scripted_placement(profile_path, provisioning_summary,
                                           registry_path, operator_artifact_dir,
                                           development_summary):
    chain = inspect_development_placement_chain(
        profile_path, provisioning_summary, registry_path, development_summary)
    operator = inspect_development_operator_publications(
        registry_path, operator_artifact_dir)
    if (operator["approval_id"] != chain["approval_id"]
            or operator["provisioning_run_id"] != chain["provisioning_run_id"]
            or operator["registry_sha256"] != chain["registry_sha256"]
            or operator["targets"] != chain["received_targets"]):
        raise DevelopmentError("scripted publication differs from received placement chain")
    return {"version":1,"status":"accepted_correlation_only","scope":SCOPE,
            "provisioning_run_id":chain["provisioning_run_id"],
            "development_run_id":chain["development_run_id"],
            "approval_id":chain["approval_id"],
            "registry_sha256":chain["registry_sha256"],
            "provisioning_summary_sha256":chain["provisioning_summary_sha256"],
            "development_summary_sha256":chain["development_summary_sha256"],
            "operator_identity_sha256":operator["operator_identity_sha256"],
            "operator_execution_authorized":operator["execution_authorized"],
            "targets":chain["received_targets"],
            "local_publications":operator["publications"],
            "verified_checks":chain["verified_checks"],
            "state_transition_observed":chain["state_transition_observed"],
            "local_publication_verified":True,"received_placement_verified":True,
            "server_acknowledgement_verified":False,
            "command_causation_verified":False,"retry_authorized":False,
            "note":"Matching local publication and later received state are correlated, not proof that the publication caused the mutation."}

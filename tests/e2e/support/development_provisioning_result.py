"""Strict sanitized inspection of external shared-server provisioning evidence."""
from __future__ import annotations

import hashlib

from .managed_provisioning_result import validate_provisioning_evidence

SCOPE = "external-shared-provisioning-evidence-not-managed-host-gameplay-or-reset"


def inspect_development_provisioning(summary_path, profile_path):
    evidence = validate_provisioning_evidence(summary_path, profile_path, managed=False)
    report, accounts = evidence["report"], evidence["accounts"]
    return {"version":1,"status":"accepted","scope":SCOPE,
            "run_id":evidence["run_id"],
            "summary_sha256":hashlib.sha256(evidence["summary_raw"]).hexdigest(),
            "worker_sha256":report["worker_sha256"],
            "worker_artifacts":evidence["worker_artifacts"],
            "run_deadline":evidence["deadline"],
            "run_worker_exit":report["worker_exit"],
            "lease_snapshot":evidence["lease"],
            "managed_host":False,"managed_host_binding":evidence["binding"],
            "provisioning_binding":report["provisioning_binding"],
            "received_identities":[{"slot":row["slot"],"character":row["character"],
                                    "entity_id":row["entity_id"],"character_id":row["character_id"]}
                                   for row in accounts],
            "ready_for_shared_checks":False,
            "server_identity_verified":False,
            "note":"Fresh external-server provisioning evidence only; not gameplay, opening/placement, offline/reset authority, retry permission or server identity."}

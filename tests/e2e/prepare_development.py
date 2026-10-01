"""Generate an operator-approved placement registry. No network, DB or server changes."""
import argparse
import json
from pathlib import Path
import re
import uuid

from .support.development import (DevelopmentError, movement_route, validate_profile,
                                  require_normal_worker_exit)
from .support.development_binding import require_provisioning_binding
from .support.development_lease import require_clear_terminal_account_leases
from .provision_development import reserve_private_profile


def placement_registry(profile, provisioning):
    validate_profile(profile)
    route, catalog_hash = movement_route(profile)
    if not route:
        raise DevelopmentError("placement requires a validated Motivational Speaking quest_catalog")
    if (provisioning.get("scope") != "shared-development-provisioning-not-gameplay"
            or provisioning.get("status") != "provisioned"
            or provisioning.get("lease_retained") is not False
            or provisioning.get("worker_closed") is not True
            or provisioning.get("credential_profile_saved") is not True):
        raise DevelopmentError("a completed clean provisioning report is required")
    require_clear_terminal_account_leases(provisioning)
    run_id = provisioning.get("run_id")
    if not isinstance(run_id, str) or not re.fullmatch("[0-9a-f]{32}", run_id):
        raise DevelopmentError("exact provisioning run identity is required; legacy reports cannot authorize placement")
    require_provisioning_binding(profile, provisioning)
    require_normal_worker_exit(provisioning)
    rows = provisioning.get("accounts", [])
    if not isinstance(rows, list) or len(rows) != 2:
        raise DevelopmentError("exactly two provisioned accounts are required")
    bindings = []
    for index, (account, row) in enumerate(zip(profile["accounts"], rows)):
        if (type(row.get("slot")) is not int or row.get("slot") != index or row.get("character") != account["character"]
                or not re.fullmatch(r"Tester [A-Z]{12}", account["character"])
                or row.get("account_creation") != "fresh_login_verified"
                or row.get("character_creation") != "refreshed_lobby_and_world_verified"
                or row.get("logout_server_close_verified") is not True
                or type(row.get("gm_rank")) is not int or row.get("gm_rank") != 0):
            raise DevelopmentError("provisioned identity/ownership/lifecycle mismatch")
        for key, maximum in (("entity_id", 2**32 - 1), ("character_id", 2**64 - 1)):
            if type(row.get(key)) is not int or not 0 < row[key] <= maximum:
                raise DevelopmentError("missing/invalid received identity; legacy reports cannot authorize placement")
        bindings.append({"name": account["character"], "entity_id": row["entity_id"],
                         "character_id": row["character_id"]})
    for key in ("entity_id", "character_id", "name"):
        if len({row[key] for row in bindings}) != 2:
            raise DevelopmentError("duplicate bot identity")
    return {"version": 2, "purpose": "development-bot-placement", "approval_id": uuid.uuid4().hex,
            "provisioning_run_id": run_id, "territory": 130, "position": route[0],
            "catalog_sha256": catalog_hash, "bots": bindings}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--provisioning-report", required=True)
    parser.add_argument("--registry", required=True, help="New private registry path; keep untracked")
    parser.add_argument("--approve-fixture-placement", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not args.approve_fixture_placement:
            raise DevelopmentError("explicit fixture placement approval is required")
        profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
        report = json.loads(Path(args.provisioning_report).read_text(encoding="utf-8"))
        registry = placement_registry(profile, report)
        # Same exclusive/private/untracked writer as credential provisioning;
        # the registry includes generated source geometry and must stay private.
        reserve_private_profile(args.registry, registry)
        print(json.dumps({"status": "registry_written_not_executed", "registry": args.registry,
                          "operator_commands": [f"!devbot place {registry['approval_id']} {i}" for i in range(2)]}))
        return 0
    except Exception as error:
        print(json.dumps({"status": "failed", "error_type": type(error).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

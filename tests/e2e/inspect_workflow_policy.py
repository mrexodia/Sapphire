"""Read-only inspection of repository E2E workflow security/lifecycle controls."""
from __future__ import annotations

import json

from .support.environment import REPO
from .support.workflow_policy import inspect_dependency_lock, inspect_workflow


def inspect():
    public = inspect_workflow(REPO / ".github/workflows/test-client.yml", private=False)
    private = inspect_workflow(REPO / ".github/workflows/gameplay-e2e.yml", private=True)
    dependencies = inspect_dependency_lock(REPO / "tests/e2e/requirements.txt")
    return {"version": 1, "status": "accepted",
            "scope": "repository-workflow-controls-not-hosted-execution-or-runner-policy",
            "workflows": [public, private], "dependency_lock":dependencies,
            "hosted_execution_verified": False,
            "runner_group_policy_verified": False,
            "ephemeral_vm_destruction_verified": False}


def main():
    print(json.dumps(inspect(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

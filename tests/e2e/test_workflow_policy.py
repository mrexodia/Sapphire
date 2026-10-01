"""Repository workflow policy contracts, not GitHub-hosted execution evidence."""
from pathlib import Path

import pytest

from .inspect_workflow_policy import main as inspect_main
from .support.development import DevelopmentError
from .support.environment import REPO
from .support.workflow_policy import inspect_workflow


PUBLIC = REPO / ".github/workflows/test-client.yml"
PRIVATE = REPO / ".github/workflows/gameplay-e2e.yml"


def test_e2e_workflow_inspector_emits_narrow_structured_receipt(capsys):
    assert inspect_main() == 0
    import json
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["status"] == "accepted" and len(receipt["workflows"]) == 2
    assert receipt["hosted_execution_verified"] is False
    assert receipt["runner_group_policy_verified"] is False
    assert receipt["ephemeral_vm_destruction_verified"] is False


def test_e2e_workflows_have_pinned_least_privilege_bounded_controls():
    public = inspect_workflow(PUBLIC, private=False)
    private = inspect_workflow(PRIVATE, private=True)
    assert public["verified"] and private["verified"]
    assert [row["name"] for row in public["jobs"]] == ["contracts"]
    assert [row["name"] for row in private["jobs"]] == ["authorize", "gameplay"]
    assert [row["timeout_minutes"] for row in private["jobs"]] == [5, 120]
    assert private["private_evidence_inspection_required"] is True
    assert private["service_free_staging_required"] is True
    assert private["failed_summary_inspection_required"] is True
    assert [len(public["pinned_actions"]), len(private["pinned_actions"])] == [3, 3]
    assert all("@" in action and len(action.rsplit("@", 1)[1]) == 40
               for proof in (public, private) for action in proof["pinned_actions"])
    assert public["scope"] == private["scope"] == (
        "repository-workflow-controls-not-hosted-execution-or-runner-policy")


@pytest.mark.parametrize("source, old, new", [
    (PUBLIC, "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
             "actions/checkout@v7"),
    (PUBLIC, "  contents: read", "  contents: write"),
    (PUBLIC, "    timeout-minutes: 25", "    timeout-minutes: 0"),
    (PUBLIC, "        timeout-minutes: 5", "        timeout-minutes: 0"),
    (PUBLIC, "          persist-credentials: false", "          persist-credentials: true"),
    (PUBLIC, "          retention-days: 7", "          retention-days: 31"),
    (PUBLIC, "          if-no-files-found: warn", "          if-no-files-found: ignore"),
    (PRIVATE, "  cancel-in-progress: false", "  cancel-in-progress: true"),
    (PRIVATE, "    runs-on: [self-hosted, Windows, X64, sapphire-e2e-ephemeral]",
              "    runs-on: ubuntu-latest"),
    (PRIVATE, "  workflow_dispatch:", "  pull_request:\n  workflow_dispatch:"),
    (PRIVATE, "--expected-revision \"${{ github.sha }}\"",
              "--expected-revision \"${{ github.ref }}\""),
    (PRIVATE, "if ($LASTEXITCODE -ne 0) { throw 'Published gameplay summary inspection failed' }",
              "if ($false) { throw 'Published gameplay summary inspection failed' }"),
    (PRIVATE, "if ($LASTEXITCODE -ne 0) { throw 'Private gameplay evidence inspection failed' }",
              "if ($false) { throw 'Private gameplay evidence inspection failed' }"),
    (PRIVATE, "if ($LASTEXITCODE -ne 0) { throw 'Failed gameplay summary is unsafe to publish' }",
              "if ($false) { throw 'Failed gameplay summary is unsafe to publish' }"),
    (PRIVATE, "$privateRuns.Count -ne 1", "$privateRuns.Count -lt 99"),
    (PRIVATE, '--private-root "$privateRoot"', '--private-root "$env:RUNNER_TEMP"'),
    (PRIVATE, '--private-artifacts "$stageRoot"',
              '--private-artifacts "$env:RUNNER_TEMP"'),
    (PRIVATE, "if ($LASTEXITCODE -ne 0) { throw 'Service-free private profile staging failed' }",
              "if ($false) { throw 'Service-free private profile staging failed' }"),
    (PRIVATE, "          test \"$SELECTED_REF\" = \"$TRUSTED_REF\"",
              "          test \"$SELECTED_REF\" = \"$SELECTED_REF\""),
])
def test_workflow_policy_rejects_mutable_unbounded_or_untrusted_controls(
        tmp_path, source, old, new):
    text = source.read_text(encoding="utf-8")
    assert text.count(old) >= 1
    path = tmp_path / source.name
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    with pytest.raises(DevelopmentError):
        inspect_workflow(path, private=source == PRIVATE)

"""Repository workflow policy contracts, not GitHub-hosted execution evidence."""
from pathlib import Path

import pytest

from .inspect_workflow_policy import main as inspect_main
from .support.development import DevelopmentError
from .support.environment import REPO
from .support.workflow_policy import inspect_dependency_lock, inspect_workflow


PUBLIC = REPO / ".github/workflows/test-client.yml"
PRIVATE = REPO / ".github/workflows/gameplay-e2e.yml"
DEPENDENCIES = REPO / "tests/e2e/requirements.txt"


def test_e2e_workflow_inspector_emits_narrow_structured_receipt(capsys):
    assert inspect_main() == 0
    import json
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["status"] == "accepted" and len(receipt["workflows"]) == 2
    assert receipt["hosted_execution_verified"] is False
    assert receipt["runner_group_policy_verified"] is False
    assert receipt["ephemeral_vm_destruction_verified"] is False
    assert receipt["dependency_lock"]["verified"] is True
    assert receipt["dependency_lock"]["package_count"] == 7
    assert receipt["dependency_lock"]["source_distributions_allowed"] is False


def test_e2e_workflows_have_pinned_least_privilege_bounded_controls():
    public = inspect_workflow(PUBLIC, private=False)
    private = inspect_workflow(PRIVATE, private=True)
    assert public["verified"] and private["verified"]
    assert [row["name"] for row in public["jobs"]] == ["contracts"]
    assert [row["name"] for row in private["jobs"]] == ["authorize", "gameplay"]
    assert [row["timeout_minutes"] for row in private["jobs"]] == [5, 120]
    assert private["private_evidence_inspection_required"] is True
    assert private["service_free_staging_required"] is True
    assert private["exact_clean_checkout_required"] is True
    assert private["failed_summary_inspection_required"] is True
    assert public["hash_locked_dependencies_required"] is True
    assert private["hash_locked_dependencies_required"] is True
    assert public["ambient_pytest_plugins_disabled"] is True
    assert private["ambient_pytest_plugins_disabled"] is True
    assert public["standalone_case_runner_contracts_required"] is True
    assert private["standalone_case_runner_contracts_required"] is True
    assert private["standalone_dispatch_required"] is True
    assert private["standalone_private_evidence_inspection_required"] is True
    assert private["standalone_failure_sanitization_required"] is True
    assert private["explicit_execution_authorization_required"] is True
    assert public["standalone_dispatch_required"] is False
    assert inspect_dependency_lock(DEPENDENCIES)["package_count"] == 7
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
    (PUBLIC, "pip install --require-hashes --only-binary=:all:",
             "pip install --only-binary=:all:"),
    (PUBLIC, "      PYTEST_DISABLE_PLUGIN_AUTOLOAD: '1'",
             "      PYTEST_DISABLE_PLUGIN_AUTOLOAD: '0'"),
    (PUBLIC, " tests/e2e/test_isolated_case_runner.py", ""),
    (PUBLIC, " tests/e2e/test_isolated_case_run_result.py", ""),
    (PUBLIC, " tests/e2e/test_isolated_case_run_failure_result.py", ""),
    (PUBLIC, "          if-no-files-found: warn", "          if-no-files-found: ignore"),
    (PRIVATE, "  cancel-in-progress: false", "  cancel-in-progress: true"),
    (PRIVATE, "pip install --require-hashes --only-binary=:all:",
              "pip install --require-hashes"),
    (PRIVATE, "      PYTEST_DISABLE_PLUGIN_AUTOLOAD: '1'",
              "      PYTEST_DISABLE_PLUGIN_AUTOLOAD: '0'"),
    (PRIVATE, " tests/e2e/test_isolated_case_runner.py", ""),
    (PRIVATE, " tests/e2e/test_isolated_case_run_result.py", ""),
    (PRIVATE, " tests/e2e/test_isolated_case_run_failure_result.py", ""),
    (PRIVATE, "--only-binary=:all: --no-deps", "--only-binary=:all:"),
    (PRIVATE, "    runs-on: [self-hosted, Windows, X64, sapphire-e2e-ephemeral]",
              "    runs-on: ubuntu-latest"),
    (PRIVATE, "  workflow_dispatch:", "  pull_request:\n  workflow_dispatch:"),
    (PRIVATE, "          ref: ${{ github.sha }}", "          ref: ${{ github.ref }}"),
    (PRIVATE, "$head -ne $env:EXPECTED_SHA", "$head -ne $head"),
    (PRIVATE, "$changes.Count -ne 0", "$changes.Count -lt 0"),
    (PRIVATE, "$_ -match '^[-+U]'", "$_ -match '^$'"),
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
    (PRIVATE, "      authorized_selected_scope:", "      foreign_authorization:"),
    (PRIVATE, "          test \"$EXECUTION_ACK\" = true",
              "          test \"$EXECUTION_ACK\" = false"),
    (PRIVATE, '          - "tests/e2e/test_live.py::test_login_idle_logout"',
              '          - "tests/e2e/foreign.py::test_foreign"'),
    (PRIVATE, "python -m tests.e2e.run_isolated_case --profile",
              "python -m tests.e2e.run_ci --profile"),
    (PRIVATE, " --authorize-disposable-fixture", ""),
    (PRIVATE, "python -m tests.e2e.inspect_isolated_case_run --private-root",
              "python -m tests.e2e.inspect_isolated_case --private-root"),
    (PRIVATE, "python -m tests.e2e.inspect_isolated_case_run_failure --private-root",
              "python -m tests.e2e.inspect_isolated_case_run --private-root"),
    (PRIVATE, "$standaloneExit = $LASTEXITCODE", "$standaloneExit = 0"),
    (PRIVATE, "Failed standalone isolated case summary is unsafe to publish",
              "Failed standalone isolated case summary may publish"),
    (PRIVATE, "          path: ${{ steps.gameplay.outputs.summary_path }}",
              "          path: .e2e-ci-summary.json"),
    (PRIVATE, "          $summaryPath = '.e2e-isolated-case-summary.json'",
              "          $summaryPath = $env:EXECUTION_SCOPE"),
    (PRIVATE, "          if (Test-Path .e2e-isolated-case-summary.json)",
              "          if ($false)"),
])
def test_workflow_policy_rejects_mutable_unbounded_or_untrusted_controls(
        tmp_path, source, old, new):
    text = source.read_text(encoding="utf-8")
    assert text.count(old) >= 1
    path = tmp_path / source.name
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    with pytest.raises(DevelopmentError):
        inspect_workflow(path, private=source == PRIVATE)


@pytest.mark.parametrize("old,new", [
    ("pytest==8.4.1", "pytest>=8"),
    ("539c70ba6fcead8e78eebbf1115e8b589e7565830d7d006a8723f19ac8a0afb7",
     "0" * 64),
    ("psutil==6.1.1", "psutil==7.0.0"),
    ("pygments==2.19.2", "--index-url=https://example.invalid\npygments==2.19.2"),
    ("colorama==0.4.6", "pytest==8.4.1"),
])
def test_dependency_lock_rejects_ranges_changed_hashes_or_unreviewed_inputs(
        tmp_path, old, new):
    text = DEPENDENCIES.read_text(encoding="utf-8")
    assert text.count(old) == 1
    path = tmp_path / "requirements.txt"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    with pytest.raises(DevelopmentError):
        inspect_dependency_lock(path)


def test_private_workflow_requires_service_free_staging_before_gate(tmp_path):
    text = PRIVATE.read_text(encoding="utf-8")
    lines = text.splitlines()
    stage = next(line for line in lines if "python -m tests.e2e.stage_ci_profile" in line)
    gate = next(line for line in lines if "python -m tests.e2e.run_ci" in line)
    text = text.replace(stage, "__STAGE_COMMAND__", 1).replace(gate, stage, 1)
    text = text.replace("__STAGE_COMMAND__", gate, 1)
    path = tmp_path / PRIVATE.name; path.write_text(text, encoding="utf-8")
    with pytest.raises(DevelopmentError):
        inspect_workflow(path, private=True)

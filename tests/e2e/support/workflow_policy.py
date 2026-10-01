"""Minimal fail-closed policy inspection for Sapphire's two E2E workflows.

This intentionally validates only security/lifecycle controls represented by the
repository text. It does not execute GitHub Actions or prove hosted runner policy.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re

from .development import DevelopmentError

PINNED_ACTION = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")
JOB = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$")
STEP = re.compile(r"^      - (?:name|uses|run):")


def _block(lines, start, end_indent):
    end = start + 1
    while end < len(lines):
        line = lines[end]
        if line.strip() and not line.lstrip().startswith("#"):
            indent = len(line) - len(line.lstrip(" "))
            if indent <= end_indent:
                break
        end += 1
    return lines[start:end]


def _integer(block, indent, key, description):
    pattern = re.compile(rf"^{' ' * indent}{re.escape(key)}:\s*([0-9]+)\s*$")
    values = [int(match.group(1)) for line in block if (match := pattern.match(line))]
    if len(values) != 1 or not 1 <= values[0] <= 360:
        raise DevelopmentError(f"workflow requires one bounded {description}")
    return values[0]


def inspect_workflow(path, *, private):
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise DevelopmentError(f"cannot read workflow policy: {path.name}") from error
    lines = raw.splitlines()
    if not lines or any("\t" in line or line.rstrip() != line for line in lines):
        raise DevelopmentError("workflow contains ambiguous tabs or trailing whitespace")

    try:
        permission_start = lines.index("permissions:")
        jobs_start = lines.index("jobs:")
    except ValueError as error:
        raise DevelopmentError("workflow lacks explicit permissions or jobs") from error
    permission = [line.strip() for line in _block(lines, permission_start, 0)[1:]
                  if line.strip() and not line.lstrip().startswith("#")]
    if permission != ["contents: read"]:
        raise DevelopmentError("workflow token permissions must be exactly contents: read")

    headers = [(index, match.group(1)) for index, line in enumerate(lines[jobs_start + 1:],
               jobs_start + 1) if (match := JOB.match(line))]
    if not headers:
        raise DevelopmentError("workflow has no jobs")
    jobs, actions = [], []
    for offset, (start, name) in enumerate(headers):
        end = headers[offset + 1][0] if offset + 1 < len(headers) else len(lines)
        block = lines[start:end]
        job_timeout = _integer(block, 4, "timeout-minutes", f"job timeout for {name}")
        try:
            steps_start = next(index for index, line in enumerate(block) if line == "    steps:")
        except StopIteration as error:
            raise DevelopmentError(f"workflow job {name} has no steps") from error
        starts = [index for index, line in enumerate(block[steps_start + 1:], steps_start + 1)
                  if STEP.match(line)]
        if not starts:
            raise DevelopmentError(f"workflow job {name} has no recognized steps")
        for step_offset, step_start in enumerate(starts):
            step_end = starts[step_offset + 1] if step_offset + 1 < len(starts) else len(block)
            step = block[step_start:step_end]
            step_timeout = _integer(step, 8, "timeout-minutes", f"step timeout in {name}")
            if step_timeout > job_timeout:
                raise DevelopmentError(f"workflow step timeout exceeds job timeout in {name}")
            uses = []
            for line in step:
                match = re.match(r"^\s*(?:-\s*)?uses:\s*(\S+)", line)
                if match:
                    uses.append(match.group(1))
            if len(uses) > 1:
                raise DevelopmentError("workflow step has ambiguous external actions")
            if uses:
                action = uses[0]
                if action.startswith("./") or not PINNED_ACTION.fullmatch(action):
                    raise DevelopmentError("external workflow actions require exact 40-hex pins")
                actions.append(action)
                if action.startswith("actions/checkout@") and not any(
                        line.strip() == "persist-credentials: false" for line in step):
                    raise DevelopmentError("checkout must not persist workflow credentials")
                if action.startswith("actions/upload-artifact@"):
                    retention = _integer(step, 10, "retention-days", "artifact retention")
                    if retention > 30 or not any(line.strip() in {
                            "if-no-files-found: warn", "if-no-files-found: error"} for line in step):
                        raise DevelopmentError("artifact upload lacks bounded fail-closed retention policy")
        jobs.append({"name": name, "timeout_minutes": job_timeout,
                     "step_count": len(starts)})

    on_start = next((index for index, line in enumerate(lines) if line == "on:"), None)
    if private:
        if on_start is None:
            raise DevelopmentError("private workflow requires structured dispatch trigger")
        triggers = _block(lines, on_start, 0)
        if not any(line == "  workflow_dispatch:" for line in triggers):
            raise DevelopmentError("private workflow lacks explicit manual dispatch")
        forbidden = re.compile(r"^  (?:push|pull_request|schedule|workflow_call):")
        if any(forbidden.match(line) for line in triggers):
            raise DevelopmentError("private workflow exposes an untrusted trigger")
        required = ("  cancel-in-progress: false",
                    "    environment: sapphire-private-e2e",
                    "    runs-on: [self-hosted, Windows, X64, sapphire-e2e-ephemeral]",
                    "    needs: authorize",
                    "        type: boolean",
                    "        default: false",
                    "          test \"$ACK\" = true || { echo 'Explicit review acknowledgement required'; exit 1; }",
                    "          test \"$ENABLED\" = true || { echo 'Private E2E runner is not enabled'; exit 1; }",
                    "          test \"$SELECTED_REF\" = \"$TRUSTED_REF\" || { echo 'Only the trusted default branch is allowed'; exit 1; }",
                    "          $privateRoot = Join-Path $env:RUNNER_TEMP \"sapphire-private-e2e-${{ github.run_id }}-${{ github.run_attempt }}\"",
                    "          if (Test-Path $privateRoot) { throw 'Private run root must start absent' }",
                    "          $stageRoot = Join-Path $env:RUNNER_TEMP \"sapphire-private-e2e-stage-${{ github.run_id }}-${{ github.run_attempt }}\"",
                    "          if (Test-Path $stageRoot) { throw 'Private staging root must start absent' }",
                    "          if ($LASTEXITCODE -ne 0) { throw 'Service-free private profile staging failed' }",
                    "          $privateRuns = @(Get-ChildItem -LiteralPath $privateRoot -Directory -Force)",
                    "          if ($privateRuns.Count -ne 1) { throw 'Private run root must contain exactly one gate run' }")
        staging = next((line for line in lines
                        if line.startswith("          python -m tests.e2e.stage_ci_profile ")), "")
        gate = next((line for line in lines if line.startswith("          python -m tests.e2e.run_ci ")
                     and '--private-root "$privateRoot"' in line), "")
        stage_root = "          $stageRoot = Join-Path $env:RUNNER_TEMP \"sapphire-private-e2e-stage-${{ github.run_id }}-${{ github.run_attempt }}\""
        stage_absent = "          if (Test-Path $stageRoot) { throw 'Private staging root must start absent' }"
        stage_guard = "          if ($LASTEXITCODE -ne 0) { throw 'Service-free private profile staging failed' }"
        if (any(value not in lines for value in required)
                or not all(value in staging for value in
                           ('--private-artifacts "$stageRoot"',
                            '--expected-revision "${{ github.sha }}"',
                            '--binaries "$pwd/build-e2e-ci/bin"',
                            '--worker "$pwd/build-e2e-ci/bin/sapphire_test_client.exe"'))
                or not gate
                or not lines.index(stage_root) < lines.index(stage_absent) \
                    < lines.index(staging) < lines.index(stage_guard) < lines.index(gate)):
            raise DevelopmentError("private workflow lacks protected serialized runner controls")
        inspection = ('          python -m tests.e2e.inspect_ci_result --summary '
                      '.e2e-ci-summary.json --expected-revision "${{ github.sha }}"')
        inspection_failure = "          if ($LASTEXITCODE -ne 0) { throw 'Published gameplay summary inspection failed' }"
        private_inspection = ('          python -m tests.e2e.inspect_ci_private_evidence --summary '
                              '.e2e-ci-summary.json --private-run-dir "$($privateRuns[0].FullName)" '
                              '--expected-revision "${{ github.sha }}"')
        private_failure = "          if ($LASTEXITCODE -ne 0) { throw 'Private gameplay evidence inspection failed' }"
        publication = "          'summary_created=true' | Out-File -FilePath $env:GITHUB_OUTPUT -Encoding utf8 -Append"
        failed_inspection = ('              python -m tests.e2e.inspect_ci_failure_result --summary '
                             '.e2e-ci-summary.json --expected-revision "${{ github.sha }}"')
        failed_inspection_guard = "              if ($LASTEXITCODE -ne 0) { throw 'Failed gameplay summary is unsafe to publish' }"
        failed_publication = "              'summary_created=true' | Out-File -FilePath $env:GITHUB_OUTPUT -Encoding utf8 -Append"
        upload_guard = "        if: always() && steps.gameplay.outputs.summary_created == 'true'"
        if (lines.count(inspection) != 1 or lines.count(inspection_failure) != 1
                or lines.count(private_inspection) != 1 or lines.count(private_failure) != 1
                or lines.count(publication) != 1 or lines.count(failed_inspection) != 1
                or lines.count(failed_inspection_guard) != 1
                or lines.count(failed_publication) != 1 or lines.count(upload_guard) != 1
                or not lines.index(inspection) < lines.index(inspection_failure) \
                    < lines.index(private_inspection) < lines.index(private_failure) \
                    < lines.index(publication)
                or not lines.index(failed_inspection) < lines.index(failed_inspection_guard) \
                    < lines.index(failed_publication)
                or lines.index(upload_guard) < lines.index(private_failure)):
            raise DevelopmentError("private workflow does not inspect passing/private or failed evidence before publication")
    normalized = path.as_posix()
    marker = ".github/workflows/"
    display = normalized[normalized.index(marker):] if marker in normalized else path.name
    return {"version": 1, "verified": True,
            "scope": "repository-workflow-controls-not-hosted-execution-or-runner-policy",
            "workflow": display,
            "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            "private_asset_workflow": private,
            "private_evidence_inspection_required":private,
            "service_free_staging_required":private,
            "failed_summary_inspection_required":private,
            "permissions": {"contents": "read"},
            "jobs": jobs, "pinned_actions": actions}

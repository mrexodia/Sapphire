# Provisioned gameplay CI

The asset-independent `test-client.yml` job is **not** gameplay CI.
`gameplay-e2e.yml` is a separate, opt-in workflow for a trusted private Windows
runner. Local rehearsal has passed; GitHub execution and infrastructure approval /
VM disposal have **not** been verified. The repository currently has no registered
self-hosted runners (checked through the read-only Actions runners API).

## Provisioning and trust boundary

1. Use a dedicated disposable Windows x64 VM, not a developer workstation or a
   shared runner accepting untrusted jobs. Install Git, Python 3.11, CMake >=3.22,
   Ninja, VS C++/Windows SDK with clang-cl, MariaDB development libraries and a
   MariaDB server installation. Register with the `sapphire-e2e-ephemeral` label.
   Restrict its runner group to this exact workflow on the reviewed default ref.
   **Labels and checks inside YAML are not runner access controls:** other workflow
   code must not be able to select this VM. If workflow-scoped runner restrictions
   are unavailable, use a separate private automation repository accessible only
   to trusted maintainers, or do not enable this workflow. Never attach an
   unrestricted asset-bearing runner to a public repository accepting PR code.
2. Provision legally available matching game data, including its adjacent
   `ffxivgame.ver` (`2016.07.05.0000.0001`). Keep it outside the checkout. Provision
   private compatible w1t1/w1f2 meshes and all eight catalogs described in
   [README.md](README.md). The route and server w1t1 meshes must hash identically.
   Legacy MSET files are rejected. Do not modify installed game assets to pass.
3. Put a local JSON profile outside the checkout with `game_data`, `mariadb_bin`,
   `navigation`, `quest_catalog`, `follow_up_catalog`, `transition_catalog`,
   `combat_catalog`, `shop_catalog`, `respawn_catalog`, `pursuit_catalog`, and
   `opening_quest_catalog`.
   Normal local profiles
   also specify `binaries` and `worker`;
   the workflow overrides these with its newly built out-of-tree outputs. A slow
   isolated runner may set integer `deadline_scale` to 2 or 3 (default 1). This
   changes bounded wait ceilings only, performs no retry or fixed sleep, and is
   recorded in both the private manifest and allowlisted summary. No DB
   credentials or connection strings belong in this profile. Fixtures create a
   fresh private DB and accounts, not a connection to an existing service.
4. Create the `sapphire-private-e2e` GitHub environment **before enabling** the
   workflow. Configure required reviewers and deployment restrictions to the
   reviewed default branch. Store the profile's absolute path in its environment
   secret `SAPPHIRE_E2E_PROFILE`. Verify these controls in repository settings;
   declaring an environment in YAML does not configure its protection rules.
5. Arrange infrastructure-level VM destruction after every job, including timeout,
   runner crash and cancellation. Registration with `--ephemeral` alone does **not**
   erase disks or kill stranded processes. Retain any needed private diagnostics
   in access-controlled storage before destroying the VM. This infrastructure is
   the maintainer's responsibility, not implemented by the Python entry point.
6. Only then set repository variable `SAPPHIRE_PRIVATE_E2E_ENABLED=true`. Dispatch
   from the default branch with the explicit review acknowledgement. The hosted
   authorization job fails before allocating a private runner if these gates are
   absent. There is no PR, push, schedule, arbitrary-ref or reusable-workflow entry.

Both E2E workflows pin external actions to exact 40-hex revisions, use a read-only
token, disable checkout credential persistence, apply bounded whole-job and every-
step timeouts, and bound artifact retention. The private workflow additionally
serializes gameplay jobs without cancelling an active run, limits the whole gameplay
job to 120 minutes, and limits the isolated gate step to 75 minutes. These ceilings
cover the previously observed roughly 56-minute 15-case gate plus build/contracts;
they remain bounds, not capacity or hosted-execution evidence. Repository controls can
be checked read-only with
`python -m tests.e2e.inspect_workflow_policy`; its receipt explicitly leaves hosted
execution, runner-group restrictions and ephemeral VM destruction unverified. The
private workflow rebuilds the checked-out server, all discovered
native script modules, worker and all six framework native tests using the
`sapphire_gameplay_ci` CMake target. GUI tools and Recast's separate test suite are
not part of that target. Framework CTest execution has a 60-second per-test timeout.

**These controls are not a sandbox.** Reviewed repository/build/dependency code
can read everything accessible to the runner account. Never enable this workflow
on code or a runner you do not trust. No runner was registered or remote settings
changed by this implementation.

## Local rehearsal

Use a fresh out-of-tree build (Windows/Git Bash example, with the VS build environment loaded):

```sh
cmake -S . -B build-e2e-ci -G Ninja -DCMAKE_BUILD_TYPE=Debug \
  -DCMAKE_C_COMPILER=clang-cl -DCMAKE_CXX_COMPILER=clang-cl \
  -DSAPPHIRE_BUILD_TEST_CLIENT=ON -DSAPPHIRE_BUILD_TOOLKIT=OFF \
  -DSAPPHIRE_BUILD_IN_TREE=OFF -DRECASTNAVIGATION_TESTS=OFF \
  -DRECASTNAVIGATION_DEMO=OFF -DRECASTNAVIGATION_EXAMPLES=OFF
cmake --build build-e2e-ci --target sapphire_gameplay_ci
ctest --test-dir build-e2e-ci --output-on-failure --timeout 60 --no-tests=error -R '^sapphire_'
python -m pytest tests/e2e/test_worker.py tests/e2e/test_policy.py tests/e2e/test_ci.py \
  tests/e2e/test_soak.py tests/e2e/test_client_smoke.py tests/e2e/test_workload_cleanup.py \
  tests/e2e/test_combat_policy.py tests/e2e/test_inventory_policy.py tests/e2e/test_minimize.py \
  tests/e2e/test_workflow_policy.py --e2e-worker build-e2e-ci/bin/sapphire_test_client.exe -q
python -m tests.e2e.inspect_ci_profile --profile .e2e-local.json \
  --binaries build-e2e-ci/bin --worker build-e2e-ci/bin/sapphire_test_client.exe
python -m tests.e2e.stage_ci_profile --profile .e2e-local.json \
  --binaries build-e2e-ci/bin --worker build-e2e-ci/bin/sapphire_test_client.exe \
  --private-artifacts <new-absolute-private-directory> \
  --expected-revision <exact-40-hex-checked-out-revision>
python -m tests.e2e.run_ci --profile .e2e-local.json \
  --binaries build-e2e-ci/bin --worker build-e2e-ci/bin/sapphire_test_client.exe \
  --private-root .e2e-artifacts/ci --summary build-e2e/ci-summary.json --require-clean
python -m tests.e2e.inspect_ci_result --summary build-e2e/ci-summary.json \
  --expected-revision <exact-40-hex-checked-out-revision>
python -m tests.e2e.inspect_ci_private_evidence --summary build-e2e/ci-summary.json \
  --private-run-dir .e2e-artifacts/ci/gameplay-ci-<private-id> \
  --expected-revision <exact-40-hex-checked-out-revision>
```

The profile inspector performs the same static availability/catalog/mesh/hash
preflight and emits no private paths; it starts no services or accounts and proves
neither build provenance nor compatibility. The optional staging command requires a
clean exact revision and a new absolute private artifact directory, exercises the
real fixture-v2 copy/config/manifest path, starts no process, removes its disposable
runtime/root, and retains only private manifest/lifecycle evidence plus a sanitized
receipt. It is not a service or database rehearsal. The summary destination must not already exist. Without `--require-clean`, local
rehearsals may use a dirty checkout; the summary explicitly records that fact.
The workflow always requires a clean checkout. The read-only inspector owns an
independent exact ordered copy of the current 16-case and eight-catalog allowlists;
a contract requires explicit producer/consumer synchronization when either changes.
It also requires successful collection/inputs/cleanup, the new
`process_cleanup_verified` claim, typed component identities, and the operator-
supplied clean source revision; historical summaries without that field are not
upgraded. The private workflow invokes this inspector against `${{ github.sha }}`
after a passing gate, then requires exactly one run below a fresh run-ID/attempt-ID
private root and invokes the private-evidence inspector against that run before
marking the summary publishable. The private root is never uploaded. Failed gate
summaries must pass the separate fail-only `inspect_ci_failure_result` sanitizer
before their diagnostic upload output is set; acceptance explicitly records that
success evidence was not accepted. This verifies
the sanitized public result and retained private evidence contracts. It cannot reconstruct the private
PID/generation records deleted with disposable fixtures,
prove hosted execution, or replace an actual current gate run. When the authorized
private run directory is retained, the second inspector matches every public hash
pair one-to-one to exactly 16 safe private environment directories, revalidates all
service generations and staged source/input identities, requires the exact private
profile hash, allowlisted path-only schema, deadline and artifact-root binding,
requires every manifest-declared disposable root/runtime to be absent and non-overlapping with retained
artifacts, requires exact private collection plus one passed setup/call/teardown per
case, and requires the exact ordered 16 JUnit classname/name identities with no
failure/error/skip element, and correlates the fault case's private
classification/verification hashes to its exact world generation teardown. It emits
no private path, database, runtime, port, PID or captured log content. It never makes absent private bytes
recoverable. `run_ci` does not itself compile
binaries, so running it against an external profile does not prove build provenance.
Component hashes identify the actual tested inputs; the workflow's build step is
separate evidence that its binaries came from the checkout.

## Gates and evidence

- Preflight verifies files, archive-version marker, script availability, quest
  chain/action/transition/shop/homepoint metadata, tile-cache headers and route/server
  mesh identity. This checks availability and consistency, **not** game correctness or
  independent real-client compatibility. Static prerequisite validation never
  modifies quest progress; the live chain must complete its first quest normally.
- The entry point collects the ten whole live modules and requires exactly the
  sixteen expected cases. Added/removed cases require explicit review of `CASES`.
  Inherited pytest selection options and automatic third-party plugins are
  disabled. The gate records the exact fixture object used by each node ID and
  requires exactly sixteen pairwise-distinct environments mapped one-to-one to the
  exact sixteen cases. Private validation additionally requires 16 distinct,
  non-nested runtime roots and artifact roots, 16 valid randomized database names,
  four distinct typed ports per fixture, and exact agreement of database/runtime/
  ports with each retained staged manifest. Every allowlisted case therefore
  provisions and removes its own disposable database/API/lobby/world environment,
  preventing an earlier case's sessions, roaming actors, or teardown backlog from
  becoming a later case's fixture. Sequential fixtures may legitimately reuse a
  released port, so cross-case port uniqueness is not claimed. The public summary
  exposes only `environment_isolation_verified`; private identities remain private. No tests, skipped cases, missing/duplicate phase reports, unexpected tests, failing
  setup/call/teardown, nonzero pytest exit, live child processes, missing/foreign/
  type-confused process generations or teardown receipts, or a retained private
  runtime prevent a passing summary. Private reinspection independently requires
  all 16 declared disposable roots and runtime directories to remain absent; an
  observed exit receipt plus a retained runtime is rejected. `process_cleanup_verified` requires every
  exact database/API/lobby/world PID generation—including restarted worlds—to
  have been running before one terminate request and to yield an observed integer
  return code; a bounded kill fallback is retained explicitly. Public source revision,
  dirty state, fixture schema/profile and deadline scale plus all preflight input
  identities must match every staged environment manifest, including script
  modules; changing source metadata, a binary, catalog or mesh between those checks
  fails verification. Exact hashes and metadata correlation are not native-build
  provenance or signatures.
- Only `.e2e-ci-summary.json` is uploaded: fixed schema, allowlisted case identities
  and booleans, checkout identity, component hashes and cleanup/collection results.
  It also carries exactly 16 ordered
  `{case, manifest_sha256, lifecycle_sha256, artifact_tree_sha256}` rows plus
  SHA-256 values for private `profile.json`, `gate-diagnostics.json`, `pytest.log`
  and `live.xml`. These bind the exact private invocation profile and each public case to exact private staged-manifest/process-
  lifecycle bytes, the complete bounded private environment artifact tree, phase
  reports and private test artifacts without publishing filenames, paths, ports,
  database names, PIDs, return codes, captured output or credentials;
  hashes are correlation, not independent content proof.
  The upload step requires the current gameplay step to create the report. It
  does not reuse a stale report after an earlier step fails. A nonzero gate can
  publish only base/source/allowlisted gate diagnostic fields accepted by the
  fail-only inspector; unknown fields, private paths, partial field groups, a
  mismatched revision or a relabeled successful outcome are rejected.
- Private run directories contain `profile.json`, `entry-error.log` on entry
  failure, `pytest.log`, `live.xml`, `gate-diagnostics.json`, and the normal
  per-case server/worker artifacts. Neither
  JUnit nor pytest failures are safe public artifacts: they can contain received
  positions, paths, scene parameters and exception details. Do not broaden the
  upload glob to include these directories, catalogs, assets or runtime trees.
- Successful normal fixture teardown includes private `process-lifecycle.json`
  with exact generation/PID/request/exit receipts and the public boolean only; PID
  details are never uploaded. This is forced owned-process cleanup, not graceful
  server shutdown or server-session exclusion. Hard-kill/cancellation cleanup
  relies on the disposable runner infrastructure; it is not proven by a normal
  local run. Any uncertain owned teardown writes private `cleanup-failure.json`;
  later poll-only exit observation cannot upgrade that artifact, and standalone plus
  combined private success inspectors reject its presence. A passed summary covers
  this sixteen-scenario headless suite only. The sixteenth case, `test_live_fault_diagnostics.py`, intentionally terminates
  the exact owned world generation in its own fixture, requires one matching
  lifecycle receipt, then verifies private exit classification, redacted log
  publication and runtime removal. Retained standalone evidence can be checked
  read-only with `python -m tests.e2e.inspect_isolated_fault --artifact-dir
  <private-artifact-dir> --junit <private-junit> --pytest-log <private-log>
  --expected-revision <40-hex>`. It requires the independent exact single-case
  runner/JUnit contract as well as fault semantics. This is fault-evidence coverage,
  not gameplay, spontaneous server-crash, crash-dump or hosted cancellation-cleanup
  proof.
- A bounded single-case development execution can retain its own JUnit, pytest log
  and fixture artifact directory, then use `python -m tests.e2e.inspect_isolated_case
  --artifact-dir <private-artifact-dir> --junit <private-junit> --pytest-log
  <private-log> --expected-case <exact-allowlisted-node-id> --expected-revision
  <40-hex>`. This proves exact runner identity/outcome, source/fixture identity,
  service-generation cleanup and runtime absence for only that case. For the
  rejected-credentials case it additionally requires the sanitized genuine-HTTP
  receipt: exact login method, expected/received 400 status, response byte/hash
  identity and no returned session field, without retaining request or response
  content. It explicitly does not independently prove the scenario semantics and
  is not a substitute for the combined gate.

Latest local evidence: clean revision `39198db88` passed the fifteen-case strict
gate in 2991.257 seconds with zero skips/errors/failures, exact collection and
staged-input identity, and removed private runtime. It retains naturally earned
level-four combo and tracked death-state evidence and adds one independently
witnessed source-bound active-vision aggro/defeat path with no player combat action.
Evidence is `build-e2e/ci-summary-proximity-aggro.json` (SHA-256
`d3a6e17ad55783cf0fabc9847deff89b8e6bb9d7c5897bd8e142318392362d1b`) with private
diagnostics at `.e2e-artifacts/ci/gameplay-ci-qi1qhtgz` and private manifest
SHA-256 `2126d2de1328695d7b12be544a6bdd096f2b4a7509d99a34bae4ac58aba124ee`;
this is local, not hosted execution. A retained preflight diagnostic at
`.e2e-artifacts/ci/gameplay-ci-xa4osh_n` rejected the stale generated shop catalog
before provisioning; the passing run regenerated the exact current source catalog
rather than weakening identity validation.

Earlier local evidence: clean revision `8ca87f3f1` passed the nine-case strict
gate in 620.91 seconds with no skips/errors/failures, exact collection and staged-
input identities, and verified private-runtime cleanup. Creation took 65.662s and
now verifies all five Gladiator starter-equipment slots plus each distinct Pugilist/
Thaumaturge main hand; health reset, Blizzard, Bootshine, opening acceptance and
sale/purchase remained covered. Evidence is `build-e2e/ci-summary-starter-slots.json`
with private diagnostics under `.e2e-artifacts/ci/gameplay-ci-i5o5pnpz`. The earlier
failed gate is retained at
`.e2e-artifacts/ci/gameplay-ci-lfghcvlf`: eight cases passed, but player-defeat
correctly failed when its natural target roamed beyond melee range during TP wait.
The fix follows only bounded received positions with witness verification. This
remains a local rehearsal, not a hosted protected-runner execution.

Original local evidence: the fresh `build-e2e-ci` target and four native suites passed; its
rebuilt binaries passed all seven live cases in 245.450 seconds with no skips,
verified collection/staged-input identities and removed private runtime. This
post-commit rehearsal used `c9f8969b2` with `--require-clean`; `source_dirty` is
false. Private evidence is under `.e2e-artifacts/ci/gameplay-ci-41fem4dt`; its
allowlisted summary is `build-e2e/ci-summary-clean.json`. The 69 controller/policy/CI
contracts pass on Windows and in the network-isolated Linux container. Workflow
syntax passes `actionlint` v1.7.7. This does not establish a GitHub-hosted /
protected-runner execution.

After the autosave BLOB-ownership fix, rebuilt `bin` server/script binaries also
passed the same strict gate at clean `fe411dbb9`: seven cases in 243.475 seconds,
zero skips, identity and cleanup checks passed (`build-e2e/ci-summary-binding.json`,
private `gameplay-ci-w0wbxl46`). Five native suites now pass on Clang/MSVC/GNU;
113 Python contracts pass on Windows and isolated Linux. Neither the empty-server
resource control nor the separate 30-minute workload is counted as a gameplay
case in this gate.

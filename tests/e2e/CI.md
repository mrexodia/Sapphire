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
   private compatible w1t1/w1f2 meshes and all seven catalogs described in
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
   recorded in both the private manifest and allowlisted summary. WSL runners
   whose host forwarding races `127.0.0.1` may set `loopback_host` to the only
   alternate accepted value, `127.0.0.2`; this does not expose any listener beyond
   kernel loopback. No DB
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

The workflow pins its external actions, uses a read-only token, disables checkout
credential persistence, serializes gameplay jobs without cancelling an active run,
and limits the job to 45 minutes. It rebuilds the checked-out server, all discovered
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
  --e2e-worker build-e2e-ci/bin/sapphire_test_client.exe -q
python -m tests.e2e.run_ci --profile .e2e-local.json \
  --binaries build-e2e-ci/bin --worker build-e2e-ci/bin/sapphire_test_client.exe \
  --private-root .e2e-artifacts/ci --summary build-e2e/ci-summary.json --require-clean
```

The summary destination must not already exist. Without `--require-clean`, local
rehearsals may use a dirty checkout; the summary explicitly records that fact.
The workflow always requires a clean checkout. `run_ci` does not itself compile
binaries, so running it against an external profile does not prove build provenance.
Component hashes identify the actual tested inputs; the workflow's build step is
separate evidence that its binaries came from the checkout.

## Gates and evidence

- Preflight verifies files, archive-version marker, script availability, quest
  chain/action/transition/shop/homepoint metadata, tile-cache headers and route/server
  mesh identity. This checks availability and consistency, **not** game correctness or
  independent real-client compatibility. Static prerequisite validation never
  modifies quest progress; the live chain must complete its first quest normally.
- The entry point collects the nine whole live modules and requires exactly the
  fifteen expected cases. Added/removed cases require explicit review of `CASES`.
  Inherited pytest selection options and automatic third-party plugins are
  disabled. Every allowlisted case provisions and removes its own disposable
  database/API/lobby/world environment, preventing an earlier case's sessions,
  roaming actors, or teardown backlog from becoming a later case's fixture. No
  tests, skipped cases, missing/duplicate phase reports, unexpected tests, failing
  setup/call/teardown, nonzero pytest exit, live child processes, or a retained
  private runtime prevent a passing summary. Preflight identities must match every
  staged environment manifest, including script modules; changing a binary,
  catalog or mesh between those checks fails verification.
- Only `.e2e-ci-summary.json` is uploaded: fixed schema, allowlisted case identities
  and booleans, checkout identity, component hashes and cleanup/collection results.
  The upload step requires the current gameplay step to create the report. It
  does not reuse a stale report after an earlier step fails.
- Private run directories contain `profile.json`, `entry-error.log` on entry
  failure, `pytest.log`, `live.xml`, `gate-diagnostics.json`, and the normal
  per-case server/worker artifacts. Neither
  JUnit nor pytest failures are safe public artifacts: they can contain received
  positions, paths, scene parameters and exception details. Do not broaden the
  upload glob to include these directories, catalogs, assets or runtime trees.
- Successful normal fixture teardown is verified. Hard-kill/cancellation cleanup
  relies on the disposable runner infrastructure; it is not proven by a normal
  local run. A passed summary covers this fifteen-scenario headless suite only.
  `test_live_fault_diagnostics.py` is a separate opt-in lane that intentionally
  terminates its own freshly provisioned world process; it verifies process-exit
  classification, redacted log publication and runtime removal, not gameplay or
  hosted cancellation cleanup.

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

# E2E implementation checkpoint and requirement audit

**Overall goal: not complete.** Green tests cover a supported subset, not the full
rollout or real-client compatibility. Branch: `feature/headless-e2e`.

## Contract

Implement an external C++ headless client controlled by Python/pytest through
normal authentication, lobby and world connections to disposable servers. Use
non-GM fixtures, received-state assertions, independent observers, explicit scene
adapters, rewards/restart tests, diagnostics, CI and supported-action exploration
and soak workflows. Keep fixture setup distinct from gameplay. Never silently
accept unknown scenes or label codec/mock tests as gameplay/real-client evidence.

## Requirement audit

| Requirement | Evidence | Status |
|---|---|---|
| Architecture / dedicated branch / atomic commits | Original proposal `autonomous-testing-plan.md`; `feature/headless-e2e` | Implemented incrementally |
| External C++ worker / shared schemas and lobby encryption | `src/test_client`; only normal sockets, no server-handler calls | Verified for enabled actions |
| Python/pytest / JSON-lines / asynchronous channels | `support/worker.py`, dispatcher, Bot/Channel state machines | Verified |
| Genuine HTTP login, lobby selection, world-ready, both keepalives, logout | Live smoke scenarios; FINISH_LOADING followed by received cleared BetweenAreas | Verified on Windows/3.3 |
| Normal character creation/opening journey | Pre-connection account/character fixture provisioning and public Ul'dah start | Not covered |
| Isolated DB/config/processes / non-GM accounts / real sessions | Private MariaDB, unique schema/ports, staged binaries, rank-zero observations, sessions required | Windows live verified; Linux deployment unverified |
| Movement / independent observer / semantic route API | Observer verifies movement/despawn; both bots walk a 322-waypoint quest route | Curated routes verified, not general navigation |
| Compatible navigation assets | Separate TSET generation, complete sampled corridors; private server mesh root and live `NAVI` initialization for territories 130/141 | Verified for two quests and the selected exit; Due Diligence disconnected |
| Versioned route/scene data | Private generated catalog v1; explicit Motivational Speaking and Gil for Gold choices | Two live verified adapters; Due Diligence remains source-derived |
| Interact / choose dialogue / unknown-scene failure | Exact received event/scene/token; no default choice or raw-packet control; contract tests | Verified for supported one/two-result returns |
| Quest state / accept and cancel / completion | `test_live_quest.py`: Motivational Speaking (65686), cancel unchanged, accept sequence 255, completion | Verified |
| Received inventory/currency/XP model | `RewardsState.cpp`: initial snapshots, deferred successful transactions, class-index and incremental XP | Unit verified; live item/XP rewards verified; nonzero currency reward still unverified |
| Exact quest rewards | Independent authored expectation: 50 XP and two items 4551, no other tracked bag/currency change | Verified |
| World restart and fresh login | Position, completed flag, absent active quest, XP and tracked bag quantities checked after restart | Verified |
| More quests / zoning / inventory operations / combat / social | Two-quest chain, optional reward, reconnect, discard, ordinary Say, 130-to-141 crossing/persistence, and independently observed Fast Blade damage | Representative subset verified; general combat and inventory move/split/swap/use not covered |
| Range/discovery/territory event triggers | Curated physical ExitRange crossing; no general quest-range/discovery adapter | Exit subset verified; remaining adapters missing |
| Yield/resume and broader scene variants | Explicit unsupported capability; only fixed one/two-result returns | Missing |
| Deterministic authored regression suite | Seven live cases, native tests and Python contracts | Supported suite verified |
| Seeded exploration / preconditions / invariants | `support/workload.py`, reproducible allowlisted decisions, server/state checks, independent observers | Two-bot exploration verified; narrow supported-state coverage |
| Bounded soak / ramp / metrics | 2..32-bot controller, <=1000 actions, explicit budget/minimum span/pacing; continuous received liveness; process RSS/private-commit/CPU and action timings | Eight bots / 488 actions over 1805s and full replay verified; observed autosave allocation retention fixed; not capacity, universal leak-freedom or overnight evidence |
| Semantic replay | Versioned allowlisted plans, route hash, logical roles and all recorded execution limits | v1 exploration and v2 paced soak replay verified; scheduling is not deterministic |
| Failure minimization | No reducer | Missing |
| Deadlines / cancellation / cleanup | Timers, bounded waits, owned-process teardown, redaction; bounded Windows sharing-error retries | Initial paths verified; broader stress/signal testing remains |
| Action/event/server logs / hashes / JUnit | Bounded sanitized journals; runtime/module/worker/catalog/mesh identities | Implemented; hashes do not prove independent compatibility |
| Asset-independent CI | `.github/workflows/test-client.yml` | Authored; hosted run unverified |
| Provisioned gameplay CI | `gameplay-e2e.yml`, `sapphire_gameplay_ci` build target, `run_ci.py`, `CI.md` | Authored and locally rehearsed with freshly built binaries; hosted execution/runner controls unverified, no registered runners |
| Independent real-client/golden trace compatibility | No independently captured session | Missing |
| Full objective | Missing rows above remain | **Not achieved; do not complete goal** |

## Verified results

- Clang/Ninja and MSVC/Visual Studio: five CTest executables pass (protocol,
  rewards, combat, synthetic navigation and borrowed database bindings). Navigation tests reject disconnected and
  off-mesh destinations rather than accepting a partial Detour path.
- GNU 11.4/Ubuntu 22.04: standalone build and the same five CTest executables pass.
- 113 Python worker/policy/CI/pacing/resource-control contracts pass with the MSVC worker and in a
  network-isolated Linux container. This WSL instance refuses even Python-only
  loopback connections; that check was not skipped or rewritten to make it pass.
- The provisioned CI entry point passes all seven cases against a fresh out-of-tree
  server/script/client build. Post-commit clean-checkout rehearsal at `c9f8969b2`:
  245.450s, zero skips, collection/input hashes/normal cleanup all verified
  (`gameplay-ci-41fem4dt` under `.e2e-artifacts/ci`, summary
  `build-e2e/ci-summary-clean.json`). `--require-clean` passed and `source_dirty`
  is false. Earlier dirty implementation rehearsals are explicitly labeled as such.
  `actionlint` v1.7.7 validates both client workflows. Read-only GitHub API inspection
  found zero registered self-hosted runners; no runner/settings were created.
  See `tests/e2e/CI.md` for mandatory workflow-scoped runner access restrictions,
  protected-environment approval and VM disposal responsibilities. Local rehearsal
  does not prove hosted approval, cancellation cleanup or independent compatibility.
- Seven live cases pass together in 255.94s (`sapphire-e2e-qpyhw78e`) after
  bot-specific state-wait notification filtering: rejected
  credentials, login/idle/logout, observed movement/Say/position persistence,
  single quest, chained quests plus inventory persistence, zoning persistence,
  and combat damage. Both tested territories use compatible server-side meshes.
- Combat uses a fresh level-one Gladiator and the unchanged Central Thanalan
  population. The action catalog validates normally learned Fast Blade (9),
  requiring 60 naturally regenerated TP. Both player and observer receive the
  same damage effect and matching-result committed HP decrease on a nearby
  level-one marmot. Request acknowledgement/effect alone is insufficient.
  The fighter disconnects; it does not bypass in-combat logout restrictions.
  This does not establish kills, combat XP/loot, combos, retaliation assertions,
  cooldown scheduling or dynamic pursuit. Initial position is fixture setup.
  The decoded `sapphire-e2e-wd3lpulz` journal records nine damage, NPC HP 94 → 85 on both clients,
  and source TP 40 after the action. A conservative local recast guard follows the
  received 250-centisecond action-start value. Private runtime cleanup succeeded.
- Current navigation generated separately in `.e2e-assets/uldah-v2`; repeat output
  refused, original OBJ and legacy mesh hashes unchanged. The 65686 route has
  322 points and length approximately 152.375m, with nearby walkable NPC approaches.
- The added Gil for Gold chain variant passes in 102.52s, including the first
  quest as its real prerequisite. Its 186-point route joins the preceding endpoint
  without teleporting. Active quest 151 survives reconnect; hand-over cancellation
  leaves progress/rewards unchanged; choosing item ID 4555 grants three ethers and
  50 additional XP, not the alternative potions. Both completions and cumulative
  rewards survive restart. Evidence: `build-e2e/quest-chain.xml` and its manifest.
- Extended chain plus inventory discard passes in 117.23s
  (`build-e2e/quest-inventory.xml`). The chosen ether reward is first verified after
  restart, then discarded through a bounded normal request. The test observes a
  committed deletion, unchanged other tracked slots, observer-confirmed logout,
  and deletion/remaining rewards/quest completion after another restart.
  Clang, MSVC and GNU builds pass the new byte-layout and transaction tests.
- `test_live_zoning.py` crosses exit 2377056 from territory 130 to 141 after a
  41-point/18.64m walk. A source observer stays outside the trigger and observes
  departure; a destination observer sees arrival and chat. Both channels remain
  alive; territory/position/rewards survive restart. Latest isolated run: 58.51s,
  `build-e2e/zoning.xml`. The current seven-case run also includes the refinement
  that leaves the source observer stationary outside the trigger.
- `.e2e-assets/runtime-nav-v1/navi` contains separately generated w1t1/w1f2 tiles.
  Live logs explicitly show both territories initialized with `NAVI`, not merely
  configured file paths. Server mesh hashes are in the manifest. Original collision
  assets were unchanged. Both quest routes were also checked against all seven
  source exit boxes using full-scale bounds; neither intersects an exit volume.
- Seed 42/two bots/12 actions: exploration and fresh-environment semantic replay
  passed (`sapphire-e2e-qmrbsx71`, latest replay `sapphire-e2e-79q32vbf`).
- Seed 7/four bots/120 actions: soak passed in 112.125s including setup/teardown
  (`sapphire-e2e-3uru8s6x`). All 120 actions passed; world peak RSS 321,454,080 bytes,
  worker peak RSS 7,892,992 bytes. These are diagnostic observations, not a capacity
  benchmark or regression threshold. Per-process samples and action timings exist.
- Seed 19/sixteen bots/960 actions: soak passed in 302.406s including setup and
  teardown (`sapphire-e2e-zosbd7a9`). Fresh replay of the identical plan passed in
  295.563s (`sapphire-e2e-blztvwpo`); both independently verify 16 active bots and
  contain 960 successful outcomes. Both plan files have SHA-256
  `5378dc8c4004185ba220d0d79fcc4807a44d353ec47a00801310d6799ce5fc24`.
  After bot-specific wait filtering, recorded runner CPU delta was 131.141s versus
  157.047s in the first run; worker delta was 46.391s versus 56.266s. These are
  observations from two runs, not a controlled benchmark or guaranteed speedup.
  Replay world peak RSS was 377,630,720 bytes. Action p95 was 2.719s, not RTT.
  Both private runtimes were removed. Five-minute runs still do not establish
  long-duration stability, large-population capacity or broader gameplay policy.
- Version-2 plans add an explicit round-start interval and minimum successful
  action span, with no post-work idle padding. Pacing requires complete soak
  rounds and walk/Say coverage for every bot. Two-second idle checkpoints verify
  all roles, ring visibility and both received heartbeat counters; a 15-second
  stale channel or monitoring gap fails. Synthetic-clock contracts cover gaps,
  resets, missing actors, unexpected scenes, deadlines and slow-round behavior.
  Four-bot/16-action paced smoke passed (`sapphire-e2e-6akqm2ey`), with 17.25s of
  actual activity for a 15s minimum; fresh replay preserved pacing and passed
  (`sapphire-e2e-tnobg4b0`). The old v1 exploration plan also replayed successfully
  (`sapphire-e2e-u7p2e6ex`).
- Seed 2026/eight bots/488 actions: **30-minute paced soak passed** at clean
  framework revision `063ea281b` (`sapphire-e2e-q0klh2yf`). The actual successful
  action span was 1805.281s, excluding setup/teardown (1880.782s total). Inspection
  of outcomes/rounds/checkpoints independently confirmed all 61 complete rounds,
  224 walks, 136 Say operations, 128 heartbeat waits, and 966 eight-bot liveness
  checkpoints. Every bot participated for at least 1803.078s; minimum round spacing
  was 30.015s and maximum checkpoint gap 3.985s. Both channels advanced by 600–601
  received replies per bot without resets. Private runtime removal was verified.
  Action p95 was 2.5s (not RTT); world/worker/runner peak RSS was respectively
  403,779,584 / 9,887,744 / 35,311,616 bytes. This is low-rate supported-town-workflow
  evidence, not capacity, broad gameplay, overnight stability or leak-freedom.
  **Original memory-growth observation (investigated below):** world median RSS increased from
  370,196,480 bytes in the first five active minutes to 400,510,976 in the last
  five; worker medians rose from 8,429,568 to 9,740,288 and runner from 28,356,608
  to 34,574,336. Sampling/checkpoint histories contribute to runner retention;
  the run does not distinguish other retention, warm-up, allocator or leak causes.
- Full 30-minute replay after the BLOB-ownership fix passed at clean revision
  `fe411dbb9` (`sapphire-e2e-c1p7inqh`): 488 successful actions, 61 rounds,
  1805.218s activity, 969 eight-bot liveness checkpoints. Each bot participated
  for at least 1802.875s, maximum checkpoint gap was 3.062s and both channels
  advanced by 600–601 replies per bot. The original/replay plan files are byte
  identical, SHA-256 `490e97e5b6f09b988bedceeaebb46195f936704b830be022e5b5fb4d7c6401ef`.
  World first/last five-minute median RSS was 370,262,016 / 370,253,824 bytes;
  private commit was 356,487,168 / 356,458,496. The previous increasing trend
  did not recur; these are bounded observations, not universal leak-freedom.
  World peak RSS was 370,331,648 bytes; action p95 was 2.594s (not RTT).
  All actions, identities, round spacing, counter progression and runtime cleanup
  were checked against the actual artifacts, not just the result summary.
- Rebuilt server/script binaries with the ownership fix also passed all seven
  live cases in 243.475s, including persisted quest/reward/inventory state.
  `build-e2e/ci-summary-binding.json` and private `gameplay-ci-w0wbxl46` verify
  clean `fe411dbb9`, exact collection, all setup/call/teardown phases, zero skips,
  staged-input identities and cleanup. The committed empty-server controller's
  separate ten-second smoke (`sapphire-e2e-uc4xuzgt`) produced 11 complete samples,
  no worker and verified cleanup; that smoke is not ten-minute or gameplay evidence.
- One-second action budget fails explicitly after one attempted action, records
  workflow failure/outcomes and cleans up (`sapphire-e2e-6lr093zy`). Replaying that
  plan preserves the one-second limit and reproduces the failure
  (`sapphire-e2e-drdjdnn4`). No private runtime directories remained afterward.
- `test_live_quest.py` never seeds quest flags or grants rewards. Initial character
  position/opening state are fixture setup before the first connection, not claims
  of a creation/opening/travel journey.

Ignored local evidence: `build-e2e/{contracts,live,quest}.xml`,
`build-e2e-msvc/contracts.xml`, `build-e2e-linux/container-contracts.xml`, CTest logs,
private generated catalogs, and `.e2e-artifacts/sapphire-e2e-*/` manifests/journals.
Existing server binaries are staged and hashed, not silently rebuilt by the runner.

## Corrections exposed by execution

- Concurrent accounts exposed time-reseeded API session collisions. The separate
  session fix uses OS randomness while retaining the existing wire length.
- Movement exposed premature self-spawn readiness; the worker now sends the normal
  FINISH_LOADING command and observes the server clearing BetweenAreas.
- Live quest reward creation required destination-based CREATEITEM transactions,
  not only source-based updates. Both are staged until successful batch commit.
- Restart exposed MSB-first quest-completion masks, unlike LSB-first condition
  flags. A manually specified quest-150 bit fixture guards the corrected decoder.
- The first combat attempt observed no action start/result: fresh fixtures had
  zero TP. The client now receives HP/MP/TP updates and waits for natural TP
  regeneration; no resource grant or fixture modification masks the condition.
- Concurrent soak resource samples exposed snapshot ping-pong: unrelated request
  responses woke state waits. Predicate-based condition waiting fixes this.
  The sixteen-bot run motivated filtering unrelated **bot events** as well:
  per-bot versions now suppress cross-bot snapshot polling, and removal clears
  the version entry. Contracts cover unrelated responses/events, matching-event wakeup
  and removal cleanup; the same 960-action plan and all seven live scenarios pass.
- The 30-minute resource trace motivated an empty-server control and persistence
  ownership investigation. The original-binary, no-client 600s control
  (`sapphire-e2e-nfsforp7`) had flat first/last 60-sample median world RSS
  (343,941,120 / 343,883,776 bytes) and private commit (330,268,672 / 330,117,120).
  This was a private diagnostic prototype, not gameplay evidence; its runtime
  was removed. The reproducible controller is now `run_idle_control.py`, with
  explicit no-gameplay results, unavailable-sample failures and cleanup tests.
- Normal player autosaves allocate BLOB streams in application
  `PreparedStatement::bindParameters`; the connector explicitly borrows them
  through execution (`setBlob(..., false)`). Ownership was not retained by the
  caller. Commit `0a73d4f8c` adds operation-owned streams, released on rebind or
  destruction, without changing BLOB bytes. The actual binder, compiled against
  a non-owning connector double, reports 1648 unbalanced allocations before the
  fix and zero afterward, including partial-bind failures. This is not a SQL
  driver implementation test. A populated 600s original-binary control
  (`sapphire-e2e-xmjztal6`) reproduced growth: first/last 60-second median RSS
  rose 9,127,936 bytes and private commit 9,203,712. Its staged server hash matched
  the original 30-minute run; its framework source was explicitly dirty while
  the diagnostic fields were being added, not a clean-build claim. The rebuilt
  server's full 30-minute replay and seven-case persistence suite then passed
  with flat world memory (details above). The controls, ownership semantics and
  allocation regression support this specific fix, not a diagnosis of every
  potential resource issue.
- One Windows teardown encountered a transient executable-file permission failure.
  Bounded retries were added; persistent failures remain visible and retryable.

## Next actions / boundaries

1. Broaden supported-state policy coverage and add longer/higher-population
   controls. The observed autosave retention is fixed and the matching 30-minute
   replay is flat; this does not establish capacity or memory stability for all
   code paths. Generator histories/allocator retention also remain distinct from
   server resource behavior.
2. Extend the initial combat slice with normally timed repeated actions, enemy
   defeat, received combat rewards and retaliation assertions. Preserve observed
   resource/range checks and require genuine navigation for any pursuit.
3. Extend explicit trigger/scene adapters; unknown content must still fail.
4. Provision and validate the authored gameplay CI on a workflow-restricted disposable
   runner (none is currently registered), including approval/cancellation/disposal.
   The separate 30-minute paced workload is not part of the seven-case CI gate.
5. Evaluate the existing `E:/Sapphire/game/ffxiv*.exe` candidates for an isolated
   real-client run, or obtain a sanitized trace. Executable presence is not
   compatibility evidence: first verify version, loopback bootstrap and isolated
   user configuration. Do not alter the user's installed executables/settings.
   Shared schemas and headless-to-server agreement cannot substitute for this.

The original legacy mesh-loading blocker is resolved without modifying developer
assets. Due Diligence still lacks a complete corridor, but it no longer blocks the
first quest: Motivational Speaking is verified. Independent real-client evidence
still requires an appropriate client run/trace; other missing scenarios remain
implementation work, not proof that user input is the only next step.

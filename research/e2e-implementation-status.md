# E2E implementation checkpoint and requirement audit

**Overall goal: not complete.** Green tests cover a supported subset, not the full
rollout or general real-client compatibility. Branch: `feature/headless-e2e`.

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
| More quests / zoning / inventory operations / combat / social | Two-quest chain, optional reward, reconnect, persisted empty-slot whole-stack move, discard, ordinary Say, 130-to-141 crossing/persistence, and three paced Fast Blades plus independently observed retaliation | Representative subset verified; inventory split/merge/swap/use and general combat not covered |
| Range/discovery/territory event triggers | Curated physical ExitRange crossing; no general quest-range/discovery adapter | Exit subset verified; remaining adapters missing |
| Yield/resume and broader scene variants | Explicit unsupported capability; only fixed one/two-result returns | Missing |
| Deterministic authored regression suite | Seven live cases, native tests and Python contracts | Supported suite verified |
| Seeded exploration / preconditions / invariants | `support/workload.py`, reproducible allowlisted decisions, server/state checks, independent observers | Two-bot exploration verified; narrow supported-state coverage |
| Bounded soak / ramp / metrics | 2..32-bot controller, <=1000 actions, explicit budget/minimum span/pacing; continuous received liveness; process RSS/private-commit/CPU and action timings | Eight bots / 488 actions over 1805s and full replay verified; observed autosave allocation retention fixed; not capacity, universal leak-freedom or overnight evidence |
| Semantic replay | Versioned allowlisted plans, route hash, logical roles and all recorded execution limits | v1 exploration and v2 paced soak replay verified; scheduling is not deterministic |
| Failure minimization | No reducer | Missing |
| Deadlines / cancellation / cleanup | Timers, owned-process teardown, redaction, Windows sharing retries; workload cleanup precedes diagnostics and survives sampler/write exceptions | Synthetic faults and a controlled live diagnostic-write failure verified; broader stress/signal testing remains |
| Action/event/server logs / hashes / JUnit | Bounded sanitized journals; runtime/module/worker/catalog/mesh identities | Implemented; hashes do not prove independent compatibility |
| Asset-independent CI | `.github/workflows/test-client.yml` | Authored; hosted run unverified |
| Provisioned gameplay CI | `gameplay-e2e.yml`, `sapphire_gameplay_ci` build target, `run_ci.py`, `CI.md` | Authored and locally rehearsed with freshly built binaries; hosted execution/runner controls unverified, no registered runners |
| Independent real-client/golden trace compatibility | Unmodified 3.3 DX11 pilot and committed manual lane: world entry, received movement, bidirectional Say and normal logout; isolated Sandbox | Narrow independent lane live-verified; broader UI/quest compatibility and normalized golden traces remain uncovered |
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
- The initial single-action combat slice uses a fresh level-one Gladiator and the unchanged Central Thanalan
  population. The action catalog validates normally learned Fast Blade (9),
  requiring 60 naturally regenerated TP. Both player and observer receive the
  same damage effect and matching-result committed HP decrease on a nearby
  level-one marmot. Request acknowledgement/effect alone is insufficient.
  The fighter disconnects; it does not bypass in-combat logout restrictions.
  That original slice did not establish repeated actions or retaliation; the
  extension below now covers three paced strikes and the first retaliation hit.
  Kills, combat XP/loot, combos, general cooldown scheduling and dynamic pursuit
  remain uncovered. Initial position is fixture setup.
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
- The extended chain now moves the earned ether stack to an observed empty ordinary
  bag slot through a bounded normal request, verifies the exact placement and every
  other tracked slot after fresh authentication and again after world restart, then
  discards the moved stack. The operation-8 acknowledgement is explicitly retained
  as non-mutation evidence because the current server publishes it before attempting
  the move and sends no slot delta. Only complete subsequent snapshots establish the
  source absence and destination contents. The test then observes a committed
  deletion, unchanged other slots, observer-confirmed logout, and deletion/remaining
  rewards/quest completion after another restart. Split/merge/swap/use are not
  covered. Clang, MSVC and GNU pass the byte-layout/state tests.
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

## Repeated combat and first retaliation

The combat regression now uses the same ordinary Fast Blade operation three
times, preserving natural received TP and independent observer range/HP checks.
A new snapshot field exposes the existing **local** conservative recast guard,
rounded upward; it is not a server-ready acknowledgement. Python waits on state
notifications (including normal heartbeats), rather than sleeping a fixed recast
interval or retrying rejected actions. Each attack requires its own request/result
identity, received group-58/250-centisecond start and identical effects plus exact
committed HP decrease on both clients. Both also require the first positive
natural action-7 retaliation and its exact committed HP against the fighter's
independently captured initial full health. Later regeneration is not treated as
absence of damage. No server gameplay code or population/resources were changed.

The first attempt, `.e2e-artifacts/sapphire-e2e-kb7o_831`, passed the three outgoing
hits but **failed** waiting for retaliation. Both player and NPC had the same
fixture spawn coordinates. Source inspection showed the horizontal facing check
normalizes the target direction, which is degenerate for coincident positions.
The test now starts only the players one metre laterally from that unchanged
public NPC spawn. This is explicit non-overlapping fixture placement—not a
fabricated walked route, enemy relocation or navigation assertion. The failing
run is retained and not relabeled as success.

The revised live case passed in **56.67s** at a dirty development checkpoint:
`.e2e-artifacts/sapphire-e2e-tyv6x5ff`, `build-e2e/repeated-combat-offset.xml`.
Normal requests 1/2/3 dealt 9/8/12 damage, with received NPC HP
94 → 85 → 77 → 65; the last was a critical effect. Attempt spacing was
3.062/3.047 seconds; received TP before each request was 100 and the local guard
was zero. Both clients verified the first natural retaliation: two damage,
fighter HP 94 → 92. The fighter remained alive and explicitly disconnected;
the observer then logged out. Whole-runtime removal was checked. This verifies
the extended slice, not damage-formula correctness, kills/XP/loot, general
cooldowns, pursuit or real-client combat presentation.

All **205** Python contracts pass with Clang and MSVC workers and in
network-isolated Linux, including 29 new combat-policy contracts. All five native
suites pass with Clang, MSVC and GNU, including fractional-millisecond guard
rounding. The strict seven-case CI collection still includes the same combat test
name with stronger assertions. Bounded journals and `combat-repeated.json` retain
the action, pre/post HP, TP, guard, timing and retaliation evidence.

A subsequent **clean full-suite rehearsal** at
`ac74b5cb977e33ff6269d92ae963db7858ed1317` passed all seven live cases in **248.767s**,
with zero skips/errors/failures and complete setup/call/teardown phases. Evidence:
`build-e2e/ci-summary-repeated-combat.json` and
`.e2e-artifacts/ci/gameplay-ci-znhtwobv/live.xml`; environment
`artifacts/sapphire-e2e-j1qk7ksu` under that private CI directory.
The staged worker SHA-256 is
`bac5d45af6c2a576a1f8fba65a300c7737c45385e2544830757c971dcca8b0a9`; the world server
remains the previously fixed, unchanged
`c10b9f7092ef081a9bf9886a9de98af2c6ed8bdb134f621c8e16f11c758187f1`.

The clean run received three eight-damage strikes (NPC HP 94 → 86 → 78 → 70),
100 natural TP before each request, and 3.047/3.031s attempt spacing. The first
retaliation dealt one damage (fighter HP 94 → 93). Each source/target/action/
request/result/effect identity and exact HP integrity was independently checked
in **both raw event journals**, along with all three group-58/250-centisecond
starts. The manifest/source cleanliness, input identities and whole-runtime
removal were also audited. This is a local headless CI rehearsal, not hosted
runner execution or independent real-client combat compatibility.

## Persisted ordinary-bag item move

`62c3391bd3c2e9c144be8051d0923e420fb208fe` adds only a whole-stack move from an
observed ordinary-bag source to an observed empty ordinary-bag destination. The
worker validates complete source/destination bag snapshots, identity, count,
indexes and an empty destination before serializing the normal operation-8 packet.
The caller cannot choose an arbitrary operation or count. The independently
authored byte fixture checks exact wire offsets. Invalid, occupied, self, non-bag,
unobserved and mismatched moves fail before sending.

The current server acknowledges a move before processing it and sends no
subsequent slot mutation. `operation_batches` therefore stores a bounded exact
context/type/error history without predicting inventory. The live chain logs out
and performs a genuine new HTTP/lobby/world login; complete received snapshots
must show the source absent, all three earned ethers at bag 3 slot 24 and every
other tracked slot unchanged. It repeats that exact-map assertion after an orderly
world restart, then deletes the moved stack through the existing committed discard
path. The observer independently verifies despawn/reappearance and position, not
private inventory.

All **215** Python contracts pass with Clang and MSVC workers and in the
network-isolated Linux container. All five native suites pass with Clang, MSVC
and GNU. A dirty-development chain run passed after the final journal changes and
was retained only as implementation evidence. The subsequent clean strict gate at
`62c3391bd` passed all seven cases in **269.054s**, zero skips/errors/failures,
with verified inputs and cleanup: `build-e2e/ci-summary-inventory-move.json`,
`.e2e-artifacts/ci/gameplay-ci-0uvahxfn/live.xml`, environment
`artifacts/sapphire-e2e-17c4r8ja`. The manifest is clean at the full revision and
the whole private runtime is absent. Raw events retain the exact operation-8
acknowledgement; `inventory-move.json` retains identical expected reconnect/restart
maps and has SHA-256
`ae457e344ee1bfdf852d1ea3b19b069726bda01dc5fc4c78632992c679191e65`.
The staged worker SHA-256 is
`ccd71dcd2b1e986ea5a00b77511b82ab60800e1e6efd5c3d3d33552c586df837`;
the server remains unchanged at
`c10b9f7092ef081a9bf9886a9de98af2c6ed8bdb134f621c8e16f11c758187f1`.
This is headless server evidence, not immediate move publication, crash
consistency, split/merge/swap/item-use coverage or real-client inventory UI proof.

## Workload diagnostic-failure cleanup hardening

Inspection found that `run_workload.py` stopped metrics and wrote resource/action
artifacts **before** `Environment.close()`. A sampler exception, serialization
error or full diagnostic volume could therefore bypass owned-server teardown.
A controlled execution of the prior committed runner reproduced the control-flow
failure: an injected `resources.jsonl` write error raised before environment
close; the synthetic runtime remained. The trace is retained privately in
`build-e2e/workload-cleanup-before.json`. This is a synthetic ownership regression,
not a claim of an actual server crash or a live disk-full incident.

The runner now has a testable `run()` entry point, validates semantics before
provisioning, and attempts environment close in a nested `finally` independent of
sampler shutdown. Actual whole-root absence is checked before final diagnostic
aggregation. Final writes use temporary files/atomic replacement and are attempted
independently. Any cleanup, sampler, summary or artifact error fails the run;
original failures survive secondary errors, and result-write failure remains a
nonzero CLI result even when no canonical report can be published. Exception
text and diagnostics use the environment's registered secret redactions.

`test_workload_cleanup.py` supplies 39 asset-independent contracts covering setup,
worker construction/teardown, sampling, workflow/shutdown, exceptions/interruption,
fatal exit cleanup, every final write/replacement, complete diagnostic loss,
serialization/summary failure, retained roots and multiple simultaneous errors.
The old artifact-failure path demonstrably skipped cleanup; the new contracts
require cleanup before failing diagnostics and reject a passing partial report.
All **176** Python contracts pass with the Windows worker and in network-isolated
Linux. No native code changed.

The changed orchestration was then exercised at clean revision
`6db6dcf094fe3191306b88d71c889300f211b96d` against the actual isolated servers:

- `.e2e-artifacts/sapphire-e2e-iu8sj47a`: two bots, eight successful walk/Say/
  heartbeat actions, four paced rounds, ten liveness checkpoints and 7.359s
  activity for a six-second minimum. Overall elapsed time 41.156s. Normal
  shutdown, final diagnostics and actual whole-runtime removal passed.
- `.e2e-artifacts/sapphire-e2e-f708iskq`: a fresh byte-identical replay completed
  all eight gameplay actions, then a private driver deliberately raised an
  `OSError` on the final `resources.jsonl.tmp` write. The driver changed no game
  packets, fixtures, action outcomes or server behavior. The runner returned
  **exit 1**, `status=failed`, `failure_stage=artifacts`, preserving the specific
  diagnostic error while publishing the other final artifacts. No canonical
  resource trace was published; its absence is not concealed by the remaining
  resource summary. Overall elapsed time 44.234s.
- At the injected failure, the driver independently checked the whole private
  root was absent and all **five** owned API/lobby/world/database/worker process
  identities had exited, using PID plus creation time. The same checks passed
  after return. `fault-control.json` records the failure and process evidence.
- Raw outcomes, logical action identity/order, round/checkpoint counts, activity
  spans, clean manifests and removed runtime roots were independently audited.
  Both plan files have SHA-256
  `1170fd62180b7f0b1f7edba9ec3ef47df2a07ef5c3d2507cbe30e63034c03f4f`.
  CLI evidence is in `build-e2e/cleanup-live-smoke.json` and
  `cleanup-live-fault.json`. The private diagnostic fault driver SHA-256 is
  `49704250fc2fea775f6aad204e93f20b0b98c42399f1b7f5be9ca78c846d23af`.

This verifies the revised ordering under a controlled write exception, not an
actual full filesystem, sustained load, capacity, every sampler failure live,
or every cleanup failure. Hard-kill recovery, blocked OS calls and all individual
process-teardown faults remain outside this verification. The prior 30-minute
workload was not repeated without a new stability hypothesis.

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

1. Broaden supported-state policy coverage, including inventory operations beyond
   the verified empty-destination whole-stack move, and add longer/higher-population
   controls. The observed autosave retention is fixed and the matching 30-minute
   replay is flat; this does not establish capacity or memory stability for all
   code paths. Generator histories/allocator retention also remain distinct from
   server resource behavior.
2. Extend combat beyond the now-verified three normally timed actions and first
   retaliation hit: enemy defeat and received combat rewards remain uncovered.
   Preserve observed resource/range checks and require genuine navigation for any pursuit.
3. Extend explicit trigger/scene adapters; unknown content must still fail.
4. Provision and validate the authored gameplay CI on a workflow-restricted disposable
   runner (none is currently registered), including approval/cancellation/disposal.
   The separate 30-minute paced workload is not part of the seven-case CI gate.
5. Broaden the now-rehearsed manual real-client lane's presentation-sensitive
   coverage and independently captured trace/layout checks. Strengthen fault and
   cancellation coverage separately from successful-path evidence. Do not alter
   the user's installed executables/settings. Narrow successful sessions are not
   general compatibility, automated UI coverage or a golden-trace corpus.

The original legacy mesh-loading blocker is resolved without modifying developer
assets. Due Diligence still lacks a complete corridor, but it no longer blocks the
first quest: Motivational Speaking is verified. Narrow independent real-client
execution is now evidenced; other missing scenarios remain implementation work,
not proof that user input is the only next step.

## Independent real-client pilot and separate manual lane

At clean framework revision `132d3f9dbb7faca8c8386581849b010c366538b4`, a private
exploratory UI driver launched the matching original DX11 client in Windows
Sandbox. The source executable SHA-256 was
`d818584c782bbe3cacbc2b306391e6f3246bc3065c517a3324784e49d572ba12` before and after
execution. The client rendered version `2016.07.05.0000.0001` on its title screen.
The existing patched/non-original executables were not used or modified.

- Sandbox networking and clipboard/audio/video/printer redirection were disabled;
  all source/game/runtime mappings were read-only except the private output
  directory. Both server and client ran on guest loopback. Game settings were in
  guest `WDAGUtilityAccount` Documents, not the host user's profile.
- API-issued sessions, normal encrypted lobby/world connections and two fresh
  non-GM fixture characters were used. Starting placement was setup, not travel.
  The original client was copied/renamed without patching. Legacy DirectX DLLs
  and guest-only XAudio/XACT registration were required; no host registration,
  network configuration or installed game setting was changed.
- Private evidence: `.e2e-artifacts/client-sandbox-live-v4/output/`, environment
  `artifacts/sapphire-e2e-me7jeeip`. Its manifest records clean source and fixed
  server SHA-256 `c10b9f7092ef081a9bf9886a9de98af2c6ed8bdb134f621c8e16f11c758187f1`.
- `frame-42.png` renders the real fixture in Ul'dah; `reply-42.json` independently
  records the level-one, GM-rank-zero peer. `reply-45.json` records 2.642017m of
  movement after ordinary W input, from `[-77.378716,0.798299,-50.928574]` to
  `[-77.714233,1.296997,-48.355835]`. This is a short displacement, not a route test.
- `reply-68.json` contains the exact real-client Say `E2E real client verified`
  received by the witness from the real entity. Manual inspection of
  `frame-66.png` confirms the real client rendered `E2E independent witness` from
  the witness. An earlier UI editing attempt sent a truncated string; it was
  retained and not counted as the exact-message assertion. Immediate screenshots
  sometimes preceded input rendering; delayed observations resolved this without
  inventing server success.
- The real client used ordinary `/logout`. World logs record its
  StartLogoutCountdown request and subsequent session removal; `reply-84.json`
  shows its absence while the witness remains ready, and manual inspection of
  `frame-84.png` confirms the still-running real client returned to its title
  screen. Process termination happened only afterward during teardown.
- `finished.json` records whole-runtime removal. The owned Sandbox launcher and
  client were closed through their discard confirmation and checked exited.
  Earlier failed preparation runs (missing version metadata/legacy dependencies)
  were retained, diagnosed and cleaned up; they are not passing compatibility
  evidence. Private evidence hashes are in `pilot-evidence-hashes.json`.

This is independent execution/presentation evidence, not shared-schema agreement.
It does **not** establish real-client quests/rewards, cutscenes, creation/opening,
combat, additional versions, protocol-layout goldens or all requested coverage.
The server also logged unhandled commands `0330` and `0004` during the pilot;
these are not silently classified as supported. No proprietary screenshot,
executable, generated geometry, session or private runtime is committed.

`tests/e2e/REAL_CLIENT.md`, `prepare_client_smoke.py`, `run_client_smoke.py` and
`support/client_smoke.py` now provide a separate bounded manual lane: offline WSB
preparation, guest-only launch, normal fixture/authentication, unique received
peer/movement/Say assertions, screenshot-bound explicit operator review and
ordinary-logout evidence. VM disposal remains a separate operator duty, never
inferred from guest process cleanup. It is not part of the seven-case headless
gameplay CI gate.

The committed coordinator was then separately live-rehearsed at clean revision
`958c123ad17ba4ab1974e8fbb63b5a7e53e5c6d1`, without changing its implementation:

- Private run `.e2e-artifacts/client-smoke-v1`, environment
  `output/artifacts/sapphire-e2e-mu7_jjtb`; result run ID
  `4628ab0b61254269b010efa796fd3513`, `status=passed`, `runtime_removed=true`.
- Only a separate private OS-key/mouse/capture helper was added to the guest
  bootstrap for interactive operation; it neither sent game packets nor changed
  scenario outcomes. Its hash and the modified bootstrap hash were recorded.
  All **51** staged-input hashes and the WSB hash were independently rechecked.
- The same original executable entered the fixture world; the independent
  witness recorded **2.638316m** displacement and the exact expected real-client
  Say. Both witness heartbeat counters advanced from 108 at spawn to 209 at
  real-client logout. This is not a sustained-work measurement or RTT benchmark.
- Interactive assistant inspection of `output/review.png` verified the exact
  fixture name in the rendered world and `E2E independent witness` in the chat
  log, before explicit approval. The runner itself performed no image recognition.
  The approved screenshot SHA-256 is
  `68a52a672634eeaf6b4511b6b9a890a1a92af488ff36ee2f77a2d8e80bc0d6c8`.
- The real entity's ordinary StartLogoutCountdown, subsequent session removal,
  observer despawn and live process were verified. Separate inspection of
  `output/logout.png` confirmed the matching-version title screen. Teardown
  followed, not a forced disconnect substituted for the logout journey.
- The guest reported actual whole-runtime removal. The owned Sandbox was then
  closed with discard confirmation; its launcher/client exited and no Sandbox
  UI processes remained. `output/disposal.txt` and `independent-audit.json`
  preserve that separate check rather than changing the coordinator's
  `sandbox_disposal=operator_required` claim.
- **137** Python contracts pass with the Windows worker, including **24** new
  real-client policy contracts. The new 24 also pass in network-isolated Linux.
  These test policy/isolation/review logic, not graphical-client execution.

The new rehearsal still used pre-connection character fixtures, skipped the
first-run creation UI, and retained an unhandled `0330` command in server logs.
It is not proof of normal character creation/opening, all client packets,
headless/real-client quest agreement, cancellation safety or hosted execution.

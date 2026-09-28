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
| Normal character creation/opening journey | `test_live_creation.py`: empty account, lobby name reservation/finalization, refreshed list/select, private territory 182, explicit source-defined Ul'dah scenes 0/1, ring and scene-40 continuation after fresh authentication and restart | First opening branch verified; complete opening quest and travel to public Ul'dah remain uncovered |
| Isolated DB/config/processes / non-GM accounts / real sessions | Private MariaDB, unique schema/ports, staged binaries, rank-zero observations, sessions required | Windows live verified; Linux deployment unverified |
| Movement / independent observer / semantic route API | Observer verifies movement/despawn; both bots walk a 322-waypoint quest route | Curated routes verified, not general navigation |
| Compatible navigation assets | Separate TSET generation, complete sampled corridors; private server mesh root and live `NAVI` initialization for territories 130/141 | Verified for two quests and the selected exit; Due Diligence disconnected |
| Versioned route/scene data | Private generated catalog v1; explicit Motivational Speaking, Gil for Gold and committed Ul'dah opening choices | Three live verified adapters; Due Diligence remains source-derived |
| Interact / choose dialogue / unknown-scene failure | Exact received event/scene/token; no default choice or raw-packet control; contract tests | Verified for supported one/two-result returns |
| Quest state / accept and cancel / completion | `test_live_quest.py`: Motivational Speaking (65686), cancel unchanged, accept sequence 255, completion | Verified |
| Received inventory/currency/XP model | `RewardsState.cpp`: initial snapshots, deferred successful transactions, class-index and incremental XP; exact 0→28 gil sale then 28→20 gil purchase deltas and persistence | Unit verified; live item/XP/nonzero-currency state verified for the bounded transactions |
| Exact quest rewards | Independent authored expectation: 50 XP and two items 4551, no other tracked bag/currency change | Verified |
| World restart and fresh login | Position, completed flag, absent active quest, XP and tracked bag quantities checked after restart | Verified |
| More quests / zoning / inventory operations / combat / social | Two-quest chain, optional reward, reconnect, persisted ordinary-bag whole-stack move, occupied-slot swap, partial split, same-item merge, discard and one exact gil-shop sale/purchase pair; ordinary Say; 130-to-141 crossing/persistence; one enemy defeat with persisted EXP/loot; one independently observed player defeat plus observed/persisted homepoint return | Representative subset verified; item use, arbitrary shops/quantities, overflow merges, equipment/currency-container moves, pursuit, raises, combos and general combat remain uncovered |
| Range/discovery/territory event triggers | Curated physical ExitRange crossing and bounded source-defined Ul'dah enter-territory operation; no general quest-range/discovery adapter | Exit and one enter-territory subset verified; remaining adapters missing |
| Yield/resume and broader scene variants | Explicit unsupported yield capability; fixed one/two-result quest returns plus source-bound scene-40 gil-shop sale/purchase returns | Yield missing; broader variants uncovered |
| Deterministic authored regression suite | Nine allowlisted live cases, native tests and Python contracts | Supported suite verified in a clean combined gate |
| Seeded exploration / preconditions / invariants | `support/workload.py`, reproducible allowlisted decisions, server/state checks, independent observers | Two-bot exploration verified; narrow supported-state coverage |
| Bounded soak / ramp / metrics | 2..32-bot controller, <=1000 actions, explicit budget/minimum span/pacing; continuous received liveness; process RSS/private-commit/CPU and action timings | Eight bots / 488 actions over 1805s and full replay verified; observed autosave allocation retention fixed; not capacity, universal leak-freedom or overnight evidence |
| Semantic replay | Versioned allowlisted plans, route hash, logical roles and all recorded execution limits | v1 exploration and v2 paced soak replay verified; scheduling is not deterministic |
| Failure minimization | `run_minimize.py`: bounded fresh-environment delta reduction with exact normalized action-failure equivalence, semantic revalidation and cleanup evidence | Verified for an unpaced deterministic deadline failure; paced plans deliberately excluded |
| Deadlines / cancellation / cleanup | Timers, owned-process teardown, redaction, Windows sharing retries; workload cleanup precedes diagnostics and survives sampler/write exceptions | Synthetic faults and a controlled live diagnostic-write failure verified; broader stress/signal testing remains |
| Action/event/server logs / hashes / JUnit | Bounded sanitized journals; runtime/module/worker/catalog/mesh identities | Implemented; hashes do not prove independent compatibility |
| Asset-independent CI | `.github/workflows/test-client.yml` | Authored; hosted run unverified |
| Provisioned gameplay CI | `gameplay-e2e.yml`, `sapphire_gameplay_ci` build target, `run_ci.py`, `CI.md` | Authored and locally rehearsed with freshly built binaries; hosted execution/runner controls unverified, no registered runners |
| Independent real-client/golden trace compatibility | Unmodified 3.3 DX11 pilot and committed manual lane: world entry, received movement, bidirectional Say and normal logout; isolated Sandbox | Narrow independent lane live-verified; broader UI/quest compatibility and normalized golden traces remain uncovered |
| Full objective | Missing rows above remain | **Not achieved; do not complete goal** |

## Verified results

- Clang/Ninja and MSVC/Visual Studio: six CTest executables pass (protocol,
  rewards, combat, synthetic navigation, borrowed database bindings and concurrent item-ID allocation). Navigation tests reject disconnected and
  off-mesh destinations rather than accepting a partial Detour path.
- GNU 11.4/Ubuntu 22.04: standalone build and the same six CTest executables pass.
- 247 Python worker/policy/CI/pacing/resource-control contracts pass with Clang and MSVC workers and in a
  network-isolated Linux container. This WSL instance refuses even Python-only
  loopback connections; that check was not skipped or rewritten to make it pass.
- The provisioned CI entry point passes all nine cases. The latest clean-checkout
  rehearsal at `fc89b2422` took 549.892s with zero skips/errors/failures and verified
  exact collection, staged-input identities and normal cleanup
  (`gameplay-ci-hb8amp8t` under `.e2e-artifacts/ci`, summary
  `build-e2e/ci-summary-purchase.json`). `--require-clean` passed and `source_dirty`
  is false. Earlier dirty implementation rehearsals are explicitly labeled as such.
  `actionlint` v1.7.7 validates both client workflows. Read-only GitHub API inspection
  found zero registered self-hosted runners; no runner/settings were created.
  See `tests/e2e/CI.md` for mandatory workflow-scoped runner access restrictions,
  protected-environment approval and VM disposal responsibilities. Local rehearsal
  does not prove hosted approval, cancellation cleanup or independent compatibility.
- Nine live cases pass together: rejected credentials, login/idle/logout, observed
  movement/Say/position persistence, single quest, chained quests plus inventory
  persistence and one persisted gil-shop sale/purchase pair, zoning persistence, enemy defeat/rewards,
  player defeat plus source-bound homepoint return, and normal lobby creation plus the
  first Ul'dah opening branch. Both public tested territories use compatible
  server-side meshes; the private opening territory does not make a navigation claim.
- The initial single-action combat slice uses a fresh level-one Gladiator and the unchanged Central Thanalan
  population. The action catalog validates normally learned Fast Blade (9),
  requiring 60 naturally regenerated TP. Both player and observer receive the
  same damage effect and matching-result committed HP decrease on a nearby
  level-one marmot. Request acknowledgement/effect alone is insufficient.
  The fighter disconnects; it does not bypass in-combat logout restrictions.
  That original slice did not establish repeated actions or retaliation; the
  first extension below covered three paced strikes and the first retaliation hit.
  The later defeat/reward extension now covers one complete level-one defeat and
  persisted current-test-table loot/EXP. Combos, general cooldown scheduling,
  dynamic pursuit and production loot selection remain uncovered. Later increments
  below cover one player defeat and homepoint return, but not raises or death penalties.
  Initial position is fixture setup.
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
  swaps the occupied ether and potion slots and verifies both exact identities/counts
  after another restart. Operation-8/9 acknowledgements are explicitly retained as
  non-mutation evidence because the current server publishes them before attempting
  the operations and sends no slot deltas. Only complete subsequent snapshots
  establish either result. The test then observes a committed deletion of the
  relocated ether, unchanged other slots, logout, and deletion/remaining rewards/
  quest completion after the final restart. A later increment below adds one
  persisted partial split and no-overflow merge; item use remains uncovered. Clang,
  MSVC and GNU pass the byte-layout/state tests.
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

## Failed-plan minimization

`7ea74c4b79` adds `run_minimize.py` and `support/minimize.py`. The reducer first
reruns the full baseline in a fresh disposable environment; it does not trust a
historical result. It accepts a candidate only when the run fails in the workflow
stage, cleanup and outcome publication succeeded, and the same semantic action
has the same normalized assertion. Normalization removes only the ephemeral state
dump after `; state=`. Passes, different action/assertion failures, setup/cleanup/
artifact failures, missing outcomes and retained runtimes are rejected.

Exploration candidates remove ordered actions; soak candidates remove complete
actor rounds. Every candidate passes the ordinary plan validator before execution.
The execution budget (1..100, including baseline), candidate hashes, original
indexes, signatures, artifact roots, accepted decisions, budget exhaustion and
one-minimal status are recorded. Output overwrite is refused. Paced/minimum-span
plans are rejected rather than weakening their sustained-work evidence. A reduced
plan is only a semantic reproduction aid—not root-cause proof or scheduling/packet
determinism.

All **239** Python contracts pass with Clang and MSVC workers and in the
network-isolated Linux container, including 15 reducer contracts. The workflow
YAML parses with the new contract selection; no native or gameplay code changed.
A clean live reduction at `7ea74c4b79` expanded the already-established one-second
walk-timeout reproduction from two to eight valid actions, then ran five isolated
candidates. It rejected a different heartbeat timeout, rejected a passing
candidate, accepted only the exact walk assertion and produced the original
semantic two-action reproduction:

- Input canonical plan SHA-256
  `b53adb26c57683d7c5c5b194e9fd011ea56877bf9457850eaeb5bed6e1aff9fd`;
  minimized canonical SHA-256
  `0edbffe8f98fd74a420cd713180fcd139a2f2fcb917995ad9420be106f13b969`.
- Eight actions became two; original indexes 0/1 were retained, indexes 2..7
  removed; five executions, budget not exhausted, structurally one-minimal because
  the validated plan requires at least two actions for two bots.
- Baseline and both accepted candidates failed on exactly
  `population-0: timeout waiting for waypoint sent` for walk bot0/waypoint5.
- All five manifests record clean full revision `7ea74c4b79`; every result records
  `runtime_removed=true`, all whole private runtime roots are absent, and the one
  passing/different-failure candidates were not misclassified.
- Evidence: `.e2e-artifacts/minimizer-live-{input,output,output-report}.json`,
  candidate roots `sapphire-e2e-wsk6hafx`, `2qgq_k26`, `eqll6136`, `jwej02mu`,
  `5po9v23t`, and `build-e2e/minimizer-live.log`. Combined candidate elapsed time
  was 154.484s. These are deterministic-deadline reducer mechanics, not broad
  failure-minimization quality or a new server defect.

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

## Enemy defeat, persisted rewards and item-ID collision fix

`fe4630824c79c2ce9c290efd88bf1fe68d9d98bd` extends the same bounded normal
Fast Blade path until the already observed level-one target reaches zero HP, with
a hard limit of 16 requests. Before every request the independent observer still
checks the living fighter, exact target HP and melee range; both clients must
receive the identical effect and exact committed HP integrity. The final integrity
must be zero and both clients must observe delayed server removal. The prior natural
retaliation assertion is retained. No enemy, skill, TP or route is granted, spawned
or fabricated.

The matching local-data exporter now supplies level-one `BaseExp=50` and Gladiator
`WorkIndex=1`. The live assertion requires exactly 50 EXP, no level/currency change,
one five-item result from test-table pool 8/9, one each of items 5016 and 12728,
and one to three item 4551. It then closes the fighter session and performs a genuine
new HTTP/lobby/world login. Both aggregate reward state and every received inventory
slot must exactly match the post-kill state. This proves one current hard-coded
`testTable` path, not production loot-table selection or general reward behavior.

The first persistence attempt reached all death/reward assertions but correctly
failed after login: item 12728 reloaded as a second 5016. The retained
`.e2e-artifacts/sapphire-e2e-eabs_85s/world.log` records duplicate primary key
`18014398526259201-5242882`. `ItemMgr::getNextUId()` had repeated asynchronous
`MAX(ItemId)` queries, allowing rapid grants to receive the same ID before the
first insert became visible. `ItemIdAllocator` now reads the database maximum once,
then serializes process-local monotonic allocation. A 64-thread native contract
requires a single seed read and a unique contiguous range. This does not establish
collision safety across multiple world processes.

A clean seven-case gate at that commit passed in **306.007s**, with zero skips,
errors or failures and all setup/call/teardown reports present. The combat case took
70.033s and used 12 distinct paced requests to reduce HP 94 → 0; minimum attempt
spacing was 3.000s. Both clients observed the first one-damage retaliation and target
removal. This run received/persisted EXP 0 → 50 and exact loot 8×5, 12728×1,
5016×1 and 4551×3 in unchanged slots across fresh authentication. Evidence:
`build-e2e/ci-summary-combat-defeat.json`,
`.e2e-artifacts/ci/gameplay-ci-slr25cla/live.xml`, environment
`sapphire-e2e-h25lwnn_`, and `combat-defeat-rewards.json` SHA-256
`b815d83dbbb9646085726d737b1a1b38d16407b75c8e8eeddd3ac8084325f5c3`.
The catalog/server/worker hashes are respectively
`521eed9a08426afce42b3899bc079d37479e7a0b7292e14bc7bf30ba8c94580e`,
`ea113af804798c70e321292887c3edd5a3ff2b664834646fdb7220ff222fec88`, and
`d34c0e69407f05f285d1590232775c0b7581dc39255dde23ba1ca33c473953e9`.
The summary records clean source, exact collection/input identities and verified
cleanup; the private runtime root is absent. No duplicate-key error occurs in the
passing world log.

All **242** Python contracts pass with Clang and MSVC workers and in a
network-isolated Linux container. All six native suites pass with Clang, MSVC and
GNU 11.4. These checks plus the live fresh-login result cover the discovered
process-local collision; they do not prove hosted execution, general combat,
real-client presentation or multi-process allocation.

## Independently observed player defeat

`test_live_player_defeat.py` starts fresh rank-zero level-one Gladiator and witness
fixtures near unchanged Central Thanalan population layout 3749193 (base 302,
level 14). The fighter waits for the exact living observed target, natural TP and
estimated melee range, then sends one ordinary Fast Blade. It sends no further
combat action. The enemy remains alive and naturally retaliates until the fighter
reaches zero HP; the stationary witness independently receives the same complete
effect sequence, exact matching committed HP updates and defeated-player despawn.
No enemy is spawned, moved, damaged through a handler or granted an action.

Fast Blade remains a narrowly fixed semantic operation: observed living BNpc,
received living non-GM Gladiator state, TP, range, action 9 and bounded request IDs.
The artificial level-one target restriction was removed so an ordinary learned
ability can address this observed level-14 enemy; this is not an arbitrary action
or packet API. Each received HP integrity now records the immediately preceding
received actor HP. This lets the scenario prove every matching damage decrease even
when normal regeneration occurs between attacks, rather than incorrectly deriving
a pre-hit value from the previous attack's post-hit value. Native and Python policy
contracts cover level-14 acceptance while preserving kind/death/range/resource guards.

The targeted dirty-checkpoint run passed in **111.56s**. The subsequent clean
strict nine-case gate at `4755fc94b` passed in **432.516s**, zero skips/errors/
failures, with exact collection/input identity and cleanup checks. Evidence:
`build-e2e/ci-summary-player-defeat.json`,
`.e2e-artifacts/ci/gameplay-ci-zd2rsqts/live.xml`, environment
`sapphire-e2e-ed1g83qo`. The player-defeat case took 87.777s and its
`combat-player-defeat.json` SHA-256 is
`0cea232b93a0094beefc2031a8f6ffaca6d97134f07449720e4f3551239a3507`.
The worker SHA-256 was
`383c8854a0048c33b77ba7e058ceb9055be473262442edc7d6894817faf1f37a` and server
SHA-256 was
`233b53537476d69c0dc62e01f30fc1baf2a96298b4a25175e8a036191c25c7d2`;
the private runtime root is absent.

That original increment proves one player defeat after one initiating strike. It
does not prove natural proximity aggro, arbitrary enemy levels/abilities, pursuit,
party combat, death penalties, persistence while dead or real-client death
presentation. The later extension below adds only the bounded homepoint return.

## Source-bound homepoint return after player defeat

A new read-only generator resolves canonical Gladiator homepoint 9 through matching
3.3 Aetheryte metadata to exactly one source LGB pop range: ID 3693863 in territory
130 at `[-144.30470, -3.15489, -163.05969]`. The validator rejects another profile,
homepoint, territory, malformed transform or ambiguous/missing pop. The clean gate's
private catalog SHA-256 is
`d8450f888c65bff44c240acbbae3c6d615f382aebc026547cbdf50f652519218`.

The worker now records the received `HomePoint` from player status. Its semantic
return operation is deliberately limited to a received-dead self actor in territory
141 with homepoint 9, no movement/event in progress, and the source-defined
`REVIVE` command with `ResurrectType::Return`; every unused command field remains
zero. Native fixtures pin those bytes and reject a living actor, another territory
or another homepoint. This is not an arbitrary revive or teleport API.

The existing natural-defeat scenario now pre-positions a third ordinary witness at
the source pop range. After both Central Thanalan clients prove the complete natural
defeat, the fighter sends the return, disappears from the old witness, reaches
territory 130 at exactly the generated position with full 94 HP, and appears there
alive to the destination witness. After normal logout, world restart and fresh HTTP/
lobby/world authentication, the fighter reloads the same territory, position and
full HP. No fixture move, grant, handler call, raise or packet injection supplies
that evidence. `combat-player-defeat.json` SHA-256 in the clean gate is
`27c89c6b3255b6d434d8e2d60cefbd7077fd0f48c9f2550681d62aa6a305e1e5`.

The clean nine-case gate at `67ef4b144` passed in **514.181s**, zero skips/errors/
failures, exact collection/inputs and verified cleanup. The extended player-defeat
case took **78.746s**. Evidence: `build-e2e/ci-summary-respawn.json`,
`.e2e-artifacts/ci/gameplay-ci-t1kaqsfb/live.xml`, environment
`sapphire-e2e-ets9haqq`. Worker SHA-256 is
`d1cf8399b6ec49b3f31224cea5c96fc72e732f86c32feac9096dc43150cf5424`;
server SHA-256 remains
`923851751f5bb9503a355058dec9e7a6e39cc5052e54ee3efccb67b4e8193e23`.
The private runtime root is absent. All 247 Python contracts pass with Clang/MSVC
workers and in network-isolated Linux; all six native suites pass with Clang, MSVC
and GNU 11.4.

This proves one ordinary return-to-homepoint path. It does not prove raise spells,
other homepoints/classes, death penalties, same-territory return, persistence while
dead, pursuit, party combat or real-client death/return presentation.

## Persisted ordinary-bag move and swap

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
world restart. The observer independently verifies despawn/reappearance and
position, not private inventory.

`9a35fb49e6da310650ce373d62d226e5d6ca5a96` adds a similarly bounded operation-9
swap between two observed occupied ordinary-bag slots with different expected
item identities. Both counts come only from received state; invalid, empty, equal,
unobserved, self, non-bag and mismatched requests fail before sending. After the
move's restart assertion, the reloaded client swaps the earned ethers and starter
potions, normally logs out, restarts the world and freshly authenticates. The full
received map must show both identities/counts exchanged and every other tracked
slot unchanged before the relocated ethers are deleted through the existing
committed discard path.

All **224** Python contracts pass with Clang and MSVC workers and in the
network-isolated Linux container. All five native suites pass with Clang, MSVC
and GNU. Dirty-development chain runs after each final journal change were retained
only as implementation evidence. The move-only clean gate at `62c3391bd` passed
all seven cases in 269.054s. The subsequent combined clean strict gate at
`9a35fb49e` passed all seven cases in **275.495s**, zero skips/errors/failures,
with verified inputs and cleanup: `build-e2e/ci-summary-inventory-swap.json`,
`.e2e-artifacts/ci/gameplay-ci-9_qy4luy/live.xml`, environment
`artifacts/sapphire-e2e-cagywl6r`. Its manifest is clean at the full revision and
the whole private runtime is absent. Raw events retain exact operation-8/9
acknowledgements separately from authoritative snapshots. `inventory-move.json`
retains identical expected reconnect/restart maps; `inventory-swap.json` retains
the exact post-restart exchange and has SHA-256
`22fdb87bdf98d2451b52d22f3085bf81e5d8dc013421a252fbc9e3d282b0b8eb`.
The staged worker SHA-256 is
`d34c0e69407f05f285d1590232775c0b7581dc39255dde23ba1ca33c473953e9`;
the server remains unchanged at
`c10b9f7092ef081a9bf9886a9de98af2c6ed8bdb134f621c8e16f11c758187f1`.
This is headless server evidence, not immediate operation publication, crash
consistency, split/merge/item-use coverage or real-client inventory UI proof.

## Persisted ordinary-bag split and merge

`e50900ab80f3f31375050a09f16cd6ab4e64ed7f` adds only a partial split from an
observed three-item ordinary-bag stack into an observed empty ordinary-bag slot,
then a same-item no-overflow merge back into the original stack. The caller must
supply exact observed source/destination counts; zero, whole-stack, self, non-bag,
occupied, unobserved and mismatched operations fail before sending. Independently
authored byte fixtures check operation-10/12 fields. Their acknowledgements remain
explicitly non-mutation evidence.

Source inspection confirmed the deferred split concern: `Player::splitItem()` used
`addItem(..., canMerge=false)`, which populated its own first free slot, then assigned
the same item pointer to the requested destination as well. The server now creates
the persistent item without auto-placement, rejects a split count greater than or
equal to the source count, decrements the source and places the new item only at the
requested destination. This is a public server bug fix exercised through ordinary
client packets, not an E2E-only handler or fixture mutation.

The live chain earns the three ethers normally and first preserves the existing
move/swap checks. It splits the stack 3→2+1 into bag 3 slot 23, logs out, restarts
the world and freshly authenticates. The complete received map must contain exactly
those two stacks while preserving the potion/equipment slots and quest/reward totals.
It then merges 1+2, repeats the restart/authentication, and requires the exact
pre-split map before ordinary discard. `inventory-split-merge.json` records both
acknowledgements and both authoritative restart snapshots; SHA-256
`4807cb2c235d2f0c2b5ff50f59469ee6b42b689264463055621c879eb28b9966`.

All **244** Python contracts pass with Clang and MSVC workers and in a
network-isolated Linux container; all six native suites pass with Clang, MSVC and
GNU 11.4. The clean strict seven-case gate passed in **332.037s**, zero skips/errors/
failures, exact collection/inputs and verified cleanup. Evidence:
`build-e2e/ci-summary-split-merge.json`,
`.e2e-artifacts/ci/gameplay-ci-dqvq1hju/live.xml`, environment
`sapphire-e2e-17x3u3kb`. The chain case took 124.551s. The clean summary records
revision `e50900ab8`, worker SHA-256
`37c6ae4ff27fe8d27b22f1d601de7112165e3d83f37faabf11aa421ec0051f2f`
and server SHA-256
`233b53537476d69c0dc62e01f30fc1baf2a96298b4a25175e8a036191c25c7d2`;
the private runtime root is absent.

This proves one partial split and one no-overflow merge for ordinary bags. It does
not prove overflow behavior, immediate delta publication, crash consistency,
equipment/currency operations, item use or real-client inventory presentation.

## Normal lobby creation and first Ul'dah opening branch

The new `test_live_creation.py` starts from an ordinary account with no character.
The external worker authenticates to the encrypted lobby, receives an empty list,
uses `CHARAOPE_RESERVENAME` and `CHARAOPE_MAKECHARA` with the same canonical
Gladiator description already accepted by Sapphire's public creation path, refreshes
the list, selects the newly observed character IDs and enters the world. The test
requires rank zero, level one, territory 182 and `created_via_lobby=true`; the API
character fixture endpoint is not used for this journey.

In private opening territory 182, a narrowly bounded action sends only Sapphire's
source-defined enter-territory event 1245187. The committed scene catalog chooses
ring branch 1 from received scene 0, requires chained scene 1, and finishes it.
After a normal logout and fresh HTTP/lobby authentication, the complete received
inventory contains exactly one item 4423 while level, EXP and currencies remain
unchanged. Starting the same event now yields scene 40 rather than replaying scene
0, indirectly proving `OpeningSequence=1`; both the inventory and scene selection
remain identical after a world-process restart.

Logout/relogin synchronization does not use a fixed sleep. For this case the worker
waits for the server's post-ack transport close, which occurs after the server has
removed and unloaded the old session, before allowing the next login/restart. Other
scenarios retain their existing faster logout behavior. The initial targeted dirty-checkpoint run passed in **47.92s** with normal teardown.
The subsequent clean strict eight-case gate at `326114b5e` passed in **343.613s**,
zero skips/errors/failures, with exact collection/input identity and cleanup checks.
Evidence: `build-e2e/ci-summary-creation.json`,
`.e2e-artifacts/ci/gameplay-ci-b511jzk6/live.xml`, environment
`sapphire-e2e-ouyqrg87`. The creation case took 21.357s within the already-started
environment; its `character-creation-opening.json` SHA-256 is
`d03f96be84330e5df54c55c514b213e0476b0a9940ccbe53f99ef6b2dd568f17`.
The worker SHA-256 is
`600586442c6a74ac88c309e23012921e819898fe8f9286f472b7e693d651829b`
and server SHA-256 is
`233b53537476d69c0dc62e01f30fc1baf2a96298b4a25175e8a036191c25c7d2`;
the private runtime root is absent. All 245 Python contracts pass with Clang/MSVC
workers and in network-isolated Linux; all six native suites pass with Clang, MSVC
and GNU 11.4.

This evidence is deliberately narrow: it covers one canonical Gladiator, one ring
choice and the initial/continuation opening scenes. It does not establish account
signup UI, all appearance/class combinations, name rejection/deletion, the complete
opening quest, travel into public Ul'dah, real-client cutscene presentation or
broader protocol compatibility.

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

## Source-bound gil-shop sale/purchase and nonzero currency

A full-build read-only generator now binds one narrow economy path to matching 3.3
EXD and Detour data. From the normally reached Gil for Gold recipient (base
1001289), it selected a complete 641-point, approximately 302.30m route to gil-shop
base 1009247/layout 4757046/event 262468. Item 4551's source price is 28 gil. The
catalog and Python validator reject other territory/profile/sale bindings,
non-gil-shop events, incomplete/discontinuous routes and out-of-range endpoints.
The purchase extension additionally resolves the selected shop's actual item list
and binds index 0, item 5890, quantity one and source price eight gil. The latest
private catalog SHA-256 is
`efb78ce4c07814cc4848266f2e67d356d64631724d13811be6f8c1d265e3dd32`.

The C++ worker accepts the sale only while holding the matching received scene-40
token/event, with a complete received inventory containing exactly one potion in
the requested ordinary-bag slot. It emits the fixed scene-255 result layout used by
the existing gil-shop script; native fixtures pin the relevant byte offsets and
reject wrong event families/storage/slots. The live chain earns the potions
normally, splits one, proves that split after restart/fresh authentication, walks
the generated route, and has an independent client verify arrival. It then requires
an exact one-potion decrease and 0→28 gil increase both immediately and after
normal logout, world restart and fresh authentication. The operation-10 receipt is
retained only as acknowledgement evidence. From the refreshed matching scene, the
worker then permits only the bound purchase with exactly the observed 28 gil and no
pre-existing item 5890. Received state must become one item 5890 and 20 gil with all
other slots unchanged; fresh authentication after restart must return the identical
map. Native fixtures pin the purchase result fields. `gil-shop-sale.json` SHA-256
in the latest clean gate is
`5079808c53761d2fc3b614e57adba9e0cc5b44d13e1fd149cae654b90d5bddda`.

The first live attempt exposed two server defects rather than prompting weaker
assertions. `addCurrency()` created a missing currency item with the generic
factory's default stack of one before adding the sale value; it now materializes
zero first. Reloading the first persisted nonzero currency also exposed that
`ItemMgr` was registered after player loading; it is now registered before any
inventory can allocate an item ID. The clean nine-case gate at `b30883295` includes
the resulting restart and took 540.585s; the chained case took 236.861s. Worker and
server hashes are respectively
`4d559f543a322dafe284f4cad35b9a29162676106f3e887ff995f7cdf7b3859d` and
`923851751f5bb9503a355058dec9e7a6e39cc5052e54ee3efccb67b4e8193e23`.

The server now also rejects zero-quantity or unlisted purchases, sale item-ID/slot
mismatches and overflowing purchase totals rather than trusting client result fields.
The clean nine-case gate at `fc89b2422` passed in **549.892s**, with the chain taking
**224.179s**. Worker/server hashes are
`66a368cc85e2434d38e2559b41549b555f7f099845fa4ef02cd1838dec89862f` and
`74fa8f17579b4a4b3d499afeca93c2a9660a58c566dbb37486b93c5e5206e784`.

This is one headless sale/purchase pair, not general shops, arbitrary item/quantity
transactions, currency-container movement, real-client shop presentation,
transaction isolation, multi-process allocation safety, crash consistency or
leak-freedom.

## Next actions / boundaries

1. Broaden supported-state policy coverage, including item use, overflow merges and
   inventory operations beyond the verified ordinary-bag move/swap/split/merge, and add longer/higher-population
   controls. The observed autosave retention is fixed and the matching 30-minute
   replay is flat; this does not establish capacity or memory stability for all
   code paths. Generator histories/allocator retention also remain distinct from
   server resource behavior.
2. Extend combat beyond the now-verified enemy/player defeat, homepoint return and persisted
   current-test-table rewards: pursuit, raises, combos, additional abilities
   and production loot selection remain uncovered. Preserve observed resource/range
   checks and require genuine navigation for any pursuit.
3. Extend explicit trigger/scene adapters and the normal creation journey beyond
   the first Ul'dah opening branch; unknown content must still fail.
4. Provision and validate the authored gameplay CI on a workflow-restricted disposable
   runner (none is currently registered), including approval/cancellation/disposal.
   The separate 30-minute paced workload is not part of the nine-case CI gate.
5. Broaden the now-rehearsed manual real-client lane's presentation-sensitive
   coverage and independently captured trace/layout checks. Strengthen fault and
   cancellation coverage separately from successful-path evidence. Do not alter
   the user's installed executables/settings. Narrow successful sessions are not
   general compatibility, automated UI coverage or a golden-trace corpus.

The original legacy mesh-loading blocker is resolved without modifying developer
assets. Matching 3.3 quest data confirms Due Diligence (65685) would award 103 gil,
but the same catalog generator still rejects its start-to-finish path as an
incomplete navigation corridor. It is not used through fabricated movement or
fixture relocation and its quest-currency reward remains unverified. Nonzero
currency is instead covered narrowly by the source-bound shop transaction above;
this is not evidence for Due Diligence or general economy correctness. Due
Diligence no longer blocks the first quest: Motivational Speaking is verified. Narrow independent real-client
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

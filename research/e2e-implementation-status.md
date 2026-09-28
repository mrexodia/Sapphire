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
| Bounded soak / ramp / metrics | 2..32-bot controller, <=1000 actions, explicit duration; process RSS/CPU and action timings | Sixteen bots / 960 actions and fresh replay verified; not capacity or long-running evidence |
| Semantic replay | Versioned allowlisted plans, route hash, logical bot roles, recorded time/ramp limits | Passing exploration plan replayed; scheduling is not deterministic |
| Failure minimization | No reducer | Missing |
| Deadlines / cancellation / cleanup | Timers, bounded waits, owned-process teardown, redaction; bounded Windows sharing-error retries | Initial paths verified; broader stress/signal testing remains |
| Action/event/server logs / hashes / JUnit | Bounded sanitized journals; runtime/module/worker/catalog/mesh identities | Implemented; hashes do not prove independent compatibility |
| Asset-independent CI | `.github/workflows/test-client.yml` | Authored; hosted run unverified |
| Provisioned gameplay CI | `gameplay-e2e.yml`, `sapphire_gameplay_ci` build target, `run_ci.py`, `CI.md` | Authored and locally rehearsed with freshly built binaries; hosted execution/runner controls unverified, no registered runners |
| Independent real-client/golden trace compatibility | No independently captured session | Missing |
| Full objective | Missing rows above remain | **Not achieved; do not complete goal** |

## Verified results

- Clang/Ninja and MSVC/Visual Studio: four CTest executables pass (protocol,
  rewards, combat, synthetic navigation). Navigation tests reject disconnected and
  off-mesh destinations rather than accepting a partial Detour path.
- GNU 11.4/Ubuntu 22.04: standalone build and the same four CTest executables pass.
- 96 Python worker/policy/CI/pacing contracts pass with the MSVC worker and in a
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
  (`sapphire-e2e-u7p2e6ex`). Longer sustained evidence is still pending.
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
- One Windows teardown encountered a transient executable-file permission failure.
  Bounded retries were added; persistent failures remain visible and retryable.

## Next actions / boundaries

1. Broaden the supported-state policy coverage and run longer/higher-population
   workloads; short passing runs do not prove stability or capacity.
2. Extend the initial combat slice with normally timed repeated actions, enemy
   defeat, received combat rewards and retaliation assertions. Preserve observed
   resource/range checks and require genuine navigation for any pursuit.
3. Extend explicit trigger/scene adapters; unknown content must still fail.
4. Provision and validate the authored gameplay CI on a workflow-restricted disposable
   runner (none is currently registered), including approval/cancellation/disposal.
   Continue longer-duration stability runs; current five-minute evidence is insufficient.
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

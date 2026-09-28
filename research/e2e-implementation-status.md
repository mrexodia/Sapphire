# E2E implementation checkpoint and requirement audit

**Overall goal: not complete.** Green tests cover a supported subset, not all six
rollout stages or real-client compatibility. Branch: `feature/headless-e2e`.

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
| Compatible navigation assets | `BuildNavigation.cpp` reuses exporter; separate TSET output, originals unchanged; `NavigationRoute.cpp` requires complete corridors and sampled surfaces | Verified for Motivational Speaking; Due Diligence disconnected |
| Versioned route/scene data | Private generated catalog v1; checked-in explicit `motivational_speaking.json` scene choices | One live verified adapter; Due Diligence remains source-derived |
| Interact / choose dialogue / unknown-scene failure | Exact received event/scene/token; no default choice or raw-packet control; contract tests | Verified for supported one/two-result returns |
| Quest state / accept and cancel / completion | `test_live_quest.py`: Motivational Speaking (65686), cancel unchanged, accept sequence 255, completion | Verified |
| Received inventory/currency/XP model | `RewardsState.cpp`: initial snapshots, deferred successful transactions, class-index and incremental XP | Unit verified; live item/XP rewards verified; nonzero currency reward still unverified |
| Exact quest rewards | Independent authored expectation: 50 XP and two items 4551, no other tracked bag/currency change | Verified |
| World restart and fresh login | Position, completed flag, absent active quest, XP and tracked bag quantities checked after restart | Verified |
| More quests / zoning / inventory operations / combat / social | Ordinary Say observed by another bot; quest-created inventory observed | Social subset verified; additional quests, zoning, item actions and combat missing |
| Range/discovery/territory event triggers | No general adapter yet | Missing |
| Yield/resume and broader scene variants | Explicit unsupported capability; only fixed one/two-result returns | Missing |
| Deterministic authored regression suite | Four live scenarios, native tests and Python contracts | Initial suite verified |
| Seeded exploration / bounded soak / replay / resource metrics | Follow-on policy work | In progress; not established by quest tests |
| Failure minimization | No reducer | Missing |
| Deadlines / cancellation / cleanup | Timers, bounded waits, owned-process teardown, redaction; bounded Windows sharing-error retries | Initial paths verified; broader stress/signal testing remains |
| Action/event/server logs / hashes / JUnit | Bounded sanitized journals; runtime/module/worker/catalog/mesh identities | Implemented; hashes do not prove independent compatibility |
| Asset-independent CI | `.github/workflows/test-client.yml` | Authored; hosted run unverified |
| Provisioned gameplay CI | Local opt-in profile and documented commands | Dedicated trusted-runner workflow missing |
| Independent real-client/golden trace compatibility | No independently captured session | Missing |
| Full objective | Missing rows above remain | **Not achieved; do not complete goal** |

## Verified results

- Clang/Ninja and MSVC/Visual Studio: three CTest executables pass (protocol,
  rewards, synthetic navigation). Navigation tests reject disconnected and
  off-mesh destinations rather than accepting a partial Detour path.
- GNU 11.4/Ubuntu 22.04: standalone build and the same three CTest executables pass.
- Python worker contracts pass on Windows and in a network-isolated Linux
  container. This WSL instance refuses even Python-only loopback connections;
  the failing WSL socket check was not skipped or rewritten to make it pass.
- Four live scenarios pass together in 96.16s: rejected credentials, login/idle/
  logout, observed movement/Say/position persistence, and full quest/rewards/
  completion persistence.
- Current navigation generated separately in `.e2e-assets/uldah-v2`; repeat output
  refused, original OBJ and legacy mesh hashes unchanged. The 65686 route has
  322 points and length approximately 152.375m, with nearby walkable NPC approaches.
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
- One Windows teardown encountered a transient executable-file permission failure.
  Bounded retries were added; persistent failures remain visible and retryable.

## Next actions / boundaries

1. Finish bounded supported-action policies, replay and metrics with live evidence.
2. Add more implemented quests, normal zoning, inventory actions and combat; add
   the corresponding received-state and independent-observer assertions.
3. Extend explicit trigger/scene adapters; unknown content must still fail.
4. Validate provisioned gameplay CI and longer/higher-population stability runs.
5. Obtain an appropriate locally run real client or a maintainer-supplied sanitized
   trace. Shared schemas and headless-to-server agreement cannot substitute for it.

The original legacy mesh-loading blocker is resolved without modifying developer
assets. Due Diligence still lacks a complete corridor, but it no longer blocks the
first quest: Motivational Speaking is verified. Independent real-client evidence
still requires an appropriate client run/trace; other missing scenarios remain
implementation work, not proof that user input is the only next step.

# E2E implementation checkpoint and requirement audit

**Overall goal: not complete.** This is an implementation checkpoint, not a claim
that the entire proposed framework or all six rollout stages have shipped.

Branch: `feature/headless-e2e`.

## Concrete success criteria

Implement an external C++ headless Sapphire client controlled by Python scenarios,
using genuine authentication/lobby/world connections against disposable servers.
Provide observed-state assertions, two-client movement tests, supported quest
scene handling, reward/persistence tests, diagnostics, CI integration, and later
supported-action exploration/soak workflows. Keep fixtures separate from tested
actions, do not use GM shortcuts, and do not claim mock/codec tests prove gameplay
or real-client compatibility.

## Prompt-to-artifact audit

| Requirement / named deliverable | Artifact and actual evidence | Status |
|---|---|---|
| Research/architecture plan | `research/autonomous-testing-plan.md` | Written; original proposal, not completion evidence |
| Dedicated branch / atomic commits | `feature/headless-e2e`; session fix and C++ worker are separate commits | In progress |
| External C++ worker, no server-handler calls | `src/test_client/{main,Client,Protocol}.{cpp,h}`; standalone build; live journeys use sockets | Verified for enabled actions |
| Reuse wire definitions / lobby encryption | Shared `PacketDef` headers plus `Protocol.cpp`; CTest layouts/stream/cipher tests and successful live lobby login | Verified for current profile |
| Python + pytest / JSON-lines control | `tests/e2e/support/worker.py`, `conftest.py`, tests; C++ stdin/stdout dispatcher | Implemented and tested |
| Multi-bot client state / async keepalives | C++ Bot/Channel state machines; live two-bot test; per-channel keepalive assertions | Verified |
| Normal HTTP authentication / lobby character selection | `Environment.api`, `Bot.login_via_lobby`; live login scenario | Verified |
| Normal creation journey | Fixtures use account/character provisioning; character creation through lobby not tested | Missing dedicated journey |
| Isolated database/config/processes | `support/environment.py`; private MariaDB, unique schema/ports, staged executables and configs; successful live setup/teardown | Windows verified; Linux provisioned path unverified |
| Application readiness | Self-spawn + received cleared BetweenAreas after FINISH_LOADING; live scenario | Verified, more lifecycle tests useful |
| `login_via_lobby`, `wait_world_ready`, `logout` | Python Bot methods; live login/idle/logout test | Verified |
| `walk_to`, route actions | Interpolated C++ movement; Python `walk_route`; independent observer position assertion | Tiny public-Ul'dah segment verified; general routing not verified |
| Navigation reuse / matching data | Optional `Catalog.cpp` links existing EXD/PathFinder libraries; NPC metadata resolves | Path attempt blocked by current mesh tile-data load failure |
| `interact`, `choose_dialogue`, unknown-scene stop | C++ exact scene identity/token validation; Python catalog lookup; unit tests reject unknown choices | Implemented, not live quest verified |
| Versioned routes / scene metadata | `scene_catalog/due_diligence.json` is source-derived; optional catalog export | Scene file present; no verified quest route yet |
| Quest-state/completion observations | C++ decodes quest slot updates/full list/completion flags; Python expectation methods | Implemented, not live quest verified |
| Quest range/discovery/territory trigger evaluation | Not implemented | Missing |
| Yield/resume / scene variants | Capability report explicitly lists scene yield unsupported; only one/two-result returns supported | Incomplete |
| One complete quest / accept and cancel branches | Candidate: Due Diligence; its NPC/requirements metadata resolved locally | Not achieved |
| Quest reward assertions | No inventory/currency/XP state model/assertions yet | Missing |
| Persistence through server restart | Live observer-movement scenario logs out, observes despawn, restarts world, logs in and verifies position | Position verified; quest/reward persistence missing |
| More supported gameplay / territory transition / combat / social | Not implemented beyond initial movement and login | Missing |
| Independent observer / non-optimistic assertions | `test_observed_movement_and_position_persistence`; predicted and received positions separate | Verified for movement |
| Non-GM accounts / real sessions / no gameplay shortcuts | Test configs rank 0, sessions required; worker checks received GM rank; only fixture setup edits initial DB state | Verified for live suite |
| Deterministic authored regression scenarios | Three live tests and contract suite | Initial subset implemented |
| Seeded exploration / action preconditions / invariant checks | Worker has some action preconditions; no exploratory policy engine | Missing |
| Semantic replay / failure minimization | Bounded sanitized action journal exists; no replay/minimizer | Incomplete |
| Soak/load / bounded ramp / success/latency/resources | Max 64 bots in worker, but no workload controller/metrics | Missing |
| Deadline/cancellation/cleanup | Per-login C++ timer, per-action Python deadlines, close/remove, subprocess cleanup; worker-death tests | Initial implementation verified; stress/signal testing remains |
| Failure artifacts / versions / JUnit | Redacted logs, observed event and action rings, hashes/fixture manifest; local JUnit files | Implemented for current suite |
| Public asset-independent CI | `.github/workflows/test-client.yml` for Windows/Linux contracts | Authored; no hosted CI run yet |
| Provisioned gameplay CI | Local opt-in profile and commands documented | No dedicated trusted-runner workflow yet |
| Independent real-client compatibility / golden captures | Fixed layout tests exist; no independently captured real-client golden session | Missing |
| Full goal completion | Green current subset does not cover missing rows above | **Not achieved; do not complete goal** |

## Verification performed

- Standalone Clang/Ninja build of `sapphire_test_client` and protocol tests.
- Standalone MSVC/Visual Studio Debug build of the same targets.
- `ctest --test-dir build-e2e --output-on-failure`: 1 test executable passed.
- `ctest --test-dir build-e2e-msvc -C Debug --output-on-failure`: passed.
- `python -m pytest tests/e2e/test_worker.py --e2e-worker build-e2e/sapphire_test_client.exe`: 14 passed.
- Same 14 Python contracts with `build-e2e-msvc/Debug/sapphire_test_client.exe`: passed.
- `python -m pytest tests/e2e/test_live.py --e2e-profile .e2e-local.json -v --junitxml=build-e2e/live.xml`: 3 passed, latest run approximately 46 seconds.
- Full-build `sapphire_test_catalog` target compiled and returned candidate quest/NPC metadata from locally available matching game data.
- Catalog navmesh route attempt failed explicitly with `PathFinder: Couldn't read tile data` for `w1t1.nav`; no successful route was fabricated.

Local generated verification outputs (ignored by git): `build-e2e/contracts.xml`,
`build-e2e/live.xml`, `build-e2e/Testing/Temporary/LastTest.log`,
`build-e2e/catalog.json`, `.e2e-artifacts/sapphire-e2e-*/`.
The exact runtime/server/module hashes are recorded per live run.

## Supporting correction uncovered during real execution

Independent bot accounts initially interfered during session creation. The narrow
supporting fix in `src/api/SapphireApi.cpp` now obtains fresh 62-character tokens
from the OS random source via `src/common/Crypt/Random.*`, rather than global RNG
state. Existing wire length is preserved; errors fail closed. The API was rebuilt
before the successful multi-bot runs. This is a separate commit from the testing
framework, not a timing workaround in tests.

The first worker revision also incorrectly treated self-spawn as complete
readiness. Live movement verification exposed the missing FINISH_LOADING command;
the worker now waits for a received condition update before reporting ready.
Sapphire registers its current logout handler under StartLogoutCountdown; the
client follows that normal path and observes the logout acknowledgement.

## Next concrete actions

1. Generate a compatible Ul'dah navmesh into a **separate local test asset
   directory**, using existing export/Recast tooling. Do not rewrite the developer's
   existing `bin/navi` or bypass the failure with teleport/straight-line fallback.
   Re-run the catalog path query and independently check start/end/route geometry.
2. Decode inventory/currency/XP observations required for the selected quest's
   rewards, with wire fixtures. Build a data-backed fixture near the quest giver
   before first login, then test acceptance/cancellation, route, scene hand-ins,
   completion/rewards and restart persistence through normal packets.
3. Add the remaining supported event triggers and a curated zone-transition test;
   explicitly report unsupported content instead of silently succeeding.
4. Add bounded seeded exploration and soak policies using the same action API,
   then semantic trace replay and metrics.
5. Validate Linux provisioning and hosted contract CI; obtain a known-good local
   real-client trace for independent compatibility checks.

The navmesh failure is an unresolved dependency for the chosen quest route, not
proof that route generation is impossible. Continue with the existing exporter
before declaring that user input is required. Real-client compatibility will need
an appropriate locally run client or a sanitized trace supplied by the maintainer.

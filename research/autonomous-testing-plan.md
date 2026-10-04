# Autonomous end-to-end testing for Sapphire

Status: **historical design document**. The headless client and most of the
scenario machinery described here were built. The project then deliberately
dropped the disposable-fixture, hosted-CI, soak, and graphical-acceptance lanes in
favour of running the same bots against an ordinary local development server.
The current, much shorter description of how the tests work is
[`tests/e2e/README.md`](../tests/e2e/README.md). The principles below about normal
protocol use, received-state assertions, non-GM bots, and never retrying an
uncertain mutation still apply.

## Recommendation (historical design)

Build an **external, headless test client** that talks to Sapphire through its normal HTTP and game connections. Give it a small, stateful client model and reusable gameplay actions. Run authored scenarios first; add constrained, seeded exploration after the basic actions are reliable.

Use **C++ for the protocol/client worker and Python for scenario orchestration**. Avoid a custom scripting language, an embedded server bot, and an LLM-driven player as the starting point.

The first milestone should be deliberately small:

> A fresh test account authenticates, selects a character through the lobby, enters the world, remains connected, and logs out. A second bot then observes normal movement. Next, one implemented quest is completed through its real event/scene exchange, and completion survives a server restart.

This is server E2E coverage through a simulated client. It does not prove that the real client renders correctly, selects the same dialogue, or plays its cutscenes correctly. Maintain a small real-client compatibility suite separately.

## Repository research

| Area | Evidence | Design consequence |
|---|---|---|
| Target version | `README.md` identifies FFXIV 3.3 and the game build. | Pin the bot protocol and content data to a version; do not assume modern FFXIV tools match. |
| HTTP authentication | `src/api/main.cpp`, `login`, returns a session and lobby connection information. | Exercise HTTP authentication as part of the full journey. |
| Lobby | `src/lobby/GameConnection.cpp` handles encryption initialization, service login, character lists/operations, and game login. | A world-only packet sender is not full E2E. The lobby needs its own state machine. |
| World connections | `src/world/Network/GameConnection.cpp` distinguishes zone and chat connections and handles session initialization/keepalives. | Maintain both channels and their lifecycle rather than treating the world as one stateless socket. |
| World readiness | `src/world/Network/Handlers/PacketHandlers.cpp`: `loginHandler` joins the world; `setLanguageHandler` finishes loading and spawns the player. | An open socket is not readiness. Model initial loading and subsequent zoning explicitly. |
| Protocol infrastructure | `src/common/Network/{Connection.h,GamePacket.h,GamePacketParser.*,PacketContainer.*}` and `PacketDef/`. | Reuse appropriate transport/schema infrastructure, with a client-specific adapter and independent compatibility checks. These are not already a complete client SDK. |
| Movement | `PacketHandlers.cpp`, `moveHandler`, updates the player and queues movement for in-range players. | Use a second client to verify movement replication; local predicted position is not an assertion. |
| Client-originated events | `src/world/Network/Handlers/EventHandlers.cpp` handles talk, range, territory-entry, return, and yield messages. | Walking alone is not sufficient to exercise every trigger. The bot needs client-side trigger behavior. |
| Quest scenes | `src/world/Manager/EventMgr.cpp`, `handleReturnEventScene`, invokes stored callbacks and updates quest state. | A bot must respond to the expected scene with the appropriate result, not merely send a talk request. |
| Concrete quest candidate | `src/scripts/quest/subquest/uldah/SubWil000.cpp` implements “Due Diligence” with acceptance, alternative scene paths, and completion callbacks. | Useful candidate for the first quest scenario, subject to checking prerequisites, NPC placement, rewards, and actual runtime behavior. The generated-template header is not sufficient to judge implementation status. |
| Quest observations | `src/common/Network/PacketDef/Zone/ServerZoneDef.h` defines active-quest, quest-update, and completion messages. | Build assertions from decoded server state, not from the commands sent. |
| Navigation | `src/common/Navi/PathFinder.h` exposes waypoint/path queries and mesh initialization; `src/tools/nav_export/` contains export tooling. | Reuse the navigation library where practical, but verify mesh availability and behavior before promising general traversal. |
| Scripts | `src/scripts/CMakeLists.txt` builds native modules; `config/world.ini.default` enables hot swap by default. | Bot scenarios should be separate from server scripts. Disable hot swap in regression runs and record module versions. |
| Fixtures/persistence | `src/dbm/main.cpp`, `sql/schema/`, `sql/migrations/`. | Use disposable databases and existing initialization/migration tooling, not the developer's current database. |
| Runtime assets | `config/global.ini.default`, `src/world/WorldServer.cpp` require game data; the README forbids distribution of client/content files. | Full E2E needs a suitably provisioned runner. Do not assume a clean public CI runner has the necessary assets or publish them as artifacts. |
| Existing CI | `.github/workflows/build.yml` builds on Linux and Windows. No project-level E2E runner or test registration was found in the inspected project files. | Add a test stage rather than assuming existing build success proves gameplay behavior. |

### Important uncertainty

This research establishes likely components and integration points, not a proven complete wire transcript. Validate login ordering, scene/result semantics, navigation assets, and supported quests against a known-good local client session before fixing the bot contract.

## Architecture

```text
Python scenario runner / pytest
  |-- disposable DB + fixture provisioner
  |-- API / lobby / world process supervisor
  |-- assertions, deadlines, reports, artifact collection
  |
  +-- C++ headless client worker(s), controlled over local pipes
        |-- HTTP authentication and lobby state machine
        |-- zone + chat sessions, framing, keepalives
        |-- received-state model + ordered event journal
        |-- gameplay actions and client event/scene adapter
        |-- waypoint/navigation support
        |
        +-- normal network traffic --> Sapphire API / lobby / world
```

A worker may eventually host many bot sessions using asynchronous I/O. Start with one or two bots, not a distributed load generator.

### 1. Protocol/client layer

Responsibilities:

- Versioned packet encoding/decoding and explicit client/server direction.
- TCP stream assembly across partial reads and multiple messages per read.
- Lobby negotiation and the normal character-selection handoff.
- Zone/chat startup, keepalives, graceful shutdown, and explicit reconnect operations.
- Session states such as disconnected, authenticated, lobby-ready, loading, world-ready, zoning, and closing.
- Bounded queues, operation deadlines, cancellation, and useful error classifications.

Do not copy server `GameConnection` wholesale: it dispatches into server services and gameplay handlers. Reuse suitable low-level pieces, not the authoritative game logic.

Initially linking `common` may be practical, but its CMake target brings data, database, and navigation dependencies. Keep the client boundary clean; consider a smaller protocol target once the first client proves the required surface. Avoid a broad preparatory refactor.

### 2. Client state and observations

Track at least:

- The bot's identity, territory/loading state, conditions, and connection health.
- Nearby dynamic actors, spawn/despawn events, and received positions.
- Active quests, sequence/variable updates, and completion flags.
- Current event/scene and pending responses.
- Inventory/currency/experience needed by enabled scenarios.

Separate **commanded/predicted state** from **server-observed state**. Sending movement does not establish that another player saw it. Sending a scene result does not establish that a quest completed.

Retain an ordered, timestamped event journal so waits can inspect state or events already received. Register event waits before triggering actions where appropriate; do not lose an immediate response because a subscriber was attached late.

Static NPC/object identities and trigger geometry may require a content catalog in addition to network observations. Keep base IDs, layout IDs, and runtime entity IDs distinct. Resolve scenario names into the correct versioned identifiers rather than scattering hard-coded runtime IDs through tests.

### 3. Gameplay action API

Expose semantic operations such as:

- `login`, `select_character`, `wait_world_ready`, `logout`.
- `walk_route`, `walk_to`, `target`, `interact`.
- `expect_scene`, `choose_dialogue`, `wait_event_finished`.
- `expect_quest_active`, `expect_quest_complete`, `expect_inventory_delta`.
- Later: combat, parties, territory transitions, and instance entry.

Each action has preconditions, allowed transitions, completion observations, a deadline, and diagnostic output. Do not expose raw packet construction as the normal scenario interface.

A semantic action completing is not automatically a test passing: scenarios still assert externally observable results and relevant invariants.

### 4. Event and scene adapter

This is a distinct subsystem, not an incidental convenience:

1. Resolve an eligible interaction from the bot's state and scenario/content metadata.
2. Move into the intended interaction range using normal movement.
3. Send the normal interaction/event request.
4. Observe the expected event/scene.
5. Supply a scenario-defined dialogue choice or scene result.
6. Handle any defined chained scene or yield/resume exchange.
7. Observe event termination and the resulting quest/reward state.

Use an explicitly supported scene catalog keyed by protocol/content version and event/scene identity. **An unknown scene must stop with an actionable unsupported-scene report, not be automatically accepted.** Some scenes need cancellation, reward choices, or intermediate responses; a universal success acknowledgement would give misleading coverage.

For range/discovery/territory triggers, begin with verified trigger metadata for the selected route. General content-driven trigger evaluation is a later capability. Sending an arbitrary event identifier without reproducing its intended conditions should not count as route/trigger E2E coverage.

### 5. Navigation

Stage navigation in this order:

1. Curated waypoints in one simple area.
2. Locally loaded navmesh routing for selected territories.
3. Content-aware transitions, doors, trigger regions, and dynamic obstacles.

Interpolate ordinary movement with plausible speed/cadence, turning, and stopping. Do not teleport to the endpoint and label it walking coverage. Treat missing meshes or unsupported transitions as capability failures, not as permission to jump through geometry.

Have a progress watchdog and a bounded replanning policy. In regression tests, unexpected recovery should be reported, not silently erase evidence of a defect. In exploratory runs, limited recovery is useful if the original stalled state remains in the trace.

Reusing server navigation helps development speed, but does not independently validate that navigation is correct. Include curated geometry/routes and selected real-client checks.

## How autonomous should the bots be?

Use three modes with the same action API:

| Mode | Decision policy | Purpose |
|---|---|---|
| Regression | Authored scenario, fixed fixtures and explicit expected transitions | Reliable developer/PR signal |
| Exploration | Seeded choices among actions whose preconditions hold, with step/time budgets | Broader supported-state coverage |
| Soak/load | Repeated weighted workflows with a fixed concurrency ramp and bounded target rate | Session stability and performance |

“Fully autonomous” can mean no human interaction is required once a test starts. It does not require the bot to infer every quest or improvise decisions with an LLM.

For exploration, log every decision, select only supported actions, and check invariants continuously. Save the shortest known failing action sequence and turn a useful failure into an authored regression. A seed alone does not reproduce server randomness or thread scheduling; record the actual actions and observations as well.

Do not make exploratory coverage a substitute for explicit expectations. Ten thousand successful connections do not establish that one quest rewards the right item.

## Scripting decision

**Yes to ordinary scripts; no to a bespoke DSL initially.**

Recommended split:

- C++17 + existing Asio infrastructure for the client worker.
- Python with pytest for fixtures, scenarios, process supervision, and reporting.
- A small versioned JSON-lines request/event protocol over local stdin/stdout pipes; keep logs off protocol stdout. Include request IDs, bot IDs, cancellation, errors, and state snapshots. JSON is control traffic, not a re-encoding of every game packet.
- Data files for fixtures, route names, scene mappings, and expected outcomes.

This avoids maintaining a second hand-written copy of the entire C++ wire schema in Python, while making scenarios easy to write and debug. Avoid native Python bindings until there is a demonstrated need.

If keeping everything in C++ is a project requirement, keep the same semantic API and author the first scenarios in C++. Scripting can be added later without changing the wire client. A pure Python prototype is also viable for a very small protocol surface, but schema drift becomes a maintenance cost as coverage expands.

Illustrative future API, **not existing runnable code**:

```python
async def test_simple_quest_survives_restart(run):
    fixture = await run.fresh_fixture("simple_delivery")

    async with run.bot(fixture.account) as bot:
        await bot.login_via_lobby()
        await bot.wait_world_ready()
        before = bot.observed.reward_snapshot()

        await bot.walk_route(fixture.route_to_giver)
        await bot.quests.accept(fixture.quest, choice="accept")
        await bot.expect.quest_active(fixture.quest)

        await bot.walk_route(fixture.route_to_recipient)
        await bot.quests.turn_in(fixture.quest,
                                 reward=fixture.reward_choice)
        await bot.expect.quest_complete(fixture.quest)
        await bot.expect.reward_delta(before, fixture.expected_reward)
        await bot.logout()

    await run.wait_for_session_cleanup()
    await run.restart_world_preserving_database()

    async with run.bot(fixture.account) as bot:
        await bot.login_via_lobby()
        await bot.wait_world_ready()
        await bot.expect.quest_complete(fixture.quest)
        await bot.expect.persisted_reward(before, fixture.expected_reward)
```

The quest helper must use an explicit supported scene adapter. It must not call server quest methods or set completion flags directly.

## Test validity and reproducibility

### Fixtures and isolation

- Separate database, ports, working directories, logs, and credentials for each isolated environment.
- Initialize/migrate with the repository tooling; version the fixture data.
- Use throwaway non-GM accounts for gameplay. `DefaultGMRank` is currently 90 in the default global config, so generate a test-specific configuration rather than blindly copying defaults.
- Keep `AllowNoSessionConnect=false` for full-login tests.
- Maintain both a small account/character-creation journey and faster scenarios with pre-provisioned characters. Label the latter's setup boundary accurately.
- Seed state only before the tested journey; never satisfy an assertion by modifying the live DB or invoking server handlers.
- Do not reset database state under a running world with cached players. Disconnect/stop the affected processes before restore.
- Keep each scenario independent; reuse the worker/library, not accidental character progress from the previous test.

### Assertions and observation hierarchy

1. Server messages decoded by the acting client.
2. A second client for visibility, movement replication, chat, and social behavior.
3. Reconnection/restart to prove persisted state was actually reloaded.
4. Optional read-only DB snapshots or structured server telemetry for corroboration and debugging.

DB queries alone are not gameplay success. Likewise, the bot updating its own internal quest state optimistically is not evidence.

Avoid adding a writable test-control API to the server initially. If diagnostic hooks become necessary, make them opt-in, local/test-only, and separate from the actual gameplay path.

### Reliable execution

- Wait for conditions/events with monotonic deadlines rather than long fixed sleeps.
- Check application readiness, not just port availability: game data, database, territory state, and scripts must be initialized.
- Disable script hot swap and record build, script, fixture, protocol, data, and navmesh versions.
- Give every step and entire run a timeout; guarantee cleanup on failure and interruption.
- Distinguish assertion failure, unsupported feature, missing asset, setup failure, server crash, and bot failure.
- Do not automatically retry gameplay actions that may already have succeeded, such as acceptance or item transactions. Infrastructure retries must preserve the first failure and obey explicit idempotency rules.
- Keep regression and recovery-testing policies separate. Unexpected reconnection should not silently turn a failed regression green.
- Treat expected failures/skips as explicit, reviewed capability entries. A previously supported scenario becoming unsupported must not disappear from the pass rate.

### Independent compatibility checks

Sharing packet definitions can reproduce the same mistake on both sides. Supplement reuse with known-good local-client traces, byte-layout fixtures, and a small real-client smoke suite. Normalize timestamps and runtime IDs in trace comparisons.

Use traces to derive state transitions and validate message encoding. Do not blindly replay a saved session: identifiers, session data, and timing change between runs.

## Staged delivery and acceptance gates (optional historical roadmap)

| Stage | Deliverable | Acceptance gate |
|---|---|---|
| 0. Feasibility | Document one known-good login/world/quest flow and required assets; choose a supported fixture/quest. | Required messages, states, scene responses, and provisioning needs are identified, with unknowns listed. |
| 1. Vertical slice | One bot: HTTP login → lobby selection → zone/chat → world ready → idle → logout. | Repeated isolated runs show received readiness, healthy keepalives, bounded completion, and clean teardown. Invalid credentials produce an expected login failure without proceeding. |
| 2. Movement | Second observer bot and a curated route. | Observer sees spawn and movement within defined tolerances; logout/despawn is observed. Route progress is not inferred only from sent coordinates. |
| 3. One quest | Explicit scene driver, accept/cancel paths where supported, turn-in, reward assertions. | Expected quest transitions/rewards are observed, and completion/rewards survive restart. No privileged shortcuts during the journey. |
| 4. Regression suite | More implemented quests, one zone transition, selected combat/inventory/social actions, CI reports. | Tests are independent; capability coverage and failures are reported accurately. |
| 5. Exploration | Seeded supported-action policies and trace replay at the semantic action level. | A failure yields a readable, rerunnable action trace with the original observation and versions preserved. |
| 6. Soak/load | Bounded populations executing realistic workflows. | Report action success/latency, disconnects, server resources, cleanup behavior, and load-generator utilization; no unexplained session accumulation. |

Do not commit to “all quests” during stage 0. Audit which selected content is actually implemented and which client-side behaviors are required. Scene support and usable content/navigation data are likely the largest uncertainties, not sockets or the choice of scripting language.

## CI and artifacts

Suggested tiers:

- Public/unprovisioned CI: build, schema/layout tests, client state-machine tests with synthetic observations, and asset-independent tests.
- Provisioned trusted CI: isolated login/movement/quest smoke and regression suites using locally available matching assets.
- Scheduled runs: longer scenario matrix, exploratory tests, and controlled soak/load runs.
- Manual/scheduled real-client checks: compatibility and presentation-sensitive behaviors that a headless model cannot validate.

Do not run untrusted PR code on an asset-provisioned privileged runner without isolation and approval controls.

For each failure retain:

- Run/scenario/bot identifiers and version manifest.
- Expected condition, actual state, failed action, and timing.
- Ordered semantic actions and a bounded decoded packet/event journal.
- Correlated API/lobby/world logs, worker logs, and crash artifacts where available.
- Relevant fixture and persistence snapshots, with credentials/session data redacted.
- JUnit XML plus a concise readable summary.

Use bounded logs/ring buffers for soak tests; measure client-worker saturation so bot CPU or tracing overhead is not mistaken for server performance. Report scenario/transition coverage separately from concurrency and packet counts.

## Proposed layout

```text
src/test_client/             # C++ worker, protocol adapters, client state/actions
  protocol/
  session/
  state/
  actions/
  scenes/
  navigation/
tests/e2e/                  # Python runner and authored scenarios
  scenarios/
  fixtures/
  routes/
  scene_catalog/
  support/
tests/protocol/             # Wire/layout and client-state tests
```

Keep server gameplay scripts in `src/scripts/`; do not mix bot scenarios into native world modules.

## Decisions originally identified before implementation

1. Are headless server E2E tests the primary target, with real-client/UI automation as a separate lane?
2. Is Python acceptable for scenario authoring, or should the initial runner stay entirely in C++?
3. Which exact client/platform and asset version should the first profile target?
4. Which starting territory and implemented quest should be the first supported journey?
5. Will full E2E run locally first, or is a suitably provisioned CI machine already available?
6. Is the near-term priority regression confidence, long-running simulation, or load testing? The first three stages are common, but later priorities differ.

Historical recommended next action: approve the external-client architecture,
then do the single-bot login/world-ready feasibility slice before committing to
general navigation or quest automation. That vertical slice and substantial
additional coverage now exist. Current remaining work is tracked in
[`e2e-current-direction.md`](e2e-current-direction.md), not by completing every
stage in this roadmap.

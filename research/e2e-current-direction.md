# Current E2E direction: development bots on the existing local stack

Status: **current product direction and completion boundary**.

This document supersedes the rollout and completion scope in
[`autonomous-testing-plan.md`](autonomous-testing-plan.md) and the historical
all-lanes audit in
[`e2e-implementation-status.md`](e2e-implementation-status.md). Those documents
remain useful design history and evidence inventories, but their isolated fixture,
hosted CI, platform, soak, exhaustive gameplay, and graphical-acceptance items are
not blockers for the current deliverable.

## Objective

Provide a practical local development tool that runs dedicated, ordinary non-GM
bots against the Sapphire services the developer already has running.

A successful development run must:

1. leave the existing MariaDB, API, lobby, and world processes under the
   developer's control;
2. authenticate through the normal HTTP API, encrypted lobby, zone, and chat
   connections;
3. use dedicated non-GM bot accounts and characters, separate from the
   developer's graphical character;
4. perform a small repeatable scenario using normal client operations and verify
   results from received state or an independent bot;
5. let the developer remain logged in with the graphical client and see the bots
   naturally in the same world;
6. expose each bot's identity, connection/state, current action, and latest result
   in the existing server ImGui administration interface; and
7. provide straightforward start, stop, and status workflows plus private,
   useful diagnostics.

The default tool must not start, stop, restart, replace, migrate, reset, or
reprovision the existing server stack. Any future administrative preparation must
remain a separate, explicit operation.

## Required evidence boundary

The development tool is complete when one bounded run against the already-running
local stack demonstrates all of the following:

- two dedicated non-GM bots complete genuine HTTP, encrypted lobby, and world
  login;
- the bots and the separately controlled graphical character are concurrently
  present in the intended public territory;
- the graphical player can see the bots' ordinary spawn, movement, and Say
  behavior;
- an independent bot receives the required movement and Say observations;
- the ImGui administration interface identifies the same bots and shows live
  state, the current or most recent action, and a terminal pass/fail/stop result;
- operator start, status, and stop commands affect only the owned bot worker and
  coordinator, never the existing database or server processes;
- normal completion observes worker exit and bot logout/despawn; uncertain or
  failed mutations are not retried; and
- the run retains a bounded private summary and worker action/event journals with
  no credentials or sessions in tracked files.

This is development feedback, not a claim that every Sapphire feature, platform,
or client presentation path is correct.

## Existing foundation

The implementation already provides most protocol and scenario machinery needed
for this narrower product:

- `src/test_client/` is an external C++ worker using normal HTTP/lobby/world
  sessions rather than server handlers or an embedded privileged bot.
- `tests/e2e/run_development.py` already attaches two dedicated accounts to an
  already-running loopback stack and explicitly does not manage that stack's
  lifecycle or database.
- The shared runner already has received-state checks for identity, world
  readiness, bidirectional Say, independent movement, normal logout/despawn, and
  optional reconnect, inventory, party, Tell, Sprint, and equipment checks.
- Worker actions and received events are retained in bounded private journals,
  and exact-owned worker exit/account lease handling already fails closed.
- The existing server ImGui application has server controls, logs, a logged-in
  player table, and player details including territory, connection duration,
  position, vitals, class, and level.
- Historical isolated and shared live runs demonstrate that the protocol worker
  can perform substantial normal gameplay. They are useful regression history,
  but do not by themselves prove the operator workflow defined here.

## Gap assessment

### P0 — required for this deliverable

1. **Define the development-bot runtime status contract.**
   Add one bounded, credential-free status representation shared by the
   coordinator and ImGui UI. At minimum it needs run ID, worker ownership,
   bot role/name and received character/entity IDs, lifecycle state, current
   action, last completed action, result, sanitized failure stage, and update
   time. Writes must be atomic enough that the UI never treats a partial file as
   valid. Credential profiles and raw sessions remain private and separate.

2. **Add practical bot lifecycle commands.**
   The current runner is a foreground one-shot command. Add a small operator
   entry point with `start`, `status`, and `stop` behavior (or equivalently clear
   subcommands). It must own only its coordinator/worker generation, reject a
   duplicate active run, use cooperative stop followed by observed owned-process
   exit, and never signal the server or database. An uncertain mutation remains a
   failure and is not automatically replayed.

3. **Integrate bot status into the existing ImGui administrator.**
   The current `Players` table displays generic server session data but cannot
   distinguish development bots or show their external scenario state. Add a
   development-bot panel or clearly marked columns that consume the sanitized
   runtime status and correlate it with live server sessions. Show offline,
   connecting, world-ready, acting, stopping, passed, and failed states without
   presenting coordinator intent as server-observed truth. Preserve the existing
   player view and server controls.

4. **Choose a small default visible scenario.**
   Reuse the established two-bot shared-development path: login, mutual presence,
   unique Say exchange, short observed out-and-back movement, then either hold for
   operator viewing or stop/logout. Optional party, inventory, combat, quest, and
   reconnect checks stay selectable; they are not prerequisites for the default
   workflow.

5. **Support the developer's separate graphical character without controlling it.**
   The tool may accept the graphical character name for received co-presence
   correlation, but must not authenticate that account, launch or automate the
   client, or require a disposable viewer. Human visual confirmation is a useful
   development observation; independent bot receipts remain the automated network
   assertion.

6. **Run focused verification.**
   Add unit/controller contracts for status parsing, atomic publication, stale or
   malformed status, duplicate starts, cooperative stop, exact worker ownership,
   redaction, and UI-facing state mapping. Then perform one bounded live run using
   approved existing bot accounts and actual local endpoints while the graphical
   character stays logged in. Record what was automated and what the developer
   visually observed.

7. **Simplify operator documentation.**
   Put the existing-stack workflow first. Document profile creation, build/run,
   start/status/stop, artifact locations, expected ImGui states, and failure
   recovery without leading with disposable-host, Sandbox, CI, or reset policy.

### Inputs that must be inspected or supplied, not guessed

- actual loopback API and lobby endpoints;
- the matching built worker path;
- approved dedicated bot account and character identities;
- the intended public territory and a compatible short route;
- the graphical character name if co-presence correlation is enabled; and
- how the currently used ImGui world-server executable is launched and where it
  may safely read the sanitized bot-status file.

A missing input should stop preflight before authentication. It is not a reason to
start a replacement stack or create accounts automatically.

### Optional later work — not a completion blocker

- disposable MariaDB/API/lobby/world environments or Docker orchestration;
- the combined isolated acceptance gate;
- destructive fixture reset or account reprovisioning;
- hosted/private CI execution and runner-group enforcement;
- Linux/macOS/platform sweeps;
- higher-population or overnight soak/load testing;
- exhaustive quest, scene, inventory, combat, social, economy, creation, and
  navigation breadth;
- graphical-client automation, Sandbox disposal, screenshot gates, or a normalized
  matching-client trace corpus; and
- general-purpose administrative placement.

These lanes may remain in the repository and can be run when explicitly desired.
They must not be used to redefine the simpler development-bot product as
incomplete.

## Safety and scope rules retained

- Bots remain external normal clients and non-GM.
- Commands sent, acknowledgements, handler calls, packet injection, grants,
  resets, and local publication are not gameplay success evidence.
- Movement and Say success require advancing received observations.
- Never retry an account or gameplay mutation whose outcome is uncertain.
- Exact-owned coordinator/worker teardown is distinct from server logout,
  despawn, offline exclusion, or database safety.
- Do not modify or recycle the developer's graphical account.
- Keep credentials, private profiles, generated assets, journals, status runtime,
  and screenshots untracked.
- Existing server/database lifecycle remains outside the bot tool's ownership.

## Completion statement

The broad historical testing program is intentionally not being completed as one
monolithic acceptance project. The current deliverable is much smaller and is
**not yet complete**: the normal shared-development runner exists, but practical
owned start/status/stop control and coordinator-to-ImGui bot action/result
visibility still need implementation and one current bounded live demonstration.

# Shared-development reset/reprovision boundary

Status: **not implemented; no destructive live probe performed**. This is a
functional suitability review for the E2E lane, not a general security verdict.
Registered placement is supported separately; it is not a general reset.

## Inspected source and missing prerequisites

| Candidate | Inspected source | Why it is not the shared reset contract |
| --- | --- | --- |
| Normal lobby character deletion | `src/lobby/GameConnection.cpp`, `CHARAOPE_DELETECHARA`; `src/api/main.cpp`, `deleteCharacter`; `src/api/SapphireApi.cpp`, `SapphireApi::deleteCharacter` | The inspected path resolves account characters and removes persistent records. It does not establish the development registry/generation, a world-cache quiescence handshake, or a fence preventing a concurrent world login throughout reset. Do not wrap it as a shared-world reprovision command. Existing isolated deletion evidence remains narrowly scoped. |
| Logout followed by DB edits | `src/world/Session.cpp`, `Session::close` | Player persistence/unload precedes observable transport closure. This supports existing fresh-login checks, but a historical closure is not an exclusive lock preventing another login. Local Python account leases cover cooperating processes only. |
| BNPC owner field as test ownership | `src/world/Actor/BNpc.cpp`, `onActionHostile`, hate-list removal, `onDeath`, `setOwner`; `src/world/AI/Fsm/StateRetreat.cpp` | Owner is acquired through hostile interaction, can transfer with hate-list changes and is cleared on death/retreat. It is not an administrative fixture-creation identity or stable permission to reset a shared enemy. |
| Existing registered placement | `src/world/Manager/DevelopmentBotPlacement.h`; `DebugCommandMgr::developmentBot` | Default-disabled, exact registered character/entity/name binding and live world-thread state checks support the existing placement operation. They do not authorize account deletion, arbitrary quest/inventory restoration, or enemy reset. |

These observations do not assert that every possible reset-related source path
has been inspected. They identify why the tempting existing primitives above
are insufficient for this lane. No public/server semantics were changed.

## Required before an in-place reset implementation

1. Explicit development-only registration and operator approval of exact accounts,
   character IDs or separately created world actors. Never infer test ownership
   from a name prefix, proximity, current combat ownership or a previous report.
2. Enforced exclusion spanning the whole operation: reject active/pending sessions
   for offline character work and prevent new entry until completion, or use an
   explicitly appropriate safe world-thread operation. A snapshot followed by a
   later mutation is not a fence. No DB mutation beneath cached live characters.
3. A defined, source-supported reset scope and partial-outcome handling. Do not
   delete/recreate unrelated state, silently adopt other actors, or retry after an
   uncertain mutation. Preserve intent, identities, outcome and operator recovery
   information; do not claim crash consistency from an in-memory ledger.
4. Independently received postconditions using ordinary non-GM sessions, with
   reset/grants/teleport recorded only as administrative setup. Keep the separate
   viewer outside all reset targets and credentials.
5. Negative lifecycle/ownership contracts and an owned bounded live check before
   offering the operation against an existing shared deployment.

Until that coordination exists, use new dedicated provisioning or approved
registered placement where appropriate. Neither substitutes for this pending
in-place reprovision/reset requirement. Do not stop a shared world with a human
viewer merely to make a test pass.

## Owned-world-actor lifecycle follow-up (committed source, no live reset)

Reviewed revision: `2a6d05b95c53c4fb7c8e5fffefa443ef903ada6f`. The 13 exact
committed source files and their hashes are retained in
`.e2e-artifacts/owned-actor-reset-review-001/inputs.json` (manifest SHA-256
`aec2de5ab2e7b66c8d2227240fa4956578845f3565790093fdfdebe976cc86f5`).
Working-tree scheduler/navigation experiments are excluded. This is a functional
suitability/design review, **not** a vulnerability verdict, binary audit, runtime
reproduction, proof of exhaustive task coverage or an implemented reset feature.

| Surface | Inspected behavior | Reset design consequence |
| --- | --- | --- |
| `Territory::createBNpcFromLayoutId` / `createBNpcFromLayoutIdNoPush` | Resolve an existing layout, allocate a runtime actor ID, construct/init a BNPC and set a trigger owner; one variant also publishes it | There is a source-supported construction path. Neither variant establishes dedicated-test registration, approval/generation ownership or a complete administrative creation transaction. Trigger owner is not test authority. |
| `Territory::updateSpawnPoints` | Natural population entries retain their own actor pointer and death time and can create later actors | Never adopt/reset a natural spawn entry as a fixture or assume a layout ID identifies one actor lifetime. A dedicated creation registry must remain distinct from natural population ownership. |
| `BNpc::init` / `initFsm` | Recalculate/fill HP and construct an FSM | Initialization is not a documented reset transaction. It does not coordinate task retirement, pending rewards or admission of other actions. Do not expose `init()` as a reset command. |
| `BNpc::hateListAddDelayed` → `DelayedEmnityTask` | Queue work that retains the BNPC and another character and later adds hostility | Empty current hate state alone does not prove actor quiescence. Previously queued work must be accounted for by actor lifetime, not guessed from a current combat snapshot. |
| `BNpc::onDeath` → `FadeBNpcTask` / `RemoveBNpcTask` | Queue delayed work retaining that BNPC; callbacks resolve its territory and use the retained actor | Actor retirement/replacement needs an explicit lifetime rule for old callbacks. An immediate world-thread operation does not by itself exclude future queued work. No repeated-removal behavior was exercised in this review. |
| `BNpc::onDeath` → `LootBNpcTask` | Delayed reward retains a player ID and loot-table name, not source BNPC/generation | Pending reward provenance cannot be recovered from this task's exposed fields. A reset must not cancel or relabel unrelated/player-earned rewards, nor claim no pending owned reward work without additional source binding. |
| `Task` / `TaskMgr` | Task interface exposes timing, queue/execute and description; manager has deferred/active collections with enqueue/update, no actor-scoped cancellation/quiescence contract | A fence must cover deferred and active work and execution-time lifetime validation. Parsing `toString()` or sleeping for a known delay is not ownership/exclusion. |
| `Chara::processActions` | Current action is retained and updated; interruption can span further ticks | A task-queue check alone would not cover current actions, statuses, AI or other callback sources. Those need an explicit supported reset boundary, not a blanket quiescence claim. |
| `StateRetreat` | Natural movement/healing and owner clearing are gameplay behavior | Leave this behavior intact. Natural retreat is neither administrative ownership registration nor authorization to force a shared enemy's reset. |

### Smallest defensible implementation sequence

This is a proposed sequence, **not** a claim that its invariants already hold:

1. Define a bounded, default-disabled dedicated-actor creation contract before
   adding a reset opcode/GM command. Bind explicit approval, owning test run,
   exact territory instance, runtime entity, source layout/catalog and actor
   lifetime/generation. Record intent before mutation and uncertain outcomes.
   Register only newly created fixture actors; no name/layout/proximity adoption.
   Keep the registry independent of combat owner and natural spawn entries.
2. Implement lifetime-scoped work accounting and retirement on the world thread.
   Preserve the normal task path when development ownership is absent. Include
   deferred and active tasks, current actions and relevant AI/status callbacks;
   retain provenance for delayed rewards. A generation token alone is not proof
   that every producer/consumer participates. Reject reset until all required
   work is classified and the relevant lifecycle fence actually holds.
3. Choose and document one reset semantic: in-place restoration **or** retirement
   and creation of a new lifetime. Do not silently substitute one for the other.
   Specify HP/state/location, rewards, navigation membership and replication;
   define bounded cleanup and partial-outcome handling without implicit retry.
   Never roll back or discard already-earned player rewards as fixture cleanup.
4. Add negative contracts for unknown/foreign/natural actors, reused IDs with
   wrong generations, changed territory, pending/unclassified work, delayed
   callbacks after retirement, interrupted actions, unrelated player rewards,
   concurrent admission and failed/uncertain publication. No native unit test
   alone establishes whole-world exclusion or crash consistency.
5. Only after those contracts and integration exist, execute one approved owned
   private fixture reset with normal non-GM pre/post observations and a separate
   unchanged viewer. Verify exact old/new actor identities and delayed-work
   disposition, preserve administrative logs, then keep existing-shared-world
   deployment a separate opt-in. Reset/spawn placement is never normal progression.

**Current stop boundary:** no destructive reset or new administrative creation
command is offered. The next required artifact is the integrated, tested
creation-ownership and actor-lifetime work fence above—not another credential
profile, a larger timeout or a guessed endpoint. Existing approved private assets
remain available for later bounded verification; they do not supply the missing
server lifecycle semantics. Offline character reprovisioning still separately
requires coordinated session exclusion across its entire mutation.

## Receipt association is a smaller prerequisite, not reset authority

`support/development_binding.py` binds a completed provisioning report to its
configured API/lobby endpoint, optional managed-host session, ordered account
names and received character/entity IDs. The placement planner rejects missing,
mismatched or legacy bindings; it does not manufacture an association for old
reports. Passwords, authentication tokens and server secrets are not hashed or emitted by this
helper. Worker/catalog changes and password rotation do not select another
account; those inputs retain their independent checks.

This digest detects accidental mixed artifacts. It is not a signature, current
authentication, deployed-server fingerprint, offline proof, cross-host lease or
permission to reset. Someone who can edit both inputs can recompute it. Operator
review and independently guarded server behavior remain mandatory. Historical
reports are preserved without retroactive approval claims.

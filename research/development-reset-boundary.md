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

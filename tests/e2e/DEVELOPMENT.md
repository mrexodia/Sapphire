# Fast shared-server development lane

This lane connects two normal non-GM bots to an **already-running local development
server**. The runner does not create a disposable environment, install/migrate a
database, change server/client configuration, restart a process, or issue
administrative resets. Separate opt-in GM fixture placement is described below.
Results are explicitly `shared-development-not-acceptance` evidence.

A clean-source **owned warm-world rehearsal** has passed twice against the same
server processes and accounts: **27.3s and 24.0s** for observed movement, party
invite/chat/disband and fresh-login position verification. Setup was paid once
(28.6s). This is a short development check, not equivalent coverage of the
55-minute acceptance suite. It used pre-connection fixtures in a private database;
normal provisioning, GM placement and an actual graphical viewer were not tested.
See `research/e2e-implementation-status.md` for artifacts, hashes and limits.

Use this lane for short development feedback and watching bots from a graphical
client. Keep the existing isolated pytest lane for clean regression/acceptance;
do not point its `Environment` fixture at a shared database. No full acceptance
run is required to use this lane.

## Keep one owned warm world available for repeated runs

When no existing development server is available, start a **bounded, disposable
warm host** once. It uses the existing isolated-environment asset/binary profile,
but does not restart or recreate fixtures between external development checks:

```powershell
python -m tests.e2e.serve_development --profile .e2e-local.json `
  --worker build-e2e-msvc/Release/sapphire_test_client.exe `
  --session-dir .e2e-dev-host/watch-001 --max-seconds 3600
```

Use a rebuilt matching worker: bound-party capabilities and a normal zero exit
from that exact owned preflight process are required **before** starting servers
or preparing fixtures. `status.json` keeps the sanitized
`worker_preflight_exit` receipt; worker construction, unknown/unbound exit or a
nonzero result fails the host and cleans its still-unstarted environment. This is
not server-session evidence because the preflight never authenticates. Keep this
terminal running and wait for its `ready` message. In another terminal:

```powershell
python -m tests.e2e.run_development `
  --profile .e2e-dev-host/watch-001/bot-profile.json `
  --artifacts .e2e-artifacts/watch-check-001 --allow-shared-development `
  --verify-party --verify-reconnect
```

Repeat with a **new artifact directory**, not a new host. Each invocation still
performs genuine fresh authentication, independent observations and normal
logout. This reuses infrastructure and characters, not authenticated sessions.

The private session directory must be new and ignored by Git (or outside this
checkout). It contains:

- `bot-profile.json`: exactly two dedicated bot accounts.
- `viewer-profile.json`: a **third, separate non-GM account/character**, plus
  local API/lobby context for an operator's matching graphical client.
  Its `account` object contains credentials; do not paste it into chat or logs.
- `server-profile.json`: endpoints/worker/catalog for normal dedicated
  provisioning. This does not attest that GM placement is deployed.
- `status.json`: identity, expiry, process IDs, lifecycle/timing and cleanup
  diagnostics, without account credentials.
- `process-lifecycle.json`: terminal private exact database/API/lobby/world
  generation/teardown rows, created only after owned cleanup.

Live narrow evidence: one managed-host development check passed in **25.4s**,
and separate normal provisioning completed in **12.0s**, with a third headless
client receiving the bots' unique Say/reconnect messages. This is not graphical
viewer evidence. The one-off diagnostic wrapper's later status-label error and
unexecuted post-provision viewer assertions remain explicitly recorded in the
audit; they are not relabelled as a passing aggregate run.

The viewer is a new ephemeral fixture, **not your existing character**. No client
is launched, no installed client/settings are changed, and graphical
compatibility is not inferred from headless results. A matching client must be
connected separately through the ordinary real-client lane. An already-running
server with your existing character still uses the external profile lane below.

Stop only after clients/checks are finished:

```powershell
New-Item .e2e-dev-host/watch-001/stop -ItemType File
```

POSIX equivalent: `touch .e2e-dev-host/watch-001/stop`. After a normal terminal
`stopped` status, inspect the immutable private cleanup evidence read-only:

```powershell
python -m tests.e2e.inspect_development_host `
  --session-dir .e2e-dev-host/watch-001
```

Acceptance requires the exact four database/API/lobby/world generation/PID starts,
running-before-cleanup and terminate-request receipts, observed integer return
codes, exact status/file digest equality, removed private profiles, and the seven
ordered successful host phases. Any recursively discovered, case-variant terminal
`cleanup-failure.json` marker rejects host and composite managed-run success even
when the lifecycle itself is complete. The inspector follows the terminal status's
absolute, separate original `Environment` artifact directory, rejects aliases to the
session tree, requires its lifecycle object to equal the retained session copy, and
recomputes the producer-recorded bounded complete artifact-tree SHA-256. That tree
identity is also returned by the composite managed-run/provisioning inspectors;
checking only the copied lifecycle is insufficient. This proves exact owned-process teardown only,
not graceful server shutdown, account offline exclusion, cache quiescence, reset
authority or cleanup of an already-running external shared server. To correlate one
passing managed check with that exact terminal host, also run:

```powershell
python -m tests.e2e.inspect_managed_development_run `
  --session-dir .e2e-dev-host/watch-001 `
  --summary .e2e-artifacts/watch-check-001/development-summary.json
```

The composite inspector binds the run's exact start/end host identity, bounded
success deadline, normal worker exit and clear leases to the same terminal
session/service lifecycle. It also strictly revalidates every requested structured
movement/social/persistence receipt and requires every unrequested check to remain
explicitly false. These retained received-state records are not rendering,
server-side offline/reset authority, or acceptance proof.

The host also shuts down on process loss, interruption, or expiry (60–14400 seconds **after readiness**).
Expiry is a hard lifetime bound and may interrupt connected clients; it is not
an automatic drain or retry. Do not start a long check near expiry.

Only its own private database/processes/runtime are removed. A stopped success
requires `cleanup_verified=true` and `process_cleanup_verified=true`; a lifecycle
mismatch or missing exact generation changes terminal status to failed. Unmodified exported
profiles are deleted on shutdown; user-modified or incomplete exports are retained
and explicitly reported. No existing database is accessed. Preparation uses
three **administrative pre-connection fixtures** at the source-supported public
route start, not normal lobby creation, progression, or GM-placement evidence.
No live cached character rows are edited, and no runtime reset is offered.

Exported profiles bind the exact host session, owner PID **and creation time**,
expiry, endpoints, worker hash and successful exact-owned preflight-worker exit.
Runners/provisioners reject stopped, expired, orphaned, legacy-without-exit-proof
or mismatched bindings **before authentication**, and HTTP operations recheck
them. Managed runs now retain sanitized start and completion receipts containing
the exact session/status hash, owner identity, deadline, endpoints, worker hash and
preflight-worker PID. Success requires typed equality at completion before lease
release; a stopped/replaced/changed host fails and retains recovery leases (and
provisioned credentials) rather than claiming a completed run. External profiles
retain an explicit `external-shared-server-without-owned-host-binding` boundary and
make no equivalent ownership claim. These are cooperating local-process checks, not server-side locks,
authentication, cross-host exclusion, or atomic protection against process loss
mid-operation. Coordinator hard-kill cleanup remains unverified; retained
private runtimes/leases need manual ownership verification, never lease stealing.

Raw running-server logs remain private. Cleanup redacts registered secrets and
known lobby session-log fields, including independently authenticated viewers'
sessions. This is not a universal sanitizer for arbitrary plugins. Windows
profile/directory ACLs are inherited; choose a suitably private parent directory.

## Prepare once (existing external server)

1. Use matching Sapphire 3.3 server/client data and a built headless worker.
2. Prepare **two dedicated bot accounts**, with usernames beginning `e2e_`, and
   one existing non-GM character per account. Do not use your own player account.
   Use the new-account provisioning command below, or existing development setup
   tools. Server-side online-state exclusion is not implemented by this runner.
3. Put both characters in the same supported public territory (130, 131, 140 or
   141), near enough to receive each other's spawn and Say. Complete/exit opening
   scenes first. Leave them offline before starting the runner. Do not log these
   accounts in manually while leased.
4. Copy `tests/e2e/development.profile.example.json` to `.e2e-dev.json` and set
   the actual API/lobby ports, worker path and bot credentials. The example ports
   are placeholders, not discovered configuration. The HTTP API and returned
   lobby endpoint must both use **127.0.0.1**. No DNS, proxy or HTTP redirect is used.
5. Keep the credential profile and artifacts private and untracked. The runner
   never copies the profile or HTTP responses into its summary. Worker journals
   contain received actors/chat, so do not publish them indiscriminately.

## Provision new dedicated accounts and characters

Create a private `.e2e-dev-server.json` containing the example profile's server
fields (`version`, `mode`, `protocol`, `worker`, `api_port`, `lobby_port`,
`territory`, optionally `quest_catalog`), **without `accounts`**. Then run:

```powershell
python -m tests.e2e.provision_development --server-profile .e2e-dev-server.json `
  --create-new-bot-accounts --output-profile .e2e-dev.json `
  --artifacts .e2e-artifacts/dev-provision-001 --max-seconds 300
```

This explicitly creates **two NEW accounts and Gladiator characters** through
normal HTTP `createAccount`, separate HTTP login, and encrypted lobby creation.
It never adopts an existing username or uses the server secret/DB/API fixture
`createCharacter`. Each character must appear in the refreshed lobby list and
enter the world as non-GM; normal logout/server connection closure follows.
No normal gameplay/progression coverage is claimed for this setup command.

The output credential file is created exclusively and flushed **before any
network mutations**. It must not exist, its parent directory must exist, and it
must be outside the diagnostic artifact directory. Inside the checkout it must
be git-ignored. On POSIX it is created with mode 0600; on Windows use a private
directory with appropriate inherited ACLs. It contains generated passwords: do
not commit, paste or publish it. The artifact directory must also be new.

`provisioning-summary.json` records creation request/receipt, separate successful
login, refreshed-lobby/world confirmation and logout stages. Successful setup has
status **`provisioned`** (CLI exit zero), not gameplay status `passed`. It also
requires a normal zero exit from the exact owned native worker before releasing
account leases and emits the same sanitized `worker_exit` receipt as the shared
runner. Its exact `worker/` directory contains a run-bound non-secret ownership
record and a bounded complete-tree SHA-256 covering all retained journals; managed
provisioning inspection recomputes both ownership and bytes. Nonzero, unknown,
unbound or constructor-failed exits retain leases and
cannot produce a provisioning association. The placement planner rejects legacy
or malformed provisioning reports without that receipt and the exact versioned
`clear` terminal lease snapshot.

The CLI's single cooperative provisioning budget is `--max-seconds 1..900`
(default 300). It starts before local profile/managed-host validation and spans
exclusive credential reservation, lease acquisition, worker startup, both
sequential HTTP/lobby/world/logout flows and exact worker teardown. Native RPC and
wait limits are capped to the remaining scaled budget. This is not hard preemption:
an already-started file, bounded HTTP, worker-construction or cleanup operation may
finish after expiry, but its late result cannot produce `provisioned`. Final lease
release and summary publication are cleanup outside the success budget. The summary's
`run_deadline` distinguishes expiration and in-budget session completion from the
overall status.

A current-code positive check on a fresh owned disposable runtime completed both
normal GM0 account/character journeys in **11.453s** under `--max-seconds 30`,
including both server logout observations, exact worker exit, lease release and the
strict `clear` snapshot. The current offline planner accepted that exact receipt and
wrote a reviewed private registry; **no placement command executed**. This is
bounded provisioning/lifecycle/receipt-consumer evidence, not gameplay, existing-
database safety or reset authority. Live expiry was deliberately not induced;
uncertain creation recovery remains covered by synthetic fail-closed contracts.

A separate fresh owned-runtime check carried the same current strict receipt chain
through actual registered placement. Each exact slot was published once by a
separate GM operator; both ordinary GM0 clients independently received territory
182→130 at the reviewed position, then completed bounded party and fresh-login
checks. The current registry-v2 rerun additionally retained one exact provisioning
run identity through the reviewed registry, both immutable pre-dispatch intents
and exactly two matching server diagnostics. Provisioning, runner and operator
workers all had exact exit-0 receipts; both account-using terminal lease snapshots
were `clear`. This remains administrative setup—not natural travel/progression,
existing-shared-database safety, reset authority, or graphical-client evidence.

Errors and deadline expiry preserve the credential file and, once acquired, local
leases; inspect partial results instead of retrying creation or deleting characters
automatically. To record the two exact local lease files without changing them:

```powershell
python -m tests.e2e.inspect_development_leases --profile .e2e-dev.json `
  --artifacts .e2e-artifacts/dev-lease-inspection-001
```

The read-only result is `clear`, `retained` (both valid receipts name one run), or
`ambiguous` (partial, malformed, unreadable, changed or mixed state). Ambiguous
state exits nonzero. It inspects no unrelated directory entries and emits no account
values, lease hashes or paths. It never removes a lease, contacts a server/database,
checks active sessions or authorizes account reuse/reset. Even `clear` is only a
local cooperating-runner snapshot, not server-side offline proof. Independently
verify both bots offline before any narrowly reviewed manual recovery; never steal
a lease to make another run pass.

The shared runner and provisioner also attach this snapshot to every terminal
summary. Reinspect retained provisioning against an already-running external server
without contacting that server:

```powershell
python -m tests.e2e.inspect_development_provisioning `
  --summary .e2e-artifacts/dev-provision-001/provisioning-summary.json `
  --profile .e2e-dev.json
```

This sanitized, read-only consumer requires the explicitly unmanaged boundary,
private-profile association, bounded deadline, two distinct GM0 received identities
in supported opening/public territory 182 or 130, fresh HTTP/lobby/world outcomes,
both server-close receipts, normal exact worker exit, complete run-owned worker tree
and clear local leases. It does not prove server identity, offline exclusion,
placement/readiness, gameplay, reset safety or permission to retry creation.

For provisioning performed against an owned managed host, stop that host normally
and instead correlate the private profile, received account/character outcomes and
exact terminal teardown:

```powershell
python -m tests.e2e.inspect_managed_development_provisioning `
  --session-dir .e2e-dev-host/watch-001 `
  --summary .e2e-artifacts/dev-provision-001/provisioning-summary.json `
  --profile .e2e-dev.json
```

The inspector emits no usernames or passwords. It requires the exact managed-host
start/end identity, bounded deadline, two distinct GM0 received identities, fresh
HTTP/lobby/world outcomes, both server-close receipts, provisioning association,
normal worker exit, exact run-bound worker artifact tree, clear leases and terminal
four-service teardown. This is
retained setup/lifecycle correlation, not gameplay, offline/reset authority or
permission to retry uncertain creation.

A successful result requires `state: clear` after release. An acquired
failed run normally records `state: retained`, with both receipts matching its
`run_id`. Partial release, replacement races, malformed files or unavailable
inspection remain failures and are never repaired automatically; provisioning
removes its otherwise-complete association rather than publishing a reusable
fixture receipt without verified lease release.

Expiry before lease acquisition leaves no lease to retain. A late account-creation
response remains `requested_outcome_unknown`, is never retried, and cannot advance
to login/character creation. Native worker exit remains distinct from each recorded
normal server logout and is not proof of offline exclusion or permission to
reuse/reset characters. No old character/account is modified, reset or removed.
Account creation is sequential, not a claim of multi-process allocation safety.
Interrupted/hard-killed runs may lack a complete summary; retained credentials/
leases do not prove crash consistency.

**Provisioned is not public-world ready.** Fresh characters normally enter the
opening territory. This command does not skip openings, teleport, grant levels,
reset quests, or assert that the shared smoke preconditions hold. Its summary
always says `ready_for_shared_checks: false`. Complete the opening or explicitly
prepare public-world fixtures with your development tools before running the
shared checks. The opt-in placement lane below can prepare the registered bots
without stopping the world. General reprovisioning/reset is still pending.

## Targeted administrative placement (opt-in; narrow owned-runtime verification)

The server now implements a **disabled-by-default**, GM-only `!devbot place`
command. This is administrative fixture setup, not gameplay. It only places one
of two explicitly registered generated bots into public Ul'dah (130) at the first
point of the validated Motivational Speaking corridor and sets OpeningSequence=2.
It does not grant items/levels/quest completion or reset enemies/other players.

1. Use a provisioning report from the current provisioner, which records exact
   received lobby character IDs as well as world entity IDs. Legacy reports
   without character IDs fail closed; do not invent IDs or rerun uncertain creation.
2. Add the matching `quest_catalog` path to your private `.e2e-dev.json`.
3. Generate and review a **new** private registry:

   ```powershell
   python -m tests.e2e.prepare_development --profile .e2e-dev.json `
     --provisioning-report .e2e-artifacts/dev-provision-001/provisioning-summary.json `
     --registry .e2e-bot-placement.json --approve-fixture-placement
   ```

   This is an offline planner: it does not contact the server or execute a reset.
   It requires a completed provisioning receipt whose
   `development-provisioning-association-v1` digest matches the configured
   API/lobby endpoint, optional managed-host session, ordered account names and
   received character/entity IDs. Registry schema v2 also retains the exact
   lowercase provisioning `run_id`; legacy v1 registries and reports with a
   missing/malformed run identity fail closed. Mixed-profile, edited-identity and
   legacy receipts without this binding or without exact `clear` terminal lease
   evidence are rejected; do not synthesize approval for old reports. Passwords,
   authentication sessions and server secrets are excluded. Worker and
   catalog changes/password rotation do not select another account and retain
   their separate validation. This is accidental-artifact association, **not** a
   signature, current authentication, server fingerprint, offline proof or lock.
   Check the provisioning run ID, both names, entity IDs, character IDs, catalog
   hash and position. The
   registry is an operator-controlled allowlist, **not a cryptographic attestation**;
   protect it against untrusted edits. Before writing an irreversible intent or
   dispatching a command, the Python operator helper mirrors the server's exact v2
   top-level fields, catalog/run/approval formats, finite bounded destination and
   exact two bot bindings; malformed, missing or extra fields fail without
   publication. The server independently checks the same schema/bounds and live
   identities, not navigation provenance. The planner binds the source route.
4. In a development server built with this feature, explicitly configure:

   ```ini
   [DevelopmentBots]
   Enabled = true
   RegistryPath = C:/private/.e2e-bot-placement.json
   ```

   Use an absolute path. Configuration is loaded at startup; arrange that one-time
   restart yourself if necessary. The harness does not edit/restart your server.
   The registry file is read on each command. Default configuration stays disabled.
5. Log your separate GM operator/viewer character in and start:

   ```powershell
   python -m tests.e2e.run_development --profile .e2e-dev.json `
     --allow-shared-development --await-placement `
     --placement-registry .e2e-bot-placement.json --cycles 1 `
     --artifacts .e2e-artifacts/dev-prepare-001
   ```

   Once `placement-ready.json` appears in that artifact directory, both bot
   sessions are logged in and idle. Check their identities against the registry.
   The runner allows **120 seconds total** for the separate administrative action.
6. From the GM operator's normal chat input, issue the two exact commands printed
   by the registry planner: `!devbot place <approval_id> 0` and
   `!devbot place <approval_id> 1`. Do not give GM rank to the bots. A non-GM viewer
   can watch; a separate GM operator must perform the placement in that case.

The server checks exact character/entity/name bindings, non-GM bot state, a valid
connected/loading-complete session, alive/not busy, no party, and source territory
182 or 130. It rejects self-targeting and targets outside the registry. Commands
execute through the existing world-thread input queue. The warp uses the existing
WarpMgr path, with BetweenAreas set immediately to prevent overlapping placement.
An approval/slot is consumed once per server process (maximum 1024 retained keys).
A queued-warp message is **not success or permission to retry**. Server logs record
operator, approval, provisioning run identity, target identities, source and
catalog hash, not credentials.

`--await-placement` and `--placement-registry` must now be selected together.
Before creating artifacts, acquiring leases or logging in, the runner strictly
reads that exact private v2 registry, rejects duplicate keys, and binds its SHA-256,
approval/provisioning IDs, source catalog/route, ordered generated names and exact
character/entity IDs. After login those received identities must still equal the
reviewed targets. `placement-ready.json` carries the same non-secret binding.
This byte hash is not a signature and does not prove the server read unchanged
bytes later; protect the private file and do not replace it during the run.

The runner waits for received public-world readiness and position, then checks
both identities/positions independently before normal Say and per-waypoint
movement checks. It retains each pre-wait territory/sequence and post-wait
identity/position/sequence. A transition from 182 must advance received state; a
bot already at 130 is classified without claiming a new transition.
Administrative waiting is timed and labelled separately. The runner never sends
the debug command itself and does not attest that the command fired: if the bots
already satisfy the destination preconditions, that is not proof of an
administrative mutation. The strict external/managed result inspectors revalidate
this preparation receipt as administrative evidence, never gameplay. By default
this run does not check fresh-login
position persistence. Add `--verify-reconnect` (below) to check received positions
across one fresh authentication without a server restart. Failed/uncertain
placements retain leases for inspection. Do not
regenerate approvals to hide failed outcomes. After server restart the in-memory
one-shot set is lost; this is not crash-consistent/idempotent reset infrastructure.

A clean linked server and separate authorized GM operator were exercised in an
owned private runtime: two normally provisioned non-GM characters received
182 → 130 transitions, then passed independent movement/party/viewer checks and
one fresh-login position check. Placement readiness took 1.125s; the combined
placement/development check took 38.719s. Evidence is recorded in
`research/e2e-implementation-status.md` under registered-bot placement.
This is **not** deployment verification for your existing shared database/server,
real graphical-client evidence, natural opening progression, server-restart
persistence, or general reset/reprovisioning coverage.

### Optional scripted GM operator (administrative setup only)

`support/development_operator.py::request_registered_placement` can dispatch one
reviewed registry slot from an **already-authorized separate GM session**. It does
not authenticate, create/promote an operator, adopt a viewer account, or discover
targets. The caller supplies the reviewed registry, slot 0/1, a private artifact
directory and explicit `approved=True` while the normal bots are waiting in
`--await-placement` mode. A graphical GM can still use the documented commands
instead; this helper is optional.

For scripted preparation, `DevelopmentOperator.login_for_preparation(auth, name,
approved=True)` is the separate GM login API. Do **not** use ordinary
`Bot.login_via_lobby` for an operator: it intentionally rejects GM characters.
The preparation object exposes only that login, exact one-shot viewer-challenge
replies, and logout/close—not movement, combat or inventory actions. It does not
create/promote an account and does not retry an uncertain login. The caller must
already own and authorize the distinct GM account/session.

The distinct worker method `development_place_registered` verifies the exact
received operator character/entity/name, ready stationary public-130 state,
nonzero GM rank, and absence of scene/party/invitation state immediately before
publication on the client Asio thread. It formats only `!devbot place <32 lowercase
hex approval ID> <0|1>`; arbitrary command text/extra arguments are rejected.
Ordinary Say still rejects debug commands and non-GM bots cannot use this method.

A native Bot accepts at most two slots from one approval, consuming each before
transport publication. The Python helper flushes an exclusive intent file before
dispatch; reusing that journal slot fails even after a timeout. These are local
per-Bot/per-journal guards, not durable or cross-host exclusion. The server still
independently validates its disabled-by-default configuration, registry, exact
registered target, live state, and process-local one-shot ledger.

The result is explicitly **local publication only**, with `placement_verified:
false`. Keep intent files and do not retry uncertain requests. Only the normal
runner's independently received positions, identities, gameplay and optional
fresh-login checks can verify the corresponding outcomes. Administrative setup
is never natural progression or normal movement evidence.

### Optional direct Tell check

Add `--verify-tell` to exchange exactly two direct Tells between the dedicated
bots, after optional party disband and before optional reconnect. Each sender and
receiver must remain idle, non-GM and nonparty, with one exact visible peer.
The separate `tell_visible` native method rechecks visibility/name/entity identity
and rejects duplicate players, NPC lookalikes, self/GM targets, transitions,
scenes and membership/invitation state immediately before ordinary publication.
It has no remote-party or offline fallback. Older workers are rejected before
HTTP login. No messages are sent to the viewer.

Each unpredictable message is generated after both baseline snapshots. Received
sender name, entity ID, character ID, nonparty context and a newer received token
must match exactly. There is a ten-second publication/delivery budget per
direction, no mutation retry, and no automatic social cleanup on failure.
The summary records `tell_verification`, both received messages/token ranges and
`tell_visible_bidirectional` timing. This is narrow visible-peer messaging, not
remote/offline Tell coverage or a general social/reset test.

A bounded owned-runtime CLI check verified both exact received Tells in 0.047s
within an 11.906s short check (including normal login/Say/logout). A separate
headless observer received public Say but no test Tell in its recorded lifecycle.
This does not establish graphical-client or general privacy coverage. See the
implementation audit for input hashes, token evidence, cleanup and scope.

## Run a short check

```powershell
python -m tests.e2e.run_development --profile .e2e-dev.json `
  --allow-shared-development --cycles 1 `
  --artifacts .e2e-artifacts/dev-watch-001
```

The artifact directory must be new. There is no account creation, teleport,
inventory mutation, combat, server termination, retry or reset in this command.
Both bots authenticate through HTTP and encrypted lobby, check non-GM/idle/public
state and exact independently received identities/positions, exchange unique Say
messages, and log out. The witness also verifies mover despawn. Cycles are bounded
to 1..10; they repeat successful actions, not failed attempts. Your character may
watch without becoming an assertion dependency. Other players need not disappear
from the world for this lane to pass.

When the profile includes the supported quest catalog, `movement_verification`
records the exact bounded authored prefix, mover/witness entities, speed, starting
witness sequence and every out-and-back target/received position. Success requires
the continuously connected witness's sequence to advance at each independently
received waypoint; stale position caches and movement acknowledgements cannot
qualify. The route remains at most 16 authored points and 5m one-way, with no
teleport, fabricated segment or replan. This is received movement evidence, not
server authority, rendering, general navigation or natural quest progression.

### Cooperative session deadline

The CLI defaults to `--max-seconds 300`; explicitly select an integer1..900 for
longer scenarios or tighter feedback. The budget starts after profile/route
preflight and artifact-directory creation, and covers lease acquisition, worker
startup, HTTP logins, scenarios, reconnects, normal logout and worker closure.
It does not reset between phases or reconnects. It caps new native RPC/wait
budgets (accounting for `deadline_scale`), rejects calls started after expiry and
rejects late returns/predicate success. Budget expiry is failure, never a retry.

This is **cooperative**, not a hard process-wall-clock limit or a server-side
cancellation transaction. Already-started bounded HTTP/startup/snapshot calls and
worker cleanup can overrun; an already-published mutation may have taken effect.
Do not interpret expiry as rollback or proof that bots are offline. A worker can
exit while a character remains visible until ordinary server timeout cleanup;
never substitute a fixed delay for offline verification. Cleanup is
not forcibly interrupted; failure retains local leases for explicit offline
review. The runner does not terminate the shared server or control the viewer.

`run_deadline` records the limit, expiry and whether session work completed within
the budget. Final lease release and report writing are cleanup outside that
accepted-session budget; their success remains required for an overall pass.
A completed-budget receipt alone is not gameplay/cleanup success. Timings remain
actual wall times, including overrun/unwinding rather than truncating at the limit.

For compatibility, direct Python `run(..., max_seconds=None)` callers retain
per-step bounds without this aggregate budget; pass an explicit integer to enable
it. The graphical bridge independently retains its existing twenty-minute
activity cap, and current policy requires final witness retirement plus exact
outer observer-worker exit within that cap before emitting a completed activity
receipt. Final client/environment cleanup remains bounded but may occur afterward.
Neither boundary establishes hard-kill/crash-consistent cleanup.

### Native worker exit evidence

`worker_exit` distinguishes owned-process teardown from server-session logout.
After the worker context exits—even on a scenario failure—the runner polls that
worker's owned process handle and records only its numeric PID/return code,
context-exit attempts/completion and sanitized error types. A nominally successful
scenario cannot release its leases or pass with a nonzero, unknown or unbound
worker exit. An earlier scenario/deadline failure remains the primary failure;
cleanup errors are recorded separately rather than masking it. No cleanup retry
or error suppression converts the run into success.

The legacy `worker_closed` flag is still set only after the normal successful
context path. Thus a failed run can have `worker_closed=false` while its new exit
record establishes that the local process exited. A constructor that never
returns a worker leaves exit observation unknown. The scope is **native process
exit**, not normal server logout, offline exclusion, world-cache quiescence,
complete thread/handle reclamation or permission to reset/reuse characters.
Failed-run leases remain retained even when native return code is zero. Inspect
the separate normal logout/despawn evidence before any offline recovery action.

### Optional observed movement

Add `"quest_catalog": "C:/private/motivational-speaking.json"` to the profile.
This must be the existing versioned, validated Motivational Speaking (65686)
quest corridor, not hand-authored arbitrary waypoints. Territory must be 130.
Place the mover at the first route point (within 0.15m as independently received)
and the witness nearby with visibility of the short route. Each cycle walks a
prefix of at most 5 metres / 16 route points out and back at 2m/s. The witness
must receive **every waypoint**; socket publication alone does not pass.

No connecting route is invented if the mover starts elsewhere. If a run stops
mid-route, inspect/reposition the offline bot through your development tools
before the next run. There is no implicit recovery or successful-state fabrication.
You can remain logged in nearby on your own character to watch.

### Optional exact-peer invitation decline

Add `--verify-party-decline` for one normal invitation from the first dedicated
bot and one explicit rejection by the second. It requires a rebuilt worker with
`invite_party_bound` and `decline_party_bound`; there is no unbound fallback and
capability failure precedes authentication. Both bots must have fresh empty
invitation history, exact lobby/world identities, empty party state and unique
visible non-GM peers. The native decline guard compares the exact pending invite
and party context on the publication thread, not merely at the earlier snapshot.

The ten-second combined publication/observation success budget requires both the
recipient's exact received deny reply and the inviter's independent exact reject
update, plus empty membership on both. Late observations fail; in-flight native
RPCs retain their bounded worker timeout and cleanup is not hard-interrupted. Local clearing of a pending invitation or
a publication receipt alone is not success. The summary records
`decline_verification` and `party_decline_exact_peer_round_trip` timing. On any
uncertainty the normal failure/retained-lease policy applies; no foreign invite
cleanup, fallback, retry, DB access or reset is performed.

This flag is mutually exclusive with `--verify-party`: that check intentionally
refuses prior invitation history. Use separate fresh runs, not cache clearing to
combine them. Movement, Tell, reconnect and viewer checkpoints remain optional;
the viewer is never invited. This is a narrow rejection check, not general social
or reset coverage. One owned-runtime CLI check verified the two received rejection
endpoints in 0.046s within an 11.828s normal login/Say/logout check. Its separate
headless observer received no invitation. Current graphical-coordinator policy now
requires this option in a second route-free fresh bot run after the comprehensive
party run, with separate viewer checkpoints, deadline, worker-exit and lease
evidence. The outer coordinator also requires distinct run IDs and exact equality
of both ordered name/entity/character identities plus the staged-worker digest
across the two runs. The original outer witness's received lobby/world identity
and exact normal closure/removal receipt must bind to that mover before reuse. The
final outer logout observer must then freshly authenticate as the paired mover and
receive the exact non-GM viewer in idle nonparty state;
its new spawn token is not asserted continuous with either nested runner. This is
provenance, not server-offline or reset authority. That policy has focused
contracts but still has no current graphical live attestation. After a current
run, `python -m tests.e2e.inspect_client_development_result --output <output>`
revalidates the outer empty baseline/fresh exact-name spawn/fresh movement/fresh
Say/review/fresh logout snapshots, binds the rendered witness Say challenge to the
exact outer run and review frame, and requires a second exact frame captured while
the final decline-run bots are still active plus a separate manual receipt for both
rendered dedicated bot characters and the fresh nested viewer Say. Use
`prepare_client_smoke approve-interaction` only after inspecting that frame; it is
not evidence that earlier bot actions rendered. The inspector also requires a
separate exact-frame manual title-screen review receipt and an exact PID-bound observed teardown of the owned
title-screen client plus every database/API/lobby/world generation during guest
cleanup, binds the private process-lifecycle file hash, strictly cross-checks the
private environment manifest's server/worker/script/catalog/combat identities
against preparation/source evidence, and revalidates all nested
host-visible evidence read-only before disposal. Launch current owned guests through
`python -m tests.e2e.run_client_sandbox launch --prepared <prepared>`; after
manually confirming the exact owned discard dialog, use `approve-disposal` and
`python -m tests.e2e.inspect_client_sandbox_disposal --prepared <prepared>` to
bind the current result to exact launcher/process-absence evidence. Both current
inspectors also require the result, strict `inputs.json`, and exact private
`input/source.json` bytes to agree on the committed coordinator revision and
manifest SHA-256, and require exact enumeration/hash equality for every staged
`input/` file with no symlinks or extras. This covers only staged inputs; external
read-only mappings remain separately identified. It is not native-build
attestation or a signature. This does not prove server-side exclusion. Exact artifacts and limitations are in the
implementation audit.

### Optional owned two-bot party check

Add `--verify-party` to exercise normal invitation, membership, party chat and
disband without creating another server. It can be combined with placement,
movement and reconnect; party cleanup precedes the optional reconnect.

```powershell
python -m tests.e2e.run_development --profile .e2e-dev.json `
  --allow-shared-development --verify-party --verify-reconnect `
  --artifacts .e2e-artifacts/dev-party-001
```

**Rebuild the worker first.** This check requires the separately advertised
`invite_party_bound`, `accept_party_bound`, `party_chat_bound` and
`disband_party_bound` methods. A worker lacking them is rejected before HTTP
login; there is no fallback to unbound commands. The methods validate the exact
expected received party/invitation context on the worker's Asio thread immediately
before invoking the ordinary protocol operation. Older methods retain their
existing behavior. No server protocol change or GM operation is involved.

Both dedicated bots must be idle, mutually visible, modelled as completely
ungrouped, and have no pending invitation or prior invite result/update/reply.
The check binds exact lobby character IDs, world entity IDs and names. The
received invitation must name the exact dedicated inviter before acceptance;
both clients must then receive the same two-member roster, leader, party ID and
chat-channel ID. Unique messages must be received in both directions with exact
sender/party/channel identities. Disband is sent only while both received rosters
still match that owned party, and both must subsequently receive exact empty
party state. An invite receipt alone proves neither membership nor disband.

If context changes (including between a Python snapshot and worker publication),
the operation fails closed. No foreign invite is intentionally accepted and no
changed/expanded party is automatically disbanded. On failure the leases remain;
a partially created party may remain for manual inspection. There is no forced
cleanup, retry, leave/kick fallback or world reset to conceal the failure.
The guard binds **received state**, not a server-side transaction/version lock;
local leases do not exclude manual or cross-host account use. Keep these accounts
exclusive to the runner and do not manually invite or operate them during a run.

`party_verification` records the actual received roster/channel, invitation receipt,
chat records and requested/verified flags. Five action phases plus worker-capability
preflight are timed. The scope is only this two-bot lifecycle, not full social
compatibility, persistence or isolation. Native context/packet tests, synthetic
runner tests and the two-run owned-warm-world rehearsal above are available;
verification on the user's existing shared database with a viewer remains pending.

### Optional fresh-login position check

Add `--verify-reconnect` to the normal shared check, with or without
`--await-placement`:

```powershell
python -m tests.e2e.run_development --profile .e2e-dev.json `
  --allow-shared-development --verify-reconnect `
  --artifacts .e2e-artifacts/dev-reconnect-001
```

This authors **one** reconnect after successful Say/optional movement; it is not a
retry/recovery mechanism. The witness remains connected. The runner requires:

- An independently received mover endpoint before logout.
- Normal logout **and server transport closure**, then witness-observed despawn.
- Removal of the old worker bot, a new HTTP login and encrypted lobby/world entry.
- The exact same lobby character ID, world entity ID and character name, still
  non-GM/ready in the expected territory.
- Received position within 0.15m of both the expected endpoint and the witness's
  pre-logout position, followed by independently witnessed respawn there.
- A unique post-login Say message received by the witness, then normal cleanup.

`development-summary.json` includes `reconnect_verification` with before/after
identities and received positions, explicit requested/verified flags and scope
`fresh-login-position-not-world-restart`. Login, despawn, respawn and liveness
phases are timed separately. No database access, server restart, administrative
command or automatic second attempt is performed. Failures keep account leases;
the command never falls back to resetting a character to make the check pass.

Without the additional option below, this checks only the selected character's
identity/position across a fresh session. It does not prove restart/crash persistence, full inventory/quest/EXP
persistence, or that an administrative command actually ran. The shared-world
run is still non-isolated. Controller/negative contracts and the owned-warm-world
rehearsal above verify the bounded check. Existing shared-database/graphical-viewer
compatibility and restart/crash persistence remain unverified.

### Optional received inventory comparison across reconnect

Add `--verify-reconnect-inventory` **alongside `--verify-reconnect`** to compare
received inventory immediately before normal logout and after fresh authentication
of the same dedicated mover. The flag does not implicitly authorize reconnect.
Both observations require complete snapshots for ordinary bags 0–3, equipment
1000 and Currency 2000; `inventory_ready` alone is insufficient because that
native readiness flag does not include equipment. Empty completed containers
are compared as empty, not treated as missing evidence.

This option is read-only: no equip/move/grant/discard/reset operation is sent.
It compares exact received storage/slot/catalog-ID/count projections and records
both snapshots, their session-local received sequence numbers, changed slots and
separate before/after timings under `inventory_verification`. Sequence numbers
may restart across sessions; freshness comes from normal closure/despawn, fresh
HTTP/lobby/world login, exact identity and the independent respawn/Say check.
The peer witnesses the lifecycle/position, **not the mover's private inventory**.

A missing container, changed projection or malformed/late observation fails;
partial before/after evidence is retained, and there is no restore or retry.
Each observation has a ten-second success budget. This does not prove item
instance IDs, quality, durability/spiritbond, Crystal/armoury/other containers,
quest/EXP persistence, an intentional inventory mutation or restart/crash
persistence. Currency is read separately and never exposed as a generic bag
operation. The default reconnect check is unchanged when this option is absent.

One bounded owned-runtime CLI check passed in **17.547s**, independently matching
both sessions' raw snapshot journals to five starter-equipment rows and completed
empty bag/currency snapshots. Nonempty bags/nonzero currency for this new option
are covered by synthetic contracts, not that live run. A separate headless
observer and normal cleanup were inspected; no graphical attestation or existing
shared-database deployment is inferred. See the implementation audit for hashes.

### Optional starter-body round trip around inventory reconnect

Explicitly combine `--verify-starter-equipment --verify-reconnect
--verify-reconnect-inventory` (three separate CLI arguments). The mover must have
Ul'dah starter class1/2/7, exactly one body2983 in equipment1000:3 and an empty
ordinary bag0:0. Other clothing, occupied destinations, incomplete selected
containers, changed identity/class or non-idle/party/invitation state are rejected.
Both native equipment methods must be advertised before authentication.

This runs after the other short scenarios:

1. Capture the complete selected bag/equipment/Currency projection, then publish
   one ordinary unequip of that exact body to bag0:0. Acknowledge once, without
   synthesizing any local inventory change. The server's `moveItem` path writes
   containers but does not send their contents to the current session.
2. Perform a normal logout/server closure/independent despawn and fresh login as
   `mover-equipment-unequipped`. Require complete received inventory with precisely
   the expected move. Acknowledgement alone cannot satisfy this assertion.
3. Perform the separately requested read-only inventory reconnect as
   `mover-reconnected`. The existing equality comparison must retain the now
   observed **nonempty bag**, without changing that comparison's semantics.
4. Recheck the same class, identity and exact unequipped projection. Only then
   publish one ordinary re-equip to equipment1000:3 and normally reconnect again,
   as `mover-equipment-reequipped`. Require complete received inventory equal to
   the original selected slots/catalog IDs/counts.

This option explicitly adds two reconnects to the ordinary one: **three in total**.
Each requires normal server closure, independent despawn/respawn, the same identity
and position, and a distinct per-session Say message. Session-local counters may
restart; they are not compared across connections. The independent witness proves
lifecycle/position/liveness, not the private inventory or rendered appearance.

`equipment_verification` retains the identity/class, before/expected/received
projections, publication-attempt markers and acknowledgements (still explicitly
not inventory-mutation proof). Acknowledgements and each complete-inventory
observation have ten-second success budgets; normal bounded RPCs are not
hard-interrupted. The six `equipment_*` preparation/acknowledgement/observation
phases are timed separately from the three reconnects. No gameplay retry, currency
mutation, grant, DB edit, reset or new administrative authority is introduced.

Re-equip is an explicit successful-scenario step, **never failure cleanup**. A
failed/uncertain acknowledgement, observation or reconnect stops before the next
operation and retains local leases/evidence. The body may remain in the bag;
verify the bot offline and inspect its state before taking any manual action.
This is slot/catalog/count evidence, not item-instance/durability, appearance,
all-character-state, world-restart or crash-consistency proof. Unequipping can
change derived stats; the runner does not claim those remained invariant.
Default runs and the read-only inventory option alone do not add equipment operations.

### Optional independently observed self-Sprint

Add `--verify-sprint` to publish **one** ordinary Sprint (action3) on the mover,
then require exact matching self-target effects on both bot sessions, a fresh
zero-TP HUD update on each, and fresh action-start/recast metadata on the mover.
It runs after movement/social checks and before an optional reconnect. The
viewer is never targeted or controlled; no enemy/fixture reset is involved.

Both bots must retain their exact received identities, idle non-GM nonparty
state and unique mutual visibility. The mover waits up to ten seconds for
naturally received TP>=50 and the native starting-action pacing guard. This is
**not** proof that a cooldown from an earlier session has expired: use this
option only when Sprint is available. Prior Sprint history in the current
session is rejected. A server refusal, missing result or late result fails;
there is no retry, recast bypass, resource grant or silent recovery.

The combined post-publication success budget is ten seconds. Baseline combat
histories are retained; only append-only suffixes count as fresh observations.
Changed/saturated histories fail instead of clearing caches or accepting stale
zero-TP rows from login. Effect source/target/action/request and full independent
result equality are required. Publication acknowledgement alone cannot pass.
`sprint_verification` and the `sprint_natural_readiness` /
`sprint_independent_effect_and_tp` phases retain identity, baselines, receipts
and wall time. Native RPCs remain bounded but are not hard-interrupted.

This consumes the mover's TP and may leave Sprint/cooldown state until its normal
expiry, including after logout. The runner does not restore it. The check proves
received status-application effects and zero-TP updates, **not** rendered Sprint,
speed changes, status expiry, exact net TP debit (regeneration can intervene),
natural progression or persisted cooldown behavior. Failure retains the normal
local account leases for explicit offline review. Default runs are unchanged.

### Leases and failed runs

The runner uses exclusive local files in the system temporary directory under
`sapphire-dev-bot-leases-v1`. Keys bind the loopback API port and case-folded bot
username, independently of profile/artifact path. Clean logout, independent
mover despawn, and worker shutdown precede release.

Failures or interruptions retain leases. Verify both bots have actually gone
offline and inspect their world state, then remove only the `.lock` files bearing
that run's `run_id`. There is deliberately no timed lease stealing or automatic
reset. These locks coordinate **cooperating local runners only**: they do not
exclude manual logins, other machines/users, or aliases for the same server.

## Confirm a separate viewer at both endpoints without received despawn

Add `--viewer-name "Exact Playername"` to require a separate, already-online
player in view of **both** bots. The name must be exact printable ASCII (1–31
characters), not either bot's name. The runner never authenticates, moves,
invites, resets, or otherwise controls the viewer. A GM viewer is allowed, but
the two test bots must remain non-GM.

1. Connect your viewer normally and remain near the two bots.
2. Start the usual development command with `--viewer-name`.
3. Read `viewer-start.json` in that run's private artifact directory. Copy its
   `reply_in_say` text into **ordinary Say** from the named viewer, once.
4. Watch the requested scenarios. After they finish, read `viewer-finish.json`
   and send its **new** `reply_in_say` text, once. Both bots must receive it.

Each checkpoint allows 10 seconds total to bind the same unambiguous player
spawn on both bot clients, then 60 seconds total for both to receive the reply.
The start also records the native worker's existing `known_players` spawn-generation
token on the persistent witness (the witness never reconnects). At finish that
same witness must still report the same viewer entity/name as spawned with the
unchanged token. Any received viewer despawn, zone loss or respawn changes the
token and fails before the finish challenge. A fresh random nonce is generated
only after the baseline observations; received chat tokens must advance beyond
each observer's baseline. Old messages, another speaker/channel, a reply seen by
only one bot, changed viewer identity/GM rank, NPC lookalikes, malformed presence
metadata and ambiguous identities fail closed. Late successful waits are also
rejected. Failure retains bot leases for manual recovery; there is no automatic
retry or forced viewer cleanup.

Viewer movement is allowed while both bots can still observe that player.
Positions are recorded, not held fixed or restored. If ordinary visibility culling
causes the persistent witness to receive a despawn/respawn, the continuity check
fails even if the viewer remained logged in; this is deliberately received
visibility evidence, not a server-side session oracle. With `--verify-reconnect`,
the finish reply must reach the newly authenticated mover as well as the original
witness. The summary records both checkpoints, each observer's baseline/received
sequence, exact run-bound Say text, received viewer position/spawn token and the
unchanged witness token under `viewer_verification`. The viewer must retain each
observer's baseline spawn token while that checkpoint waits for its reply; a
received despawn/respawn during either reply window fails.

**Scope:** this proves endpoint liveness plus absence of any received viewer
despawn/respawn on one continuously connected witness between them. It does not
prove server-side online exclusion, packet-loss-free observation, unchanged viewer
gameplay state, a particular client executable, rendered appearance, screenshots,
or graphical compatibility. A third headless
client can exercise this contract but cannot substitute for the independent
real-client lane. Allow enough managed-host lifetime for operator replies.

One clean-source live check of this option passed in **25.5s**, including
movement, party and reconnect verification. A separate headless client supplied
the two replies; all four independent received message/token matches were
inspected. Its selected before/after identity, position and party fields matched,
and all owned processes cleaned up. Graphical compatibility remains unverified;
see the audit for the exact scope and `.e2e-artifacts/development-viewer-live-001`.

## Evidence and limitations

`development-summary.json` records worker/catalog hashes, an exact run-bound
complete-tree identity for the owned `worker/` journals, entities, scope,
completion/error stage, lease disposition, elapsed time and phase durations:
HTTP login, lobby/world entry, initial witness checks, Say, optional movement,
logout/despawn and account release. `worker_session_including_close` is an
inclusive parent timing; do not add it to its child phases. Reinspect one retained
run against an already-running external shared server with:

```powershell
python -m tests.e2e.inspect_development_result `
  --summary .e2e-artifacts/<run>/development-summary.json
```

This failure-closed consumer requires the explicitly unmanaged host boundary, exact
normal worker exit, bounded success deadline, clear local leases, run-owned complete
worker journal tree, and a sequence-advancing received Say observation in both
directions. It also strictly validates every requested movement, party, Tell,
reconnect/inventory/equipment, Sprint, or decline receipt. A base run is therefore
only narrow login/bidirectional-Say/logout evidence; it is not a substitute for those
optional scenarios. Managed-host runs use the separate composite inspector above.

A configured protocol and successful session are not a server binary fingerprint.
The report explicitly leaves `server_identity_verified` false. Passing proves
only the checks actually executed against that shared world. It does not prove
isolation, fixture reset, persistence across restart, combat/progression, capacity,
graphical-client compatibility, or acceptance coverage.

World-enemy/respawn resets and general reprovisioning of existing characters remain
separate follow-up work; the command above is only opening bypass/placement of
registered dedicated bots. A future reset must be development-only, explicitly targeted, require
exclusive ownership/offline actors as appropriate, and record administrative
preparation separately from normal gameplay evidence. Broad world resets must not
interrupt a human viewer or be silently run between tests. The inspected source
prerequisites and blockers are recorded in
`research/development-reset-boundary.md`: ordinary deletion/logout and BNPC combat
ownership are not sufficient reset authority or exclusion.

## Measure existing pytest cases without a full gate

```powershell
python -m pytest tests/e2e/test_live.py::test_login_idle_logout `
  --e2e-profile .e2e-local.json `
  --e2e-timings .e2e-artifacts/login-phase-times-001.json -v
```

This example is **one isolated test**, not the shared-server runner or full gate.
`--e2e-timings` is optional and requires a new output file. It records pytest
setup/call/teardown durations and outcomes, including failed phases. Test `call`
may include explicit world restarts, so these timings do not yet separate pure
gameplay from every internal restart. The timing report is diagnostic, not a
coverage or acceptance verifier.

Synthetic checks (no server, no credential profile):

```powershell
python -m pytest tests/e2e/test_development.py tests/e2e/test_development_provisioning.py tests/e2e/test_development_placement.py tests/e2e/test_development_reconnect.py tests/e2e/test_development_party.py -q
```

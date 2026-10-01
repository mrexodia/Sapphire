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

## Frozen coordinator source for the manual graphical lane

Feature `2f480c49a` replaces the graphical preparer's mutable checkout mapping with
an independent shallow checkout of the exact committed HEAD. Dirty/staged/
untracked host files are excluded, including the preserved performance experiments.
The local clone has no hardlink/alternate dependency, configured remote or
submodule fetch. Gitlink revisions are recorded but not materialized; this is a
coordinator/runtime-source snapshot, **not** native-build source attestation.
Line-ending configuration is pinned for guest Git inspection.

`input/source.json` records materialized-file hashes and revision; `inputs.json`
binds that manifest. The guest checks revision, clean status, file hashes,
remotes/alternates and absence of unexpected materialized submodules before
registry/client/environment setup. Extra ignored files also fail. This is
accidental-change/reproducibility checking, not a signature or security boundary.
The operator must not edit the prepared bundle during use; readonly guest
mapping does not prevent host-side edits. Native binaries and external assets
retain separate identities.

**Focused verification:** 36 source-snapshot and existing real-client policy
contracts passed in **17.08s**; a further guest-before-setup rejection contract
passed in **0.10s**. Tests cover committed-vs-dirty/staged/untracked inputs,
independence after removing access to the original repo, file/hash/revision
changes, ignored/untracked additions, remote/alternate rejection, destination
reuse and unmaterialized gitlinks. These are local filesystem/Git policy checks,
not VM/client execution. Timing artifacts:
`.e2e-artifacts/client-snapshot-focused-timings-1.json` and
`client-snapshot-guest-guard-timings.json`.

**Actual preparation only** succeeded at
`.e2e-artifacts/client-frozen-preparation-001`. Inspected evidence confirms:

- Snapshot revision `2f480c49afece47aa4c9165e05dc1bed95826f73`, **2,414** source
  file hashes and ten unmaterialized gitlink records; changed worker/client/
  territory files match committed bytes rather than host experiment bytes.
- All staged input hashes match, including the previously supported exact
  unmodified DX11 client; `inputs.json` remains `prepared_not_executed`.
- WSB maps the private snapshot, not the original repository, readonly. Networking,
  clipboard, audio/video input and printer redirection remain disabled; only the
  run's output mapping is writable. Installed client/settings/networking untouched.
- `preparation-verification.json` records these checks. Input manifest SHA-256:
  `551510402e68eba052a72e54b84404f93c39f86b2b6fa4a0bbc9b8df56a1453d`.

No sandbox, graphical executable or server was launched for this increment.
New guest execution/disposal and graphical co-presence with the shared-development
runner are **still unverified**. Earlier manual pilot/coordinator evidence below
is historical, not proof of this new snapshot path. All original reset,
platform/CI and acceptance gaps remain open; no full gate or soak was run.

## Provisioning receipt association and reset-source boundary

Feature `ece249544` adds `support/development_binding.py`: successful provisioning
receipts bind configured API/lobby endpoints, optional managed-host session,
ordered case-folded account names and received character/entity IDs using a
versioned canonical digest. Passwords/authentication tokens/server secrets are
excluded; worker/catalog/password changes do not select another account and keep
their independent validation. The placement planner now requires saved credentials,
clean completed provisioning and an exact receipt association. It rejects mixed
profiles, edited identities and missing/legacy bindings without synthesizing
approval. The seven-field server registry schema and server behavior are unchanged.

**Limits:** this prevents accidental artifact mismatches, not intentional editing
of both files. It is neither a signature nor current authentication, deployed
server identity, offline proof, cross-host exclusion, or reset permission.
Historical provisioning/placement artifacts remain historical evidence; their
old receipts are not retroactively upgraded into current planner approvals.

**Verification:** 81 focused provisioning/placement/host/binding contracts passed
in **1.07s**; 15 binding contracts passed in **0.33s** from the committed archive.
No native code changed or new native build was needed. Artifacts:
`.e2e-artifacts/development-binding-{focused-timings-1,clean-timings}.json`.

One fresh bounded owned-runtime check in
`.e2e-artifacts/development-binding-live-001` exercised the normal provisioner CLI
and offline registry CLI. Startup **18.953s**, provisioning **11.750s**, total with
planning/negative checks/cleanup **31.625s**. Both new non-GM characters received
territory 182, exact identities and normal server logout closure. The emitted
association matched the saved profile and the planner retained the exact received
IDs. Changed endpoint, account name, identity and missing legacy association were
rejected offline. Bot leases released, worker closed and owned cleanup completed;
only pre-existing MySQL PID 7764 remained. The controller is `ece249544`, with the
unchanged clean Tell worker/backend hashes recorded in the summary. No placement,
reset, graphical client, gameplay scenario or full gate was executed here.

`inspected-evidence.json` hashes the exact driver, summaries, journals and planner
log. Aggregate SHA-256:
`fdb315c58dd5dd09c0c6506e711b60535c41097730a12b51655e73b5a182baf6`.
Credentials, registry, runtimes and raw artifacts remain untracked.

**The reset gap remains open.** `research/development-reset-boundary.md` maps the
inspected lobby/API deletion chain, session unload ordering and BNPC combat-owner
lifecycle to missing shared-reset prerequisites. Historical logout is not an
exclusive fence; combat owner is not durable fixture ownership. No destructive
live probe, DB-under-cache shortcut, or reset wrapper was added. A future reset
needs explicit registered ownership, appropriate atomic session/world-thread
coordination, defined partial-outcome handling and independently observed
postconditions. This source-suitability review is not a general security verdict.
All existing graphical/platform/CI/acceptance and broader reprovision/reset gaps
remain pending.

## Short visible-peer Tell check (not general messaging/graphical acceptance)

Feature `987b59443` adds optional `run_development.py --verify-tell` and
`support/development_tell.py`. Exactly two messages go between the dedicated
bots, after optional party disband and before optional reconnect. The distinct
native `tell_visible` method validates its three typed arguments and current
idle/non-GM/nonparty state, then requires one unambiguous separate visible
non-GM player with the exact entity/name. It rejects NPC lookalikes, duplicate
player names, self/GM targets, transitions/scenes/invites and remote/offline
fallback, on the Asio thread immediately before ordinary Tell publication.
Old workers fail capability preflight before authentication.

Both participant identities are rechecked, including received lobby character
IDs. Each unpredictable message is generated after both baseline snapshots;
delivery must carry the exact actor/name/character ID/nonparty context and an
integer token strictly newer than baseline and no newer than the received state.
Each direction has a ten-second publication/delivery budget; late successful
waits fail. Publication acknowledgements are never delivery evidence. Failure
retains leases; there is no retry or automatic party cleanup. The viewer is not
addressed. Context-filtered action journals retain target/name/message without
unrelated credential fields.

**Focused verification:** 158 applicable Python contracts passed in **5.92s**;
24 new Tell/journal contracts passed in **0.65s** from an archived committed
snapshot. Native protocol CTest passed **1/1**, including ordinary-byte equality
and 19 rejected visible-send cases. Timing/build artifacts:
`.e2e-artifacts/development-tell-{focused-timings-1,clean-contract-timings}.json`
and `development-tell-native-{build,tests}.log`. Combined party/disband/Tell/
reconnect ordering is contract-tested; the new live check exercised Tell alone
with required login/Say/logout rather than repeating the other scenarios.

**One bounded product-CLI live check passed:**
`.e2e-artifacts/development-tell-live-001` used three new pre-connection non-GM
fixtures in an owned private runtime, not normal provisioning/progression. The
controller/native feature inputs match `987b59443`, with preserved experiments
excluded. The worker SHA-256 is
`b25644e04fa18aa52c9de6e95ee0d43e6a4f62b30dea5d85606994a03ff9105f`;
backend hashes remain those of the clean linked `e665c041f` placement build.
`development-tell-inputs.json` records these identities separately.

- Startup **18.016s**, short development check **11.906s**, Tell phase **0.047s**,
  complete driver including third-client lifecycle and cleanup **37.234s**.
- Exactly two `tell_visible` publications bind the other dedicated recipient.
  Exact received journal matches advance witness token **120→122** and mover
  token **122→124**, including the full sender character IDs.
- The separate **headless** observer received public Say from both bots. Its
  recorded lifecycle contains no test Tell, and selected identity/territory/GM
  rank/position/party/pending-invitation snapshots match. This is bounded observed
  nonreceipt, not general privacy, continuous-presence or all-state invariance.
  Its only journaled actions are login/logout/close/remove.
- All three normal server logout closures were inspected. Bot leases released,
  workers closed and owned runtime/process cleanup completed. Only pre-existing
  MySQL PID 7764 remained. Existing DB/client settings/networking were untouched.

`inspected-evidence.json` hashes the exact driver, summaries and bot/observer
journals and records the two token proofs. Aggregate summary SHA-256:
`fc2744853744b56ed488df2fd20590d5b938d55b04fb8c5092268de094b978a5`.
No placement/reset, movement, party, reconnect, graphical launch, full gate,
expensive soak or platform sweep was run for this live increment. The original
requirements and broader reprovisioning/reset/deployment gaps remain pending.

## Registered-bot placement: narrow owned-runtime live verification

Features `ea0d30036`, `0e49ba287` and `a6b2c1143` add a distinct administrative
worker method, a separate preparation-operator Python API, and credential-field
filtered request journaling. Ordinary `Bot` login still rejects GM characters;
ordinary Say still rejects debug commands. The administrative method requires
exact received operator identity, GM/ready/stationary/public-130/nonparty state,
an explicit setup flag, one lowercase-hex approval ID and slot 0/1. Each native
Bot consumes at most those two slots of one approval before publication. The
helper flushes an exclusive intent before dispatch and never retries uncertain
publication. These are local safeguards, not server-side transaction locks,
cross-host exclusion or crash-consistent ledgers. Existing server guards remain
independent and disabled by default. Operator login/reply methods do not expose
movement/combat/inventory or create/promote accounts.

**Clean build and focused verification:** linked server/API/lobby/DB tool and
script modules built with Windows LLVM/Ninja Release from committed `e665c041f`
and committed submodules, excluding all working-tree experiments. The worker
was built with the administrative feature at `ea0d30036`; its changed native
inputs byte-match that commit. Live controller revision was `0e49ba287`.
`placement-live-inputs-002.json` records separate revisions and binary SHA-256s.
Native placement and protocol CTests each passed **1/1**. Focused Python checks
passed **286 in 7.56s** before the separate login API, then an overlapping **107
in 5.13s** for that API. Final operator/privacy contracts passed **25 in 0.55s**
from an archived `a6b2c1143` snapshot, not the dirty working-tree worker.
Logs/timings are under `.e2e-artifacts/placement-{server,operator}-*.log` and
`development-operator-*-timings*.json`. These are not full acceptance results.

**Failure preserved:** `.e2e-artifacts/placement-live-001` stopped at the ordinary
Bot's intentional non-GM login guard after successful provisioning. No placement
request was sent. The separate GM had connected before the wrapper rejected it;
worker teardown and owned-runtime cleanup followed, not a claimed normal GM
logout. The exact failed driver/report are retained. This motivated the separate
`DevelopmentOperator.login_for_preparation`, without weakening ordinary login.

**One fresh, bounded live check passed**, in
`.e2e-artifacts/placement-live-002`:

- Owned runtime startup **19.797s**, normal account/character provisioning
  **11.640s**, combined placement and development check **38.719s**, entire driver
  including operator lifecycle and cleanup **77.250s**. Administrative placement
  waiting alone was **1.125s**; these timings do not imply acceptance speedups.
- Only the newly owned runtime enabled the command and loaded the reviewed
  registry. A distinct owned operator fixture received GM rank 1 before its
  first lobby/world connection, with exactly one identity-bound DB row updated
  while it was the database's sole character. No live cached character was
  edited; both normally provisioned registered targets remained GM rank 0.
- Both target journals contain **182 → 130** InitZone transitions. Exact
  registered identities and destination positions were received and independently
  observed. Two server request records bind approval/slot/operator/target/source/
  destination/catalog; local receipts remain `placement_verified: false` and
  intents remain `publication_outcome_unknown`, never rewritten as mutation proof.
- Normal public-world movement, exact two-member party/chat/disband and fresh
  HTTP/encrypted-lobby/world reconnect passed. The mover's new session received
  territory 130 and the same identity/position. This is narrow fresh-login
  evidence, not restart/crash persistence or natural opening progression.
- The separate **headless GM operator**, not a graphical client or the user's
  character, supplied exactly two fresh viewer Say replies. Both normal clients
  received each checkpoint. Operator identity/territory/GM rank/position/party/
  pending invitation matched before/after; HP/resources/all-state invariance and
  continuous presence are not claimed. Its journal contains only login, two
  registered placement requests, two Say replies, logout, close and remove.
- Normal logout/server closure and released bot leases were inspected. Owned
  runtime/process cleanup completed; subsequent process inspection found only
  the pre-existing MySQL PID 7764. Existing database/client settings/networking
  were untouched. Private credentials/registry and raw artifacts stay untracked.

`inspected-evidence.json` hashes summaries, bot/operator journals, intents,
registry and server log. Passing aggregate summary SHA-256:
`78549787183c9d8f2c1c1050b09c49c22402693ad9776a14bdc0212c95c2a8b8`.
The original action journal records administrative method names only; exact
bindings are supported by intents and server records. Richer whitelisted action
arguments were added afterward and contract-tested, **not** retrospectively
attributed to this live run. No live mutations were repeated to enrich logs.

**Still pending:** deployment against the user's existing shared server/database,
a real graphical viewer alongside these bots, general safe character
reprovisioning/owned-world resets, and the original gameplay/platform/hosted-CI/
acceptance gaps below. Expanded Linux remains 7/15. No full gate, expensive soak,
platform sweep, graphical launch, or overall completion claim was made.

## Named viewer endpoint confirmation (not graphical acceptance)

Feature `1c15616a5` adds `--viewer-name` to `run_development.py`, backed by
`support/development_viewer.py`. It never logs into or controls that character.
Both normal bots must first receive the same unambiguous, separate player
identity (name/entity ID/GM rank). At start and finish, a newly generated random
nonce in ordinary Say must be received by **both** clients, with chat tokens
newer than their respective pre-challenge snapshot sequences. The finish check
uses the fresh mover session when reconnect verification is enabled.

The identity window is 10 seconds total; the reply window is 60 seconds total
per checkpoint, not per observer. Late successful waits are rejected. Wrong
speaker/channel, stale or invalid event tokens, reused start replies, one-sided
publication, NPC lookalikes, duplicate names, changed identity and bot-as-viewer
selection fail closed. Viewer movement is permitted; the runner does not hold or
restore its position or modify that character's gameplay state. A GM viewer is allowed by the
contract, while test bots remain non-GM; a GM viewer was not live tested at this
checkpoint (the subsequent registered-placement check above now covers that role).

**Focused evidence:** 266 applicable contracts passed in **7.09s**. The 36 new
viewer contracts also passed in **0.34s** from the committed source snapshot.
Artifacts: `.e2e-artifacts/development-viewer-focused-timings-1.json` and
`development-viewer-clean-contract-timings-1.json`. Native code/binary is unchanged;
the live worker remains the previously verified clean `64793b3034…` binary.
The live controller snapshot byte-matches `1c15616a5`, excluding the separate
working-tree performance experiments. Backend binary hashes match `e34d695fd`.

**One bounded live product-CLI check passed**, with an externally controlled third
non-GM **headless** client supplying exactly two normal Say publications:

- Owned host startup **25.859s**, development check **25.485s**, complete driver
  including viewer lifecycle and owned cleanup **60.437s**.
- Start received chat tokens: mover **118→122**, witness **118→120**.
  Finish: reconnected mover **118→120**, original witness **302→304**.
  All four exact actor/channel/message/token matches were inspected in journals.
- Viewer identity/reply phases totaled about **0.157s** with automated replies;
  this is not a human response-time estimate. Movement, exact party/chat/disband
  and fresh-login position checks also passed.
- The external viewer remained ready after the check. Its received identity,
  territory, GM rank, position, party and pending-invitation fields matched
  between captured before/after snapshots. HP/MP/TP and all other state were not
  claimed unchanged; normal regeneration and unrelated updates remain possible.
- Both runner leases released, the viewer completed normal logout/server closure,
  host exit was zero, owned runtime/process cleanup verified, host credential
  exports removed, and stopped-profile reuse rejected. Subsequent process
  inspection found only the pre-existing MySQL service (PID 7764).

Evidence root: `.e2e-artifacts/development-viewer-live-001`. It contains the passing
`verification-summary.json` (SHA-256
`cff2adf1d8f9af320088513d61149cc5b18a55985ff0e72a6ee1bb717736b297`),
`check/development-summary.json`, both challenge files, bot/viewer action/event
journals, `viewer-before-after.json`, and `host-final-status.json`.
`inspected-evidence.json` binds file hashes and all four received-token proofs.

**Limits:** endpoint presence is not continuous presence or graphical/client
attestation. No graphical executable was launched, existing database/client
settings were untouched, and normal provisioning was not repeated in this run.
The prior post-provision snapshot gap remains specific to that failed diagnostic;
this case verifies snapshots around the short gameplay check only. Live GM
placement was still pending at this checkpoint; the later owned-runtime evidence
above is narrower than shared-server deployment. Broader resets/reprovisioning,
original platform/CI/graphical and full acceptance requirements remain open.
No full gate or soak was run.

## Bounded warm host and live dedicated provisioning (not acceptance)

Feature `203bf98f7` adds `tests/e2e/serve_development.py`: one owned private
runtime/database, three pre-connection non-GM fixtures (two bots and a separate
viewer), private profile export, and operator-stop/expiry/process-loss shutdown.
The 60–14400-second lifetime starts at readiness. The host never accesses the
user's existing database, restarts between checks, or prepares live cached
characters. Its own fixture preparation remains administrative, not normal
lobby-creation evidence. It does not launch a graphical client or preserve the
private database after shutdown.

Managed profiles bind a local session ID, owner PID/creation time, deadline,
API/lobby ports and worker hash. The runner/provisioner checks the binding before
creating run artifacts or authenticating; HTTP operations recheck it. Explicit
stop markers, stopped/failed states, stale identities, expired deadlines,
changed workers, missing/oversized status files and dead/zombie owners fail
closed. These checks are not atomic server-side leases or crash-consistent
cleanup. Unchanged exported profiles are removed; changed/partial exports are
retained and reported. Status-write failures do not skip owned-process cleanup.
Known production lobby session-log fields are now redacted at export even when
an independently authenticated viewer's session was not registered in the
fixture API wrapper. Arbitrary plugin logs remain outside that sanitizer claim.

Focused verification: **230 passed in 6.99s** in the working tree, then **230
passed in 7.36s** from a committed `203bf98f7` source snapshot, excluding the
uncommitted client/controller performance experiments. Timings are in
`.e2e-artifacts/development-host-{focused,clean-focused}-timings-1.json`.
The unchanged clean worker is the previously native-verified
`64793b3034513ed9118baa8dba7aa484c7ca5ef57343c94862af981577e60fb2` binary;
server/API/lobby/DB-manager hashes still match the historical `e34d695fd` gate.
No newly linked GM-placement server or full acceptance gate was used.

**Live evidence, including failed diagnostics:**

- `.e2e-artifacts/development-host-live-001`: host startup/stop/cleanup and stale
  profile rejection worked. The diagnostic driver passed a string instead of
  `Path` to the viewer `Worker` constructor and failed before launching that
  client. Its report and exact driver are retained. The private runtime was
  removed; no gameplay check or normal provisioner call began.
- `.e2e-artifacts/development-host-live-002`: corrected the known pre-client
  driver error and used a new private environment, not a mutation retry.
  Host readiness took **25.453s**. The ordinary development check passed in
  **25.359s**, with observed movement, exact two-bot party/chat/disband and
  fresh-login position verification. Both normal bot cleanup and leases passed.
- The separate provisioner returned its documented success status
  **`provisioned` in 11.968s**. Both new accounts independently authenticated;
  encrypted lobby creation/refreshed-list/world entry bound exact character and
  entity IDs. Both characters were non-GM in opening territory **182**, and both
  normal logout/server closures completed. Its worker closed and leases released.
  `ready_for_shared_checks` remains **false**: public placement/progression was
  not demonstrated for these newly provisioned characters.
- A third distinct non-GM headless client independently received both bots'
  unique Say messages plus the fresh-login Say, and subsequently completed
  normal logout/server closure. Its journal contains only login/logout/close/
  remove commands. This supplies co-presence/liveness evidence, **not graphical
  compatibility or an unchanged post-provision state snapshot**.
- The second one-off driver incorrectly expected provisioner status `passed`
  instead of `provisioned`. Its aggregate remains **failed**, and the planned
  post-provision viewer snapshot assertions did not run. Do not relabel that
  driver as passing. The underlying development/provisioning summaries and
  journals were inspected separately; no successful mutation was repeated merely
  to get a green diagnostic wrapper.
- Host CLI exit was zero, final status `stopped`, private runtime/process cleanup
  verified, unchanged host exports removed, and captured stopped-profile reuse
  rejected. The private DB name/port were verified distinct from the existing
  `sapphire` database/3306 service. Process inspection afterward found only the
  pre-existing MySQL PID 7764. Ten known session-log field occurrences were
  inspected and redacted in exported logs. Normal provisioner's separate private
  credential output is retained, bound to the now-stopped host.

The second directory contains `check/development-summary.json`,
`provisioning/provisioning-summary.json`, their action/event journals,
`viewer-worker/{actions,events}.jsonl`, `host-final-status.json`, and the failed
`verification-summary.json`/`driver.py`. `inspected-evidence.json` records the
narrow post-hoc artifact audit and SHA-256 hashes, explicitly **not** a passing
aggregate-driver verdict. The graphical viewer, post-provision viewer state
comparison, live GM placement, broader resets/reprovisioning, and original
acceptance/platform/CI requirements remain open.

## Live warm-world development rehearsal (not acceptance coverage)

After explicit broad local authorization, a committed-source client/controller
snapshot at `1ad7fa50aeb1b8b4ba25fbe7f88c98ce920eb7b8` was built separately from
all working-tree performance experiments. Client.cpp, PartyActions.cpp and the
Python worker were byte-compared with that revision. The clean Clang worker hash
is `64793b3034513ed9118baa8dba7aa484c7ca5ef57343c94862af981577e60fb2`.
Clean-source focused contracts passed **199/199 in 6.89s** and the native protocol
test passed **1/1**; artifacts are `.e2e-artifacts/shared-dev-clean-focused-timings.json`,
`shared-dev-clean-{configure,build,native-tests}.log`.

One owned private environment was started once using server/API/lobby/DB-manager
binaries whose hashes exactly match the recorded `e34d695fd` Windows gate.
Two non-GM characters were administratively prepared **before first world
connection**, at the source catalog start, then reused for two explicitly authored
successful-path runs of `run_development` with movement, party and reconnect
verification. No gameplay retry, server restart, fixture reset or additional
character provisioning occurred between runs. Both runs kept the exact same
owned API/lobby/world/database PIDs.

| Timing | First run | Second run |
|---|---:|---:|
| Shared development check total | 27.297s | 23.984s |
| Source-prefix out-and-back movement | 6.719s | 6.469s |
| Invite + observed membership + chat + disband | 0.453s | 0.188s |
| Reconnect logout/despawn | 5.875s | 5.093s |
| Final sequential logout/despawn | 11.547s | 11.828s |

One-time environment startup took **28.578s**, cleanup **0.531s**, and the whole
rehearsal **80.843s**. Logout waits dominate the warm run; they were not shortened
by removing server-close or independent-despawn assertions. These timings cover
only the selected short scenarios, **not** a faster equivalent of the 55-minute
full acceptance suite.

Each run retained **44 semantic actions**, including **24 observed waypoint
commands**, the five bound party operations, and fresh authentication. Party IDs
and channel IDs differ across runs. Both clients received exact empty membership
after disband; fresh-login character identity/position and unique post-login Say
were verified. This is position stability across a fresh session after an
out-and-back route, not proof of arbitrary changed-position/restart/crash
persistence. All account leases were released, the owned runtime was removed,
and a process check found only the pre-existing local MySQL service afterward.
The user's existing `sapphire` database and characters were not touched.

Evidence: `.e2e-artifacts/shared-dev-live/sapphire-e2e-lm4tswcb/development-{1,2}`
contains summaries and raw worker action/event journals. The two journals contain
644 and 614 events respectively. Summary and journal hashes plus committed-input
checks are in `.e2e-artifacts/shared-development-rehearsal-verification.json`;
aggregate timing/identity/cleanup evidence is in
`.e2e-artifacts/shared-development-rehearsal-summary.json` (SHA-256
`2f39157116252c03ae6e415d353667f68fafa2c02f33e3007e9b9c281258aa5e`).

**Limits:** this did not exercise `provision_development` normal lobby creation,
`!devbot place`, the latest server command build, an existing shared dev database,
a graphical viewer, or any full acceptance/platform/soak gate. Those requirements
remain open. The warm checks now have real protocol evidence, not just mocks;
that does not validate the separate Linux scheduling/navigation experiments.

## Fast development lane (not acceptance coverage)

At `c078afc17`, `tests/e2e/run_development.py` adds an explicitly opted-in,
non-isolated two-bot lane against an already-running loopback development server.
It uses dedicated existing accounts, local exclusive account leases, ordinary
HTTP/lobby/world sessions, independently witnessed identities/Say/despawn, and
optional per-waypoint observation of a <=5m out-and-back prefix from the existing
Motivational Speaking catalog. It never owns server processes or accesses the DB.
A human viewer may remain in the world. Failures retain account leases; automatic
retries/resets are absent. Server binary identity is explicitly unverified.

`tests/e2e/DEVELOPMENT.md` and `development.profile.example.json` describe setup,
limitations, manual failed-lease recovery and the separation from isolated gates.
Existing dedicated characters must already be offline and positioned appropriately.
At `8e80536e6`, `tests/e2e/provision_development.py` adds opt-in **new-account**
provisioning: two generated dedicated accounts via normal HTTP createAccount,
separate successful HTTP login, encrypted-lobby Gladiator creation with refreshed
list/world confirmation, non-GM checks and normal logout. A new private credential
profile is exclusively written and flushed before requests; uncertain failures
preserve credentials and account leases without retries, adoption or deletion.
It uses no DB access or server secret. `provisioning-summary.json` distinguishes
request/receipt, fresh login and received character/world evidence and explicitly
sets `ready_for_shared_checks: false`: opening/public-world preparation is still
required. At `620438063`, provisioning also records the exact received lobby
character ID and verifies its world-entity binding. The new
`tests/e2e/prepare_development.py` produces a private operator-reviewed registry
from a completed provisioning report and the validated 65686 route start.
`!devbot place <approval_id> <slot>` is a disabled-by-default GM-only server command:
it checks exact registered generated bot name/entity/character identity, connected
idle/alive/non-GM/no-party state and territory 182/130; it queues only that bot's
opening bypass/placement into public 130 using the existing world-thread warp
path. BetweenAreas guards overlapping requests; approval/slot consumption is
bounded and process-local, not crash-consistent. No unrelated player, enemy,
EXP, item or quest-completion reset is performed.

The shared runner's explicit `--await-placement` mode writes
`placement-ready.json`, allows 120 seconds total for separate GM preparation,
then requires received ready/position state followed by independent identities
and position observations. Administrative wait timings remain separate from
normal actions. Neither a registry nor a queued-warp response proves mutation;
the runner does not attest administrative command execution. Fresh-login position
verification is now optional (below), with the narrow owned-warm-world evidence
above. General character reprovisioning and enemy/world-state resets remain
**not implemented**. Normal provisioning now has the narrow owned-warm-host live
evidence above. GM placement still needs a feature-built server and an
operator-approved registry/GM session, independently of the short warm checks.

Placement verification: **161 focused Python tests passed in 5.86s** (the previous
selection plus `test_development_placement.py`); timing evidence is
`.e2e-artifacts/development-placement-focused-timings-2.json`. Native
`sapphire_dev_placement` passed **1/1**; the changed server command translation
unit compiled with Clang, recorded in
`.e2e-artifacts/development-placement-{object-build,native-build,native-tests}.log`.
This is policy/control-flow plus translation-unit evidence, not a linked/deployed
server or live command/zoning/persistence claim. No full acceptance suite ran.

At `3556c2496`, `--verify-reconnect` adds one explicitly requested fresh-login
identity/position check without restarting the world. The witness stays online;
normal logout/server closure and independent despawn precede new HTTP/lobby/world
authentication. Exact lobby character/world entity/name identity, ready/non-GM
state, received endpoint, independent respawn and unique post-login Say are
required. Missing evidence fails without retries and retains the account leases.
`development-summary.json` records requested/verified flags, received positions,
identities and `fresh-login-position-not-world-restart` scope; timings separate
authentication, despawn, respawn and liveness. This does not attest a GM command,
full character state, restart or crash persistence.

Reconnect-focused verification: **178 passed in 6.23s**, adding
`test_development_reconnect.py` to the prior focused selection; evidence is
`.e2e-artifacts/development-reconnect-focused-timings-1.json`. Negative cases
cover missing server close/despawn, failed fresh authentication, changed IDs/name,
wrong territory/position/GM rank, absent or misplaced independent respawn and
missing fresh Say. These are synthetic/controller and existing-worker contracts,
not themselves live shared-world reconnect evidence. No server or character was
modified for those contracts; the later owned-warm-world rehearsal above supplies
separate narrow live evidence without exercising an existing shared dev database.

At `7eff55c09`, `--verify-party` adds one optional normal two-bot invitation,
exact received membership/channel, bidirectional party-chat and disband check.
It rejects existing party/invitation state, binds the exact received inviter and
both lobby/world identities, and requires both clients to receive empty party
state after disband. Foreign/changed ownership fails without cleanup/retry;
uncertain accounts remain leased. It runs before optional reconnect.

Four separately advertised native `_bound` party methods compare the expected
received party/invitation context on the Asio thread before invoking the ordinary
wire operation. Old workers fail capability preflight before HTTP login; they
cannot silently ignore the new guards. These are received-state guards, not
server-side transaction locks or multi-host ownership enforcement. The original
unbound methods and server protocol remain unchanged. Context arguments are
recorded in bounded journals without unrelated session fields.

Party-focused verification: **199 Python tests passed in 6.66s**, with the new
`test_development_party.py` and updated worker contracts. MSVC Release worker
and protocol targets built; `sapphire_protocol` passed **1/1**, including changed
invitation/roster/party/channel context rejection. Evidence:
`.e2e-artifacts/development-party-{focused-timings-1.json,msvc-build.log,native-tests.log,verification-inputs.json}`.
Input hashes explicitly identify the diagnostic worker/controller built with the
pre-existing uncommitted packet-output/wakeup experiments; those experiments
were excluded from the feature commit and are **not** validated performance fixes.
At that checkpoint no full acceptance or live shared-server party run was performed.
Only the party implementation hunks were staged in the otherwise dirty
Client.cpp/worker.py. The suggested private development profiles were absent.
Subsequent broad local authorization enabled the clean-source owned-warm-world
rehearsal above, deriving ports/accounts from the owned environment and using
existing local asset configuration rather than guessing credentials/endpoints.
Deployment on the user's existing database with a graphical viewer remains open.

Focused verification: **127 passed in 5.59s**, running `test_development.py`,
`test_policy.py`, `test_ci.py`, and `test_worker.py` with the existing MSVC worker.
Evidence: `.e2e-artifacts/development-focused-contract-timings-2.json`. This is
synthetic policy/control-flow plus worker-contract evidence, not shared-world or
new server-build evidence. The new `--e2e-timings` option reports pytest setup,
call and teardown times; call still includes any in-scenario restarts. Development
summaries additionally separate login, witness, Say/movement and logout phases.
Provisioning-focused verification: **138 passed in 5.77s**, adding
`test_development_provisioning.py` to the same focused selection, with timing
artifact `.e2e-artifacts/development-provisioning-focused-timings-1.json`.
The active goal now prioritizes fast shared-world feature development and explicit
scoped administrative preparation while retaining all original acceptance gaps.
No full acceptance gate was run, as requested. Earlier uncommitted Linux
scheduler/navigation/client-event experiments remain separate and unvalidated;
the existing Linux, hosted-CI and real-client blockers are unchanged.

## Requirement audit

| Requirement | Evidence | Status |
|---|---|---|
| Architecture / dedicated branch / atomic commits | Original proposal `autonomous-testing-plan.md`; `feature/headless-e2e` | Implemented incrementally |
| External C++ worker / shared schemas and lobby encryption | `src/test_client`; only normal sockets, no server-handler calls | Verified for enabled actions |
| Python/pytest / JSON-lines / asynchronous channels | `support/worker.py`, dispatcher, Bot/Channel state machines | Verified |
| Genuine HTTP login, lobby selection, world-ready, both keepalives, logout | Live smoke scenarios; FINISH_LOADING followed by received cleared BetweenAreas | Verified on Windows/3.3 |
| Normal character creation/opening journey | `test_live_creation.py`: four empty accounts spanning Ul'dah starters Gladiator/Pugilist/Thaumaturge, lobby reserve/finalize/select, all ring choices with Ring1 and Ring2 round trips, exact duplicate-name rejection, one normal deletion with fresh-login absence, all five Gladiator starter slots plus each distinct starter-main-hand round trip, source-routed Coming to Ul'dah scenes 0/1/2, active sequence 255 and opening scenes 40→30 after restart | Starting classes, ring/accessory branches, deletion and quest acceptance verified; giver-to-recipient corridor blocks turn-in/rewards and that opening's private-to-public travel; appearance breadth and other cities/classes remain uncovered |
| Isolated DB/config/processes / non-GM accounts / real sessions | Private MariaDB, unique schema/ports, staged binaries, rank-zero observations, sessions required | Locally live-verified on Windows and containerized Ubuntu 22.04; hosted deployment unverified |
| Movement / independent observer / semantic route API | Observer verifies movement/despawn; both bots walk a 322-waypoint quest route | Curated routes verified, not general navigation |
| Compatible navigation assets | Separate TSET generation, complete sampled corridors; private server mesh root and live `NAVI` initialization for territories 130/141 | Verified for two quests and the selected exit; Due Diligence disconnected |
| Versioned route/scene data | Private generated catalog v1; explicit Motivational Speaking, Gil for Gold, opening ring and Coming to Ul'dah acceptance choices | Four live verified adapters; Due Diligence and Coming to Ul'dah completion remain route-blocked |
| Interact / choose dialogue / unknown-scene failure | Exact received event/scene/token; no default choice or raw-packet control; contract tests | Verified for supported one/two-result returns |
| Quest state / accept and cancel / completion | `test_live_quest.py`: Motivational Speaking (65686), cancel unchanged, accept sequence 255, completion | Verified |
| Received inventory/currency/XP model | `RewardsState.cpp`: initial snapshots, deferred successful transactions, class-index and incremental XP; exact 0→28 gil sale then 28→20 gil purchase deltas and persistence | Unit verified; live item/XP/nonzero-currency state verified for the bounded transactions |
| Exact quest rewards | Independent authored expectation: 50 XP and two items 4551, no other tracked bag/currency change | Verified |
| World restart and fresh login | Position, completed flag, absent active quest, XP and tracked bag quantities checked after restart | Verified |
| More quests / zoning / inventory operations / combat / social | Two-quest chain, optional reward, reconnect, persisted ordinary-bag whole-stack move, occupied-slot swap, partial split, same-item merge, discard, persisted round trips for all five Gladiator starter slots, all three starter main hands, all four source-defined Ring1 and Ring2 choices plus one exact gil-shop sale/three-item purchase/VFX action/liquidation/three-stage later-gear purchase/resale/equip path; ordinary Say, exact same- and cross-zone nonparty plus cross-zone party direct Tell and a received three-client party decline/reinvite/join, leadership-transfer, kick and explicit-disband lifecycle with exact same-zone fan-out and bidirectional cross-zone party chat; bidirectional 130↔141 physical crossing/persistence; one enemy defeat with persisted EXP/loot; independently observed living Return, Sprint status/TP debit, Pugilist Bootshine, six-defeat level-two progression, True Strike, Thaumaturge Blizzard, 18 four-attacker level-14 defeats with shared persisted rewards and one naturally earned Fast Blade→Savage Blade combo; one source-bound unprovoked active-vision aggro/defeat path; one pursuit/leash position-and-health reset/re-engagement/player defeat plus observed/persisted homepoint return and unchanged tracked EXP/level/currency/items/inventory | Representative subset verified; arbitrary shops/quantities, other later gear and positive direct currency-container moves (generic moves are rejected), alliances/free companies/linkshell channels, general aggro/leash policy beyond the two exact source-bound paths, combo chains/other combos, broader abilities and general combat remain uncovered; level-one off-hand/waist purchases, shop-funded overflow-merge inputs and supported consuming-item shop paths are source-shop-blocked under the evidenced economy; raise is blocked by absent normal offer/execution semantics |
| Range/discovery/territory event triggers | Curated bidirectional physical ExitRange crossings, bounded source-defined Ul'dah enter-territory operation, source-LGB opening WithinRange scene 20, and two source-LGB Central Thanalan map discoveries (sphere and rotated box) | Exact represented paths are verified; general adapters remain missing |
| Yield/resume and broader scene variants | Explicit unsupported yield capability; fixed one/two-result quest returns plus source-bound scene-40 gil-shop sale/purchase returns | Yield missing; broader variants uncovered |
| Deterministic authored regression suite | Fifteen allowlisted live cases, native tests and Python contracts | Supported suite verified in a clean combined gate |
| Seeded exploration / preconditions / invariants | `support/workload.py`, reproducible allowlisted decisions, server/state checks, independent per-waypoint observers and one bounded fresh-session corridor replan | Two-bot exploration verified; narrow supported-state coverage |
| Bounded soak / ramp / metrics | 2..32-bot controller, <=1000 actions, explicit budget/minimum span/pacing; continuous received liveness; process RSS/private-commit/CPU and action timings | Eight bots / 488 actions over 1805s and full replay verified; observed autosave allocation retention fixed; not capacity, universal leak-freedom or overnight evidence |
| Semantic replay | Versioned allowlisted plans, route hash, logical roles and all recorded execution limits | v1 exploration and v2 paced soak replay verified; scheduling is not deterministic |
| Failure minimization | `run_minimize.py`: bounded fresh-environment delta reduction with exact normalized action-failure equivalence, semantic revalidation and cleanup evidence | Verified for an unpaced deterministic deadline failure; paced plans deliberately excluded |
| Deadlines / cancellation / cleanup | Timers, owned-process teardown, redaction, Windows sharing retries; bounded profile deadline scale 1..3 is recorded and adds no retry/sleep; final movement publication waits for its asynchronous zone-socket write; workload cleanup precedes diagnostics and survives sampler/write exceptions | Synthetic faults, a controlled live diagnostic-write failure, one intentional owned-world termination, and a clean scale-1 Windows gate verified; broader stress/signal testing remains |
| Action/event/server logs / hashes / JUnit | Bounded sanitized journals; runtime/module/worker/catalog/mesh identities | Implemented; hashes do not prove independent compatibility |
| Asset-independent CI | `.github/workflows/test-client.yml` | Authored; hosted run unverified |
| Provisioned gameplay CI | `gameplay-e2e.yml`, `sapphire_gameplay_ci` build target, `run_ci.py`, `CI.md` | Authored; current isolated fifteen-case Windows gate passes, older nine-case Linux gate passes, but the current expanded Linux gate remains red under observed delayed scene/action/logout/zoning delivery; hosted execution/runner controls unverified, no registered runners |
| Independent real-client/golden trace compatibility | Unmodified 3.3 DX11 pilot and committed manual lane: world entry, received movement, bidirectional Say and normal logout; isolated Sandbox | Narrow independent lane live-verified; broader UI/quest compatibility and normalized golden traces remain uncovered |
| Full objective | Missing rows above remain | **Not achieved; do not complete goal** |

## Explicit plan-to-artifact closure checklist

This checklist maps the normative implementation and acceptance statements in
`autonomous-testing-plan.md`, including requirements that are easy to lose in the
higher-level table. **Partial** and **blocked** entries remain open requirements;
a nearby passing test does not close them.

| Plan area | Concrete evidence | Verdict |
|---|---|---|
| External architecture; no embedded/GM shortcut | `src/test_client`, `support/environment.py`; all journeys use loopback HTTP/TCP, encrypted lobby handoff and rank-zero sessions | Verified for supported actions |
| C++ worker + Python/pytest + JSON-lines control | `sapphire_test_client`, `support/worker.py`, pytest scenarios; control version 1 with request and bot IDs | Verified |
| One/two-bot start before scale-out | Authored one-to-three-client tests precede bounded 2..32-bot workload policy | Verified; maximum live evidence is 16 bots, not 32 |
| Versioned wire schemas and explicit direction | `Protocol.h/.cpp`, profile `sapphire-3.3`, protocol CTest byte-offset/layout fixtures | Verified for decoded/encoded subset |
| Split/coalesced TCP stream assembly and parser bounds | `sapphire_protocol_tests`; split/coalesced, malformed length, packet-count and frame-size cases | Verified; compressed frames explicitly unsupported |
| HTTP, encrypted lobby selection and normal handoff | `Client.cpp`, rejected-login/live-login tests and creation journey | Verified |
| Zone/chat startup, both keepalives, logout and reconnect | live smoke, zoning, workload reconnect and fresh-login scenarios | Verified |
| Explicit disconnected/loading/ready/zoning/closing lifecycle | worker state snapshots and phase guards; live zoning/logout assertions | Verified for represented phases |
| Bounded queues, deadlines and cancellation | 64 KiB control limit, two-frame send-queue cap, bounded journals, monotonic Python/native timers, recorded deadline scale 1..3, asynchronous final-movement write completion, and explicit `close`/`remove` cancellation of timers/sockets | Verified; timed-out operations are never retried and owned teardown cancels the worker |
| Useful error classes | protocol/invalid-request worker errors; setup, assertion, worker-death and owned-process exit distinctions | Verified at harness boundary and for one live owned-world termination; not a universal server error taxonomy |
| Do not copy authoritative server gameplay | Worker uses shared low-level definitions/crypto only and has no world-service linkage or handler calls | Verified |
| Identity, territory/loading, conditions and channel health | snapshots plus liveness/checkpoint policy | Verified for modeled fields |
| Nearby actors, spawn/despawn and received positions | observer smoke, zoning, combat and defeat scenarios | Verified |
| Quest, event and scene state | active/update/completion decoding and exact event/scene/token identity | Verified for catalogued scenes |
| Inventory, currency and experience state | `RewardsState`, live reward/inventory/shop/equipment evidence | Verified for enabled containers/transactions; broader operations open |
| Predicted versus received state | separate `predicted_position`/`observed_position`; route completion explicitly says observer proof is required | Verified |
| Ordered journal and race-safe waits | sequenced bounded worker events; Python state/event versions registered before triggers | Verified |
| Base/layout/runtime identity separation | versioned catalogs bind source actor/event IDs and resolve received runtime entities | Verified for catalogued content |
| Core semantic API | login/select/world-ready/logout, movement, interaction, scene choice, quest/reward expectations are wrapped above raw packets | Verified for supported subset |
| Later combat/social/transition/instance API | natural combat, Say, exact direct Tell, a full-roster party lifecycle, same-/cross-zone party chat and one bidirectional physical zone-transition pair are live | **Partial:** instance entry is absent; combat/social/transition breadth is narrow |
| Action preconditions/transitions/deadlines/diagnostics | native guards, Python predicates, per-action timeouts and journals | Verified for enabled methods |
| Scene adapter: approach→interact→observe→choose→finish→state | live quest, shop and opening scenarios use explicit catalogs and received identities | Verified for supported one/two-result and opening chains |
| Unknown scenes fail closed | worker/policy contracts; workload invariant rejects any unexpected scene | Verified |
| Yield/resume scene exchange | Server logs prove quest yield is unimplemented and no established resume packet/result exists | **Blocked; unsupported capability is explicit** |
| Range/discovery/territory triggers | bidirectional physical ExitRange crossings plus source-bound enter-territory, opening WithinRange and two Central Thanalan discovery operations | **Partial:** exact sphere and rotated-box discovery paths are verified, but general adapters are absent |
| Curated waypoint stage | independently observed quest/shop/transition/pursuit routes | Verified |
| Navmesh routing for selected territories | matching TSET catalogs/meshes for territories 130 and 141; disconnected/off-mesh routes fail closed | Verified for selected corridors only |
| Content-aware transitions/doors/dynamic obstacles | one source-defined bidirectional exit pair is crossed | **Partial:** normal dynamic-door code is instance-bound and currently blocked by unavailable normal instance entry; debug obstacle toggles are not evidence |
| Plausible movement cadence, direction and stopping | 100 ms interpolation, bounded speed, computed heading and terminal stop flag; independent position receipt | Verified for curated routes; no real-client movement-trace equivalence claim |
| Progress watchdog and bounded replanning | workload movement requires every waypoint from an independent observer; exploration permits one recorded fresh-session replan only from the same curated corridor, while soak/regression fail without recovery | Verified for bounded workload navigation; no general-navigation replanner claim |
| Independent navigation validation | witness clients and narrow graphical-client movement pilot supplement server-derived geometry | Verified narrowly, not general path correctness |
| Authored regression mode | strict fifteen-case allowlist plus native/Python contracts | Verified for supported suite |
| Seeded exploration mode | v1/v2 plans, allowlisted preconditions, decisions, observations and replay | Verified for walk/Say/heartbeat/reconnect subset |
| Soak/load mode | bounded ramp/pacing/actions, liveness and process/worker resource samples | Verified as bounded smoke and 30-minute low-rate evidence; not capacity/overnight proof |
| Record actual actions, not seed alone | plan/outcome/checkpoint journals retain semantic order, limits and observations; replay warns that scheduling is nondeterministic | Verified |
| Preserve and shorten a useful failure | fresh-environment exact-signature minimizer and retained live deadline failure | Verified for unpaced semantic-plan failures only |
| Disposable DB/ports/workdirs/credentials | per-test MariaDB schema/process tree and generated secrets/config | Verified on local Windows and Linux gates |
| Repository initialize/migrate tooling and fixture version | DB manager install/update, migration call, manifest fixture version | Verified |
| Non-GM/full-session config; hot swap disabled | generated `DefaultGMRank=0`, `AllowNoSessionConnect=false`, hot swap false | Verified |
| Creation journey plus faster pre-provisioned fixtures | normal four-account lobby creation case and separately labeled pre-connection character fixtures | Verified for Ul'dah subset |
| No live DB mutation/assertion shortcut | fixture SQL occurs only before first connection; journeys use protocol and restart reload | Verified by code path for enabled scenarios |
| Independent scenarios and no cached reset | each case creates/removes its owned environment; world is stopped before preserved-DB restart | Verified |
| Observation hierarchy | acting-client messages, independent observers, reconnect/restart and diagnostic-only DB checks are separated in scenarios/artifacts | Verified |
| Monotonic waits and application readiness | condition/event waits; world binds only after data/territory/script setup and clients require received world-ready | Verified |
| Record build/script/fixture/protocol/data/nav identities | gate manifest and summary hashes; game assets remain private | Verified; hashes identify inputs but do not prove compatibility |
| Step/run timeout and failure cleanup | worker, action, pytest/workload budgets; cleanup-fault matrix and `cleanup_verified` gate | Verified for tested failure modes; host-kill behavior remains infrastructure-owned |
| No ambiguous retry of gameplay mutations | timeout marks worker failed; no automatic gameplay retry; receipts are not mutation proof | Verified |
| Regression versus recovery behavior | strict gate rejects process loss/skips; reconnect occurs only in explicitly authored scenarios/plans | Verified |
| Reviewed capability/skip accounting | capabilities advertise unsupported surfaces; strict gate rejects skipped/missing/duplicate/foreign cases | Verified |
| Independent packet/client compatibility | byte fixtures and one unmodified 3.3 DX11 world/movement/Say/logout pilot | **Partial:** no normalized golden trace and no graphical quest/scene agreement |
| Stage 0 feasibility record | READMEs/catalogs document assets, selected quests, states, scene results and explicit unknowns | Verified against headless runtime; known-good graphical quest transcript remains absent |
| Stages 1–4 acceptance | repeated login, observer movement, persisted quest and selected regression actions with CI reports | Verified for declared subset |
| Stages 5–6 acceptance | readable replay/minimization; action latency, disconnect/liveness, resources, cleanup and load-generator utilization | Verified for narrow bounded workloads; no capacity claim |
| Public/unprovisioned CI tier | `.github/workflows/test-client.yml` | Authored and locally validated; **hosted run unverified** |
| Provisioned trusted CI tier | `.github/workflows/gameplay-e2e.yml`, protected-runner contract, Windows/Linux local rehearsals | Authored/local only; **blocked by no registered authorized runner** |
| Scheduled exploration/soak tier | local workload commands and artifacts | **Partial:** no authorized hosted scheduled execution |
| Manual/scheduled real-client tier | policy plus completed isolated manual Sandbox lane | Verified once locally; no scheduled breadth |
| Untrusted-code isolation/approval | `CI.md` requires workflow-scoped ephemeral VM, protected environment and disposal | Documented; **hosted enforcement unverified** |
| Failure identity, expectation/action/timing and versions | manifests, action plans/outcomes, pytest/JUnit and bounded state dumps | Verified |
| Correlated logs/journals/crash diagnostics | redacted API/lobby/world/DB/worker logs, bounded decoded journals and structured unexpected-process-exit metadata are retained | **Partial:** one owned-world termination is verified, but platform crash dumps are only retained where externally produced |
| Fixture/persistence evidence, redaction, JUnit and summary | scenario JSON snapshots, restart state, redaction contracts, `live.xml` and CI JSON summary | Verified |
| Bounded soak logs and generator saturation | capped plans/journals, checkpoints, action percentiles and API/lobby/world/DB/worker/runner resource samples | Verified; scenario coverage remains reported separately from concurrency |
| Initial design decisions | Headless primary + separate real client; Python; 3.3 profile; Ul'dah/Motivational Speaking; local-first; regression then bounded exploration/soak | Resolved and documented |

## Verified results

- Clang/Ninja and MSVC/Visual Studio: six CTest executables pass (protocol,
  rewards, combat, synthetic navigation, borrowed database bindings and concurrent item-ID allocation). Navigation tests reject disconnected and
  off-mesh destinations rather than accepting a partial Detour path.
- GNU 11.4/Ubuntu 22.04: the full `sapphire_gameplay_ci` target and all six CTest
  executables pass. The older strict nine-case Linux live gate remains green, but
  the current expanded fifteen-case Linux gate is not green; it is not counted as
  platform gameplay verification.
- **281** Python worker/policy/CI/pacing/resource-control contracts pass with the
  current MSVC worker; 17 asset-backed cases skip without an explicit live profile.
  All six native suites pass under current MSVC and GNU builds. The attempted local
  Clang worker path was absent, so no new Clang result is claimed here.
- The current strict **fifteen-case Windows** gate at `e34d695fd` passed all cases in
  **3334.527s** with deadline scale 1, exact collection, all fifteen per-case staged
  manifests matched, clean source, and complete process/runtime cleanup. Evidence:
  `.e2e-artifacts/ci-current/gameplay-ci-bi18aeo4` and
  `build-e2e/ci-summary-windows-isolated.json`; summary SHA-256
  `665328be156fff96479a9ad94ee753c1dc59c05a12a345d93374eddb9562ff05`,
  private gate-diagnostics SHA-256
  `18b93604cc95270713efbf39157e2bddcac9a139dbe8ea008adddd2b77df9863`.
- The latest successful strict Linux evidence remains the nine-case rehearsal at
  `4bbf7ec9a` (1009.57s, `gameplay-ci-kekux1o4`, summary
  `build-e2e/ci-summary-linux-gameplay.json`). A current GNU-worker expanded run at
  `e34d695fd` used fifteen fresh environments inside an isolated Linux network
  namespace and deadline scale 3. Collection, staged-input identities, and cleanup
  all verified, but only seven gameplay cases passed; delayed scene/event completion,
  logout acknowledgement, cross-zone liveness, combat results, and return/zoning
  transitions failed their bounded semantic deadlines. It is retained only as
  blocker evidence at `.e2e-artifacts/linux-native-current/gameplay-ci-51vqgda3`
  and `build-e2e/ci-summary-linux-native-expanded-failed.json` (summary SHA-256
  `ecb088df8ea527f185d2d8be2aaec71029ed9bb6fd49266b7650a9a862970f79`).
  Docker Desktop and native-WSL variants were also tried; increasing deadlines and
  moving game data off the host mount did not produce a green expanded gate, so no
  further blind rerun or Linux compatibility claim is made.
  `actionlint` v1.7.7 validates both client workflows. Read-only GitHub API inspection
  found zero registered self-hosted runners; no runner/settings were created.
  See `tests/e2e/CI.md` for mandatory workflow-scoped runner access restrictions,
  protected-environment approval and VM disposal responsibilities. Local rehearsal
  does not prove hosted approval, cancellation cleanup or independent compatibility.
- Fifteen live cases pass in one strict Windows gate across fresh per-case environments: rejected credentials, login/idle/logout, received
  party join/leave, observed movement/Say/position persistence, single quest, chained quests plus inventory
  persistence and one persisted gil-shop sale/purchase pair, zoning/discovery/cross-zone-party persistence, observed living Return, enemy defeat/rewards,
  natural level-two and level-four progression plus one exact combo, unprovoked source-bound active-vision aggro/defeat, player defeat with independently observed pursuit/leash/reset, source-bound
  homepoint return and unchanged tracked reward/inventory state, and normal lobby creation spanning all four
  Ul'dah ring choices and all three starter classes plus persisted opening/equipment checks. Both public tested territories use compatible
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
  persisted current-test-table loot/EXP, independently observed Pugilist Bootshine,
  independently observed Thaumaturge Blizzard and source-bound living Return. Later
  increments cover one naturally earned Fast Blade→Savage Blade combo and one player
  defeat/homepoint return with exact exposed reward/inventory state unchanged. Broader
  abilities, general cooldown scheduling, general aggro/leash policy beyond one
  active-vision and one initiated-pursuit path, raises,
  unexposed penalties and production loot selection remain uncovered.
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
  persisted partial split/no-overflow merge and one source-bound non-consuming VFX
  item action; consuming item mutation remains uncovered. Clang,
  MSVC and GNU pass the byte-layout/state tests.
- `test_live_zoning.py` crosses exit 2377056 from territory 130 to 141 after a
  41-point/18.64m walk. A source observer stays outside the trigger and observes
  departure; a destination observer sees arrival and chat. Both channels remain
  alive; territory/position/rewards survive restart. The transition generator now
  also resolves the sole enabled source-LGB discovery sphere containing arrival:
  layout 3643706, map 21, part 1. The bounded client accepts that exact range only
  from a finite received position inside its source volume, permits one request per
  session, receives the exact map/part reply and exact source-derived 15 EXP, then
  proves discovery bit persistence from fresh PlayerStatus after world restart.
  This is not acknowledgement-as-mutation proof: the clean run journals a reply
  first and an independent fresh-login `discovery_state` later. Run
  `sapphire-e2e-be9syxf4` passed in 55.52s at revision `38dc3b2db`; manifest SHA-256
  is `fd5bc9da699e3d4f5b46c558d0135485bc716e099e2151243adb45eda03ae820`, event
  journal SHA-256 is `8bccb4669335ff70bfff250d0fe4d7ba9a278a93ec8214ba603843e59c949e6d`,
  `dirty=false`, and its private runtime was removed.

  At `fff4f6a7a`, the same journey continues over a source-navmesh 731-point,
  347.457m route to source-LGB rotated box 4204061 (map 21, part 3). A fourth
  client at the endpoint independently receives the traveler within 0.15m; that
  witnessed position must also match the actor's predicted endpoint before the
  exact normal request is constructed. The independently observed arrival position
  similarly gates part 1. Distinct exact replies yield source-derived cumulative
  30 EXP, while a fresh login after world restart—not either reply—proves discovery
  parts `[1,3]` and endpoint persistence. The client rejects unknown layout/part
  pairs, repeated parts, malformed/off-volume positions and witness/endpoint
  disagreement. Exact sphere/box request bytes and catalog identity, route length,
  endpoint and w1f2 mesh contracts pass with Clang, MSVC and GNU. A failed 240s
  route-budget hypothesis remains preserved; no automatic retry or recovery was
  added. The clean case passed in **302.66s** at
  `.e2e-artifacts/discovery-live/sapphire-e2e-qc4pa4el`; manifest SHA-256 is
  `db41b278a741112b93321b0503b881092b9bc52b2061f1686ae303bed1be00f8`, dual
  discovery artifact SHA-256 is
  `58f8bc182e401cab62b53de4cdefb7b2d4f6113d2266a278e2fb82fc31ddc703`, and
  bounded event-journal SHA-256 is
  `3375fae3a5762c388545d92ce90f6336ddf4e17b622f1032a3c6fe2bb762e8b3`.
  At `1be6fc6dc`, the journey continues from part 3 over a second complete
  source-navmesh route to exact reverse exit 2372269. The 755-point route is
  **359.629710m** and begins at the independently witnessed discovery endpoint;
  every requested waypoint is received. The existing Central Thanalan observer
  independently sees the traveler inside the conservative reverse-exit volume.
  The bounded action accepts only the exact 141→130 source tuple (exit 2372269,
  destination pop 2377058) in addition to the exact existing 130→141 tuple, and
  rejects mismatched territory/exit/pop bindings. The source observer, already
  independently identified before the outbound crossing, receives the returning
  traveler at public-Ul'dah pop `[40.215672,4,-148.808304]`, exact Say and later
  departure. Both channels advance after return. A world restart and fresh HTTP/
  lobby/world session—not the zone-jump request—prove territory 130, exact arrival
  position, both discovery bits and unchanged 30 EXP. The clean focused case passed
  in **561.87s** at `.e2e-artifacts/discovery-live/sapphire-e2e-1sybq9ei`;
  manifest SHA-256 is
  `486eb2cb442a12659f0c996fba6df0888e5afbc28623b9c2633a9a7eb82f83c6`,
  `bidirectional-transition.json` SHA-256 is
  `bcef1764d5c0e253c497fe00fdaf87833710ba31e05e60a5725af1172d7ef4e6`,
  discovery artifact SHA-256 is
  `93be66c13159456b1f98476326263463c5dfe997c441c1a508f0ec5c7ec47680`, and event
  journal SHA-256 is
  `a659ca49605aa8724b81b08f0a688641b85987d883e040305d7b3f37849166f8`.
  The source is clean and runtime removal is confirmed. This proves one exact
  bidirectional public-territory pair, not general exits, doors, dynamic obstacles
  or the private opening-territory route.

  A source audit bounds the missing navigation stage rather than substituting a
  debug toggle. `EventObject::setCollisionEnabled()` does update Detour box/sphere/
  cylinder obstacles, and normal instance code uses it: Sastasha's hidden door is
  disabled only after the Chopper encounter reaches `SUCCESS` and the ordinary
  touch event runs. `Encounter` also owns lockout collision transitions. Those
  actors and state machines exist inside instance content, while the current
  normal duty path remains unavailable: `findContent` trusts an arbitrary requested
  territory and `cfDutyAccepted` still logs `TODO: Duty accept`, with no received
  unlock eligibility in the fixtures. The only direct open-world obstacle toggle
  found is `DebugCommandMgr`'s debug `obstacle` command. Entering Sastasha through
  the trusted duty request, fixture placement or the debug command would therefore
  violate the E2E boundary. Door/dynamic-obstacle coverage is source-blocked until
  normal unlock, matchmaking/acceptance and instance-entry semantics are complete;
  the physical exit pair is not a door proxy.

  The first expanded strict
  gate preserved a 9/10 failure: longer world uptime let the source-layout defeat
  target roam 11m before the fighter connected, exposing a stale same-spawn-point
  assumption. At `56911f505`, initial selection binds the exact source layout and a
  <20m received position independently seen by the observer, then uses the existing
  bounded witnessed follow. The targeted case passed in 146.44s and the subsequent
  strict gate passed 10/10. This verifies two exact range shapes/parts, not general
  map-range evaluation.
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
- `a1b8ee21f` adds received progress checks at every workload waypoint rather than
  accepting only a sent route or final prediction. Exploration alone may recover
  once through normal logout and fresh HTTP/lobby/world authentication, and only
  when the witness and reloaded positions resolve within 0.75m of the same curated
  route. The outcome retains the original stall, positions and resume waypoint;
  a second stall, identity change or off-corridor position fails. Soak never
  retries. Three dedicated contracts cover successful one-shot recovery, zero-retry
  soak failure and second-stall failure. **255** Python contracts pass with Clang,
  MSVC and network-isolated GNU workers. At clean revision `fa5261ef2`, a normal
  two-bot/12-action exploration exercised the per-waypoint watchdog without recovery
  and passed in 30.343s of action span with `dirty=false` and runtime removal
  (`sapphire-e2e-5txfcfcn`); its `result.json` SHA-256 is
  `94335064b37888ccadfe4df42c96fe488b82f86865ff1ff563a55eed6924c2c8`.
  The bounded recovery path is contract-verified, not claimed as a live injected
  network-fault result.
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

## Received party lifecycle

At `465dc9d66`, two normal non-GM clients independently receive each other's exact
spawn entity/name before the leader sends a bounded normal party invitation. The
member accepts only the exact pending character-ID/type/result/name tuple received
from the server. Both clients then independently receive the same nonzero party ID,
leader index and exact two-member entity/character/name roster. The member sends a
normal leave request only from received self-membership; because this is a
source-server two-member party, both clients receive the resulting empty disband
state. No invitation receipt is treated as membership proof. Exact invite, accept
and leave byte fixtures and malformed/unobserved rejection contracts pass with
Clang, MSVC and GNU. The clean live case passed in **27.62s** at
`.e2e-artifacts/discovery-live/sapphire-e2e-zlc5dlwq`; manifest SHA-256 is
`be39e5187670bc5c43128a595ca7b07b71c186b9ff11bedf36298303aff69d10`, event
journal SHA-256 is
`20af0eded10445ad9edd8c494802410e1fd9b67afb3816aee72bee619797ef37`,
`dirty=false`, and the private runtime was removed.

At `0545efdf4`, the zoning scenario retains that exact party while the leader
physically crosses from territory 130 to 141. Both clients preserve the same party
and member identities. Each independently receives its own exact territory and the
server's explicit zeroed-detail representation for the remote-zone member, after
which both receive disband state. The first run correctly rejected an invalid
assumption that asynchronous cross-zone party entries expose the remote territory;
that failed diagnostic remains preserved rather than weakening identity checks.
The clean case passed in **55.97s** at
`.e2e-artifacts/discovery-live/sapphire-e2e-bphktcjy`; manifest SHA-256 is
`bb67ef03eb5216b03d5d41ae05dcd51bf2978d28ceeb1c28157daf071a42c546`, event
journal SHA-256 is
`9dfaa593eb0cf57c5b83a8b6af6899258805b85fa09989ba3a6a7fac44fcb856`,
`dirty=false`, and runtime cleanup is confirmed.

At `5758d9208`, party state also retains the exact nonzero chat-channel identity.
The sender may construct a normal chat-channel request only from received self
membership and that exact channel; empty, oversized, non-printable, debug-command,
zero-channel and non-member requests fail closed. The receiver decodes the separate
chat connection and accepts a message only when channel, party ID and the sender's
entity/character/name all match its own received roster. Both directions are
independently received in the local lifecycle and again after the clients occupy
territories 130 and 141. Exact request bytes and rejection contracts pass under
Clang, MSVC and GNU. One MSVC exact-byte failure exposed unspecified structure
padding in the character-deletion helper; explicitly zeroing the complete sent
wire object made the existing fixture deterministic rather than weakening it.
The combined clean cases passed 2/2 in **55.60s** at
`.e2e-artifacts/discovery-live/sapphire-e2e-rqiisz2h`; manifest SHA-256 is
`ad4f6872670ebe34491c9102a64b11d2d56a4ae78410a07dbb8b8e3b1c8bfa94`, local
party journal SHA-256 is
`f5a8ea88b1566b38f17bd9c63e7975eecb49a21bd7aee927d250973a36b91291`, and
cross-zone journal SHA-256 is
`6f338e2aad4bd137931a8055456eb44412f1df315f27f15dfdc66a7b0b9579dd`.
The source is clean and runtime removal is confirmed.

At `11b70e6cb`, the first exact pending invitation is instead declined with the
normal reply operation. The member receives exact auth-type/deny/inviter-name result,
the leader receives exact rejected member character-ID/name/type/result, and both
remain ungrouped. A second bounded invite is then independently received and
accepted before the existing roster/chat/leave assertions. Exact decline bytes and
wrong-type/result rejection contracts pass on Clang, MSVC and GNU. The clean case
passed in **26.29s** at `.e2e-artifacts/discovery-live/sapphire-e2e-7yyuk4wm`;
manifest SHA-256 is
`619095332fcebf24c020645d89b92b94d691b6dbed038a919c322f1788329337` and event
journal SHA-256 is
`4a9a8470a0bdecc37f3e112cdbb6eca6047bac73031d1967a7adefc568634980`.
The source is clean and runtime removal is confirmed.

At `25e13e4ea`, the received leader may send another bounded invite while grouped;
a nonleader cannot use that path. A third exact observed player accepts, all three
clients independently receive the same original party ID/channel and exact
three-member identity roster, and one normal party-chat message from the newcomer
is independently received by both existing members. The newcomer leaves and
receives empty state while both remaining clients receive the original exact
party/channel and two-member roster before final disband. The first attempt's
hard-coded two-member acceptance wait was preserved as a failed diagnostic and
replaced with an explicitly bounded expected roster size, not a weaker assertion.
Clang/MSVC/GNU protocol and Python contracts pass. The clean case passed in
**27.49s** at `.e2e-artifacts/discovery-live/sapphire-e2e-l0coz4w0`; manifest
SHA-256 is `75e7db086985d99be6865cdbfd78ef0e2fc8469615c8b64361e3be8b92483589` and event
journal SHA-256 is
`39ca5cc85558a008164df4af46464c38c2623471932d98e9e9518fa6e68ac68a`.
The source is clean and runtime removal is confirmed.

At `3f817ee61`, the exact received leader transfers leadership to an exact other
roster member through the normal operation. All three clients independently retain
party/channel/roster identity and receive the leader index changing from 0 to 1.
The former leader's attempt to construct another invite fails locally because its
received roster no longer marks self as leader; no unauthorized request is sent.
After the third member leaves, both remaining clients retain the transferred leader
identity through the two-member state and final disband. Exact target-name bytes,
nonleader and wrong-target rejection contracts pass on Clang, MSVC and GNU. The
clean case passed in **27.94s** at
`.e2e-artifacts/discovery-live/sapphire-e2e-a3b_shu2`; manifest SHA-256 is
`7831c9e86f6781b12ee722c8d1ce038997dd24c35c9586d3d7e267cc4fa7e3c4` and event
journal SHA-256 is
`04d057e20956d5cd47d1ed46962539759bb9e63d22276440dab4ae0c8bf48116`.
The source is clean and runtime removal is confirmed.

At `66e3102a6`, the transferred received leader removes the exact third roster
member with the normal kick operation. The former leader's same attempt fails
locally from its received nonleader state; two-member rosters are also rejected by
the bounded API rather than conflating kick with disband. The removed client
receives exact empty party state, while both remaining clients independently retain
the original party/channel, transferred leader and exact two-member identities.
Exact target-name bytes plus nonleader, two-member and wrong-target rejection
contracts pass on Clang, MSVC and GNU. The clean case passed in **27.64s** at
`.e2e-artifacts/discovery-live/sapphire-e2e-rzm5oed6`; manifest SHA-256 is
`5df7d60e71a20ceb52f88463dffecee02b315a83e3851ee98085ec8f48c71d2a` and event
journal SHA-256 is
`1de5f6a9750617f0b4a56af096bb0a0135d5bf3539326b3e1b2b58533f548457`.
The source is clean and runtime removal is confirmed.

At `0eed41656`, after kick leaves the exact two-member roster, the transferred
leader sends the explicit normal disband operation. The former leader's same action
fails locally from received nonleader state. Both clients independently receive
empty party state; this is distinct from the earlier implicit two-member disband
caused by leave. Exact zero-reserve bytes and nonleader rejection pass on Clang,
MSVC and GNU. The clean case passed in **28.33s** at
`.e2e-artifacts/discovery-live/sapphire-e2e-sabonb13`; manifest SHA-256 is
`2006685064792d9f1522da97d9eda52688f641f497233ee880751c9a0f8c9c8d` and event
journal SHA-256 is
`b780d07b48e2114cff5c9f0d2e93140b534835950620eb3f52b7ccf64e0f76ca`.
The source is clean and runtime removal is confirmed.

At `6fc3c74b7`, the transferred leader normally re-invites the removed third member
and then five more exact observed clients, with each acceptance bound to the exact
expected roster size from 3 through the protocol limit of 8. All eight clients
independently receive the same original party ID/channel, transferred leader and
exact full identity roster. A message from the eighth member is independently
received by the other seven. The leader receives an exact ninth nearby player, but
the client fails closed at count 8 and sends no invite. Explicit disband then yields
empty state on all eight. The clean case passed in **32.87s** at
`.e2e-artifacts/discovery-live/sapphire-e2e-t4izk_fz`; manifest SHA-256 is
`ebc3fe02b05d7d039288a08714e90408c93bf671ef016afc507edf709bca83d5` and event
journal SHA-256 is
`6729372c37849b922e0f62f03711ab374ed2a3d15da3c2a90432c348975ce830`.
The source is clean, runtime removal is confirmed and the full Python contract
suite remains 256 passed/10 live skips. This proves the source protocol's roster
limit, not server capacity.

At `013906289`, the eighth member normally logs out. The first run preserved a
failure showing all peers still received territory 130 because `Session::close()`
announced the party disconnect before publishing `connected=false`. The fix
publishes offline state first; it does not remove or fabricate membership. All
seven peers now independently receive the same full roster and identities with
that member's detailed territory redacted to zero. A fresh HTTP→lobby→world session
for the same ordinary account restores the same entity, party ID/channel, full
roster and territory-130 detail on all peers, after which its party chat again
reaches all seven. Explicit disband still clears all eight. The corrected server
and contracts build under Windows Clang and GNU/Linux; MSVC, Clang and GNU worker
contracts report 256 passed/10 live skips. The clean live case passed in **38.46s**
at `.e2e-artifacts/discovery-live/sapphire-e2e-_j0vorao`; manifest SHA-256 is
`81ab8dc5b958a44bb9ec5bdc3e5423bd69311759f2039398f7eca27fa3ef4a51` and event
journal SHA-256 is
`328421c201f6ef8518c360fc51019642a3aba1c411cb615b58e11ad736940d47`.
The source is clean and runtime removal is confirmed.

At `235989a3b`, each initial party member sends a normal direct Tell to the other's
exact received player entity/name. The request is restricted to exact current
party/spawn membership and 1..128 printable non-debug text. The receiver decodes
the separate chat connection and accepts only a non-GM sender whose character ID,
name and derived entity match exactly one received party member and player spawn.
Both directions are independently received with exact text. The first run preserved
an `unknown client IPC (0064)` failure from incorrectly using the world channel;
the corrected implementation uses Sapphire's registered chat channel rather than
weakening the receive assertion. Exact opcode/type/target/message bytes and
unobserved/wrong-name/debug rejection pass on Clang, MSVC and GNU. The clean case
passed in **36.10s** at `.e2e-artifacts/discovery-live/sapphire-e2e-xugcmq3a`;
manifest SHA-256 is
`07ba1bcbe5da74f26a4ea420c1fe84bbe18ef2ce78e63a69a1c6fd86b48859c7` and event
journal SHA-256 is
`0d1473a37ca16ae265d6bd0082f30a39dac2c879b1fc09091cb70b4221b57050`.
The source is clean and runtime removal is confirmed.

At `71faf44aa`, the full-roster reconnect path also exercises the unavailable Tell
result after ordinary logout. Seven peers first receive the exact member identity
with territory zero and the sender independently receives the target despawn; only
that matching offline party identity can be requested. The sender then receives
`FFXIVIpcTellNotFound` on the same chat connection with the exact target name before
the existing fresh-session reconnect. Initial diagnostics preserved both an opcode
collision from decoding `0x66` outside the phase-bound request and a timeout from
incorrectly watching the world connection; the final decoder is request-phase-bound
to the chat connection. Online/offline mismatch and stale-spawn contracts pass on
Clang, MSVC and GNU. The clean case passed in **36.86s** at
`.e2e-artifacts/discovery-live/sapphire-e2e-53vnt0pf`; manifest SHA-256 is
`6404b607a66556800da6851d17487ee4c21d3723712097ed17acd07f89a1d04a` and event
journal SHA-256 is
`42ff16004682eafd4b565145e2d3f2176ee0d72d422b918005164a38c53353b3`.
The source is clean and runtime removal is confirmed.

At `1178e9735`, online Tell support is no longer party-bound. Before any invitation,
two ordinary clients send both directions to the other's exact received player
spawn. Each receiver matches one received actor entity/name and the test independently
binds the packet's nonzero character ID/name/entity to the sender's own normal lobby
identity; both exact texts arrive with party ID zero. The decoder retains non-GM,
printable-message, unique-spawn and party-character-ID consistency checks. Offline
Tell remains narrowly bound to an exact received offline party member. Exact nonparty
bytes and unobserved/wrong-name/debug rejection pass on Clang, MSVC and GNU with
**257 passed, 11 live skips**. The clean case passed in **36.17s** at
`.e2e-artifacts/discovery-live/sapphire-e2e-irhz3e89`; manifest SHA-256 is
`459f212ba5f0cc6c07d1d23d705d0dc002c3ac399907fef38a4b1dc13cb286ff` and event
journal SHA-256 is
`ff165d3c80b08445a8f7382a6c0424337b5c3adda928d0bc86109e64c0a24baa`.
The source is clean and runtime removal is confirmed.

At `0763c28bc` with evidence preservation at `71b2dda55`, the physical 130→141
zoning case extends direct Tell across zones in both directions. Each side first
receives the other's exact party-chat character ID/name/entity on the current
nonzero party/channel; the bounded sender permits a remote redacted party identity
only while that liveness evidence is at most 16 worker events old. The receiver
accepts the Tell only when the packet's character ID/name resolves to exactly one
current party member when no same-zone spawn exists. Both clients receive the same
party ID and exact text while their own roster reports local territory 130 or 141
and the remote member's territory zero. Exact remote-party bytes plus missing,
stale, nonmember and malformed identity contracts pass on Clang, MSVC and GNU.
The clean case passed in **305.27s** at
`.e2e-artifacts/discovery-live/sapphire-e2e-qtwuhpx0`; manifest SHA-256 is
`c31b87f6a8426dcc182004828a76816093502f7b4f4cc5c5c9a539557b900ae3`,
`cross-zone-social.json` SHA-256 is
`03accc4cd4d0fb78298590801f59e39ed11a5d577a5dda20cda93068e90c7a7f`, and event
journal SHA-256 is
`b6afafe3b4b39e563db7d2a2c14ad0beb8919a8cfe86a89ddbc083cc3dc277a2`.
The source is clean and runtime removal is confirmed.

At `4daabcaed`, the same physical zoning case then disbands the party and verifies
bidirectional cross-zone **nonparty** Tell. Each client retains only an exact player
entity/name identity actually received as a same-session spawn; zoning/despawn marks
that identity remote rather than inventing a directory lookup. Immediately before
disband, the traveler receives exact party-chat liveness from the source. The first
nonparty Tell requires that exact identity/liveness no more than 16 worker events
old; the reply requires the exact incoming Tell as equally fresh liveness. Both
receivers resolve the packet to one unique current-or-prior received identity, while
the scenario independently binds character ID/name/entity to the sender's encrypted
lobby identity. Both exact texts arrive with party ID zero. Current-spawn, grouped,
unknown, stale, absent-liveness, wrong-name and malformed-message contracts fail
closed on Clang, MSVC and GNU with **257 passed, 12 live skips**. The clean focused
case passed in **316.62s** at
`.e2e-artifacts/discovery-live/sapphire-e2e-fvijo69m`; manifest SHA-256 is
`548871a8100f1cb84216e27248b6511730c21443e502c6ffd9f6e6de6f3be4e3`,
`cross-zone-social.json` SHA-256 is
`b5106823f256d012e86f7aab7e1eaf84272e662a19825f2b6fc11195f485c94e`, and event
journal SHA-256 is
`c87b7215133ff63fcad4fcc5e6ae4658a8a74223731e603a4c5305e09d457728`.
The source is clean and runtime removal is confirmed. This proves one same-session
cross-zone nonparty exchange, not a general player directory, friend system,
alliance, linkshell/free-company or arbitrary chat-channel behavior.

A source/data audit confirms that the remaining group-channel breadth cannot be
reached honestly with the current matching content. `CmnDefLinkShell.cpp` contains
a normal event script for `0xB0006` and would call `createLinkshell` after scene-2
yield, but an exhaustive matching-3.3 `Level`→`ENpcBase` scan found **380** placed
category-11 event bindings and no exact `0xB0006` actor in any territory. The only
other caller is the GM-only `DebugCommandMgr::linkshell`; existing join/leadership/
leave handlers all require an already received valid linkshell ID. Seeding one in
the database, invoking the manager, using the debug command or inventing an actor
would violate this framework's ordinary-protocol/source-content boundary.
`FreeCompanyMgr::createFreeCompany` has no normal production caller, and there are
no social-alliance handlers/managers beyond territory intended-use naming. Therefore
linkshell, free-company and alliance E2E remain blocked until matching source data
places a normally reachable distributor/creation journey or the server gains an
established ordinary creation protocol and received identity semantics. No such
channel is claimed from the party proxy.

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

At `3f4393028`, the source catalog additionally binds level-one Pugilist Bootshine
53 (`WorkIndex=0`, 60 TP, melee range, 2.5s group-58 recast). A normal source-payload
Pugilist fixture and separate witness use unchanged natural layout 3746475. The
first clean gate exposed that the target may roam more than ten metres during the
preceding defeat/relogin flow; that failure remains at
`.e2e-artifacts/ci/gameplay-ci-qoyux9wr` and is not success evidence. `2b9dfaf1e`
therefore follows at most six received target positions within 20m using ordinary
movement, with the witness verifying each reached point. Both clients then require
the identical Bootshine effect and exact matching committed HP, while the actor
requires received action-start metadata. No target, TP, class or skill is granted.

The clean nine-case gate passed in **614.955s**; combat took **72.673s**. Combat
catalog SHA-256 is
`4b82031745650ad0f8e4ef37256beabd21c273d1294d4f3a699e2b6d76b38ffa`,
worker SHA-256 is
`c6954c261f0e728683735da8b2f1792e907f51ab2746cad2c1a39e411c83b2f8`,
and `combat-defeat-rewards.json` SHA-256 is
`94357d8c24fbdda0184f57033d6c561b03e11b92c9bc117a587603d23af9d1c5`.
This proves one additional starting-class ability, not positional bonuses, combos,
general abilities or general combat.

At `a63c1548f`, the generated combat catalog audits the first combo follow-up that
is actually represented by the current server action table: Gladiator Savage Blade
11 follows Fast Blade, has source level 4, costs 60 TP and uses the same 2.5-second
group-58 recast. Matching `ParamGrow` rows require exactly 2,000 cumulative EXP to
reach level 4. The currently evidenced natural level-one enemy grants 50 EXP, so a
path using only that exact population requires at least **40 ordinary defeats**.
The validator fails closed on the action, class/work index, level, EXP total,
per-defeat EXP and minimum-defeat count; six independent mutation contracts plus
52 existing policy/CI contracts pass. Generated catalog SHA-256 is
`a7c03c62ee0e724166f95bcf7da0b0fc839361452378fc315e5275f284b5d173`.

This is prerequisite evidence, not combo execution evidence and not a claim that
40 defeats are impossible. In particular, the server table gives Bootshine 53 an
empty `nextCombo` and True Strike 54 zero `comboPotency` and no caster/target
statuses, so the already-covered level-one Bootshine must not be relabelled as a
combo proxy. A focused diagnostic also waited ten seconds for an exact received
self-targeted action-53 `TypeCombo` marker after a successful witnessed Bootshine;
only the normal enemy damage result and action-start arrived. That expected failed
experiment is retained at
`.e2e-artifacts/discovery-live/sapphire-e2e-y3wrdh7c` (event journal SHA-256
`0093ca0204cb39ed213d7a43a5de47e5d14dbd8558efd6c7360a1627bbe91f94`),
with its runtime removed, and is not success evidence. At that revision a true
combo remained uncovered pending bounded normal level-four progression, exact
received combo-result semantics and an independent witness; the later `7436b4a44`
path below closes one Fast Blade→Savage Blade case without relabelling Bootshine.

At `93b4914d6`, a separate normal Pugilist path proves the attainable next
progression step without grants. Across seven fresh HTTP→lobby→world actor sessions
and seven independent witness sessions, the same character naturally defeats six
unchanged level-one Central Thanalan marmots. Every defeat uses ten paced,
received-TP/range-bound Bootshines; both clients require each identical damage
result and exact committed HP, then exact 50-EXP/current-`testTable` loot. After
each defeat the clients log out normally, the world is cleanly restarted and the
next fresh authentication must return the exact prior inventory, level and EXP.
The received sequence is level 1 at EXP 0/50/100/150/200/250, then level 2 at EXP
0 after the sixth reward.

Only that independently received level-two state enables source action True Strike
54 (`WorkIndex=0`, 50 received TP required, melee range and 2.5-second group-58
recast). A fresh natural target first receives a witnessed Bootshine and then both
clients receive the identical 10-damage True Strike result plus committed HP
84→74; the actor separately receives action-start metadata. The API rejects wrong
class, level, actor level, TP, range, target and malformed IDs and exposes no
arbitrary action interface. Natural regeneration means this does not claim an exact
50-TP debit, and the current server table does not make this Bootshine→True Strike
sequence a combo.

The clean focused case passed in **396.47s** at
`.e2e-artifacts/discovery-live/sapphire-e2e-yzkkgyv0`; manifest SHA-256 is
`ab79c41fe9416ab6cfbb075effbe26af278c8dcc3f4151474bb1669529f26e5b`,
`combat-level-two-true-strike.json` SHA-256 is
`8a428fcff384e56247d6ce764e45d7a642ff3bf3425e3ef497df1bc5f7dd91a9`,
and journal SHA-256 is
`1ece88df732daaaefa4c6294cc03d957fec2bdbc27ee9a9799813b0c7f72cfd6`.
The manifest is clean at the exact commit, all private runtimes were removed, the
expanded native protocol suite passes on Clang/MSVC/GNU, and **265 passed, 13
skipped** Python contracts agree across those workers. The clean thirteen-case gate
recorded above repeats the complete path; its progression artifact SHA-256 is
`54dd46a7ebafdec9e57294ccf6565bed1810ba4174264a0610f407b8fdeb83a7`.
This proves one exact natural level-up and one level-two ability, not general
progression, arbitrary abilities, positional bonuses or combo semantics.

At `7bf5716a1`, four fresh level-one Gladiators and a fifth non-attacking witness
bind exact natural layout 3749193/base 302: a level-14 enemy with 237 received HP
and source `ParamGrow` reward 115 EXP. The attackers use only ordinary Fast Blade
requests. Before every hit all five clients require the same current target HP,
the acting fighter's living state and independently received melee range; after
every hit all five require the identical effect/result ID and exact matching
committed HP. The clean focused run required 29 such effects and every attacker
contributed, while the witness never attacked.

Every attacker then received exact 115 EXP and one complete current-`testTable`
loot result; the witness's reward snapshot remained byte-for-byte semantically
unchanged. After all five clients independently observed delayed removal, normal
logout and one clean world restart, four fresh HTTP/lobby/world sessions returned
each attacker's exact EXP and complete inventory. No enemy, damage, HP, TP, EXP or
loot was injected or granted. The focused case passed in **124.32s** at
`.e2e-artifacts/discovery-live/sapphire-e2e-dsyhokdl`; manifest SHA-256 is
`6ec94ad6c47a35dc79dbf0053421dda9dca69c0c7d892716a03ebfcb48b7bef3`,
`combat-high-level-multi-attacker.json` SHA-256 is
`ac3dac165b2ae6295b0c93c35b2aeddef476beb6357ca214d170630583b77755`,
and journal SHA-256 is
`03ca9d897b6e6830bc773b50ca194b7e044bf3097ea87c0cd80539eec81c97f7`.
The exact committed revision is clean and its runtime was removed.

The expanded source catalog also establishes that 2,000 EXP requires at least 18
of this exact 115-EXP enemy, versus 40 exact 50-EXP enemies. The original focused
high-level path proves one exact multi-attacker hate/reward path, not general reward
sharing, level scaling, party contribution policy, combat capacity or arbitrary
enemies.

A follow-up diagnostic initially appeared to find no Fast Blade `TypeCombo`
(`0x1d`) readiness result. Inspection proved the server packet stores effects on
the caster in `CalcResultCt`, while the worker decoded only target-side
`CalcResultTg`. At `7436b4a44`, bounded action-result decoding exposes both arrays
as `effects` and `source_effects`; independently authored native fixtures pin the
wire fields. This changes test-client observability only, not server publication.
The formerly failed diagnostic remains at
`.e2e-artifacts/discovery-live/sapphire-e2e-o1o1wxk2` and is not absence evidence.

The same commit then proves the actual combo through a fully ordinary path. Four
Gladiators and a non-attacking witness perform **18** exact natural level-14
defeats. Every cycle requires all five clients to receive every Fast Blade damage
result, source-side `TypeCombo` value 9/flag `0x80`, exact committed target HP,
complete 115-EXP/test-table rewards for all four attackers, unchanged witness
rewards, normal logout, owned client close, world restart and fresh persistence.
Source-derived thresholds 300/600/1100 produce the exact received progression:
level 1→2 after defeat 3, level 2→3 after defeat 8, and level 3→4 after defeat 18,
ending at level 4 with 70 EXP. No level, EXP, action, target, HP, TP or loot is
granted.

Only the received level-four state, at least 60 received TP, the same living target,
melee range, elapsed 2.5-second recast and an unexpired 12.5-second exact Fast Blade
marker enable bounded Savage Blade 11. All five clients receive the same 13-damage
follow-up, exact committed HP, `TypeComboHit` (`0x1e`), and Savage Blade's next
`TypeCombo` value 11; the actor also receives group-58/250-centisecond action-start
metadata. The first otherwise successful progression run correctly failed because
the assertion expected only `TypeComboHit` and omitted the independently received
next-combo marker; that diagnostic remains at
`.e2e-artifacts/discovery-live/sapphire-e2e-z3gtmyow`.

The clean focused path passed in **1326.77s** at
`.e2e-artifacts/discovery-live/sapphire-e2e-h99wkmzl`; manifest SHA-256 is
`a3cf74975755bf65f9f42afbf999142d081a99c1cbe6ae2a07bd73debd4bc445`,
`combat-level-four-combo.json` SHA-256 is
`207c261df2820d5e4e69f7f83f6e245b37ed09f39e6cef2cb3863e44539c34b7`,
and journal SHA-256 is
`941363b9999f1cdb96cc0ecd34e983c4dcfe5c4ffd0b2a8ba8d8377974aa0389`.
The source is clean, runtime removal is confirmed, native combat contracts pass on
Clang/MSVC/GNU and **270 passed, 15 skipped** Python contracts agree across those
workers. The final clean fourteen-case gate repeats the combo path; its artifact
SHA-256 is
`2e1395b8b8fe11680c56426fa5715d202f2d49ff7134bddaa8f4a0c2fceec8d3`.
This proves one Fast Blade→Savage Blade combo, not arbitrary combo chains,
positional combos, interruption, exact TP debit or broad combat correctness.

Three strict-gate diagnostics are retained rather than hidden. `gameplay-ci-yvo5b2qn`
exposed the new explicit empty `source_effects` field in an exact item-VFX assertion
and then cascaded after combo teardown. `gameplay-ci-g893sffa` showed that repeatedly
waiting for optional observable transport close can exceed 30 seconds after a
received normal logout acknowledgement; the scenario now closes its owned client
and restarts the owned world without treating close timing as persistence proof or
retrying gameplay. `gameplay-ci-6ie9kp7o` passed the full combo but showed its final
living target remained damaged for the following player-defeat case; explicit
world-reset teardown fixed scenario isolation. The clean `gameplay-ci-uhwz3vc4`
then passed all 14 cases with exact collection, no skips and cleanup verified.

At `569a02898`, the same case adds source-defined Thaumaturge Blizzard 142
 the same case adds source-defined Thaumaturge Blizzard 142
(`WorkIndex=5`, MP cost metadata 3/4, 2.5s cast/recast and 25-unit range). A fresh
normal class-7 fixture selects a living natural level-one marmot within 20m using
received state; its witness independently observes both actors within spell range.
The bounded request requires at least four received MP. Both clients receive the
same 18-damage Blizzard result in the clean gate, including status 176, and exact
matching-result committed HP 94→76. The caster also receives source integrity and
group-58/250-centisecond start metadata. Natural MP regeneration overlaps the cast,
so this does not prove the exact MP debit, elemental-state behavior or interruption.

The first post-change broad gate is retained at
`.e2e-artifacts/ci/gameplay-ci-lfghcvlf`: eight cases passed, while player-defeat
failed because its selected natural enemy roamed beyond melee range during the TP
wait. `77abdae02` applies the same bounded received-position rule: at most six
positions within 20m, each independently observed. The targeted player-defeat case
then passed in 160.10s. The clean nine-case gate at `77abdae02` passed in
**676.69s** with zero skips/errors/failures; combat took **80.075s** and player
defeat took **124.522s**. Exact collection/input identities and runtime cleanup
were verified. Evidence:
`build-e2e/ci-summary-blizzard-follow.json`,
`.e2e-artifacts/ci/gameplay-ci-qdi9rcb4`, combat artifact SHA-256
`ac9596e01cb5490c8b47fffb16b574e0c82ebba476d82f967a7e62725baa38ff`,
combat catalog SHA-256
`2f8cb733628aeae9140e61ba9bb81a3ab00a1871c49724ffa73976bb6f8d84bf`
and worker SHA-256
`68c0a18c9c32e8aa103900239c25a617089165a64c1eaa4ad461d142a4b939d9`.
This proves one natural Blizzard path, not general magic/combat or independent
real-client presentation.

At `e3685631a`, a fresh living non-GM player in Central Thanalan performs
source-catalogued common Return action 6 through one normal action request. The
bounded operation requires an exact received living self, territory 141, homepoint
9, idle state, elapsed local action guard and bounded request ID. The actor receives
one exact action-6/kind-1/self-targeted five-second cast plus group-57,
90000-centisecond recast metadata; a source-zone witness independently receives the
same cast and then the actor's despawn. A separate destination witness in territory
130 independently receives the actor at source pop range 3693863, and a world
restart plus fresh HTTP/lobby/world session proves that exact territory/position
persisted. The source-generated action metadata also requires level zero, no cost,
common class-job zero and no enemy target. Exact bytes and territory/homepoint/death/
request rejection plus malformed/capped cast decoding pass on Clang, MSVC and GNU;
the Python suite reports **257 passed, 12 live skips**. The clean focused case passed
in **48.09s** at `.e2e-artifacts/discovery-live/sapphire-e2e-c44fm6rh`; manifest
SHA-256 is `14c8518ed49a493752c9c22bc469fa1d32c19c3e09da7885da61a789d2c92ae9`,
`living-return.json` SHA-256 is
`58a0a1de1596f007e58d26b1dc665e552e43d5c90147e08832b1e4749a6f2f6e`, and event
journal SHA-256 is
`4dbcf907256746d6e30b99b67ef2b556c73f5880855276c080818ec7eddd0347`.
The source is clean and runtime removal is confirmed. This proves one normal living
Return path, not arbitrary teleports, interruption/cooldown policy or broad ability
support.

At `cb59aca38`, a fresh non-GM player and independent witness exercise the
source-catalogued common Sprint action 3 through a normal action request. Both
receive one identical self-targeted action result containing exact status 50,
`TypeSetStatusMe` (`0x12`), source flag `0x80`, parameter 30 and the bounded request
ID; both separately receive a HUD commit with TP zero. The actor also receives the
source-derived group-56, 3000-centisecond action-start metadata. The API requires
exact received living player state, at least 50 received TP, an elapsed local guard
and bounded request ID; it does not expose arbitrary actions. Exact bytes and
kind/death/TP/request rejection pass on Clang, MSVC and GNU, with **257 passed, 11
live skips** in the expanded Python suite. The clean focused case passed in
**28.35s** at `.e2e-artifacts/discovery-live/sapphire-e2e-axabc8dz`; manifest
SHA-256 is `a73bc9996805f583ededb8feba6ab149c1bd1b7f1365edb6c9c862f5a64d865a`
and event journal SHA-256 is
`da04d36415d3ae0abe9afea59dea407ea7206cb2f5cedc6999edc79a2fc6eb21`.
The source is clean and runtime removal is confirmed. This proves one common
self-status ability and exact TP-zero commit, not general statuses or abilities.

## Source-bound unprovoked active-vision aggro

`0e17a7ec2` extends the read-only pursuit catalog with exactly one unchanged
Central Thanalan population: layout 3746983, base 735, level 6, `activeType=0`,
vision sense 1/range 14, wandering range 6 and normal population flags. For the
received level-one fixture the source formula gives an adjusted range of
`14 - 1.53^3 = 10.418423`. A complete 82-point, **37.694m** source-navmesh route
starts about 20m from the spawn and traverses a bounded three-metre radial approach;
a separate source-navmesh point places the independent witness about 30m away.
Catalog v2 rejects changed identity, activity/sense metadata, transform, adjusted
range, incomplete routes, an approach starting inside the outer bound, no point
within five metres, or an unsafe witness placement. The generator also compiled and
executed against the same population/navmesh in a network-isolated Ubuntu 22.04/GNU
full-project build (toolkit disabled); it reproduced catalog v2 with 82 points and
37.694055m.

`test_live_aggro.py` logs in two ordinary non-GM clients and verifies the exact
living source actor before movement. The fighter sends only normal route movement:
it sends no combat action, receives no player action-start, and has no received
effect sourced by itself. Both clients independently receive the same unrequested
enemy action-7 damage and matching exact committed HP integrity. The enemy continues
ordinary attacks through natural regeneration until both clients receive zero HP;
the focused run retained 55 matching effects from the bound source. Aggregate EXP,
level, currencies, item totals and complete inventory remain exact while dead and
a source-bound homepoint return is used only to permit normal cleanup.

The first clean diagnostic (`sapphire-e2e-_6py5qhr`) established exact aggro/damage
but correctly timed out at 90 seconds because regeneration prolonged defeat. A
subsequent attempted escape (`sapphire-e2e-5syeggww`) established further pursuit
but did not reach the server's retreat transition before its bounded deadline, so
that unsupported reset claim and route were removed. `sapphire-e2e-eqch4r6q`
completed every gameplay and cleanup assertion but failed while serializing a
`walk_route()` return value that is deliberately `None`; it is not counted as
success. All three clean failed runtimes were removed.

The final focused path passed in **178.53s** at
`.e2e-artifacts/discovery-live/sapphire-e2e-9f9os_b4`; manifest SHA-256 is
`6b408f9c889f2e4ac514bd529b1561e16bdd1345a2959018a0de413f93e2436b`,
`combat-proximity-aggro.json` SHA-256 is
`c368410cec2c5f80c1e3193e13a7b0f91facb98ca6c92ba59e3a65b5265e582c`,
and journal SHA-256 is
`5039d10fd3b3c1cc9cd009d0170c380fb3250d095933d00ca34af665fed0611e`.
The first exact committed effect is 94→92 HP. Revision `212bd1c61` is clean and its
runtime is absent. The clean fifteen-case gate at `39198db88` repeats all gameplay
assertions; its aggro artifact SHA-256 is
`5a3a788fde46bf1f98c747c9f8caa297c9bbe0d8d208146c5b4bb31ce555db56`.
This proves one source-defined vision path and unprovoked defeat, not general
senses, line of sight (the source contains a TODO), target selection, linked aggro,
other levels/populations, pursuit/reset policy or real-client presentation.

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
presentation. Later extensions below add the bounded homepoint return,
pursuit/leash/reset evidence and exact exposed reward/inventory non-change.

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

At that revision this proved one ordinary return-to-homepoint path. It did not
prove raise spells, other homepoints/classes, death penalties, same-territory return, persistence while
dead, party combat or real-client death/return presentation.

The later pursuit extension adds a read-only catalog generated from the unchanged
staged w1f2 population and matching private navmesh. It binds layout 3749193/base
302/level 14 and a complete 22-point, ten-metre route beginning beside the natural
spawn and ending more than eight metres away. After the one ordinary initiating
Fast Blade, the fighter sends no further combat action and walks that route. The
stationary witness verifies fighter arrival; both clients must then observe the same
enemy move at least two metres from its natural spawn toward the endpoint before
the existing natural defeat and homepoint-return assertions continue.

The clean gate at `482204b56` passed in **524.777s**; the extended case took
**83.044s**. Pursuit catalog SHA-256 is
`f9e0a8d917cc8b776725e1e238c3e3e33f83dc4dcf50e2b278f863054e1863a2` and
`combat-player-defeat.json` SHA-256 is
`18faafe1464236c832ed05210c965dc6520a87b1a26e9dd2b3716c367d77f12d`.
This proves one natural hostile pursuit response, not general pathfinding, automatic
proximity aggro, leash/reset behavior or arbitrary enemies.

The `5fb4c6750` extension adds a complete 110-point, ~50.69m route from the same
spawn, constrained by the matching w1f2 mesh to 45..70m displacement/path length.
After one ordinary Fast Blade, the fighter walks that route while an observer proves
arrival. Received enemy movement exceeds 35m from spawn; the enemy then naturally
returns within two metres of its source position while the fighter remains alive.
The fighter normally walks back, re-engages once and the prior independently
observed defeat/return/restart flow continues. The enemy retained 228/237 HP after
return, so this is explicitly a position leash/reset, not evidence of a health reset.

The clean gate passed in **608.636s** and the extended case took **119.001s**.
Pursuit catalog SHA-256 is
`1d809116cb6ec2fe00ef5e2cad0137400951216f6aa69179646e11dda569be42`;
`combat-player-defeat.json` SHA-256 is
`0250dc0c893692ff47dbeb311ea6dedef3f0f1e165f4c19963ac28274ee56a35`.
The four preceding targeted attempts remain privately under
`.e2e-artifacts/leash-live{,2,3,4}` and respectively show an unsupported worker
method, coarse peak observation, variable pursuit lag, and the then-unobservable
full-health assumption; none is success evidence.

`3b94d9150` adds bounded decoding of the server's ordinary HUD-parameter update
rather than inferring retreat healing from position or logs. Native contracts reject
invalid HP/MP bounds and source zero and cap the journal at 128 updates. After the
same enemy arrives at spawn, both clients must receive its restoration to exactly
237/237 HP before re-engagement. The targeted case passed in 161.90s; its artifact
SHA-256 is
`6fc4313f5b591d1d6c0b013c3cbd1d8c3864b1cedeba83ca43679359f9633911`.
The clean nine-case gate at that commit passed in **647.79s**, with player defeat
at **124.873s**, exact collection/input identities and cleanup. Evidence:
`build-e2e/ci-summary-health-reset.json`,
`.e2e-artifacts/ci/gameplay-ci-9avpxoit`, and clean artifact SHA-256
`63a3bfca2c8bb0d63ab528043dc1225849031c56eebebc4e0dedf421c35b8863`.
This remains one source-bound enemy/route, not general pathfinding, automatic
proximity aggro or universal leash/health-reset policy.

At `a93a12a37`, the same ordinary defeat captures received aggregate EXP, level,
currencies, item totals and every inventory row before hostility. Exact equality is
then required while dead, after the received homepoint return, and after normal
logout, world restart and fresh HTTP→lobby→world authentication. A separate
mutation contract rejects changes to each aggregate category and an inventory row.
The clean focused case passed in **148.09s** at
`.e2e-artifacts/discovery-live/sapphire-e2e-1gb7g8q2`; manifest SHA-256 is
`609cea2acc4918bc9f6ab6590798f19e27845e693def9b23e7f87f0aa9653c06`, artifact
SHA-256 is `fcfe6307de7cc1c2106c9fe49c303427111ff7c82cc1d2fd5643daadbc6f61cc`
and journal SHA-256 is
`787ca1c48c8856ac4d0583ecfc087dd23e8ef2908e40cd4ccfa5a99ebc24cc5c`.
The preceding failed run `sapphire-e2e-i8y_63gd` exposed that received inventory is
a keyed mapping rather than the synthetic contract's initial list shape; it is
retained and was fixed without weakening equality. The then-current fourteen-case gate
repeated this assertion; its player-defeat artifact SHA-256 is
`45da09c84d4fc4c1c10933fb4cf54dd84bb6461bc0d1a80480ea74deb1d07e81`.
This establishes absence of a death penalty only for those explicitly received
fields on this one path. Durability is not exposed by this worker, and persistence
while dead, raise behavior, other classes/homepoints and real-client presentation
remain uncovered.

Raise is not a defensible next protocol scenario at this revision. Public action
entries 125 (Raise), 173 (Resurrection) and 3603 (Ascend) have zero potency/cure/
restore values and no caster or target statuses, and no action-specific script
exists. Generic `Action::update()` interrupts whenever its resolved target is dead;
`playerPreCheck()` also leaves party/dead validation as a TODO. No production source
publishes a raise offer or binds a raiser identity. The client `REVIVE/RaiseSpell`
branch instead contains an explicit TODO for raiser position, weakness and HP/MP/TP
semantics and currently teleports to the player's homepoint. Sending that command
without a received offer would exploit trusted input exactly like the rejected duty
shortcut. The only implemented direct HP/status reset is `GmCommand::Raise`, which
is forbidden evidence. Normal raise coverage is therefore source-blocked until an
ordinary learned-action path publishes a received offer and the acceptance handler
validates and commits it; Return evidence is not a raise proxy.

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
consistency, split/merge/consuming-item coverage or real-client inventory UI proof.

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
equipment/currency operations, consuming item mutation or real-client inventory presentation.

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

The later `59ab9e539` extension runs four isolated empty-account journeys in the
same case and pins all source-defined results 1..4 to exact items 4423..4426. Its
bounded creation payload accepts only source-defined Ul'dah starters Gladiator,
Pugilist and Thaumaturge; received class-job and independently located level-one
work-index state prove each class rather than trusting the request. Every character
proves scenes 0→1, its sole selected ring after fresh HTTP/lobby authentication,
scene 40, and identical inventory/continuation after one shared world restart. A
policy contract fixes the complete choice map and the native protocol contract
rejects a non-Ul'dah class. The clean nine-case gate passed in **556.957s**; creation
took **58.868s** and `character-creation-opening.json` SHA-256 is
`c93f2a7ad1093e42260edc3f9bc7e99eafb808a0607ffe4ca247668444cf32f6`.
Worker SHA-256 is
`30212b835fb2db774ca952ef8dca6943b52c9e350f14e7d7c48b178890aff7c6`;
the private runtime root is absent. The immediately preceding failed gate is retained
under `.e2e-artifacts/ci/gameplay-ci-a5wh09qq`: it used the stale profile worker and
also caught natural target drift before Fast Blade, so it is not success evidence.

At `30f8a21f3`, the first newly created Gladiator additionally moved its received
starter sword 1601 from main-hand slot `1000:0` to observed-empty bag slot `0:0`
through ordinary operation 8 before starting the event. The operation receipt is
explicitly marked as non-proof. Exact source absence, destination item/count and
subsequent ring placement were first established by a fresh HTTP/lobby session and
then remained byte-for-field identical after restart. Native malformed-state tests
bound the action to one observed gear slot, a complete gear snapshot and an empty
ordinary slot. The clean gate passed in **581.964s**; creation took **59.418s**,
artifact SHA-256 is
`b546ef6ead17aa7080f23c12e25b2e1e963bf5da8c757644537a911c1ac4bdb0`,
and worker SHA-256 is
`d9357ec002694d802c9481ec31e13efa444161b697f1da56c87a2f09774e048c`.

At `3cc5a112a`, the subsequent fresh session sends a separately bounded reverse
operation only for observed item 1601 in an ordinary bag and an observed-empty main
hand. Its receipt is also non-proof; after logout, the restart snapshot proves exact
bag-source absence and restoration of `1000:0`, while retaining the ring. Native
fixtures reject other items, quantities, containers and an occupied destination.
The first targeted attempt is retained at
`.e2e-artifacts/creation-reequip-live/sapphire-e2e-lt1qud09`: it exposed a genuine
fast-reconnect race in which a new connection attached during the old session's
close-to-map-erase window. `0fe7d4cfe` now removes the old session map entry and
persists/invalidates its player before transport close becomes observable. The next
targeted run and clean gate logged `Session not registered, creating` on immediate
reconnect and passed. The clean gate took **560.217s**, creation **58.947s**;
artifact SHA-256 is
`cf00367024b64a2726e35c445e8979130c3bf2fb968477edacf3b3e9f00e6f52`,
worker SHA-256 is
`954a26161dc8ecfe6995289fee7bebfca2dea47f2c9fed721cb41df8577809a8`,
and server SHA-256 is
`ab48e771c1d467f8d1dc243e838ce1fdd6260e01e0974611ffbc4b9ad637c5e8`.

At `e5b6c6579`, the same read-only generator inspects opening-territory LGB layers
and resolves all three source-script event ranges. It selects box 4101537, generates
a complete eight-point ~3.123m navmesh route into its transformed volume, and binds
event 1245187 to expected scene 20. The worker accepts only territory 182, that exact
event/parameter, finite coordinates and a predicted endpoint within 0.15m. All four
normal creation branches walk the route, receive scene 20, finish it explicitly and
then prove the endpoint through fresh authentication. The clean targeted case passed
in **144.87s** (`sapphire-e2e-va9arwo0`); artifact SHA-256 is
`d17450875ddb8d8f9ad716f5fe7832d8b6d6db91641da8339db92a8130da630c`.
Protocol fixtures pass with Clang, MSVC and GNU; 255 Python contracts pass on all
three workers. This is one source-defined range, not general discovery evaluation.

At `86c096912`, a read-only catalog binds Coming to Ul'dah 66130, Wymond layout
3969639, Momodi layout 3969632, source reward metadata (50 EXP/103 gil) and a
complete ~9.84m w1t1 route from the canonical opening start to Wymond. The first
Gladiator walks that route normally and accepts through explicit scenes 0→1→2.
Active sequence 255 and endpoint persist through restart; `OpeningSequence=2` is
then independently demonstrated by opening scenes 40→30. The generator also tries
Wymond→Momodi and records `incomplete navigation corridor`, retaining no partial
route. Thus neither turn-in nor the listed rewards are claimed. The clean gate took
**608.839s**, creation **66.021s**; opening catalog SHA-256 is
`be1413b805b57746f84cc697307dcaf4b2d1e726725892bc691064e742fc3e80`
and `character-creation-opening.json` SHA-256 is
`1bbe7def532fdbc6f802ece68fb38abce6d30a84b2751508daba917815c89332`.

At `ee6f58fc2`, the same ordinary operation-8 path is independently exercised for
each distinct Ul'dah starter: Gladiator 1601, Pugilist 1680 and Thaumaturge 2055.
The reverse operation validates the received class/item pair and fails closed for
all other classes/items, quantities, containers, incomplete snapshots and occupied
main hand. Each operation receipt remains explicitly non-proof. Fresh authentication
proves all three unequips; the shared world restart proves all three exact re-equips
while retaining each selected ring. The targeted case passed in 100.44s; artifact
SHA-256 is
`370b5f7e0cd53759f10a1ba7d82912a41d704a68dacfd7494bb169b1e8cc80c9`.
The clean nine-case gate passed in **665.89s**, with creation at **66.434s**,
exact identities and cleanup. Evidence:
`build-e2e/ci-summary-starter-equipment.json`,
`.e2e-artifacts/ci/gameplay-ci-em9omn5g`, clean artifact SHA-256
`43dc01c7ede66e53d1df812b109e3554477ed9987b15586439697eb040aa108f`
and worker SHA-256
`a2d0d869c321fd125c53ea3d7828a416b35ef16bb35392a78800b98524ffcade`.

`8ca87f3f1` extends the same received-state operation to Gladiator body 2983, hands
3520, legs 3296 and feet 3750 in addition to main hand 1601. Each item moves to a
distinct observed-empty ordinary-bag slot before the opening; fresh authentication
proves all five unequips. The reverse operation now binds class, item and exact gear
slot; restart proves all five restored while Pugilist 1680 and Thaumaturge 2055
main-hand coverage remains. Native fixtures cover every supported wire destination
and reject unknown slots. The targeted case passed in 102.13s; artifact SHA-256 is
`4e2d05e5f87b073ce33f4b02aa03b20664f54016dcdd18058af4044848dc6191`.
The clean gate passed in **620.91s**, creation **65.662s**. Evidence:
`build-e2e/ci-summary-starter-slots.json`,
`.e2e-artifacts/ci/gameplay-ci-i5o5pnpz`, clean artifact SHA-256
`c87089d15aa50207a427d1c04740ef206f1f7b9c30023469c6531149d6fd6da8`
and worker SHA-256
`d7a2ae2631a81508fbb30deec2255a451a4329bc4374a05a7807bcc845a1ba45`.

At `b65d74567`, each source-defined opening ring (4423..4426) is also bound to
received class/item/quantity state and exact Ring1 slot 11. The silent opening
grant is not treated as live mutation evidence: fresh authentication first proves
the exact ordinary-bag source. Operation 8 then requests the equip, and the shared
world restart proves each ring at `1000:11`. A reverse operation remains a receipt
only until another fresh HTTP/lobby/world session proves the ring back in its exact
original bag slot. The targeted case passed in **127.13s**; artifact
`.e2e-artifacts/creation-ring-live/sapphire-e2e-azs17ll9/character-creation-opening.json`
has SHA-256
`bd461e51c559e1b8ef11d5d4652ae55d56d8df6276b9ca716202364417306df2`.
Native fixtures at that revision covered all four ring IDs and rejected Ring2
substitution. No acknowledgement was used as equipment mutation proof.

At `bc0c21b00`, matching Item source rows establish that all four opening items use
single-stack equip-slot category 12. The bounded API now permits only Ring1 or
Ring2 for those exact IDs. After the retained four Ring1 round trips, item 4423 is
moved from its freshly observed bag slot to empty Ring2 slot 12; world restart and
fresh authentication prove it only at `1000:12`. Its reverse operation remains a
receipt until another fresh session proves the exact original bag state. The clean
case passed in **143.15s** at
`.e2e-artifacts/discovery-live/sapphire-e2e-t_32lguo`; manifest SHA-256 is
`bae3e9d5847fa4b6d1eb066c2aad47c05c8d9cbd16a02f7e87506cf38f5bf8b8` and
artifact SHA-256 is
`ee6bcaf4ed5f61fbcda3fdbe4fc1399bf084310cbb89231fc69c74bb62455ca6`.
The manifest is clean and its private runtime was removed. Clang, MSVC and GNU
reward fixtures cover both ring slots and reject non-ring destinations. This is one
second-ring round trip, not evidence for other accessory types.

At `486238678`, the live matrix closes the remaining Ring2 variants rather than
extrapolating from item 4423. Each exact freshly authenticated bag identity for
4423, 4424, 4425 and 4426 is independently moved to empty `1000:12`; each operation
receipt remains non-proof until a separate world restart and fresh HTTP/lobby/world
session proves the exact Ring2 identity and complete inventory. Each reverse move
is likewise followed by another fresh login proving the original bag slot and full
reward state. All four Ring1 and all four Ring2 paths therefore have direct live
persistence evidence while the existing exact native fixtures cover every ID/slot
pair and reject non-ring destinations. The clean case passed in **207.62s** at
`.e2e-artifacts/discovery-live/sapphire-e2e-4u598gz4`; manifest SHA-256 is
`f78758c8111b04a94e6760a7699f4a67c25f0c218505c0a78a3d6c974599ee1f`,
`character-creation-opening.json` SHA-256 is
`bf72627014cf87952eb4406e4a8c25c428e3fee90a86833fe9a9939f273bb1a1`, and event
journal SHA-256 is
`a1083a020a427719f3342fb18573b155f38ff08651cfc162952f4e6dfbd2f8dc`.
The source is clean and runtime removal is confirmed. This closes the exact
source-defined Ring2 matrix, not arbitrary accessories or other creation choices.

At `694802919`, the first fully evidenced disposable creation branch is then deleted
through the normal encrypted lobby operation. The request is built only from its
exact freshly received character/content/entity/index/world/name identity and is
accepted only for the sole matching list entry. The deletion reply is explicitly
not mutation proof: the same lobby session first refreshes to an empty list, then a
new HTTP login and independently encrypted lobby session proves the character still
absent. The clean case passed in **143.49s** at
`.e2e-artifacts/discovery-live/sapphire-e2e-49hnew7j`; manifest SHA-256 is
`ccac6be28c9f530ac9e010b2142ae284f8805a85d53d8c0fdfee82dd0acac118`, artifact
SHA-256 is `26d8f0bf4a4b32e0f7d3fb9c5b8f25d13d41e4a530338860334ea45958ae8a8e`, and
event-journal SHA-256 is
`11c233eeb5528b3d9f68297184db8876e28a9f5f52aa9b55f31cf801bf8d7b51`.
The manifest is clean and runtime removal is confirmed. Exact byte fixtures and
bounded mode/name/identity rejection pass with Clang, MSVC and GNU. This proves one
normal deletion, not account lifecycle UI.

At `36d85d7b0`, a second empty account normally reserves the already-created first
character's exact name. The lobby returns source error code 3074, status 0 and
message 13004; only that phase- and identity-bound NACK is accepted as the expected
rejection. Execution exposed that `LobbyPacketContainer` encrypted a complete final
Blowfish block but published the unpadded segment length, truncating non-eight-byte
NACK ciphertext. The fix publishes matching padded segment/outer lengths and checks
container capacity; aligned successful packets remain byte-for-byte unchanged.
Clang and GNU build the corrected lobby, while Clang/MSVC/GNU protocol and worker
contracts pass. The clean creation case passed in **143.44s** at
`.e2e-artifacts/discovery-live/sapphire-e2e-snn32y05`; manifest SHA-256 is
`150d592b0f9775692292aa9f6934e7435e43f3d2f41a9f8ef0569b0910c664c2`, artifact
SHA-256 is `7a2d4f466d74fdad0ebe36981fd464a1682c0e02e2348de4f57a281f1e0a3c02`, and
event-journal SHA-256 is
`e161777fefb454a140fbc4de39c9022072cd0c94b75f26c3fbc2aede1bb898bf`.
The source is clean and runtime removal is confirmed. This verifies duplicate-name
rejection only, not all naming policy or account UI behavior.

The first broad gate retained at `.e2e-artifacts/ci/gameplay-ci-aybzbmom` reached
8/9 passes and exposed an unrelated invalid simultaneity assertion: two independent
clients both observed the naturally moving enemy pursue, but their asynchronous
snapshots were 0.988m apart rather than within 0.15m. Commit `670238294` replaces
same-tick equality with the semantic requirement that each separately received
position moved from spawn toward the fighter endpoint; later exact matching combat
results and committed defeat state remain unchanged. The targeted defeat case then
passed in 144.99s. The strict clean gate passed all nine cases in **650.23s** with
creation at **102.054s**, exact identities and cleanup. Evidence:
`build-e2e/ci-summary-starter-rings.json`,
`.e2e-artifacts/ci/gameplay-ci-9he7litu`, clean creation artifact SHA-256
`3fbaf24054645b9638460370168397b43e21e74c77b2e60b95241562559198e0`
and worker SHA-256
`b61fde96d4b6d3f786dddaf1e167f56cb6b5688d3984c4adb790e6dd493e7227`.

Two later twelve-case diagnostics retained at `gameplay-ci-_x94ts6l` and
`gameplay-ci-n4n73ly6` exposed a second invalid moving-target assumption. A pursuing
enemy can pass the fighter endpoint between replicated snapshots, and a naturally
roaming initial enemy position can make its vector to that endpoint only 1.075m.
Commit `7504e7051` instead records the exact received enemy position immediately
before the pursuit, requires the authored fighter route itself to exceed 5m, and
requires each independent enemy snapshot to move at least 2m with at least 2m
forward projection and cosine greater than 0.5 along that route. This accepts
overshoot without accepting lateral or backwards roaming. The clean focused case
passed in **149.93s**, followed by the clean 12/12 gate recorded above; combat
results, leash/reset and exact defeat assertions are unchanged.

This evidence remains deliberately narrow: it covers the three Ul'dah starting
classes, one canonical appearance payload, all ring choices, all five Gladiator
starter slots and each distinct starter main hand, the initial/continuation scenes
and Coming to Ul'dah acceptance. It does not establish quest turn-in/rewards,
other accessory types/off-hand/head/waist, other later equipment, account signup UI,
appearance breadth, other cities/classes, broader naming policy, travel into
public Ul'dah, real-client cutscene presentation or broader protocol compatibility.

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

## Owned-process exit classification and retained logs

At `790a985d4`, `Environment.check_alive()` writes the first structured
`process-failure.json` before raising `SetupError`: schema version, classification,
owned process name, return code, expected redacted log name and the fact cleanup is
still required. It records no argv, credentials, session identifiers or private
configuration and never converts the process exit into a passing result.

A separate fault-lane test provisioned fresh isolated database/API/lobby/world
processes, intentionally terminated only its owned world process, observed Windows
return code 1, required the exact `unexpected_process_exit` classification, and
then ran normal owned teardown. The test independently required retained
`world.log` and manifest, absence of generated secret/database-password values from
all published text logs, and actual whole-runtime absence. It passed in **23.79s**
at `.e2e-artifacts/discovery-live/sapphire-e2e-b_xxisnj`; manifest SHA-256 is
`e007dc4da596dceff36a50be1f78bd0f1afc6444ce265311475a8e13c855ecb8`,
`process-failure.json` SHA-256 is
`77617f78bbb701c9a4722d90cd309b43db55e4d56ed50af038c2ef3f3d8cbc11`,
retained world-log SHA-256 is
`a077f58327951f444f55dbcd087f3ac55fbea77c9cbf600f9b92e8d521a99004`,
and verification SHA-256 is
`f59403cacfa192b9b62665acb1b9fe1577e2da9353b39f66586959e526e7f6dc`.
Revision and source were clean and the runtime is absent. The full contracts report
**271 passed, 17 skipped** with Clang/MSVC workers and network-isolated GNU.

This is an intentional graceful OS termination of one disposable process, not an
organic server crash, signal matrix, crash-dump test, hosted cancellation test,
power-loss recovery, or proof that forced termination of the Python coordinator
cleans stranded processes. The fault lane remains separate from the fifteen-case
gameplay gate so an expected world kill cannot mask or contaminate gameplay.

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
and binds index 0, item 5890 and source unit price eight gil. At `f6149ad6d`, the
catalog derives a bounded quantity of three from the item's source stack cap and the
28 gil earned by the preceding sale, for an exact 24-gil total. The current private
catalog SHA-256 is
`73995f5f3e75336219784729f0e03b2e0efe5faf801afc560871d6858714df74`.

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
pre-existing item 5890. Received state must become one stack of three item 5890 and
four gil with all other slots unchanged; fresh authentication after restart must
return the identical map. Native fixtures pin quantity three at the purchase result
offset. The clean chained case passed in **245.68s** at
`.e2e-artifacts/discovery-live/sapphire-e2e-_51romwt`; manifest SHA-256 is
`16fed7ed588fe225158d599cb9efe2cb48a5cb05405065c87c8e2be3bcd1890d`,
`gil-shop-sale.json` SHA-256 is
`72e3a163158ca1329271d777fa975576c7c9bfefa302c7d2634bc8c6a842db32`, and event
journal SHA-256 is
`ae8ec3674ae12f21c890ba2535baca705cdcc706a8d43818b5f231c84ca2642f`.
The source is clean and runtime removal is confirmed.

At `3e05c4635`, the catalog additionally binds purchased item 5890 to source ItemAction
row 232, supported VFX type 852 and argument 235. After leaving the shop, the worker
can send only a normal item-action request for the exact received ordinary-bag
three-stack, source slot/container, self identity and bounded request ID. The actor
and independent observer receive the identical self-targeted action result:
ActionKey 5890, kind 1, request/result zero and one `TypeCheckBarrier` (`0x36`)
effect with value 235, flag zero and zero arguments. Immediate received state and a
fresh login after world restart both prove the stack remains exactly three; this is
the server's deterministic non-consuming VFX behavior, not a claim of consumable
mutation. Wrong item/count/container/slot and malformed request contracts pass on
Clang, MSVC and GNU. The clean chained case passed in **246.03s** at
`.e2e-artifacts/discovery-live/sapphire-e2e-qmqobp3y`; manifest SHA-256 is
`52d98b1083eee30b5a03bf7748a249f61efb8b7d3a980cb1d523eb8a5098a10f`,
`gil-shop-sale.json` SHA-256 is
`ff522859187962794b77ded5ba67fbe79401ab7aeb9099b91ff6a8d8c69fd580`, and event
journal SHA-256 is
`f138c0002500b5f4c43a84404c9dd46cbe23713639a8b13921a53cfa523fd0f4`.
The source is clean and runtime removal is confirmed.

At `2a0b89391`, the same source catalog deterministically selects the cheapest
non-starter, all-class, level-one, single-stack equipment listing affordable from
two normally earned potion sales: index 11, item 3286, source slot 7 / equipment
slot 6, and 39 gil. After the VFX stack survives restart, two ordinary split
operations create three one-item stacks and two further fresh logins—not receipts—
prove them. Normal scene-40 sales liquidate each exact stack for eight gil and the
remaining potion for 28, yielding exact received inventory absence and 56 gil. A
separately bounded purchase accepts only that post-sale state, item 3286 absent and
the exact refreshed shop scene; received state becomes one ordinary-bag item 3286
and 17 gil, then survives world restart and fresh authentication unchanged. This proves acquisition. Exact equipment-purchase bytes,
source metadata and malformed-state rejection pass on Clang, MSVC and GNU. The
clean chained case passed in **282.58s** at
`.e2e-artifacts/discovery-live/sapphire-e2e-aymipk4v`; manifest SHA-256 is
`79ee979320b234a84c894993afcfc21b93e9d667ebced3c79641a28b20cd3e87`,
`gil-shop-sale.json` SHA-256 is
`0c67f21cf253393fea59bf6d97575d7df506c4fe9160814768029484a418cbe9`, and event
journal SHA-256 is
`187f968b585e3adac8cce083113ea38afecd8ec914d46028ba697ef8ad0ab22d`.
The source is clean and runtime removal is confirmed.

At `379a70083`, the purchased item is also equipped through ordinary inventory
operations. Fresh state must first show starter legs 3296 at equipment `1000:6`
and item 3286 in its exact bag slot. An operation-8 receipt for unequipping 3296 is
kept as acknowledgement only; restart/fresh authentication proves slot 6 empty and
3296 in the selected empty bag slot. The new bounded equip request accepts only a
living Gladiator inventory snapshot with exact item 3286 count one, complete bag and
equipment containers, source-defined destination slot 6 empty and no alternative
item/slot. Its operation-8 receipt is again non-proof. A second restart and fresh
session prove item 3286 only at `1000:6`, starter 3296 in its exact bag slot, 17 gil,
unchanged level/EXP and no other inventory change. Exact bytes plus wrong class,
item, count, occupied destination and wrong-slot rejection pass on Clang, MSVC and
GNU. The clean chained case passed in **306.58s** at
`.e2e-artifacts/discovery-live/sapphire-e2e-suykkdd9`; manifest SHA-256 is
`63f51af2db1d1dac6841c46a8c317c85570c721188ea0121425970939d2b9c3d`,
`gil-shop-sale.json` SHA-256 is
`2d68c1adc12cc6b2ac176f9363bb306087ca539c597828eda6b4d9779c2bdbcf`, and event
journal SHA-256 is
`6cf626c05abea2a27c4eb7cc598605153508a438c20500b35aec1bf2d1962041`.
The source is clean and runtime removal is confirmed. This proves one source-listed
later leg item, not general equipment compatibility.

At `2d7d9ef15`, the catalog also derives the cheapest affordable listing in a second
equipment slot after reselling that first purchase: index 9, item 3748, source slot
8 / equipment slot 7, and 54 gil. The equipped leg item 3286 is first normally
unequipped; restart/fresh authentication proves it in the exact bag slot before a
source-bound scene-40 sale. Received state and another restart—not the scene
request—prove item absence and exact restoration from 17 to 56 gil. A separately
bounded request then buys only item 3748 from that exact state. Fresh authentication
proves one bag item 3748 and 2 gil. The starter feet 3750 are normally unequipped
and restart-verified, and the equip API accepts only exact pair 3748/slot 7 with an
empty complete destination. A final restart proves item 3748 only at `1000:7`,
starter items 3296 and 3750 in their exact bag slots, 2 gil, unchanged EXP/level and
no other mutation. Operation-8 receipts remain acknowledgement-only. Exact purchase
and equip bytes plus wrong item/slot/class/count, occupied destination and malformed
shop-state rejection pass on Clang, MSVC and GNU with **257 passed, 12 live skips**.
The clean chained case passed in **372.96s** at
`.e2e-artifacts/discovery-live/sapphire-e2e-eswai293`; manifest SHA-256 is
`614bd818246f22c86f2bd2c24d674561241519a9ad47ca878ec223b2bb6ab815`,
`gil-shop-sale.json` SHA-256 is
`9143cabde1c507c61adbc922cc4599790ea635ebcc6a9260d482b7e9e1c24b28`, and event
journal SHA-256 is
`1310002467e3559a61ec6ec8abeac6676c791086cba566e2adaf3fec01d3a1b3`.
The source is clean and runtime removal is confirmed. This proves two exact later
items across leg/feet slots and one resale cycle, not arbitrary listings or general
equipment compatibility.

At `485ffee34`, the source catalog completes the affordable distinct-slot sequence
at this shop. After item 3748 is normally unequipped, fresh authentication proves
its exact bag slot; scene-40 sale plus a separate restart prove its absence and 56
gil. The already displaced starter legs 3296 have source price 45 and are then sold
from their exact received bag identity; another restart proves exact absence and
101 gil. From that state only, the catalog-derived cheapest third-slot listing is
index 3, body item 2967, source slot 4 / equipment slot 3, costing 59 gil. Fresh
authentication proves one exact bag item and 42 gil. Starter body 2983 is normally
unequipped and restart-verified before item 2967 can move to empty `1000:3`; a final
restart proves item 2967 there, starter body 2983 and feet 3750 in exact bag slots,
42 gil and unchanged EXP/level. Exact third-purchase/body-equip bytes and wrong
item/slot/class/count/state rejection pass on Clang, MSVC and GNU with **257 passed,
12 live skips**. The clean chained case passed in **410.58s** at
`.e2e-artifacts/discovery-live/sapphire-e2e-ynntgsuh`; manifest SHA-256 is
`14ca7f17881df6b530a33a7c43cf6b03e50cb8770fe70e3ec60571b0477e90b6`,
`gil-shop-sale.json` SHA-256 is
`5bec82ae31fdbfa7484fccd2777a6b5b3f3c16535605e809014097046175988b`, and event
journal SHA-256 is
`75dfef3b156343039972e85f523a17aa650a97ea03e432ff1a58969b5b234162`.
The source is clean and runtime removal is confirmed. This covers the affordable
body/legs/feet slot types exposed by this source shop and earned-gil path, not every
listing, other shops or general equipment compatibility.

At `7c4769d18`, the final exact 42-gil state also exercises the generic inventory
operation's currency boundary. The bounded request can encode only the independently
received fixed currency item `2000:0` (catalog 1, exact count 42) toward observed-
empty `2000:1`; wrong count, missing snapshot/container or occupied destination fail
closed. The server still publishes its ordinary operation-8 acknowledgement before
validation, so the receipt explicitly says `rejection_verified: false`. The handler
now rejects every generic delete/move/swap/split/merge touching Currency 2000 or
Crystal 2001, whose fixed quantities must use dedicated semantic persistence paths;
otherwise `moveItem()` would persist item UIDs into quantity columns. World restart
and fresh HTTP/lobby/world authentication—not the acknowledgement—prove the entire
inventory, exact 42 gil, equipment and rewards unchanged and slot `2000:1` absent.
Exact bytes and acknowledgement-policy contracts pass on Clang/MSVC/GNU workers;
the full GNU server target also builds from a network-isolated tracked-source copy.
The clean chained case passed in **416.28s** at
`.e2e-artifacts/discovery-live/sapphire-e2e-nq6af4vu`; manifest SHA-256 is
`f874d7b1c22567d9d45945ef53cb1f0eab658a0b1248775fd099df5395efa82a`,
`gil-shop-sale.json` SHA-256 is
`f2107ac97c24f34744a04b6b1257466927ed582180d6f89c6d6a41ea2b2a8c2e`, and event
journal SHA-256 is
`79787d3c814445f8db2d19174755d3696da239476b810d0f194abfe01fc1e631`.
The source is clean and runtime removal is confirmed. This proves deterministic
rejection of an invalid generic currency-container move plus ordinary shop-driven
gil mutations; it does not claim a positive direct currency transfer operation.

At `d6fb47d80`, the chain reaches a second source shop and a previously uncovered
head slot without fixture relocation. From the exact post-body-equip state, starter
body 2983 is sold from its received bag identity for source price 59; immediate
state and restart prove exact absence and 101 gil. The catalog scans source shop
rows for the cheapest level-one all-class single-stack head listing affordable from
that state, then accepts only a complete source-navmesh corridor from the current
shop: layout 4393619 / ENpc 1005495 / event 262415, index 0, item 2638, 47 gil,
source slot 3 / equipment slot 2. The route has 200 points and length
**92.945559m**, every requested waypoint is received by the actor, and a fresh
normal client at the destination independently observes arrival within 0.15m. The
purchase accepts only that exact received scene, 101 gil, equipped body 2967 and
absence of item 2638/starter body. Restart proves one exact bag item and 54 gil.
Because starter head is genuinely empty, the bounded equip request accepts only
2638→`1000:2`; another restart proves that location, exact remaining bag/currency/
EXP state and no other mutation. Exact purchase/equip bytes, wrong event/item/slot
and malformed-state contracts pass on Clang, MSVC and GNU with **258 passed, 12
live skips**. The clean chain passed in **488.80s** at
`.e2e-artifacts/discovery-live/sapphire-e2e-o0i4ls0c`; manifest SHA-256 is
`4a0ec052bbc48a30d3e81ae1f9949bf3240616459cae63f4aff9125bb04a324d`,
`gil-shop-sale.json` SHA-256 is
`46038cb70cc56a68be41091ed16745bcd5148587ca954459f15ab8db8211b47e`, and event
journal SHA-256 is
`004b0e1b263a864b9dc88e3098ee3251cb4ed6d726f1253bd4ac85f17b893fa1`.
The source is clean and runtime removal is confirmed. This proves one normally
routed second shop and one later head item, not general merchant/navigation or all
equipment slots.

At `a1c27a973`, the same chain extends to one source-listed ear accessory and a
third normally reached shop. The exact starter-feet bag identity is sold at the
head shop for source price 48; immediate state and restart prove exact absence and
102 gil. The catalog then scans source rows for the cheapest level-one all-class
single-stack ear listing affordable from that state and accepts only a complete
source-navmesh corridor: layout 4614930 / ENpc 1005900 / event 262425, index 0,
item 4200, 66 gil, source slot 9 / equipment slot 8. Its head-shop-to-ear-shop route
has 201 points and length **91.368600m**; the actor receives every requested
waypoint and a fresh normal destination client independently observes arrival
within 0.15m. Purchase is gated by exact scene, 102 gil, equipped head 2638 and
absence of item 4200/starter feet. Restart proves the exact bag item and 36 gil;
the bounded equip request accepts only 4200→`1000:8`, and another restart proves
that location, empty ordinary bags, 36 gil, 100 EXP/level one and no other mutation.
Exact bytes and malformed-state contracts pass on Clang, MSVC and GNU with **258
passed, 12 live skips**. The clean chain passed in **517.31s** at
`.e2e-artifacts/discovery-live/sapphire-e2e-f35w1x93`; manifest SHA-256 is
`dbbf118e0133830943c6de3c7621ecfbfd035c9cf3ce2a90c9c0a7595a928f01`,
`gil-shop-sale.json` SHA-256 is
`26f8bf1a41aaa0e0127210fde79b84bb708ed84d38e7b550992bd0d28bae9ca6`, and event
journal SHA-256 is
`6c1f61cac855a3247d6e245d8e61dd4ca91f292362ea1abe07c16c34aab629ed`.
The source is clean and runtime removal is confirmed. This proves one ear item and
one additional exact route/shop, not all accessories or general routing/shops.

At `17ad3c752`, a fourth source shop and a second later accessory type are covered.
The final body/head/ear equipment identities are each ordinarily unequipped to exact
empty bag slots. Operation-8 receipts remain explicitly non-proof: separate fresh
world sessions after each operation prove the exact source absence/destination
presence before the next request. All three bag identities are then sold through
the still-received ear-shop scene for their source prices 59/47/66; received state
and restart prove empty bags, those equipment slots empty and exactly 208 gil. The
catalog selects the cheapest affordable level-one all-class single-stack neck item
and accepts only a complete source-navmesh route from the ear shop: layout 4067692 /
ENpc 1004417 / event 262640, index 1, item 15130, 168 gil, source slot 10 /
equipment slot 9. Its 56-point route is **23.282667m**; every actor waypoint is
received and a fresh normal destination client independently witnesses arrival
within 0.15m. Exact scene/funds/absence gates precede purchase. Restart proves one
bag item and 40 gil; a bounded 15130→`1000:9` request is followed by another restart
proving the exact neck location, empty bags, 40 gil and unchanged 100 EXP/level one.
Four retained failed diagnostics (`sapphire-e2e-mx2dhuyg`, `sapphire-e2e-1asvrb_2`,
`sapphire-e2e-_mbhu245`, plus instrumented `sapphire-e2e-25o8auwd`) showed why an
operation receipt and immediate unchanged snapshot cannot establish rejection or
mutation: the server had accepted the move but did not publish an immediate
inventory delta. The scenario was corrected to use fresh-session state rather than
weaken the assertion. Exact purchase/equip bytes and malformed-state contracts pass
on Clang, MSVC and GNU with **258 passed, 12 live skips**. The clean chain passed in
**589.42s** at `.e2e-artifacts/discovery-live/sapphire-e2e-5b4w9c3m`; manifest
SHA-256 is `d462db8255ef812e06b37bb52e1b88e2f29d3a119878a51b7d74902e1c7a5e4b`,
`gil-shop-sale.json` SHA-256 is
`14320a36749a857be9a463b10fabcf8ea5c39b058487a8be8a836c71414b3a9b`, and event
journal SHA-256 is
`d20fccd37af1a651e7f941af1ef22e540520a5e55c593b451460be74e3fb31cd`.
The source is clean and runtime removal is confirmed. This proves one neck item and
one additional exact route/shop, not wrist/waist/off-hand coverage, arbitrary
merchant access or general navigation.

At `6ea7ed1e7`, the same exact source shop covers a normally purchased wrist item
without fabricating a second route. Neck 15130 is ordinarily unequipped to exact
empty `1:21`; the operation-8 receipt remains non-proof and a fresh world session
proves the bag identity and empty `1000:9`. Normal sale through the exact received
262640 scene and another restart prove item absence and 208 gil. Source scan selects
that shop's cheapest affordable level-one all-class single-stack wrist listing:
index 2, item 15132, 168 gil, source slot 11 / equipment slot 10. Purchase is gated
by exact scene, funds, empty neck/wrist slots and absence of both item identities.
Restart proves one exact bag item and 40 gil; bounded 15132→`1000:10` followed by a
second restart proves the wrist location, empty bags, 40 gil and unchanged 100 EXP/
level one. Exact purchase/equip bytes, wrong event/item/slot and malformed-state
contracts pass on Clang, MSVC and GNU with **258 passed, 12 live skips**. The clean
chain passed in **647.59s** at
`.e2e-artifacts/discovery-live/sapphire-e2e-o0fpf4zp`; manifest SHA-256 is
`a16f443fccd17347c9cb06f55c84fc272fd12c879b5d69521d6ae1ee177f5523`,
`gil-shop-sale.json` SHA-256 is
`6f6e332074a22699564eb243e071d3c08eb396bf9ccf1ffd3e181dc168741c2e`, and event
journal SHA-256 is
`052d33e67006d78f841e81ff17fc39575791162549b03be874d6f1c0e69e0129`.
The source is clean and runtime removal is confirmed. This proves one wrist item
and same-shop listing transition, not arbitrary accessories, waist/off-hand slots
or general merchant behavior.

At `2169c25f6`, the catalog records why the next off-hand/waist increment has no
honest level-one shop path instead of inventing one. From the exact wrist-end state,
normal wrist resale would make at most 208 gil. The read-only source scan examines
all forty listing positions of every placed territory-130 category-4 shop handler,
without applying a class restriction, for nonzero-price single-stack items with
`EquipLevel <= 1`, price `<= 208`, and source slot 2 (off-hand) or 6 (waist). It
finds **zero listed candidates** and therefore zero source-navmesh-routed candidates
for both slots. Python requires the exact scan budget/level/slot/count tuple and
fails closed if source data changes. A clean regenerated catalog at `2169c25f6`
has SHA-256
`797c9d5d1aca19c588f0edfffff65619221be9703a05149c88b55046dfadb531`;
52 focused catalog/policy/CI contracts pass and the Clang full-project target builds
and executes against the matching private source data/navmesh. Standalone test-
client build trees do not define this full-project catalog target, and a network-
isolated GNU full-project attempt exceeded its 600-second local build deadline, so
no new GNU/MSVC execution claim is made. This establishes only that the current
level-one, 208-gil, placed-Ul'dah-shop path has no off-hand or waist listing; it does
not prove those slots unsupported after legitimate leveling, greater funds, another
territory, quest rewards or different source data.

At `118eebd59`, the same exhaustive listing scan also tests the minimum honest input
for an overflow merge instead of assuming one can be fabricated. For every placed
Ul'dah gil-shop listing, it asks whether the exact source item is stackable and
whether buying `StackMax + 1` units at source unit price is possible with the
maximum evidenced 208 gil; only then would two legal stacks capable of overflowing
one destination exist. There are **zero listed candidates** and therefore zero
source-navmesh-routed candidates. Python requires the exact
`required_units=stack_max_plus_one` and zero counts. The clean generated catalog
SHA-256 is
`bfe3c02f4a969f30006a0c5caf48ea48c5e1820ff68e6cf9085496baf3a5bce4`, and the same
52 focused contracts pass. This blocks only the current ordinary shop-funded path;
it does not prove overflow semantics, nor rule out a future legitimate larger
currency balance, repeated combat/quest rewards, another territory/shop, or a
source item with a lower attainable overflow threshold.

At `9b13c35e0`, the scan closes the corresponding ordinary-shop hypothesis for a
deterministic consuming item. Server source consumes only implemented ItemAction
families Companion 853, Mount 1322 and Song 5845; VFX 852/944 deliberately does not
consume, while other action types fall through to the explicit unsupported debug
path. Across every placed Ul'dah category-4 shop listing, with source price at or
below the maximum evidenced 208 gil, there are **zero listed items** whose ItemAction
row uses 853, 1322 or 5845 and therefore zero routed candidates. The exact action
set and zero counts are Python-enforced. The clean generated catalog SHA-256 is
`f0d619a6ef8024d73a7ac742093b4c09743a1e18e028fa65109a612c10753af2`; 52 focused
contracts pass. This blocks only the current shop-funded, placed-Ul'dah path and
does not justify a consuming-item mutation claim. A legitimate quest/combat reward,
more funds, another territory/shop, or newly implemented source action semantics
would require a new exact inventory/unlock/restart scenario.

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

This is one headless sale/multi-quantity purchase pair and one non-consuming VFX item action, not general shops, arbitrary item/quantity
transactions, consuming item mutation, currency-container movement, real-client shop presentation,
transaction isolation, multi-process allocation safety, crash consistency or
leak-freedom.

## Full Linux gameplay deployment and restart correction

A local Ubuntu 22.04 container now provides actual Linux gameplay evidence, not
only worker contracts. The complete `sapphire_gameplay_ci` target was built with
GNU 11.4 from an isolated rsync source copy; API, lobby, world, DB manager, script
modules and worker were staged together. All six native suites passed in 0.20s.
The proprietary game directory was mounted read-only and remains untracked. An
initial smoke attempt mounted only `game/sqpack`; the world requires the sibling
version file, so that setup failed closed and its shutdown crashed. Mounting the
complete private game directory read-only corrected the deployment input, after
which genuine login/idle/logout passed in 133.92s.

The first strict nine-case Linux gate then reached eight passes but failed the
creation case's world restart. Preserved diagnostics in
`.e2e-artifacts/linux-ci/gameplay-ci-arnftlzr` show the replacement world finishing
territory setup and then reporting `bind: Address already in use`; because
`Acceptor` explicitly disabled address reuse, prior Linux client sockets in
`TIME_WAIT` prevented the owned listener from restarting. The same log then
recorded SIGSEGV/SIGABRT because an early initialization return still allowed the
main update loop to enter partially initialized world state.

Commit `4bbf7ec9a` keeps exclusive Windows bind behavior, enables POSIX
`SO_REUSEADDR` for an owned listener restart, and publishes `m_bRunning` only after
all update-loop services are ready. A deliberately invalid-data Windows startup
then exited with status 1 after `Failed to open file`, without entering the update
loop or producing a crash signal. The Linux creation/restart case passed in
216.75s. The subsequent strict clean-source gate passed all nine cases in
1009.57s with exact input identities and cleanup:

- summary: `build-e2e/ci-summary-linux-gameplay.json`;
- private diagnostics: `.e2e-artifacts/linux-ci/gameplay-ci-kekux1o4`;
- revision: `4bbf7ec9a2aaaa9663cb54223cee52c68b35f69b`;
- worker SHA-256:
  `b24e9014926dc436aef4dd3ba5b4e667fb8b9c1058218262f7facddda1d6ed6d`;
- creation artifact SHA-256:
  `0be489b0557b670a494caa9e01e9161b892a5a74f84391cb277d228c4c1b36cf`.

This verifies the current supported live suite on one local containerized Linux
deployment. It does not establish hosted runner execution, other distributions,
capacity, multi-process safety, leak-freedom or independent graphical-client
compatibility.

## Next actions / boundaries

1. Broaden supported-state policy coverage, including consuming item mutation, overflow merges and
   inventory operations beyond the verified ordinary-bag move/swap/split/merge, and add longer/higher-population
   controls. The observed autosave retention is fixed and the matching 30-minute
   replay is flat; this does not establish capacity or memory stability for all
   code paths. Generator histories/allocator retention also remain distinct from
   server resource behavior.
2. Extend combat beyond the now-verified initiated and unprovoked active-vision
   enemy/player defeat paths, homepoint return, naturally earned Fast Blade→Savage
   Blade combo and persisted current-test-table rewards: broader aggro/leash and enemy-reset policy, other combo chains,
   broader abilities and production loot selection remain uncovered. Preserve
   received source/target effects, resources and range checks, require genuine
   navigation for pursuit, and do not replace progression with grants or
   fixture-edited levels. Raise remains blocked by absent normal offer/acceptance
   semantics; do not send the trusted `RaiseSpell` command without a received offer.
3. Extend explicit trigger/scene adapters and the normal creation journey beyond
   the first Ul'dah opening branch; unknown content must still fail. Instance entry
   is not currently a defensible shortcut: `findContent` accepts a requested
   territory without checking a received unlock/level, while `cfDutyAccepted`
   explicitly logs `TODO: Duty accept`. The level-one fixtures expose no established
   received duty-unlock state. Do not send a normally unavailable duty request merely
   because this server trusts it; first obtain a source-defined ordinary unlock
   journey and exact received eligibility/match semantics.
4. Provision and validate the authored gameplay CI on a workflow-restricted disposable
   runner (none is currently registered), including approval/cancellation/disposal.
   The separate 30-minute paced workload is not part of the fifteen-case CI gate.
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

## Current strict-gate transport and isolation hardening

The current regression increment closes several harness races without weakening
received-state requirements:

- `Channel` retains an optional completion callback with each asynchronous write.
  A movement waypoint remains `moving` until its terminal zone frame has actually
  been published by Asio; `route_sent` is still local transport/prediction evidence
  and never substitutes for the independent observer.
- Private profiles may select only integer `deadline_scale` 1..3. The selected
  value is in every manifest and public allowlisted summary. It multiplies bounded
  command/state ceilings and the native 30-second zoning watchdog only; there is no
  fixed sleep, mutation retry, or acknowledgement-as-state fallback.
- Combat loops now wait for each exact received committed HP value before enabling
  the next actor, and unprovoked-aggro checks wait for effect plus matching integrity
  instead of racing a later packet. Full-party teardown publishes the independent
  logouts concurrently before waiting for every acknowledgement.
- The strict runner fixes pytest's root explicitly, retains private
  `gate-diagnostics.json`, provisions a fresh environment per allowlisted case,
  verifies every staged manifest, and requires every environment's process and
  runtime cleanup. This avoids accepting prefixed/foreign node IDs or inheriting
  roaming actors and teardown backlog between cases.

Commits `c56ad6fbe`, `e211f5f33`, `909c27b00`, `6c5540e00`, `028d38eb5`, and
`e34d695fd` preserve the intermediate diagnosis and final bounded behavior. The
temporary low-port and alternate-loopback experiments were explicitly reverted
after proving that WSL host forwarding did not provide a reliable kernel-loopback
lane; no wildcard or LAN listener support was retained.

The clean current Windows gate described above is the positive verification
surface. The retained expanded Linux failure is equally important: it proves that
collection, input binding, and cleanup work on the current GNU worker, but it does
not prove expanded Linux gameplay compatibility. The older nine-case Linux success
therefore remains the only green Linux live scope. This requirement stays open
until a new source-supported scheduling/transport hypothesis produces a clean
expanded run; repeating the expensive gate without one is not warranted.

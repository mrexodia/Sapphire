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

## Owned native worker exit: required and independently reported

Feature **`933a9eff6`**, with test correction **`90b4f527c`**, wraps the shared
runner's owned worker context in `support/development_worker_exit.py::ObservedWorker`.
Every report starts with an unknown exit record. After context teardown the wrapper
polls that exact owned `Popen` handle and records only context-attempt/completion,
numeric PID/return code and sanitized error types. A nominally successful scenario
cannot release its account leases or pass unless context exit completed and the
owned process has a positive integer PID and observed return code zero. Unknown,
unbound or nonzero exits fail closed.

An earlier gameplay/deadline exception remains primary even if a test adapter would
suppress it or worker cleanup itself fails. Failed-run leases stay retained even
when the native process exits zero; cleanup failure metadata contains no exception
message, command line, stderr or credentials. A constructor failure remains
explicitly unobserved. Legacy `worker_closed` is still normal-path-only, so it is
not conflated with this process receipt. `DEVELOPMENT.md` documents that local
worker exit is **not** server logout, actor disappearance, offline exclusion,
world-cache quiescence, complete handle/thread reclamation or reset authority.

Initial focused contracts **124 passed, 0.99s**. The first frozen-source selection
at `933a9eff6` retained **143 passed / 1 failed**: an older graphical-viewer test
double did not accept the reconnect helper's existing `inventory_report` keyword,
so the runner correctly reported failure. `90b4f527c` fixes only that test contract
and asserts the exact keyword instead of weakening production behavior. The final
focused selection is **144 passed, 0.95s**; the final frozen committed selection at
`90b4f527c` is **60 passed, 0.47s**. Artifacts:
`development-worker-exit-contracts-{001,002}.json`, both frozen-source manifests
and timing files. The failed first clean result remains preserved.

A separate control-only native diagnostic used worker revision `899cfa747`
(SHA-256 `b0400f61813c3ee9c7ae1f1b8bdd945b296d1410628e0bf301d937cc11cd0099`)
and controller `90b4f527c`. It started no server and used no account, endpoint or
gameplay action. One fresh worker completed a capabilities request and normal
context teardown with return code0 in **0.015s**. A second fresh owned worker was
terminated through its exact `Popen` handle; return code1 was observed and rejected
with `DevelopmentError` in **0.016s**. Both action/event/stderr journals are empty.
Post-check inspection found no owned processes and only pre-existing MySQL7764.
`development-worker-exit-native-001/inspected-evidence.json` binds the raw files;
verification-summary SHA-256 is
`1958721c559140ac33f884c082be4223ceaf38f9f9a457ad35b2877a0ef6f625`.

No live HTTP/lobby/world session was rerun for this lifecycle-only increment, and
the earlier deadline live evidence predates it. Therefore there is no new gameplay,
server-session closure, character-reuse, hard-kill recovery or leak-freedom claim.
No full gate, soak or platform sweep ran; overall goal remains incomplete.

## Provisioning requires exact owned-worker exit before lease release

Feature **`74e2da62d`** reuses the owned-worker wrapper in
`provision_development.py`. Provisioning reports begin with explicit unknown exit
state; only completed context teardown with a positive integer PID and return code
zero can reach `worker_closed:true`, release the two account leases, emit the
account/identity association and return `provisioned`. Constructor failure,
nonzero/unknown/boolean PID or return code, observation failure and teardown errors
retain credentials/evidence and leases without retrying creation. The report keeps
only sanitized process metadata.

`support/development_worker_exit.py::require_normal_worker_exit` centralizes the
strict receipt validation. `prepare_development.py` now rejects legacy, missing,
malformed or failed receipts before generating a placement registry. This receipt
is still separate from each character's required `logout_server_close_verified`;
it does not establish server-offline exclusion, cache quiescence or reset authority.
`DEVELOPMENT.md` documents that boundary.

While selecting these contracts, two existing placement tests exposed a regression
from the aggregate deadline increment: `run_development` reused `deadline` for the
120-second placement timestamp, then attempted `.report()` on that float. Minimal
fix **`99ef17666`** renames the local timestamp to `placement_deadline`; no timing,
placement or gameplay policy changed. The focused placement selection then passed
**34 tests, 0.27s**.

Final combined provisioning/placement/binding/deadline/viewer contracts passed
**203 tests, 1.30s** in the feature worktree and **203 tests, 1.36s** from frozen
clean commit `74e2da62d`. Tests cover successful receipts, exact ordering, retained
leases after fully completed creation with abnormal worker exit, constructor
failure, strict integer fields, sanitized reports, rejected legacy planner inputs
and unchanged negative ownership/lifecycle policies. Artifacts:
`development-provisioning-worker-exit-{contracts-001,clean-timings,source}.json`
and its frozen source.

Post-commit native control `development-provisioning-worker-exit-native-002` used
the unchanged worker `899cfa747` / SHA-256
`b0400f61813c3ee9c7ae1f1b8bdd945b296d1410628e0bf301d937cc11cd0099`.
One capabilities-only worker exited zero and was accepted in **0.016s**; another
fresh exact-owned child was terminated, returned1 and was rejected in **0.016s**.
No server, endpoint, account, provisioning or gameplay action was used; all native
journals are empty and only pre-existing MySQL7764 remained. Summary SHA-256:
`2a502627fd4267cb383ec2a2a596a5e288282eab0147d28c0a18733ca1d6b71d`.
The preceding `native-001` preflight failed before worker creation because its
private driver transcribed the expected SHA-256 incorrectly; that failure remains
retained and was not upgraded or overwritten.

Bounded **`development-provisioning-worker-exit-live-001` passed** on a fresh owned
disposable runtime using controller `74e2da62d`, the same worker and unchanged clean
backend `e665c041f` with checked hashes. Normal HTTP account creation, fresh HTTP
login and encrypted lobby creation produced two new GM0 Gladiators in private182:
**Tester NFLDNKKKKZCW /2097153/18014398526259201** and
**Tester AKUGJRBATUBE /2097154/18014398526259202**. Each had a distinct received
identity and normal server closure. The exact eight actions are login/logout/
close/remove for each bot; raw events contain both `server_logout_complete`
observations.

The native worker exited with PID471876/return code0 before leases were released.
The offline planner accepted that report and wrote but did not execute a placement
registry; missing, nonzero, boolean-PID and incomplete receipts were independently
rejected. Startup took **17.562s**, provisioning **12.063s**, whole owned check
**30.547s**. Source integrity, exact lease absence, owned-runtime removal and
process cleanup were inspected; only pre-existing MySQL7764 remained. Private
`inspected-evidence.json` binds the summary, journals, manifest and process list;
provisioning-summary SHA-256 is
`a7bcf5f51a161f8a71b2923d593779a0873c36b7c37ca6d74233c1098cae94f0`.

This is provisioning/lifecycle evidence, not public placement execution, opening
progression, normal gameplay, existing-database access, graphical compatibility,
general reprovisioning/reset or a server-side session fence. No full gate, soak or
platform sweep ran; overall goal remains incomplete.

## Warm host requires normal native preflight exit before startup

Feature **`6360eae53`** wraps `serve_development.py`'s capability preflight with
the same exact-owned-process observer. `status.json` starts with an unknown
`worker_preflight_exit` and retains the sanitized result. The host may start its
owned environment and prepare three fixtures only after the required bound-party
capabilities were returned and that exact native process completed context teardown
with a positive integer PID and return code zero. Constructor failure, unknown,
boolean or nonzero exit fails in `worker_preflight`; the still-unstarted environment
is cleaned and no fixture is created. This preflight never authenticates and is
not a server-session/offline receipt.

Focused host contracts passed **36 tests, 0.76s**. The combined host/worker-exit/
provisioning/placement/deadline selection passed **186 tests, 1.87s** in the feature
worktree and **186 tests, 1.88s** from frozen clean `6360eae53`. Negatives cover
return codes1/-9, unknown and boolean values, constructor failure, unsupported
capabilities, no server start/fixture creation, sanitized status and owned
environment cleanup. Artifacts:
`development-host-worker-exit-{contracts-001,clean-timings,source}.json` and its
frozen source.

`development-host-worker-exit-native-001` then exercised the committed host order
with the unchanged native worker `899cfa747`. In a fake environment that starts no
server and uses no endpoint/account/gameplay action, a normal capabilities-only
worker exited zero, after which the synthetic environment reached ready/stopped.
A second exact-owned worker was terminated after capabilities; return code1 was
recorded, host status stayed failed, environment starts remained0, fixture count0
and cleanup completed. Both native journals are empty, source integrity passed and
only pre-existing MySQL7764 remained. Whole two-case control **0.062s**;
verification-summary SHA-256
`ae49f8e29982fdd8d3b73629ef0e0b3d78cc1f5ba7d55a2b22b60e88ea0d2e71`.

No actual server or warm-host live scenario was rerun, so this adds pre-start
lifecycle enforcement rather than gameplay, server cleanup, fixture correctness,
hosted execution or hard-kill proof. No full gate, soak or platform sweep ran;
overall goal remains incomplete.

## Managed-host and graphical consumers reject legacy exit-only booleans

Feature **`c15f1af94`** moves strict normal-worker receipt validation into
`support/development.py`, leaving `ObservedWorker` as the producer and making the
same contract available without an import cycle. Managed-host checks now require
the bound ready `status.json` to contain a valid `worker_preflight_exit` in
addition to owner PID/creation time, deadline, endpoint, protocol and worker hash.
Missing, malformed, boolean-valued or nonzero receipts fail before runner or
provisioner authentication. This remains a cooperating local artifact check, not
a signature, server lock or atomic process-loss fence.

`support/client_development.py::require_graphical_check` now also requires the
normal runner's exact `worker_exit`, in addition to released leases,
`worker_closed`, every requested movement/social/reconnect/viewer result and the
same GM0 viewer identity at both checkpoints. A legacy summary containing only
`worker_closed:true` cannot close the current graphical bridge. Native process
exit still does not replace each normal logout/despawn/server-closure observation.
`DEVELOPMENT.md` and `REAL_CLIENT.md` document both distinctions.

Combined host/graphical-policy/client-smoke/worker/provisioning/deadline contracts
passed **283 tests, 2.82s** in the feature worktree and **283 tests, 2.53s** from
frozen clean `c15f1af94`. Negatives cover every receipt lifecycle boolean,
zero/boolean PID, nonzero/boolean return code, wrong scope and absent receipt, plus
unchanged owner/binding/subcheck/viewer policies. Artifacts:
`development-exit-consumers-{contracts-001,clean-timings,source}.json` and its
frozen source.

A post-commit artifact check loaded graphical bridge004's original passed normal-
runner summary (SHA-256
`c6d65ae5084e4cf5d38562a3df1eb2011a986ac7f7ab2c14479c33c9b453aa4f`).
That historical report has `worker_closed:true` but predates `worker_exit`; the
current validator rejected it with `DevelopmentError`. This does not erase or
upgrade the original version's inspected graphical observations. It proves only
that the stricter current coordinator requires fresh evidence. Artifact:
`development-exit-consumers-artifact-check-001.json`.

No graphical client, server, endpoint, account or gameplay operation was run for
this policy increment. Current-code graphical execution, user's existing shared
deployment, server-side exclusion and hard-kill behavior remain pending. No full
gate, soak or platform sweep ran; overall goal remains incomplete.

## Graphical coordinator requires its outer observer-worker exit

Feature **`cb3ac558c`** wraps `run_client_smoke.py`'s outer native witness worker
with `ObservedWorker` and initializes `observer_worker_exit` before setup. The
coordinator still requires the final witness's normal server closure and native
bot removal first. Only then does it enter the explicit `observer_worker_exit`
stage; context teardown must observe the exact owned process with a positive
integer PID and return code zero. Nonzero or unknown exit changes an otherwise
successful manual scenario to failed. The original failure remains primary when
logout, server closure, removal, activity deadline or another scenario step fails.
Graphical-process/environment cleanup and terminal artifact publication still run.

This is distinct from the optional development runner's nested `worker_exit`:
current development-mode graphical success now requires both the normal runner's
receipt and the outer manual observer's receipt, plus separate witness-retirement
server lifecycle observations. Neither process receipt proves actor absence,
offline reuse authority, Sandbox disposal or crash consistency. `REAL_CLIENT.md`
adds the receipt to the explicit result-inspection checklist.

Focused lifecycle contracts passed **13 tests, 0.21s**. The combined graphical
policy/snapshot/timing/viewer/worker selection passed **141 tests, 16.28s** in the
feature worktree and **141 tests, 16.28s** from frozen clean `cb3ac558c`. Synthetic
coordinator paths cover normal zero exit, return code1, unknown return code, final
server-closure/removal failures and deadline expiry while preserving operation
ordering, retained retirement evidence, cleanup and terminal failure stages.
Artifacts: `client-observer-worker-exit-{contracts-001,clean-timings,source}.json`
and its frozen source.

No Windows Sandbox, graphical client, server, account or gameplay operation was
run. Bridge004 predates both new process receipts and remains historical evidence
only at its original coordinator version; current-code graphical execution and
operator disposal evidence are pending.

## Graphical bot scenario requires an aggregate deadline receipt

Feature **`54f4e01ba`** closes a distinct nested-run deadline gap. The manual lane
already had a 20-minute absolute activity deadline and `ActivityWorker` capped
individual native calls by its remainder, but its direct `run_development()` call
used the programmatic unbounded default and emitted no aggregate runner deadline
receipt. `run_graphical_development()` now computes an integer 1..900-second
cooperative budget from the remaining activity window with a one-second admission
margin, passes the exact normal party/Tell/reconnect/viewer flags plus
`max_seconds`, and retains the existing absolute `ActivityWorker` cap. Too little,
NaN or infinite remaining time rejects before runner/worker startup.

`require_graphical_check()` now requires the exact six-field enabled deadline
receipt: strict integer limit, unexpired, session work completed within budget,
cooperative-not-hard-limit scope, and explicit cleanup-outside-budget boundary.
Missing, disabled, expired, malformed, type-confused, extra-field or incomplete
receipts cannot close the bridge. The accepted receipt is copied into the bridge
evidence. It is not hard preemption: in-flight bounded calls and cleanup can finish
later, while the outer graphical activity/lifecycle checks remain authoritative.

From new remote-free frozen exact commit
`54f4e01ba67823cc19275ec9202e8a71d6cf9fd1`, graphical bridge, smoke, lifecycle,
runner and deadline contracts passed **140 tests in 0.97s**. Tests verify exact
flag/budget forwarding, 900-second cap and admission margin, late/invalid budget
rejection, every receipt field/type/bound and missing/extra shape while retaining
all prior worker-exit, lease, viewer and server-lifecycle policies. Test-log
SHA-256:
`0b5047c4a32bfa7ec6d2a985d16d4b41bd2b00ab8b9f8ac35a83680c29b81110`.

The current validator rejected historical `client-development-live-004` read-only;
that report predates nested worker-exit, terminal-lease and aggregate-deadline
receipts. Artifact-check SHA-256:
`b7b98aaead07ddb03183943710f9cf5797a2117bce056c531fb478b9c8a2008e`.
This does not erase or upgrade its original graphical evidence and does not isolate
which of the three later policies would fail first. A post-test display command
then used `.e2-artifacts` instead of `.e2e-artifacts`; that failed shell aggregate
is retained in `client-nested-deadline-verifier-display-failure.json` and was not
relabeled. The tests/artifact check had already completed; only read-only display
and clean-source status were rerun.

No Sandbox, graphical client, server, account or gameplay operation ran for this
increment. Current-code graphical execution therefore still requires a fresh,
manually attended, approved matching-client run and explicit disposal evidence.
No full gate, soak or platform sweep ran; overall goal remains incomplete.

## Graphical bridge adds strict read-only reconnect inventory comparison

Feature **`deced4c08`** extends only the fixed nested normal-bot scenario with the
existing `verify_inventory` option. It performs no item action: immediately before
ordinary logout and after the already-required fresh login, the actor must provide
complete received projections for bags0–3, equipment1000 and Currency2000, and
slot/catalog/count contents must match. The graphical viewer remains a separate
endpoint witness and neither supplies nor observes private inventory contents.

The graphical consumer now requires `inventory_verification` requested/verified,
the exact established scope, unchanged empty `changed_slots`, exact projection
fields and ordered containers, strict sequence integers, canonical slot keys,
container/slot bounds, positive catalog/count values, exact row fields and equal
before/after contents. Missing, malformed, type-confused, foreign-container,
out-of-range, extra-field or changed projections fail. This does not add item-
instance identity, quality/durability, Crystal/armoury containers, mutation,
world-restart persistence or independent inventory observation.

From a new remote-free frozen exact commit
`deced4c085712d29b78dad59ab88e93a3462f83b`, graphical, inventory, reconnect,
deadline, lifecycle and smoke contracts passed **163 tests in 1.12s**. Contracts
verify exact `verify_inventory=True` forwarding and malformed/changed consumer
receipts while preserving nested/outer deadlines, leases, exits, viewer identity
and prior subchecks. Test-log SHA-256:
`c2381d059d93a160c32f1cf11a49d1da216c84f780b0798b685cadce9c0563a1`.

The exact current projection validator accepted both projections from existing
headless `development-inventory-live-001`: five starter-equipment rows, before
sequence122, after sequence118, unchanged contents. Read-only artifact-check
SHA-256:
`fa40532187e7c12c259720a8e4d4c4e06bed3b990ffc41ae55b27af56c62d21f`.
That confirms consumer compatibility with genuine received headless data only; it
neither reruns nor upgrades the artifact into graphical evidence. No Sandbox,
graphical client, endpoint, account or gameplay operation ran. Current graphical
execution and its explicit disposal remain pending, as do reset and broad gates.
Overall goal remains incomplete.

## Persistent witness rejects received viewer despawn/respawn

Feature **`8c651230e`** strengthens the optional separate-viewer contract beyond
independent endpoint snapshots without controlling the viewer. At the start
checkpoint each observer must now supply the native worker's existing
`known_players` record for the exact visible viewer: matching name, spawned state,
strict received-sequence bounds and a non-boolean spawn-generation token. The
runner retains the original witness through the scenario, binds its actor ID,
viewer ID and start token, and requires that exact witness/token both before and
through the finish Say reply. Any viewer despawn, zone loss or subsequent spawn
received by that witness changes the native token and fails closed. The mover may
still reconnect, and the viewer may move without changing spawn generation.

The report records the narrowly named scope
`unchanged-received-spawn-token-on-persistent-observer-not-server-session-proof`.
The graphical bridge requires that exact six-field receipt, the witness's runner
entity and viewer identity, and an identical receipt nested in the finish
checkpoint. Missing, malformed, type-confused, extra-field, changed-token,
changed-observer and internally inconsistent receipts are rejected. Older
summaries, including the prior graphical run, cannot satisfy this current policy.
The two independent ordinary Say challenges and all prior deadline, lease,
worker-exit, inventory and no-viewer-control requirements remain unchanged.

Frozen, remote-free source **`8c651230ec350f239cf6798d66b1cdfbe9ae7e21`**
passed **233 tests in 1.78s** across viewer, graphical bridge, development,
reconnect, inventory, deadline, smoke and lifecycle contracts. Negatives include
missing/malformed known-player state, boolean tokens, changed generation before the
finish challenge and a generation change while waiting for its reply. The source
copy had no remote and only its expected ignored Python cache, which was removed.
Test-log SHA-256:
`ea39dafccc87a8bc470273e1fc84da142c15b9d7a61a3a4fe8024447a7e5186b`.
Artifacts: `development-viewer-continuity-clean-{source.json,python.log}`.

A read-only compatibility inspection of the retained raw journal from
`development-placement-v2-live-001` found the separate GM operator's single spawn
on the persistent headless witness at sequence201, before the start baseline208.
There was no viewer spawn/despawn through the finish reply at sequence378, and the
witness had exactly one login. The check is independently retained as
`development-viewer-continuity-live-artifact-check.json` (SHA-256
`bc179931ce0de54853e29d784a973e222633ac8c0bf368dd59511d495f4ce3f6`).
It is raw-journal compatibility evidence only: that run predates the new report,
used a GM headless operator rather than a graphical GM0 client, and is not upgraded
to current graphical execution.

An unchanged token proves only absence of a viewer despawn/respawn event received
by one cooperating persistent client. It is not server-side online exclusion,
packet-loss-free observation, unchanged viewer gameplay, continuous rendering,
process identity, graphical compatibility or reset authority. No server, account,
worker process, Sandbox, matching client, endpoint or gameplay operation ran for
this increment. A fresh manually attended current graphical run remains pending;
no full gate, soak or platform sweep ran.

## Graphical companion scenario now requires ordinary self-Sprint

Feature **`8afbbeb0a`** adds the existing `verify_sprint=True` normal-gameplay
option to the fixed nested graphical companion scenario. It publishes exactly one
ordinary action3 self-Sprint from the non-GM mover after movement/social work and
before reconnect; the separate viewer is neither targeted nor controlled. Both bot
sessions must independently receive the same fresh self-target status50 effect and
a fresh zero-TP HUD update, while the mover must also receive group56/
3000-centisecond start metadata. Natural TP/pacing readiness, the existing
cooperative nested deadline and the outer graphical activity deadline still apply.
There is no grant, cooldown bypass, retry, resource restoration or reset.

The graphical consumer does not accept `requested/verified` booleans alone. It
requires the exact current eight-field Sprint receipt and narrow scope; two
ordered distinct character/entity identities bound to the runner entities; a
strict uint16 request; natural TP50..1000; two bounded three-history baselines
without prior mover Sprint; advancing uint64 received sequences; exact typed
source/target/action/kind/request/result/status payloads; typed HP/MP/zero-TP
rows; exact mover start and absent witness start; and equal independent effect
records. Missing, malformed, extra, reordered, stale, foreign, type-confused or
internally inconsistent evidence fails closed. The returned bridge proof names
only the narrow Sprint scope and explicitly leaves rendered action verification
false. Historical graphical summaries without Sprint remain rejected.

Frozen, remote-free source **`8afbbeb0afe488cbd4d62482d02d7546ae15df06`**
passed **342 tests in 3.03s** across graphical policy, Sprint, viewer, movement,
reconnect, inventory, party, Tell, deadlines, worker exit, smoke and lifecycle.
The selection includes publication/no-retry contracts plus consumer mutations of
scope, identities, request/TP, baselines, effect typing/target, zero TP, start,
sequence and schema. Test-log SHA-256:
`6486023f5795849056103eb9d7384f9f311ea6969a2b1a36a8ad9595ea685dfb`.
Artifacts: `client-graphical-sprint-clean-{source.json,python.log}`.

The current strict receipt consumer accepted the genuine retained headless report
from `development-sprint-live-001`: request1 after 100TP, baseline sequences
126/124, received sequences141/128, equal independently received effects, exact
mover start and no witness start. The read-only result is
`client-graphical-sprint-live-artifact-check.json` (SHA-256
`e4fbe74b6385d6ef0b7affe1f9862c4024af26a79d4a9ac970684f184b988505`).
This verifies compatibility with genuine normal-client data only; that older run
used a separate headless viewer and is not upgraded to graphical evidence.

No server, account, worker process, Sandbox, matching client, endpoint or gameplay
operation ran for this increment. Received effect/TP evidence does not prove
movement speed, status expiry, exact net TP debit, cooldown readiness, persistence
or rendering. A fresh manually attended current graphical run and explicit guest
disposal remain pending; no full gate, soak or platform sweep ran.

## Graphical companion scenario requires starter-body round trip

Feature **`e68038dfd`** adds the existing `verify_equipment=True` option to the
fixed nested graphical companion scenario. After social/Sprint work, the non-GM
mover publishes one ordinary unequip of starter body item2983 from equipment
1000:3 to required-empty bag0:0. It must complete a normal logout, server closure,
independently observed despawn, fresh HTTP/lobby/world login, identity/position
check, independent respawn/Say and received inventory projection before the normal
read-only inventory reconnect. It then publishes one ordinary re-equip and repeats
that fresh-login lifecycle/projection. Thus the scenario has three mover reconnects
in total. The separate viewer account is never passed to these operations.

Acknowledgements remain explicitly non-authoritative mutation evidence. The
current graphical consumer requires the exact 18-field equipment result, narrow
scope, mover identity/entity and supported Ul'dah starter class; exact initial
body and empty destination; derived unequipped contents; exact before,
unequipped, before-re-equip and restored projections; agreement with the normal
inventory comparison; strict typed operation8/context acknowledgements marked
`inventory_change_verified:false`; and two exact successful fresh-login lifecycle
receipts with bounded matching positions and no world restart. Missing, malformed,
type-confused, extra, foreign, changed or internally inconsistent rows fail closed.
The bridge proof exposes only the slot/catalog/count round-trip scope, not item
instance identity or rendered appearance. Historical graphical summaries without
this option remain rejected.

Frozen, remote-free source **`e68038dfde7adfdb86b0409e7700ed2e4117e63e`**
passed **373 tests in 3.24s** across graphical policy, equipment, Sprint, viewer,
movement, reconnect, inventory, party, Tell, deadlines, worker exit, smoke and
lifecycle. Negatives include wrong scope/count/identity/class, absent body,
changed derived/fresh-login/restored/main projections, malformed acknowledgements,
failed server closure, mismatched position, extra fields and all existing
no-retry/no-restoration mutation failures. Test-log SHA-256:
`c9605a7c4ab9b60b9d7af5a92301960f8f3352a70d8a8a5031068c8464df0c60`.
Artifacts: `client-graphical-equipment-clean-{source.json,python.log}`.

The strict current consumer accepted the retained genuine headless
`development-equipment-live-002` result read-only: Gladiator entity2097153,
body2983 at 1000:3 (sequence122), then at bag0:0 (fresh-session sequence118 and
matching normal inventory projection), then restored to 1000:3 (fresh-session
sequence118). Both operation8 receipts remained labelled not mutation proof, and
the two additional lifecycle receipts were required. The compatibility artifact
is `client-graphical-equipment-live-artifact-check.json` (SHA-256
`18f2536309f2a2808f008ba7ab7e9486b235e925f8e10a33cf029f86474c41d4`).
It does not repeat the mutations or upgrade that headless-viewer run to graphical
evidence.

No server, account, worker process, Sandbox, matching client, endpoint or gameplay
operation ran for this increment. This is slot/catalog/count restoration across
fresh logins, not item-instance, appearance, quality/durability, world-restart,
crash-consistency or all-state proof. Uncertain mutation still retains leases and
is never retried/restored automatically. A fresh manually attended current
graphical run and explicit guest disposal remain pending; no full gate, soak or
platform sweep ran.

## Graphical bridge requires exact reciprocal received Tell evidence

Feature **`dbca3e6ba`** closes an evidence-consumer gap without adding another
action. The fixed graphical companion scenario already requested two ordinary
visible-only Tell publications, but `require_graphical_check()` previously accepted
only `requested:true` and `verified:true`. It now requires the exact four-field
Tell report and narrow scope, exactly two ordered directions, strict three-field
sender/recipient identities bound to the runner entities, reciprocal distinct
character/name identities, strict advancing uint64 baseline/state/message tokens,
nonparty context, and exact run-bound direction/nonces. Boolean-as-integer values,
stale/wrong-run text, foreign/reordered peers, one-sided rows and extra/malformed
fields fail closed. Publication acknowledgements remain insufficient; only the
received recipient rows qualify. The bridge proof now names the Tell scope.

Frozen, remote-free source **`dbca3e6ba550e40fe8697bdd0b390203cb1879df`**
passed **375 tests in 3.19s** across graphical policy, Tell, equipment, Sprint,
viewer, movement, reconnect, inventory, party, deadlines, worker exit, smoke and
lifecycle. Consumer negatives cover wrong scope/count/identity, nonreciprocal
peers, stale/boolean sequences, wrong actor/nonparty context/token/message,
extra fields and malformed run IDs in addition to the existing native/controller
Tell failure set. Test-log SHA-256:
`69007329ca1a769dfacae0e0636c32cbd0de19cb4c617ec7745e5ab562cfa934`.
Artifacts: `client-graphical-tell-clean-{source.json,python.log}`.

The current strict consumer accepted both genuine reciprocal rows from retained
`development-tell-live-001` read-only. Run
`1db515bb9ff34f08bd445b4555d4b014` bound entities2097153/2097154; recipient
windows advanced 120→token122/state122 and 122→token124/state124, with party ID0.
The compatibility artifact is `client-graphical-tell-live-artifact-check.json`
(SHA-256
`6c193f5599144299bd073dbc2cf9b92fcecabf228685462f5c98a5c5b8f390b9`).
It neither republishes a Tell nor upgrades the separate headless-observer run into
graphical evidence.

No server, account, worker process, Sandbox, matching client, endpoint or gameplay
operation ran for this increment. Visible-peer Tell does not prove remote/offline
messaging, privacy, delivery under disconnect, general channels or rendering. A
fresh manually attended current graphical run and explicit guest disposal remain
pending; no full gate, soak or platform sweep ran.

## Graphical bridge requires exact owned-party evidence

Feature **`e20adfdac`** closes the corresponding party consumer gap without adding
or repeating a social mutation. The graphical scenario already required the exact
owned two-bot lifecycle, but its downstream consumer previously accepted only
`requested:true` and `verified:true`. It now requires the exact eight-field report
and narrow scope; two ordered distinct identities bound to runner entities; strict
positive party/channel IDs, count2 and leader index0; two exact typed members in
public130; the exact successful invitation target; two run-bound chat rows on that
party/channel with matching actor/character/name and positive tokens; and explicit
empty-after-disband success. Boolean-as-integer, foreign/reordered/duplicate
identities, wrong territory/member/channel/invitation/message, one-sided or extra/
malformed evidence fails closed. The bridge proof names only the owned-two-bot
party scope, not general social behavior.

Frozen, remote-free source **`e20adfdacaf26bf7d159a5e17941f1a03d6c0a69`**
passed **376 tests in 3.17s** across graphical policy, party, Tell, equipment,
Sprint, viewer, movement, reconnect, inventory, deadlines, worker exit, smoke and
lifecycle. Consumer mutations cover scope, terminal disband state, identities,
party/count/member typing, territory, invitation, chat count/channel/token/message
and schema in addition to existing uncertain/foreign-state refusal contracts.
Test-log SHA-256:
`f341c554b8ebaed89e1313b9e81219793a1049e42c70a8389c2aab96d417a6be`.
Artifacts: `client-graphical-party-clean-{source.json,python.log}`.

The strict party subreceipt consumer accepted genuine data from historical owned
Sandbox `client-development-live-004`: run
`68139e552f114c8ca59623b4ec931055`, entities2097153/2097155, party
4672924418049, channel18858827734585344, leader0, both exact level-one members,
successful invitation, two bound chats and the recorded empty-after-disband result.
The read-only compatibility artifact is
`client-graphical-party-historical-artifact-check.json` (SHA-256
`682f35b968d13b9bcea4f9f78427b63e5b46eb8ff887d9efd133c31a4734c997`).
This validates only that historical subreceipt. The old overall summary still
lacks current Sprint, equipment, inventory, deadline, lease and continuity policy
and is not upgraded to a current graphical pass.

No server, account, worker process, Sandbox, matching client, endpoint or gameplay
operation ran for this increment. The result covers one two-member same-zone
lifecycle, not larger parties, leadership changes, kick/decline, cross-zone chat,
alliances, free companies, linkshells, persistence or rendering. A fresh manually
attended current graphical run and explicit guest disposal remain pending; no full
gate, soak or platform sweep ran.

## Graphical bridge requires the exact main reconnect lifecycle

Feature **`ef595c058`** replaces the remaining boolean-only main reconnect
consumption with the same strict receipt validator used for both equipment
reconnects. Current graphical success now requires the exact mover identity before
and after, public130, four finite positions within 0.15m of the authored expected
point, normal old-session server closure, independent despawn, fresh-login
independent respawn/Say, and `world_restart_performed:false`. The mover must be the
same strict identity already bound by the equipment round trip. Missing, malformed,
type-confused or extra fields; changed identity/territory/position; absent closure,
despawn or Say; and a claimed world restart fail closed. The bridge proof names the
fresh-login-position scope rather than treating `verified:true` as sufficient.

Frozen, remote-free source **`ef595c058db2ac533760ac8e8e4ea222ee4e4fd4`**
passed **377 tests in 3.13s** across graphical policy, reconnect, party, Tell,
equipment, Sprint, viewer, movement, inventory, deadlines, worker exit, smoke and
lifecycle. New consumer negatives cover boolean identity/territory, malformed and
distant positions, absent server closure/despawn/Say, restart confusion and extra
schema fields alongside all existing no-retry reconnect failures. Test-log SHA-256:
`0af916971aba3a8c104c2ca3f64c32bd7872f535562f6a740a702e839c6e2be0`.
Artifacts: `client-graphical-reconnect-clean-{source.json,python.log}`.

The strict subreceipt validator accepted historical owned Sandbox
`client-development-live-004` read-only: exact entity2097153/character
18014398526259201 before/after, public130, all four bounded positions, normal
server closure, independent despawn, fresh Say and no world restart. Artifact
`client-graphical-reconnect-historical-artifact-check.json` has SHA-256
`8749f7ca749406bb3011be047969f9b286127f7c9f59936754e84f84141350a4`.
That validates only the reconnect subreceipt; the historical overall run still
lacks other current requirements and is not upgraded.

No server, account, worker process, Sandbox, matching client, endpoint or gameplay
operation ran for this increment. Fresh login proves neither world restart/crash
persistence, server-side offline exclusion, cache quiescence nor reset authority.
A fresh manually attended current graphical run and explicit guest disposal remain
pending; no full gate, soak or platform sweep ran.

## Movement now has strict independent per-waypoint receipts

Feature **`d92ab936c`** upgrades the shared runner and graphical consumer from an
aggregate waypoint count to structured received evidence. For a catalogued route,
the runner binds the original mover and continuously connected witness, records
the witness's initial received sequence, the exact <=16-point/<=5m one-way authored
prefix and speed2.0, then appends one receipt for every out-and-back target in every
cycle. Each receipt contains cycle/step, exact target, the mover position received
by the independent witness and a strictly advancing witness sequence. The witness
must retain its exact entity, and each received position remains within 0.15m.
Stale sequence/cache state now fails the runner; partial receipts remain in the
failed summary and no movement is retried.

The graphical bridge requires the exact ten-field movement result and narrow
`independent-witness-waypoints-not-server-authority-or-rendering` scope. It
independently derives the out-and-back plan, checks one graphical scenario cycle,
route point/length bounds, catalog hash shape, exact mover/witness entities,
strict float speed, complete ordered observation count, finite targets/positions,
0.15m agreement and globally advancing uint64 sequences. It also binds the route
origin to the strict main reconnect expected position. Missing, malformed,
type-confused, stale, reordered, shortened, foreign, distant, extra or
origin-inconsistent evidence fails closed. Historical summaries containing only
`movement_waypoints_per_cycle` no longer satisfy current policy.

Frozen, remote-free source **`d92ab936c961284b6fa10815278dc9967048ecae`**
passed **418 tests in 3.50s** across graphical policy, movement, placement,
reconnect, party, Tell, equipment, Sprint, viewer, inventory, deadlines, worker
exit, smoke and lifecycle. Negatives include stale producer sequences and consumer
mutations of scope/cycles/entities/speed/baseline/route/completeness/order/target/
received position/sequence/catalog/origin. The synthetic inventory fixture's
initial sequence expectation was corrected from100 to101 because its now-realistic
reciprocal Say advances the mover before capture; production policy was not
weakened. Test-log SHA-256:
`c79bb744a18903af067b86b0f2a461adba5e4fb79478b0c2aac1ad654aba49a2`.
Artifacts: `development-movement-receipts-clean-{source.json,python.log}`.

A read-only reconstruction from genuine retained
`development-placement-v2-live-001` journals exercised the current strict consumer.
Its 13-point catalog prefix produced exactly 24 walk publications; witness baseline
sequence212 advanced strictly through 24 selected mover movement events to336,
with every first qualifying position within0.15m of its action target. Summary,
action and event hashes are bound in
`development-movement-receipts-live-artifact-check.json` (SHA-256
`2269b8f007f94fe62f10ff9414be5cda8621fa080ee950fcc7e09275c1e91784`).
The old run predates the new report field, so this is raw-journal consumer
compatibility only, not a retroactive current report or graphical evidence.

No server, account, worker process, Sandbox, matching client, endpoint or gameplay
operation ran for this increment. Independent received positions do not establish
server authority, collision/general navigation correctness, natural progression,
rendering or real-client movement-trace equivalence. A fresh manually attended
current graphical run and explicit guest disposal remain pending; no full gate,
soak or platform sweep ran.

## Graphical bridge requires complete viewer checkpoint receipts

Feature **`f1e45848e`** closes the last identity-only viewer-consumer gap. The
runner now uses the explicit
`two-endpoint-say-and-persistent-witness-presence-not-rendering` scope, and each
observer must retain its baseline viewer spawn-generation token while waiting for
that checkpoint's Say reply. A despawn/respawn received during either start or
finish reply window therefore fails, not merely an interruption between the two
endpoint baselines.

The graphical bridge requires the exact seven-field top-level viewer result and
no-control flag. Each checkpoint must have the exact current fields, stage and GM0
identity; exactly two ordered observers; strict per-observer presence tokens; two
complete finite received viewer observations; two exact reply rows with advancing
baseline/received sequences; one identical fresh run-prefix/stage/32-hex ordinary
Say challenge received by both; and matching stable viewer identity/token through
the wait. Start must bind `mover,witness`; finish must bind the final
`mover-equipment-reequipped,witness` sessions and the exact persistent-witness
continuity receipt. Missing, malformed, type-confused, stale, one-sided, wrong-run/
stage/observer/session, changed-token, extra or internally inconsistent evidence
fails closed. Historical identity-only checkpoint summaries cannot pass current
policy.

Frozen, remote-free source **`f1e45848e528f89c09593f4becfb36c38c2e18b9`**
passed **420 tests in 3.46s** across graphical policy, viewer, movement, placement,
reconnect, party, Tell, equipment, Sprint, inventory, deadlines, worker exit,
smoke and lifecycle. New negatives cover interruption during the start reply wait,
wrong scope/stage/token/observation count, malformed baseline/received sequence,
wrong observer/GM/message/final mover session and extra fields, while retaining all
prior continuity and no-viewer-control contracts. Test-log SHA-256:
`a998e7f7fdb0e6dd0a4eaf203ff92ab8ef26e5424e06a6067c67b304ec3d0f80`.
Artifacts: `client-graphical-viewer-checkpoints-clean-{source.json,python.log}`.

A read-only reconstruction from genuine `development-placement-v2-live-001`
summary/events passed the generic current endpoint validator. Start tokens were
mover199/witness201 with reply windows206→210 and208→210; finish tokens were
reconnected-mover113/witness201 with windows118→120 and376→378. No viewer
spawn/despawn occurred inside those windows, and witness token201 remained exact
across the scenario. Artifact
`client-graphical-viewer-checkpoints-live-artifact-check.json` has SHA-256
`77c22bbe82b4da4a3c06409d18f9052db9cb668d897c1a82d3ac991539487711`.
That older run used a GM headless operator and a pre-equipment mover name; it is
consumer compatibility only, not a current GM0 graphical report.

No server, account, worker process, Sandbox, matching client, endpoint or gameplay
operation ran for this increment. Exact received endpoint replies and persistent-
witness spawn generation do not prove rendering, client provenance, server-side
session continuity, packet-loss-free observation or all-state viewer invariance.
A fresh manually attended current graphical run and explicit guest disposal remain
pending; no full gate, soak or platform sweep ran.

## Graphical coordinator adds a separate fresh party-decline run

Feature **`5dd20330e`** preserves the producer's party/decline mutual exclusion
instead of weakening fresh-history checks. After the comprehensive graphical bot
run completes normal session/worker/lease cleanup, the coordinator starts a second
fresh `run_development` invocation against the same owned fixtures. A copied
profile omits only `quest_catalog`, so movement is not repeated; the original
profile/catalog remains unchanged. This second run requests only exact-peer decline
and the two viewer checkpoints. It computes a new cooperative budget inside the
same outer graphical deadline and uses a new worker/artifact directory. Any expiry
before admission fails without starting it.

`require_graphical_decline_check()` requires pass/shared-development scope, no
administrative wait/database/restart/movement, exact clear terminal leases and
normal exact-owned worker exit, an enabled completed unexpired deadline, two
strict entities in public130, and every unrelated optional subscenario exactly
disabled. Its exact ten-field decline receipt binds ordered distinct identities,
successful invitation target, recipient answer0 reply, inviter result5 rejection,
strictly advancing baseline/received sequences and empty parties afterward. It
then requires complete current no-control viewer checkpoints on the fresh
`mover,witness` sessions with persistent-witness continuity. Boolean/type/schema,
foreign peer, stale sequence, mixed party+decline, route activity, one-sided
outcome or wrong final mover session fails closed. `result.json` records separate
`development_check` and `decline_check` hashes/evidence; neither can substitute for
the other.

Frozen, remote-free source **`5dd20330e5099ccac94ab3a96efa6299e95eb4fd`**
passed **447 tests in 3.81s** across graphical/decline policy, viewer, movement,
placement, reconnect, party, Tell, equipment, Sprint, inventory, deadlines,
worker exit, smoke and lifecycle. Negatives cover malformed/mixed decline results,
foreign identities/targets, boolean answers/sequences, missing empty-state proof,
wrong viewer session and outer-budget forwarding. An older synthetic decline
expectation was corrected from sequences10→12 to11→13 because the now-realistic
normal reciprocal Say advances both sessions before the authored decline baseline;
no production guard was weakened. Test-log SHA-256:
`f7a6e1e09e9bea3b4aa6b07d1344cc06c38de71b0ce6f188cc7776780e52fde4`.
Artifacts: `client-graphical-decline-clean-{source.json,python.log}`.

The strict decline subreceipt validator accepted genuine retained
`development-decline-live-001` data read-only: entities2097153/2097154, exact
invitation, recipient answer0, independent inviter result5, baselines122/120,
received sequences130/124 and both-empty result. Artifact
`client-graphical-decline-live-artifact-check.json` has SHA-256
`1839137291423b061a831f934355142959d398f972a9dc0e58e57608910617a0`.
That run used a separate headless observer and predates current viewer/deadline/
lease/exit composite policy; it is subreceipt compatibility only, not a current
graphical pass.

No server, account, worker process, Sandbox, matching client, endpoint or gameplay
operation ran for this increment. The check covers one visible dedicated-peer
decline, not arbitrary invitations, offline messaging, larger-party policy,
rendering or general social behavior. Normal closure between the two authored
owned-fixture runs is not a server-side offline/reset/adoption fence. A fresh
manually attended current graphical run and explicit guest disposal remain pending;
no full gate, soak or platform sweep ran.

## Graphical bot reports retain exact shared-runner boundaries

Fix **`7300ff317`** adds one common fail-closed metadata consumer before either
current graphical bot result is accepted. Both reports must be version1,
`sapphire-3.3`, exactly one cycle, and carry a lower-case 64-hex worker digest;
server identity verification, server-process ownership, database access, account
reset, administrative preparation wait/command attestation and world restart must
all be explicitly false. The comprehensive run additionally requires a lower-case
64-hex catalog digest, while the deliberately route-free decline run requires
`catalog_sha256:null`. Missing values, booleans substituted for integers, malformed
hashes, or administrative/owned-server results can no longer satisfy the graphical
shared-development consumer.

Frozen, remote-free source **`7300ff3172458967101855b9f0b0de1d37124249`**
passed **456 tests in 3.71s**. Dedicated negatives apply each malformed boundary to
both consumers. Test-log SHA-256:
`da798a6ae83ecf135de28e3da47c6a95622a887cbd5602be9d2fd44d7cee642b`.
Artifacts: `client-graphical-runner-scope-clean-{source.json,python.log}`.

The same consumer accepted shared-runner metadata read-only from historical
`client-development-live-004` and genuine `development-decline-live-001`, recorded
in `client-graphical-runner-scope-live-artifact-check.json` (SHA-256
`15bd21056da0f39fa66f5fbd57a4dc4a67961521ee9f6a3d35e074ac647235fc`).
This is metadata compatibility only and does not upgrade either artifact to the
current composite policy. The first attempted compatibility source,
`development-placement-v2-live-001`, was correctly rejected because that placement
run explicitly enabled administrative-preparation waiting; the retained failed
probe has SHA-256
`d032293ff2e995c67b9150dcc8d7cde5c6e443f2d6675018b068d119251a09a1`.
No data was mutated and no fallback weakened the validator.

No server, account, worker process, Sandbox, matching client, endpoint or gameplay
operation ran for this increment. These producer assertions and hashes do not prove
server ownership, database isolation, absence of hidden external mutation, worker
correctness or current graphical compatibility. A fresh attended graphical run
remains pending; no full gate, soak or platform sweep ran.

## Graphical comprehensive/decline runs bind one dedicated bot pair

Fix **`8afb8a301`** closes cross-run substitution after the two individual strict
consumers pass. `development_run_pair` now requires two distinct lower-case 32-hex
runner IDs while both summaries carry the exact current staged-worker SHA-256, the
same ordered positive distinct entity IDs, and byte-for-byte equal strict
name/entity/character identity rows. The ordered names must also equal the two
validated dedicated character names in the graphical runner profile. A second
internally valid run for foreign characters, swapped entities, a different worker,
a duplicated run ID, malformed identity, or changed character ID cannot complete
the outer bridge.

The result scope is
`same-dedicated-bot-identities-across-distinct-runs-not-offline-or-reset-proof`.
It deliberately does not infer that the first server session was offline, that
cached state was quiescent, or that either character could be reset/adopted. Each
run's normal server closures, worker exit and clear cooperating-runner leases remain
separate evidence. The graphical viewer remains excluded from both bot profiles.

Frozen, remote-free source **`8afb8a301b3d5c1c546fe79c10baf76545aee502`**
passed **458 tests in 3.94s** across graphical/decline policy and all coupled
movement/social/inventory/lifecycle contracts. Negatives cover duplicate run ID,
foreign worker, reordered entities, changed character ID/name, duplicate entities
and a profile-name mismatch. Test-log SHA-256:
`bba70ed3e9c30c545ab20bdb06f9d877cef7d64506b043637d79119a1bffb6f2`.
Artifacts: `client-graphical-run-pair-clean-{source.json,python.log}`.

No retained artifacts are falsely upgraded to a paired current pass. The consumer
correctly rejected unrelated historical `client-development-live-004` and
`development-decline-live-001` summaries (different workers/characters and the
older comprehensive schema); evidence SHA-256:
`a495fd6c0620a27250bfe259772a292f2a593d9c5dd3f11c5371161f4cd60354`.
The first read-only verifier attempt itself failed with `KeyError` because it tried
to extract Sprint names from that pre-Sprint summary before calling the consumer;
that failed verifier is retained with SHA-256
`46d9c9bfb6ae696eae7be2a2ed158fb242058da80425164142a13a587d07f517`
and was not relabelled. The corrected probe used its historical party identities
only as expected input and still required consumer rejection. No gameplay,
mutation, server, Sandbox or graphical operation ran. A current attended graphical
execution remains pending; no full gate, soak or platform sweep ran.

## Final graphical logout observer is the freshly authenticated paired mover

Fix **`2514730ad`** replaces the coordinator's prior generic `other_player`
presence assertion after nested bot work with an explicit
`logout_witness_restoration` receipt. The outer observer freshly authenticates
using the first dedicated profile account, then must expose the exact mover
name/entity/character ID from the strict run-pair receipt through both its received
lobby character list and world identity. It must be ready in public130, rank zero,
stationary, outside an event/scene, ungrouped and without a pending invitation.
Its state must independently contain exactly one current player spawn for the
original graphical viewer entity/name, GM rank zero, a finite position and a
non-boolean spawn-generation token bounded by its received sequence.

The receipt scope is
`fresh-paired-witness-login-and-viewer-presence-not-offline-exclusion`. Its newly
received viewer token is deliberately not compared with tokens owned by either
finished nested worker; it proves neither uninterrupted graphical presence across
worker boundaries nor a server-side continuous session. The later existing
`retire_witness()` still separately requires normal logout acknowledgement, server
connection closure, local bot close/removal and final exact outer-worker exit.

Frozen, remote-free source **`2514730ade13943cb7def04b054f53234f223300`**
passed **460 tests in 3.68s**. Negatives cover wrong phase/self entity/lobby
character, nonempty party, pending invitation, foreign/GM viewer, absent spawn,
boolean token, malformed pair scope/identity and reused run ID. Test-log SHA-256:
`d4253768a3b262990e4c78a2b0da773088ad0353c301e11d5de34bb55e7eafa0`.
Artifacts: `client-graphical-logout-witness-clean-{source.json,python.log}`.

No historical artifact contains the new current run-pair receipt, so none was
reconstructed or upgraded. No server, account, worker, Sandbox, matching client,
endpoint or gameplay operation ran. Current manually attended execution and
explicit Sandbox disposal remain pending; no full gate, soak or platform sweep ran.

## Original graphical witness identity is bound through normal handoff

Fix **`790a70f6d`** closes the other side of the bot-account reuse chain. Before the
first headless witness is retired, the coordinator retains its received world-ready
state. After both strict nested runs establish their shared pair, the new
`development_witness_handoff` consumer requires that original state's exact lobby
name/entity/character identity to equal the paired mover identity and the expected
owned witness name. The original session must have been rank-zero, ready in
public130, empty-party and without a pending invitation. Its exact retirement
receipt must name outer bot `witness` and contain strict boolean
`server_close_observed:true` and `native_bot_removed:true` under scope
`normal-witness-session-retirement-not-offline-exclusion`.

The resulting scope,
`same-dedicated-witness-across-normal-handoff-not-offline-exclusion`, joins
identity and normal lifecycle evidence before profile reuse. It does not infer
server-side offline exclusion, cache quiescence, cross-process reset authority or
safe reprovisioning. The later run-pair, restored logout witness, final retirement
and outer worker exit remain separate receipts.

Frozen, remote-free source **`790a70f6d9a984a271739a3b2b00b27400d29090`**
passed **462 tests in 3.71s**. Negatives cover loading/GM initial state, changed
lobby character ID, nonempty party, pending invitation, integer-for-boolean closure,
missing removal, foreign outer bot and mismatch against the paired character.
Test-log SHA-256:
`e414d8a466edbd3db108ff8385e4273eaa563668dc515543e6877e66c4a647cc`.
Artifacts: `client-graphical-witness-handoff-clean-{source.json,python.log}`.

Historical `client-development-live-004` predates both strict witness-retirement
and current run-pair receipts, so it cannot be reconstructed into this proof. No
server, account, worker, Sandbox, matching client, endpoint or gameplay operation
ran. Current attended execution/disposal remains pending; no full gate, soak or
platform sweep ran.

## Outer graphical deadline includes exact observer-worker exit

Fix **`8977615b9`** closes a late-success window after final witness retirement.
The coordinator now initializes a structured 1200-second `activity_deadline`
receipt when manual activity begins. Successful activity requires the exact outer
`ObservedWorker` context to finish and report normal process exit before the
absolute deadline; the post-context check rejects equality with or passage beyond
the deadline. A late zero-exit worker is therefore a failed
`observer_worker_exit` stage, not a passing run followed by slow cleanup.

The exact receipt records `enabled:true`, integer `limit_seconds:1200`, strict
`expired`, and `activity_and_worker_exit_completed_within_budget`, with scope
`cooperative-manual-activity-success-deadline-not-hard-cleanup-limit` and explicit
`environment_cleanup_may_exceed_deadline:true`. Failures before expiry remain
failed/incomplete rather than being mislabeled expired. Final title-screen process
termination and environment removal are not forcibly interrupted; they may happen
after activity success, but any cleanup error still changes the overall result to
failed.

Frozen, remote-free source **`8977615b90ca1d2ccce4289dd94cabb84e09a8f0`**
passed **463 tests in 3.87s**. Coordinator control tests distinguish normal
completion, expiry before/during final witness retirement, a newly simulated expiry
during exact outer worker exit, nonzero/unknown worker exit, server-closure and
bot-removal failure. The late worker case retains PID/returncode0 but cannot set
the completed deadline bit. Test-log SHA-256:
`361c236d2ff97683e83d2a8604e3cbe54f222582eecb63144b4afde3e21c2427`.
Artifacts: `client-graphical-outer-deadline-clean-{source.json,python.log}`.

Historical graphical results do not contain this receipt and are not upgraded from
their wall-time diagnostics. No server, account, worker, Sandbox, matching client,
endpoint or gameplay operation ran. This is cooperative success bounding, not
hard preemption, crash consistency or proof that cleanup cannot block. Current
attended execution/disposal remains pending; no full gate, soak or platform sweep
ran.

## Current graphical result has a read-only pre-disposal inspector

Feature **`3020a585a`** adds
`python -m tests.e2e.inspect_client_development_result --output <output>`. It is
read-only and development-enabled/current-policy only. The CLI binds
`result.source_revision` to the exact current committed revision, requires the
successful manual-lane/client hash/fixture setup boundary, hashes both nested
summaries, and reruns the complete strict comprehensive and decline consumers. It
then recomputes the distinct run pair and checks byte/type-exact stored evidence,
prepared catalog/route origin, original-witness handoff, final-witness restoration,
two normal retirements, exact outer worker exit, completed 1200-second deadline and
ordered phase timing.

The inspector also binds `review.json`, `review-ticket.json` and the exact review
frame hash, requires a nonempty logout frame and exact ordinary-logout log marker,
checks terminal status/run association and requires the coordinator's
`runtime_removed:true`. It does **not** inspect screenshot pixels, prove the manual
review truthful, inspect server internals, or infer VM disposal. Its accepted scope
is `current-graphical-development-result-before-separate-sandbox-disposal` and it
always emits `sandbox_disposal_verified:false`; owned-Sandbox discard remains a
subsequent operator obligation.

Frozen, remote-free source **`3020a585ac2d1a33f47880c33509da40331272e3`**
passed **483 tests in 4.21s**. Inspector tests hash every synthetic file before and
after successful inspection, exercise the CLI, and reject wrong source/status/
cleanup/disposal, fixture/catalog/hash, pair/handoff/restoration, retirement,
worker-exit/deadline/timing, review, logout and terminal-status evidence, including
boolean-for-integer substitutions. Test-log SHA-256:
`162691e43652905a62f3e34c92bba5e4d17bfd076fd69309f9f6208c694d7503`.
Artifacts: `client-current-result-inspector-clean-{source.json,python.log}`.

Two implementation-test defects remained failures until corrected: initial
collection hit a missing-parenthesis `SyntaxError` at `client_result.py:204`; the
next synthetic decline changed its run ID without changing the run-bound viewer
challenge prefix and produced 17 expected strict-consumer failures. Parentheses
and synthetic challenge data were corrected; no production assertion was weakened.
The first historical probe also supplied a mistyped expected commit hash; its
failed-input record has SHA-256
`fd2b6844ea16f9bf58d43b7cbf9980684e4c495c28696ce03ccba149edbda47f`.

The corrected read-only probe used actual HEAD and rejected historical
`client-development-live-004` (source `2a33024b6`) without modifying any file;
evidence SHA-256:
`b2ba0cfdb7d00dc81029abd1de9ca23962ee0a99e9a3e220b31c4a1e2a843c58`.
That rejection does not create a current graphical pass. No server, account,
worker, Sandbox, client, endpoint, gameplay or disposal operation ran. Current
manual execution and separate disposal remain pending; no full gate, soak or
platform sweep ran.

## Outer graphical Say is fresh received evidence, not a fixed stale message

Fix **`496dec3ca`** closes a stale fixed-challenge window in the independent
real-client lane. Immediately after publishing the `say` phase, the outer witness
now captures and retains a full received-state baseline. The exact expected
`E2E real client verified` message must be absent. Success requires exactly one
new chat row with the exact graphical entity, kind10 ordinary Say, exact text, a
non-boolean token strictly after baseline and no newer than the received state.
Malformed, duplicate, stale, pre-sent or acknowledgement-only evidence fails; the
coordinator never retries the operator action. `real_say_receipt` records the
baseline/token/received sequence and narrow scope
`fresh-ordinary-real-client-say-received-by-independent-witness`.

The committed current-result inspector now independently replays the complete
outer received-state chain: the original lobby/world witness must equal the paired
mover; the exact named non-GM viewer must spawn within one metre of the fixture,
move 1–5 metres with the recorded distance matching both snapshots, remain visible
through the fresh Say baseline/receipt and review, then be absent after ordinary
logout while the restored witness identity remains unchanged. Its scope is
`received-real-client-spawn-movement-say-review-logout-not-rendering`; this still
does not inspect pixels or infer uninterrupted presence between snapshots.

Frozen, remote-free source **`496dec3caf899a8bcdbaeeb65735ef239500d9a5`**
passed **494 tests in 4.34s**. Negatives cover preexisting exact text, stale/
boolean tokens, wrong kind, equal-but-wrong actor type, extra/duplicate rows,
stale coordinator baseline, changed witness/lobby identity, foreign viewer,
boolean recorded distance, mismatched receipt, and viewer presence after logout.
Test-log SHA-256:
`a74423fd5c0321defc1475e6c9b69e95dc9e54db76a66d2403c99acbe20a1aaa`.
Artifacts: `client-fresh-say-clean-{source.json,python.log}`.

Two focused test expectations failed before correction: `actor:true` did not equal
synthetic entity12 and correctly represented no matching message rather than a
malformed match, so the type-confusion case now uses `12.0`; the authored stale-Say
coordinator failure stops at phase `say`, not the later witness-retirement phase.
Only test expectations/fixtures changed; production checks were not weakened.

Read-only current code accepted the genuine historical outer Say data from
`client-development-live-004` using its preceding movement snapshot as the
available baseline: sequence403→kind10 token480/received480 for entity2097154.
Artifact `client-fresh-say-historical-compatibility.json` has SHA-256
`ed6f18c38c8600591c82519a06bb65a0dfb7c36fd28e11688a1c25dc68f686f5`.
This is strict subreceipt compatibility only: that old coordinator did not retain
the new phase baseline/receipt or any other current composite evidence, so it is
not upgraded to a current pass.

No server, account, worker, Sandbox, matching client, endpoint, gameplay or
disposal operation ran. Current manually attended execution and separate disposal
remain pending; no full gate, soak or platform sweep ran.

## Outer graphical movement starts from a fresh post-phase baseline

Fix **`f065ffebd`** closes the analogous stale-displacement window in the
independent real-client lane. Immediately after publishing `movement`, the outer
witness now captures and retains a baseline that must still show the exact viewer
within 0.15m of the original received spawn. The final state must place that same
entity 1–5m from origin and carry a strictly advancing received-state sequence.
`real_movement_receipt` binds actor, origin, baseline/final positions, baseline/
received sequences and exact computed distance under scope
`fresh-bounded-real-client-movement-received-by-independent-witness`. Pre-phase
movement, cached final position, non-advancing sequence, boolean/type-confused
values or excess movement cannot pass; there is no retry.

The current-result inspector reruns both baseline and final movement consumers,
requires exact type-aware receipt equality, compares the reported distance to the
two retained states, and continues to bind initial/final outer witness identity.
This is independent witness received-state evidence, not rendered animation,
client input provenance beyond the manual procedure, server-session continuity or
general route correctness.

Frozen, remote-free source **`f065ffebd25b0183e280f1d535066a7fa6a5af69`**
passed **499 tests in 4.47s**. Negatives cover a baseline beyond 0.15m, malformed/
boolean baseline sequence, no sequence advance, movement over 5m, changed inspector
baseline, altered receipt and stale final state. The coordinator control path also
records the structured receipt before continuing to the fresh Say phase.
Test-log SHA-256:
`1ba49812c1ef369707f1c4b8d24ae8f74ae61d228f5eff1b89588db213abc017`.
Artifacts: `client-fresh-movement-clean-{source.json,python.log}`.

Read-only current code accepted genuine historical outer movement from
`client-development-live-004` using its preceding spawn snapshot as the available
baseline: sequence302→403 and 1.078566m for entity2097154. Artifact
`client-fresh-movement-historical-compatibility.json` has SHA-256
`54d01f52800d0543666f5bb5c1c9334eb11a9e4a0bb634303a3e77d23d64b546`.
That old coordinator did not retain the new post-phase baseline/receipt or other
current composite evidence; this is subreceipt compatibility only, not a current
pass.

No server, account, worker, Sandbox, matching client, endpoint, gameplay or
disposal operation ran. Current manually attended execution and separate disposal
remain pending; no full gate, soak or platform sweep ran.

## Outer graphical spawn is fresh and bound to the prepared fixture name

Fix **`a8378d7f8`** retains the outer witness's complete pre-client state before
launch and requires it to be world-ready with no other player and a strict received
sequence. World entry can pass only after a newer state contains exactly one
living level-one non-GM player whose exact name equals the prepared graphical
fixture and whose received position is within one metre of the fixture point.
`real_spawn_receipt` binds entity/name/rank/level/position and baseline/received
sequences under scope
`fresh-exact-fixture-real-client-spawn-not-client-provenance`. A preexisting,
foreign, stale, ambiguous, distant or type-confused spawn fails before movement.

The current-result inspector now replays that empty baseline and exact spawn,
requires the outer lobby/world witness identity to equal the paired mover in every
retained outer snapshot (including logout), and type-compares the stored spawn
receipt. This provides received-state association with the expected fixture; it
does not prove executable provenance, rendered appearance, first-run UI choices,
continuous presence between snapshots or server-side session exclusion.

Frozen, remote-free source **`a8378d7f8f8b8aed850f4148955f249f9e8c5864`**
passed **505 tests in 4.64s**. Negatives cover preexisting players, stale/noninteger
sequence, wrong exact name, distance over one metre, changed pre-client self,
foreign stored receipt and mismatched lobby identity in later snapshots. One
initial inspector negative changed only the spawn snapshot's lobby character ID;
it exposed that identity was then checked only at the initial state. The consumer
was strengthened to require the exact paired identity at every outer snapshot,
after which the negative passed; no producer assertion was weakened.
Test-log SHA-256:
`d698a8fd11459d3171ed6636176b94f972f68bc3b765c33c63194bc5f2a65b18`.
Artifacts: `client-fresh-spawn-clean-{source.json,python.log}`.

Historical graphical results do not retain a pre-client state, baseline sequence
or spawn receipt, so none can be reconstructed into current evidence. No server,
account, worker, Sandbox, matching client, endpoint, gameplay or disposal operation
ran. Current manually attended execution and separate disposal remain pending; no
full gate, soak or platform sweep ran.

## Outer graphical logout absence is phase-bounded

Fix **`dcff7ee26`** closes the last stale-window gap in the attended outer journey.
After publishing `logout`, the restored exact witness must first receive the named
viewer still present and retain its sequence and position. The viewer's absence
must then be received at a strictly newer sequence. The exact stored
`real_logout_receipt` is revalidated by the current-result inspector under scope
`fresh-real-client-absence-after-logout-phase-not-server-logout-proof`; foreign,
missing, pre-phase, stale or type-confused transitions fail. The already-required
exact `StartLogoutCountdown` server log marker and still-running graphical process
remain distinct checks rather than being inferred from despawn.

This receipt proves only a fresh received absence on the exact final witness. It
does not prove server-side offline exclusion, cache quiescence, graphical title-
screen rendering, process provenance, account reuse safety or Sandbox disposal.

Frozen, remote-free source **`dcff7ee26ab930611ca0d7a86559e1723ad5b144`**
passed **510 tests in 4.56s**. Negatives cover wrong viewer name, malformed/boolean
baseline, stale or nonadvancing absence, foreign logout-baseline actor, altered
receipt and a viewer remaining after logout. Test-log SHA-256:
`c8976772b0d2889ac3403e4216a7ed841713ac578cc95ef98dd7071a8c1212a5`.
Artifacts: `client-fresh-logout-clean-{source.json,python.log}`.

A read-only historical compatibility probe correctly failed. In
`client-development-live-004`, review is sequence528 on the original outer witness,
while logout absence is sequence336 on the freshly authenticated restored witness;
that run did not retain a post-logout-phase baseline. The failed probe remains
`client-fresh-logout-historical-compatibility.json`, SHA-256
`68375cb8a5dc7fada8e268d1c9a3e9e2e4f555616925c75a1dee41008a384fcd`;
it is not relabelled as evidence.

No server, account, worker, Sandbox, matching client, endpoint, gameplay or
disposal operation ran. Current manually attended execution and separate disposal
remain pending; no full gate, soak or platform sweep ran.

## Manual rendering review uses a run-bound ordinary Say challenge

Fix **`8778e8f7f`** replaces the fixed witness rendering prompt with
`E2E witness challenge <first-12-run-hex>`, derived fail-closed from the exact
32-character lower-case graphical run ID. The coordinator retains the challenge,
sends it through the ordinary non-GM witness Say operation, includes it in the
published review instruction and exact review ticket, and captures the frame only
after sending. Operator approval now requires exact ticket shape and the derived
challenge in addition to run ID, frame SHA-256, both named checks and explicit
manual approval. The current-result inspector recomputes the challenge and binds
report, ticket, review and frame before acceptance.

This prevents a fixed or foreign Say screenshot/receipt from satisfying a new run.
It remains manual pixel evidence: structured validation does not prove that the
operator inspected the pixels, that delivery rendered correctly, or that the
viewer continuously observed the witness.

Frozen, remote-free source **`8778e8f7f08c33d3845c5c9e74b4a13f973e7889`**
passed **513 tests in 4.66s**. Negatives cover malformed/mixed-case/type-confused
run IDs, stale challenges, altered review fields, foreign ticket challenge, changed
frame, wrong phase and result/ticket mismatch. Test-log SHA-256:
`32ab68392562f7c9320305476e3ebd151085bb61008005436a40ad7338e5d72f`.
Artifacts: `client-run-bound-review-clean-{source.json,python.log}`.

Current policy correctly rejected the historical fixed-message review from
`client-development-live-004` because its ticket has no run-bound challenge. The
read-only rejection `client-run-bound-review-historical-rejection.json` has
SHA-256 `6df54cc0eba71517d2d0b74b482398a3ebdcac310a6103feafeb87847119bbf4`.
It does not revoke that artifact's historical scope or promote it to current
rendering evidence.

No server, account, worker, Sandbox, matching client, endpoint, gameplay or
disposal operation ran. Current manually attended execution and separate disposal
remain pending; no full gate, soak or platform sweep ran.

## Title-screen rendering requires separate exact-frame manual review

Feature **`6ba302459`** closes the prior gap where a nonempty `logout.png` was
accepted without the documented human title-screen check. After the exact ordinary
logout marker, fresh received absence and still-running client check, the
coordinator now hashes the captured frame and publishes `logout-ticket.json` with
exact run/hash/scope. Only after terminal `status=passed` may the operator run:

```
python -m tests.e2e.prepare_client_smoke approve-logout \
  --output <output> --reviewed-title-screen
```

That command rehashes the frame, requires the exact passing terminal run and
atomically writes `logout-review.json` with the sole explicit
`client_title_screen_rendered` check. The current-result inspector requires and
revalidates the report hash, ticket, receipt and bytes before accepting pre-disposal
evidence. This remains distinct from the ordinary server logout marker, received
despawn, process liveness, first rendering review and later Sandbox disposal.
Neither a receipt nor a hash performs pixel recognition or proves server-offline
exclusion.

Frozen, remote-free source **`6ba302459b57cf6bb322810f710e0ae64b339ab1`**
passed **517 tests in 4.81s**. Negatives cover wrong/failed terminal runs, changed
frame, malformed/foreign run/hash/scope, false or type-confused manual approval,
incomplete checks, report/hash mismatch and modified frame bytes. An initial
focused collection exposed a development `SyntaxError` from stray `},{` after the
logout-marker assignment; it was corrected before commit and never represented as
a passing run. Test-log SHA-256:
`9102b2102111c7f8dd2d8eafda2e6c7b8703de9ea008cdec7816a9abb0850d64`.
Artifacts: `client-title-review-clean-{source.json,python.log}`.

Read-only inspection of `client-development-live-004` found a nonempty historical
logout frame but no title-screen ticket or receipt, so current policy rejects it.
Artifact `client-title-review-historical-rejection.json` has SHA-256
`e4849417bada7411f7dbf2d35d1b6f1537a09e899a1ca27831e613eeb6d7bf1f`.
Its older disposal confirmation is not silently upgraded into this missing manual
rendering attestation.

No server, account, worker, Sandbox, matching client, endpoint, gameplay or
disposal operation ran. Current manually attended execution, both manual rendering
reviews and separate disposal remain pending; no full gate, soak or platform sweep
ran.

## Owned Sandbox disposal has exact launch and composite evidence policy

Feature **`7b1e881e5`** adds an opt-in host lifecycle wrapper and read-only composite
verifier without launching a Sandbox during development. Current runs are launched
with:

```
python -m tests.e2e.run_client_sandbox launch \
  --prepared <prepared> --timeout-seconds 1800
```

The wrapper validates the prepared manifest/config, rejects any pre-existing
Windows Sandbox UI process before launch, records the exact new launcher PID,
session/config/input hashes and every canonical observed Sandbox UI process
identity, and waits within an explicit 60–7200 second bound for all such UI
processes to disappear. It never kills or retries the Sandbox. Unknown PID,
inspection denial, timeout, reappearance or unobserved launcher exit retains a
failed receipt with `automatic_kill_attempted:false` and
`retry_attempted:false`; absence is not inferred from a timeout.

After the operator has actually inspected and confirmed the owned discard dialog,
`approve-disposal --confirmed-owned-discard` binds that manual attestation to the
exact disposal-file hash. Then
`python -m tests.e2e.inspect_client_sandbox_disposal --prepared <prepared>` reruns
the strict current graphical-result inspector and requires the same passing run
and result hash in the versioned launch, process-absence and manual-confirmation
chain. Only this composite emits `sandbox_disposal_verified:true`, under scope
`current-graphical-result-and-explicit-owned-sandbox-disposal`. This is exact host
UI-process disposal evidence under a no-preexisting-process admission rule, not
pixel recognition, server-side offline exclusion, cache quiescence, account reuse
or reset authority. The launcher return code is retained but not interpreted as
gameplay or graphical success.

Frozen, remote-free source **`7b1e881e5edd0631a9fbfb202531818940056e1c`**
passed **526 tests in 5.05s**. Synthetic negatives cover pre-existing Sandbox UI,
unobserved launcher timeout with no kill/retry, changed session PID, foreign or
malformed process rows, boolean manual confirmation, changed result bytes and a
foreign run at composite inspection. Test-log SHA-256:
`f68bb17a96069323198afe142535693eddbb1ad95417fe4de7d0ed5597bddf05`.
Artifacts: `client-sandbox-disposal-clean-{source.json,python.log}`.

The historical `client-development-live-004` disposal remains valid only at its
recorded historical scope. Current read-only policy rejects it because it did not
use the no-preexisting-process launch wrapper and lacks versioned session,
result-bound disposal and manual confirmation files. Rejection artifact
`client-sandbox-disposal-historical-rejection.json` has SHA-256
`a53bf41209e49c44720264e06c7510b1fc7e306a2de9aae8bcd344d7b082ff8a`.

No Windows Sandbox, server, account, worker, matching client, endpoint, gameplay
or disposal operation ran. Real Windows process-name/launcher behavior, current
manual execution, both rendering reviews and composite disposal remain pending;
no full gate, soak or platform sweep ran.

## Exact graphical-client teardown is retained as cleanup evidence

Fix **`d68ea780b`** binds the final intentional guest cleanup of the unmodified
client process. A successful run now requires the exact positive `client_pid` to
remain alive after ordinary graphical logout, title-screen capture, final witness
retirement and outer worker exit. During `finally`, the coordinator issues exactly
one forced termination to that owned process, waits up to ten seconds, and retains
version/PID, running-before-cleanup, request, observed-exit and integer-return-code
fields under scope
`exact-owned-title-screen-client-forced-cleanup-not-ui-exit-proof`. Natural exit
before owned teardown, unknown/noninteger exit or failed termination changes a
would-be pass to failed. No retry is added.

The current-result inspector requires exact receipt shape, strict booleans, PID
equality and observed integer return code. This proves bounded cleanup of the
exact launched native process only. Forced termination is not normal client UI
exit, server logout/offline exclusion, cache quiescence, Sandbox disposal or
rendering evidence; those remain separate receipts.

Frozen, remote-free source **`d68ea780b7775628b5ca09ecb98bbc26e80c3a8a`**
passed **534 tests in 7.14s**. Negatives cover boolean PID/return code, mismatched
PID, false running/request/exit fields, spontaneous post-verification exit and
unknown return code after a forced request. Test-log SHA-256:
`84730e9ac068d98a077b8e3227e910cc988dd4b3813ca7b39af4756da0119f20`.
Artifacts: `client-process-teardown-clean-{source.json,python.log}`.

Current policy correctly rejects `client-development-live-004`: it retained client
PID5796 but no exact teardown receipt. Read-only rejection artifact
`client-process-teardown-historical-rejection.json` has SHA-256
`ebdcdea4c97aaa5bc635ea57fa5fce7f74a05f5512ad4094138601be714e0c1e`.
This does not revoke the historical cleanup/disposal evidence at its original
scope.

No client, Sandbox, server, account, worker, endpoint, gameplay or disposal
operation ran. A current manually attended execution and composite disposal remain
pending; no full gate, soak or platform sweep ran.

## E2E workflows have enforceable repository control policy

CI commits **`279623c59`** and **`1f26e71f6`** harden both `.github/workflows/test-client.yml` and
`.github/workflows/gameplay-e2e.yml`. All six external action uses are pinned to
exact 40-hex revisions; both workflows declare only `contents:read`, disable
checkout credential persistence, bound every job and every individual step, and
set explicit artifact missing-file/retention policy. The public matrix job is
bounded to25 minutes. Private authorization is bounded to5 minutes, private
gameplay remains45 minutes, serialized without cancellation, manually dispatched,
default-branch reviewed, protected-environment named and selected only by the four
self-hosted/Windows/X64/ephemeral labels.

New `support/workflow_policy.py` fail-closes on mutable actions, additional token
permission, absent/zero/excess timeout, step timeout beyond its job, persisted
checkout credentials, retention over30 days, ignored missing artifacts, untrusted
private triggers, cancellation, missing environment/authorization dependency,
changed runner selector, absent boolean opt-in/default-false input, disabled-feature
bypass or failure to compare the selected ref to the repository default branch. Both workflows execute its own contract file, and
`python -m tests.e2e.inspect_workflow_policy` emits hashes/job/action inventories
under scope `repository-workflow-controls-not-hosted-execution-or-runner-policy`.
It explicitly emits false for hosted execution, actual runner-group policy and
ephemeral VM destruction.

Frozen, remote-free source **`1f26e71f6d14a6dbed5ac0bccd4e0b14b25faded`**
passed **54 focused tests in 1.06s**. Test-log SHA-256:
`15db058809a3b3938b82cc3ec10e6f65df558e062ef2a019b42e5716ae7a30d7`.
Structured policy receipt SHA-256:
`472687b82408ee3fb6ba8dfdd1aba04f58effb03f3ee9cd4f6caf4f805ec413a`.
Artifacts: `workflow-authorization-clean-{source.json,python.log,receipt.json}`.
A separate PyYAML BaseLoader syntax parse of both committed files passed; its log
SHA-256 is `30630799f965d2d1296180bda59c626d9c45c26fc3b1055bb4a4fe43a9b4cd23`.
That is YAML syntax evidence only, not GitHub Actions schema validation.

No workflow was dispatched, no runner was registered and no repository/environment
setting or remote infrastructure changed. Hosted action availability, protected
environment reviewers, runner-group exclusivity, cancellation destruction and the
current Linux gate remain pending. No gameplay, full gate, soak or platform sweep
ran.

## Isolated cleanup binds every owned service process generation

Feature **`c0640c42b`** extends disposable `Environment` lifecycle evidence beyond
an empty Python process map and removed runtime. Every database, API, lobby and
world launch now records exact process name, contiguous per-name generation and
positive PID. Normal `_stop` retains whether that exact process was still running,
one terminate request, explicit bounded kill fallback if needed, observed integer
return code and narrow scope
`exact-owned-isolated-process-teardown-not-graceful-server-exit`. World restarts
create another generation rather than overwriting identity. Duplicate active-name
start is rejected.

On close, private `process-lifecycle.json` binds all starts and teardowns before
runtime removal. The strict CI gate revalidates exact typed in-memory rows against
that file and requires every generation exactly once, all four service names,
contiguous generations, running-before-cleanup, terminate request and observed
integer exit. Its allowlisted public summary adds only
`process_cleanup_verified`; PIDs and return codes remain private. Missing, stale,
foreign, duplicate, boolean-confused or spontaneously exited rows prevent a green
gate. Forced process cleanup remains distinct from graceful server shutdown,
server-session exclusion, cache quiescence and crash/cancellation cleanup.

Frozen, remote-free source **`c0640c42bfae3f20232e8410e3aed935b3ae5d28`**
passed **60 focused tests in 1.26s**. Tests cover terminate→kill fallback, exact
world generation2 after restart, all four required names, missing/mismatched rows,
boolean PID/request/return-code confusion, artifact mismatch, retained runtime and
live process. Test-log SHA-256:
`694f5c6b3eb50d421a0dc76ae8ae4f051779006aacd9f01d7da0c2aec2cb088c`.
Artifacts: `isolated-process-teardown-clean-{source.json,python.log}`.

The first local aggregate supplied a nonexistent extensionless Windows worker path
and produced 14 setup errors rather than native evidence; it remains failed in
`isolated-process-teardown-verifier-input-failure.json`, SHA-256
`b09f97512417db2dc350d285abc1951977728acbad8ce4d7cf78ae8c941e912f`.
The corrected focused command required no worker fixture and did not relabel that
failure.

Read-only current policy rejects historical clean gate summary
`ci-summary-proximity-aggro.json`: its earlier `cleanup_verified:true` predates the
new private generation receipts and public `process_cleanup_verified` field.
Rejection artifact SHA-256:
`0b73eeb6645170c345482813b89f6fc03af247dcc4c174b68434949aadba4efb`.
That historical gate remains valid only at its original cleanup scope.

No service, database, account, worker, client, gameplay or gate operation ran.
A new isolated gate is required for positive process-generation evidence; full
gate, Linux/platform and hosted execution remain pending.

## Current graphical results bind exact private service teardown

Fix **`9046367cc`** consumes the preceding isolated lifecycle evidence in the
manual graphical bridge. After exact client teardown, `Environment.close()` must
remove the runtime and publish `artifacts/sapphire-e2e-*/process-lifecycle.json`.
Before terminal result publication, the coordinator type-compares that file with
the in-memory start/teardown rows, runs `require_process_teardowns`, and retains
its relative path, SHA-256 and narrow proof under scope
`exact-graphical-isolated-service-teardown-before-result-publication`. Any mismatch
changes the graphical result to failed cleanup.

The current-result inspector accepts only the exact three-part private relative
path, rehashes and parses the file read-only, requires exact top-level shape and
reruns all database/API/lobby/world generation checks. It type-compares the stored
proof before acceptance. This binds current structured graphical evidence to the
exact owned private service exits; it still proves neither graceful server
shutdown nor account/session offline exclusion, cache quiescence, Sandbox disposal
or crash consistency.

Frozen, remote-free source **`9046367cc9f145ebbb068eda28cf481fa2d5ae16`**
passed **538 tests in 5.31s**. Negatives cover foreign/traversing lifecycle path,
changed hash, boolean proof count, malformed boolean return code and file/report
mismatch, in addition to coordinator cleanup publication. Test-log SHA-256:
`008bf6041a4799c461feac14d7b16ce19c8b781766f695d72450d2fe567ef887`.
Artifacts: `client-service-teardown-clean-{source.json,python.log}`.

An initial synthetic fixture used a same-named class assignment for enclosing
lifecycle rows and produced 11 `NameError` failures; rows were moved to instance
initialization without weakening assertions. The retained failure artifact has
SHA-256 `59a85a82307987ff09394e3b90bf736eb3f2d82915adf8d3ca33b9367168c5b2`.

Current policy correctly rejects historical `client-development-live-004`: one
private environment manifest exists, but its result has no service-teardown
binding and its artifact tree has no lifecycle file. Read-only rejection artifact
SHA-256:
`92adc632bf026072be0e0fc89f0061ff7053c73bad0aea5cb10e4fef4d4ac418`.
The older runtime removal/disposal evidence remains historical only.

No service, database, account, worker, graphical client, Sandbox, gameplay or
disposal operation ran. A fresh current manually attended execution remains
pending; no full gate, soak or platform sweep ran.

## Graphical bot interaction now requires its own exact reviewed frame

Feature **`510889dfc`** closes a narrower rendering-evidence gap without treating
headless receipts as pixels. The final route-free decline-run viewer checkpoint
now invokes one coordinator-only callback after both exact dedicated bots have
freshly received the shared run/stage-bound finish Say and before either begins
logout. While those sessions remain active, the guest allows two seconds only for
drawing and captures `interaction.png`. Delay/file existence is not a rendering
oracle.

The coordinator then restores its exact independent logout witness and enters a
new `interaction_review` phase. The operator must inspect the immutable frame for
both exact dedicated bot names and the exact fresh viewer Say, then explicitly run
`prepare_client_smoke approve-interaction --reviewed-bot-interaction`. The strict
ticket binds the outer run, nested decline run, ordered bot names, exact challenge,
frame SHA-256 and scope
`final-fresh-viewer-challenge-while-dedicated-bots-active`. Changed images, stale
or foreign challenges/runs/bot names, wrong phases, malformed types and incomplete
checks fail closed. Callback/capture failure retains bot leases and cannot publish
a passing nested result.

The read-only current-result inspector independently rehashes the frame, compares
ticket names/run/challenge with the strict nested summaries, validates the manual
receipt, and requires a fresh outer witness snapshot from the review wait. This
third manual review is separate from the earlier fixture/witness-Say frame and the
post-logout title-screen frame. It proves only one reviewed co-presence/Say moment;
it does not prove rendering of prior movement, party, Tell, Sprint, equipment,
inventory, decline UI, continuous presence, or any server-side exclusion.

Frozen, remote-free source **`510889dfc44099a8549347d0b03cfd0a498857fd`**
passed **546 tests in 6.04s**. Contracts include callback-before-logout ordering,
callback-failure lease retention, strict bridge forwarding, exact active-phase
approval, changed-frame rejection, independent result inspection, and foreign or
type-confused run/challenge/bot/frame/receipt negatives. Test-log SHA-256:
`b9d4c6156615777b87f8bd042bd81bf32659000948d19c1f43d64117451af74d`.
Artifacts: `client-bot-interaction-review-clean-{source.json,python.log}`.

The first focused aggregate correctly failed two positive synthetic fixtures that
omitted the new `interaction_review` state. Completing those inputs made current
policy pass without weakening its requirement. Retained failure artifact SHA-256:
`a42f0e9f1107c18494552bd75b0e3d54b7a529c40a3a70eeee375dd5d09d9636`.

Current policy correctly rejects historical `client-development-live-004`: it has
none of the interaction phase snapshot, manual interaction receipt, frame, ticket
or review file. Read-only rejection artifact SHA-256:
`d03711ec32bf2f43f35824f21b2b7d8d86af7ce5c2ef6611bc5628a8821f0fbd`.
Its prior fixture/Say and title-screen rendering attestations retain only their
original narrow historical scopes.

No service, account, worker, client, Sandbox, gameplay, screenshot capture, pixel
review or disposal operation ran. A fresh current manually attended run must
produce all three explicit reviews and composite disposal evidence. No full gate,
soak or platform sweep ran.

## Current graphical evidence binds exact prepared source-manifest bytes

Fix **`86e5451ea`** closes an unconsumed provenance edge between preparation,
guest result and host inspection. New `support/client_provenance.py` accepts only
the exact current `inputs.json` and `input/source.json` schemas, strict lowercase
revision/digest fields, false dirty/submodule-fetch/remote/working-tree flags,
canonical safe relative file/gitlink paths, non-boolean version fields, distinct
unmaterialized gitlinks, and valid tracked-source/input hash maps. It requires the
source-manifest bytes' SHA-256 and revision to agree with all of:

1. `input/source.json` itself;
2. `inputs.json` top-level source fields;
3. its exact `inputs["source.json"]` entry;
4. current committed HEAD supplied to the inspector; and
5. `result.json`'s guest-recorded `source_manifest_sha256`.

The Sandbox launch/disposal path now performs the prepared-source validation before
launch publication as well. The current graphical-result inspector repeats it
read-only and emits only revision/hash/count provenance. This identifies the
committed coordinator manifest consumed by the guest; it remains neither a
signature nor native binary/client/game-data source attestation. Guest-side
`verify_source` remains the separate check of materialized committed files before
fixture/process setup.

Frozen, remote-free source **`86e5451ea06e28cd150b6466e49e2307fb8073ba`**
passed **568 tests in 23.21s**. Contracts cover changed/missing result hash,
inputs revision/hash, source bytes/boundary flags, unsafe relative paths, malformed
gitlinks, and rejection before Sandbox launch, alongside the source snapshot,
graphical result and disposal chains. Test-log SHA-256:
`294d1131388e3f3c4777322246cf4bdbf81ba855eddfef9545aaafa6a661296b`.
Artifacts: `client-prepared-source-binding-clean-{source.json,python.log}`.

Current exact-schema policy rejects historical `client-development-live-004`.
Its result/top-level source revision and manifest digest agree, but its older
`inputs.json` retains the obsolete extra `operator_control` field, so it is not
upgraded to current evidence. Read-only rejection artifact SHA-256:
`0b47820c5991d8815d3b0b2cb3f1a9a6b4cc7f4eeaa381f972f1cbd8104b4dda`.
The historical run retains only its original source-isolation scope.

No preparation, service, account, worker, client, Sandbox, gameplay, screenshot,
remote or disposal operation ran. Current attended graphical execution and all
broader blocked requirements remain pending.

## Current graphical evidence rehashes every staged guest input

Fix **`b38d0d5cb`** consumes the complete `inputs.json["inputs"]` map rather than
using it only for `source.json`. After the strict source-manifest check, both the
pre-launch Sandbox path and current result inspector recursively enumerate the
exact private `input/` tree, reject symbolic or non-regular entries, rehash every
file, and require typed dictionary equality with the preparation manifest. Missing,
changed and unlisted extra files fail closed; the accepted proof retains only the
file count and nested source provenance, not private paths or hashes.

Scope is deliberately
`all-exact-staged-graphical-input-files-match-preparation-manifest`: this covers
staged server/worker binaries and libraries, compiled scripts, graphical client
files, fixture/profile/bootstrap inputs and optional localized catalog/navigation
copy. It does **not** cover the separately mounted sqpack, movie, MariaDB, Python,
Git or navigation roots, prove that native binaries came from the source revision,
provide a signature, or establish execution/rendering compatibility. Those inputs
retain their existing separate identities and live evidence requirements.

Frozen, remote-free source **`b38d0d5cb56e6618d7196ec1967456237828ef6b`**
passed **572 tests in 21.49s**. New negatives mutate one listed non-source input and
add one unlisted file at both pre-launch and current-result boundaries; existing
source/hash/path/schema negatives and the complete graphical/disposal chains also
pass. Test-log SHA-256:
`81f3bdb64f1460279d85180dcaa7caf7c11ec70e46a667f36f0833ab0c22c6df`.
Artifacts: `client-staged-input-binding-clean-{source.json,python.log}`.

Historical `client-development-live-004` remains rejected before complete input
rehashing because its obsolete extra `operator_control` field violates the current
exact preparation schema. No historical evidence is upgraded. Read-only rejection
artifact SHA-256:
`8560311a8ec81765d29bac606f6667c44fb453bceba3f8b746bc7f8e39cf9b14`.

No preparation, service, account, worker, client, Sandbox, gameplay, screenshot,
remote or disposal operation ran. A fresh current prepared and manually attended
run remains required; no full gate, soak or platform sweep ran.

## Graphical results consume exact isolated-environment identities

Fix **`a86acd6d3`** binds the private Environment `manifest.json` into the terminal
graphical result by constrained artifact-relative path and SHA-256. The current
read-only inspector requires the exact graphical environment schema and
cross-checks its clean committed revision, profile/fixture/deadline boundary,
unique typed ports, four staged server executable digests, worker digest, complete
root compiled-script map, localized quest catalog/navigation hashes and three
committed combat-data hashes against the already strict preparation/source
manifests. It additionally binds the worker and quest-catalog digests to both
nested bot summaries and the graphical fixture.

The external server-navigation map is required nonempty with canonical safe
relative names and strict digests, but there is intentionally no completeness
claim for the separately mounted host navigation root. Database/runtime/data/nav
paths are shape evidence only and are not published by the accepted proof. The
result emits digest/count identities under scope
`exact-graphical-environment-input-identities-not-native-build-provenance`; it does
not prove binary source provenance, sqpack/navigation completeness, process
execution, matching-client behavior, rendering or server-side session exclusion.

Frozen, remote-free source **`a86acd6d37ffd2ea12958515da1716f6f8c1a6bc`**
passed **580 tests in 22.56s**. Negative contracts cover foreign manifest paths,
changed hashes, dirty source boundary, boolean executable hash, changed scripts,
unsafe external navigation rows, changed committed combat data and changed catalog
identity, while coordinator cleanup publication and all prior graphical/disposal
consumers remain covered. Test-log SHA-256:
`333737ebdd2d0a70d45893b7567d17f7237b1fc08413f0ae4322f3e52709b46a`.
Artifacts: `client-environment-identities-clean-{source.json,python.log}`.

One initial positive synthetic assertion still expected one tracked source file
after adding three committed combat-data identities; correcting that expectation
produced the clean aggregate without weakening production policy. Retained failure
artifact SHA-256:
`505598d2f79a6257250d62f47ee1a1b6f43b3d865df7bec2912324d3d4d86b41`.

Historical `client-development-live-004` contains one private environment
manifest but its result predates the required exact path/hash receipt, so current
policy rejects rather than upgrades it. Read-only rejection artifact SHA-256:
`171705fe82e554a7f5387db0519efc0a0a8c5f006ee4cf8de02762a402ddcbff`.

No preparation, service, account, worker, client, Sandbox, gameplay, screenshot,
remote or disposal operation ran. A fresh current manually attended run remains
required; no full gate, soak or platform sweep ran.

## Owned warm-host terminal status binds exact service generations

Feature **`6e28b65b0`** strengthens only `serve_development`'s bounded private warm
host. After owned Environment cleanup it type-compares the original private
lifecycle artifact with the Environment's in-memory starts/teardowns, requires all
four exact database/API/lobby/world generation/PID receipts, and atomically retains
a private `process-lifecycle.json` copy beside terminal `status.json`. A normal
`stopped` result now requires both `cleanup_verified` and
`process_cleanup_verified`; mismatch, missing generation or publication failure
changes terminal status to failed.

New read-only command
`python -m tests.e2e.inspect_development_host --session-dir <private-session>`
requires an exact terminal-success schema, normal exact preflight-worker exit,
three distinct ports, all four distinct positive owned PIDs equal to lifecycle
starts, running-before-cleanup/terminate-request/observed integer-return-code rows,
status/file hash and typed proof equality, removed exported profiles, and seven
ordered successful host phases. It emits narrow scope
`terminal-owned-warm-host-cleanup-not-external-server-or-offline-proof` without
credentials or process rows.

This does not apply to the normal already-running external shared-development
lane and proves neither graceful service shutdown, server-side account/actor
offline exclusion, cache quiescence, coordinator hard-kill cleanup, reset authority,
shared-world cleanliness nor acceptance cleanup. Preflight failures before any
service starts remain failed status and correctly have no positive service proof.

Frozen, remote-free source **`6e28b65b0d655ee06721f72dda6f7257bc538183`**
passed **338 tests in 3.83s**. Negative contracts cover failed/type-confused
terminal fields, duplicate/boolean PIDs, changed digest/proof/timing rows, changed
return code, and a coherently rewritten three-service artifact; existing host,
provisioning, placement, lease, deadline, viewer and runner contracts remain
covered. Test-log SHA-256:
`85da772da65ed1d69d9b11ba909d96fe4b0a2a1444c2bfa32aedca592caf1547`.
Artifacts: `development-host-teardown-clean-{source.json,python.log}`.

One negative test expected the later exact-service error even though the shared
generic lifecycle validator correctly rejected the missing database first. The
expected fail-closed layer was corrected without changing production policy.
Retained failure artifact SHA-256:
`52963e0ac8f8d01891d12abb154e230f811329a5549eb28b7a9fc0678a922a7a`.

Historical `development-binding-live-001` retains neither terminal host status nor
an exact process-lifecycle file and is not upgraded. Read-only rejection artifact
SHA-256:
`f1fc2b4f1f838d2742b0fa29199eacc00a8e9c0458f504849d29bff14a80a472`.

A bounded stop-on-ready execution from frozen source
**`6e28b65b0d655ee06721f72dda6f7257bc538183`** then produced positive native
evidence at `development-host-teardown-live-001`. It used the previously retained
clean worker SHA-256
`b0400f61813c3ee9c7ae1f1b8bdd945b296d1410628e0bf301d937cc11cd0099`,
created one disposable private database/runtime and three pre-connection fixture
accounts, observed readiness, immediately published the owned stop marker, and
returned zero in **24.594s**. No bot authenticated or performed gameplay; no viewer
or graphical client ran, and no retry occurred.

The terminal inspector accepted exact one-generation database/API/lobby/world
teardown, all seven ordered phases, removed private profiles and status/file hash
equality. Inspected evidence SHA-256:
`77da7addbce22966aa4990d683333d99b50d96b146ae649b97ce2758f94aaaba`;
private lifecycle SHA-256:
`3208e7abbd16a9b475a2205845a6b45e3a7a96219917479b22e78d899629c3c5`.
Read-only host process inspection found no MariaDB, Sapphire service or worker
process afterward. This is positive owned warm-host cleanup only, not a shared
external-server, graceful shutdown, offline/reset or gameplay result. No full
gate, soak or platform sweep ran.

## Managed runs retain one unchanged ready-host binding through completion

Feature **`789de5650`** makes `check_managed_host` return a sanitized provenance
receipt after its existing stop-marker, exact session, ready status, owner
PID/create-time/liveness, deadline, endpoint, worker-hash and normal preflight-exit
checks. Managed runner and provisioner summaries retain both start and completion
receipts. Before lease release, they require typed equality of the exact session,
status SHA-256, owner identity, deadline, endpoints, worker digest and preflight
worker PID under scope
`cooperating-owned-host-ready-binding-not-server-session-lock`. A stopped,
replaced, rewritten or type-confused host therefore fails and retains leases; the
provisioner also retains its recovery credential profile after any account mutation.

External shared profiles retain an explicit
`external-shared-server-without-owned-host-binding` receipt and make no host
ownership claim. Managed provisioning-association consumers now require the strict
start/end receipt rather than accepting a host-session field alone. These checks
remain cooperating local-file/process observations: they do not prevent process
loss immediately after completion, prove server-side account exclusion, authorize
reset/reprovisioning or attest shared-world cleanliness.

Frozen, remote-free source **`789de5650db962b7460f832e3adb967706f069a3`**
passed **358 tests in 4.17s**. Contracts cover exact real status receipt formation,
external boundary publication, runner/provisioner equality, changed completion
identity with retained recovery state, malformed/type-confused fields, and managed
association consumption. Test-log SHA-256:
`90cb200222e5368e9938a59f9b447afa1638bcce851e9287c65016b045f875f3`.
Artifacts: `development-host-run-binding-clean-{source.json,python.log}`.

Historical `development-host-live-002` passed at its original scope but has no
managed-host start/end receipt and is not upgraded. Read-only rejection artifact
SHA-256:
`6b0bd19aec921d6934d87622a43de7992e1f5cbb5328e32eb5ec8089bb610dc3`.

A new frozen-source live check at `development-host-run-binding-live-001` then
started one bounded disposable warm host, ran normal non-GM movement, exact party
lifecycle, reconnect and complete read-only inventory comparison, and stopped the
host. The full driver returned zero in **52.609s**; the runner passed in
**26.421s** with exact normal worker exit, clear typed lease snapshot and no retry.
Its start/end receipts have identical host session/status hash, owner identity,
deadline, API/lobby ports, clean worker hash and preflight-worker PID. Sanitized
run inspection SHA-256:
`870a27d84f898eadc7f29e0dae6861374e0d3491e1804203f4a3539145ff6852`;
summary SHA-256:
`8c3f9d4ed5b10725ff7498044646b1b23b288d103d4745aba3b4c924485f1abb`.

The separate terminal host inspector accepted exact four-service teardown and
profile removal; evidence SHA-256:
`f91c06e952d7993b526054dfeb95a0030b16c890185fbb8fc382ed3207035e6a`,
lifecycle SHA-256:
`42f7312de00e5038cdcd31681b199831e8ce493c3f62fbc2b6ae940e72eee343`.
Read-only process inspection found no MariaDB, Sapphire service or worker process
afterward. This is one disposable owned-host development check, not evidence for
an existing external server, graphical viewer, offline/reset authority or
acceptance breadth. No full gate, soak or platform sweep ran.

## Managed run and terminal host now have one composite inspector

Feature **`53ca7fe01`** adds read-only command
`python -m tests.e2e.inspect_managed_development_run --session-dir <session> --summary <development-summary.json>`.
It reruns the strict terminal-host inspector, requires a passing shared-development
boundary with all server-ownership/database/reset/restart claims false, validates
exact typed start/end host binding, normal exact run-worker exit and clear terminal
lease snapshot, and compares the run's session, owner PID/create-time, deadline,
API/lobby endpoints, worker digest and preflight-worker PID with the terminal host
status. The accepted receipt binds exact run-summary and host-lifecycle hashes.

This is deliberately lifecycle/provenance correlation. It does not revalidate
movement/social/inventory assertions, turn a local status file into server-side
exclusion, prove graceful shutdown/cache quiescence, authorize reset/reprovisioning,
or apply to an already-running external server.

Frozen, remote-free source **`53ca7fe01cdea1d43dbbab77b887744b3071b550`**
passed **366 tests in 4.70s**. Negatives cover failed/owned-server run boundaries,
type-confused changed completion PID, foreign worker digest, nonzero worker exit,
boolean lease-state proof and terminal identity mismatch; positive CLI inspection
is read-only. Test-log SHA-256:
`74ecb4778337f85498aa75e947754bdeecfe608571a884720d96f5e37a6cd7bf`.
Artifacts: `development-managed-composite-clean-{source.json,python.log}`.

The current inspector accepted the preceding live managed run and exact terminal
host evidence without mutation. Composite evidence SHA-256:
`8af245ecb64da5f35c6d4ce917fb6432bfe3325f33e32d08ca0d298b0a7d625e`.
It binds run-summary SHA-256
`8c3f9d4ed5b10725ff7498044646b1b23b288d103d4745aba3b4c924485f1abb`,
ready-status SHA-256
`17ac425d27ac99123a19e1304f814332e232517396c3eaf52232c114ba719059`
and terminal lifecycle SHA-256
`42f7312de00e5038cdcd31681b199831e8ce493c3f62fbc2b6ae940e72eee343`.
No new service, account, gameplay or process operation ran for this read-only
compatibility check. No full gate, soak or platform sweep ran.

## Retained bot leases have a read-only fail-closed inspector

Feature **`33adadfea`** adds `inspect_development_leases.py` and
`support/development_lease.py`. Given a private two-account profile, the command
derives only those two exact per-user cooperating-runner lease paths. It never
lists unrelated entries, emits account values/path hashes/paths, contacts a server
or database, or mutates/releases any file. Recovery inspection still validates the
full profile schema but does not require the historical worker executable to remain
installed.

Each receipt is limited to 4KiB, must be a regular non-symlink file, retain the
exact current `{run_id,recovery}` schema and one lowercase 32-hex run ID, and pass
before/open/after file-identity checks. These checks reject ordinary replacement
races but are explicitly not a cross-file lock. The result is `clear` only when both
exact paths are absent, `retained` only when both valid receipts identify the same
run, and otherwise `ambiguous`; ambiguous CLI results exit nonzero. Root/final
symlinks, non-directory roots, partial pairs, mixed runs, malformed/oversized files
and unreadable/changed snapshots all fail closed. Foreign directory entries are
untouched and uninspected.

The summary always says active sessions were not checked, offline state was not
verified, release was not authorized and the snapshot is not atomic. Therefore even
a `clear` result cannot authorize reuse/reset, and `retained` is correlation rather
than permission to remove either file. `DEVELOPMENT.md` directs operators to verify
both bots independently offline before narrowly reviewed manual recovery and never
to steal a lease.

The new focused file passed **16 tests**. Combined lease/shared runner/deadline/
provisioning/worker-exit/host/binding/placement contracts passed **231 tests,
2.32s** in the feature worktree. A detached clean exact
`33adadfeacd7ff0af43dc20c98bf9a02dc9119bb` selection passed **231 tests, 2.84s**;
the worktree was clean before/after and harness wall time was **6.313s**. Artifact:
`.e2e-artifacts/development-lease-inspection-clean-001.json`; test-log SHA-256
`53495481963dc1283e843eae2de4866e17f8c401b0a838dcf4ded2c26d907736`.

The first product profile check, `profile-check-001`, accidentally resolved modules
from the main checkout rather than the detached worktree. Its identical local
`clear` snapshot is retained but not used as frozen-source evidence. Fresh
**`development-lease-inspection-profile-check-002`** explicitly ran the product CLI
from detached `33adadfea` against live-002's retained private profile. It observed
both exact local paths absent and wrote `state:clear`; summary SHA-256 is
`80fe439731c6d41db4ed1adac4b91ca50656d75252d0ee70af3af7488955a21a`.
No server/process/database operation or lease release occurred. This is current
local filesystem evidence only, not proof those characters are offline or safe to
reset/reprovision. No full gate, soak or platform sweep ran; overall goal remains
incomplete.

### Runner/provisioner terminal summaries bind their reported lease state

Feature **`09c0ee071`** attaches the exact read-only snapshot to every terminal
`run_development` and `provision_development` summary. After a successful release,
`clear` is mandatory; unavailable, retained or ambiguous inspection changes an
otherwise successful result to failed. The provisioner also removes its completed
association/next-step fields, so a fixture receipt cannot be published when exact
lease release is unverifiable. No release/retry/repair is attempted.

For an acquired failed run, both valid retained receipts normally match the
summary's `run_id`; this is recorded separately from the older intended-state
boolean. A partial release remains failed with one present receipt and
`state:ambiguous`, rather than being rewritten or described as retained. Failure
before this run acquires leases does not adopt another run's receipt. Inspection
exceptions, including a second interruption during terminal publication, become a
sanitized `state:unavailable` plus error type; exception text is not retained and
the original operation evidence can still be written.

The expanded focused selection passed **298 tests, 2.91s** in the feature worktree.
Detached clean exact `09c0ee071a072ecd82cf20f5503f490c18451174` passed **298 tests,
3.14s** with clean before/after state; harness wall time was **6.828s**. Negative
contracts include partial release, malformed/ambiguous state, terminal-inspection
failure, sanitized interruption, runner success rejection and provisioner binding
suppression. Artifact: `.e2e-artifacts/development-terminal-lease-clean-001.json`;
test-log SHA-256
`4c19264a7745e8c82704a4cd92f73de9efe2a7966abdbad202fec1702eb6bdc7`.

No server, account, endpoint or real lease-release fault was exercised for this
producer integration. The current bounded live provisioning evidence predates the
embedded snapshot and is not upgraded. At this feature revision historical
consumers still used their existing strict status, binding and worker-exit checks;
the subsequent consumer increment below closes that policy edge. This is stronger
terminal evidence, not server-offline proof, release authority, crash consistency
or reset/reprovisioning coordination. No full gate, soak or platform sweep ran;
overall goal remains incomplete.

### Placement and graphical consumers require exact clear evidence

Feature **`cfb2bd636`** adds
`development_lease.require_clear_terminal_account_leases`. The validator requires
the exact version-1 `clear` snapshot: both ordered absent records, strict integer
version/count/index fields, every non-authority/contact/mutation flag exactly false,
no retained run, no extra fields and top-level producer-state agreement. Boolean-
as-integer substitutions, reordered records, false claims changed to integers,
legacy absence, retained/ambiguous state and malformed/extra data fail closed.

`prepare_development.placement_registry` now requires this evidence before accepting
a provisioning binding or producing an operator registry. The optional graphical
bridge likewise requires it before accepting the normal runner's nested result.
Thus a current planner cannot turn an old clean-looking provisioning report into a
placement approval, and a current graphical result cannot rely on the old
`lease_retained:false` boolean alone. Neither consumer treats the snapshot as
server-offline proof or reset authority.

Detached clean exact `cfb2bd636422d0fa00951619230925f6c37e9a02` passed **349 tests,
3.72s** with clean before/after state; harness wall time was **7.250s**. Contracts
cover exact-schema acceptance plus absent, malformed, extra, reordered,
boolean/integer-confused, retained and authority/contact-claim negatives in both
consumer paths. Artifact: `.e2e-artifacts/development-lease-consumers-clean-001.json`;
test-log SHA-256
`5777fc77a59507f97d345aa144cfe5e8d37294b229cfef6a63052c0ccfa875cb`.

A frozen-source offline artifact check loaded bounded live-002's original
`provisioned` report, SHA-256
`bbb0885709cf49b9a8f8cc93e084f8bc0991829e5d79a9330da891e3945b1c3a`.
That report predates `lease_snapshot`; the current planner rejected it with
`DevelopmentError`, wrote no registry and contacted no server/database. The
historical product result remains unchanged at its original version. Artifact-check
SHA-256: `bfe9dd2ac6a098931a5e706da52a2d3cd816f06eca317b3a3f63aad33396972f`.

### Current producer→strict-planner chain live on a fresh owned runtime

Bounded **`development-lease-consumers-live-001` passed** from a clean, remote-free
snapshot of controller `c198af1c3dd26f8bd520c2acda2ca4bd8cef5f4f`
(source-manifest SHA-256
`ee1a29f626c3ead12327a82907c5de90fd573c21f7f3bc811a0adb11d169246a`), unchanged
worker `899cfa747` / SHA-256
`b0400f61813c3ee9c7ae1f1b8bdd945b296d1410628e0bf301d937cc11cd0099`, and the
previously attested clean `e665c041f` backend hashes. It used a new private database,
new credentials and new artifact paths.

Normal HTTP creation, separate login and encrypted lobby/world entry produced GM0
Gladiators **Tester RRWLQJNWESMJ / 2097153 / 18014398526259201** and
**Tester GGPGLLFWVTVL / 2097154 / 18014398526259202** in private182. The exact
eight actions are login/logout/close/remove for each bot, with one normal
`server_logout_complete` each at sequence131. Provisioning completed in **11.453s**
under the 30-second cooperative budget. Exact worker PID174476 exited0, both lease
paths were absent, and the emitted strict version-1 terminal snapshot was `clear`
with producer-state agreement.

The current offline planner accepted that exact current report and wrote a private
registry bound to both character/entity identities. Registry SHA-256 is
`e6f00c48704633cc16d33b62e1b944d08949fd7e3b70bf6275b3dc3c64450adf`.
**No placement command was executed.** Startup took **17.484s** and the whole driver
**30.953s** including environment cleanup. Source re-verification, empty worker
stderr, password scan, exact lease absence and runtime/process cleanup passed; only
pre-existing MySQL PID7764 remained.

Private `inspect-evidence.py` independently re-ran the pure planner validator,
checked identities/actions/events/receipts and hashes all retained diagnostics.
`inspected-evidence.json` SHA-256 is
`760020fd8f2474fb2c1dbed2a94c57aa95ebd4e562a5ad86809e2d4dd0e58f4f`;
provisioning-summary SHA-256 is
`a5ab96b117c9b8db99e46331f68d423f672b1e1780fe8d579598a1c6e6ae1ce9`.

That artifact closes positive current producer→strict-planner integration only;
it deliberately did not execute placement. Current placement execution is recorded
separately below, while current graphical execution remains pending. The registry,
worker exit, normal server closures and local clear snapshot still do not prove
server-side offline exclusion, account reuse authority, lease atomicity,
reset/reprovisioning authority, gameplay, graphical compatibility or shared-world
cleanliness.

### Current strict receipt chain through registered placement

Bounded **`development-strict-placement-live-001` passed** on another fresh owned
disposable runtime using the same clean `c198af1c3` controller snapshot and
source-manifest hash. It did not access an existing database or start a graphical
client. Before any connection, the driver pinned the only newly generated operator
by account/character/entity/rank and changed exactly one GMRank0 row to GMRank1.
That isolated pre-first-connection fixture setup is administrative preparation,
not gameplay or permission to edit a live cached character.

Current bounded provisioning created normal GM0 **Tester GCUCMBAADWVD /
2097154 / 18014398526259202** and **Tester VBEHJMHZLWFC / 2097155 /
18014398526259203** in private182 in **11.485s**. Its exact worker PID217296
exited0 and its strict terminal lease snapshot was `clear`. The current strict
planner bound those exact received identities into registry SHA-256
`8f6f30c0cdfb9b7d9b99ccf701e1332110891579d11f0c5f877dc42306d97555`.

A separate authenticated GM operator published each exact approval/slot once; the
exclusive pre-dispatch intents remain `publication_outcome_unknown`, so neither
local receipt is misreported as mutation proof and neither request was retried.
Both ordinary non-GM clients independently journaled `init_zone` **182→130** at
the reviewed position. Their subsequent **25.625s** normal check verified a
received two-bot party/chat/disband, exact identity/position on a fresh login,
independent old-session despawn, and two ordinary Say challenges from the separate
operator. The operator's selected territory/position/party state remained
unchanged. This separate player is **not** graphical-client attestation.

Provisioner PID217296, normal-runner PID68444 and operator PID253640 each have exact
observed exit0 receipts. All six logout journeys have one
`server_logout_complete`; both provisioning and runner terminal lease snapshots
are strict `clear`; all worker stderr files are empty. Startup took **17.469s** and
the whole driver **63.016s** including teardown. The private runtime and exact
leases are absent, source re-verification/password scan passed, and no Sapphire or
owned database process remains.

Private independent inspection checked the reviewed identity bindings, exact two
administrative action records and intent files, both received zone transitions,
fresh-login territory130, normal party/reconnect/viewer observations, all worker
exits/closures, terminal lease evidence, diagnostics and cleanup. Summary hashes:

- `inspected-evidence.json`:
  `e0dc55ce0b6b0139558442c8eee2e5b0691fd4fa0f9782312251ef15b071e3b4`
- `verification-summary.json`:
  `a52dd98a545f0db371c161239d8fdb5e35fa90243c74cfcad62374b27c2d9ec2`
- `check/development-summary.json`:
  `af3590bad92fcfcecc2d1d1eac04e0bc4dad85193966cf7ab24709dd71d168cc`

Placement is administrative setup only: it proves neither natural travel nor
progression and grants no reset/reprovisioning or account-reuse authority. The
fresh owned runtime does not prove safety on an existing shared server, graphical
compatibility, arbitrary social behavior or shared-world cleanliness.

### Placement registry v2 binds the provisioning run identity

Feature **`00e01b840`** closes a remaining setup-audit association gap. The offline
planner now requires the exact lowercase 32-hex provisioning `run_id`, emits it as
`provisioning_run_id`, and advances the strict placement registry to version2.
The operator helper copies it into each durable pre-dispatch intent/local receipt.
The server's exact-field parser requires that field and rejects version1, missing,
malformed, type-confused or extra-field registries. Successful server diagnostics
now include the provisioning run identity beside approval, operator, target,
source and catalog identity. The native action remains selected by the independently
reviewed approval ID; this addition is artifact provenance, not authentication,
a signature or a server-session/offline fence.

Focused provisioning/planner/operator/lease contracts passed **131 tests in
1.47s** from detached clean exact commit
`00e01b840271f4d6de0775480f39e6df425f935e`. The exact-source standalone native
parser contract compiled and passed; an exact first-party `DebugCommandMgr.cpp`
translation-unit compile also passed against the previously attested clean
placement-build dependency include tree. Native negatives include legacy v1,
missing/malformed run identity, floating version and extra fields. Evidence:
`.e2e-artifacts/development-placement-provenance-clean-001.json`; Python log
SHA-256 `b4a02be1019c304a77f63f088b42a404d56b7e485d77139fc71cdb66f8d6bdb9`;
native-test SHA-256
`1e64355bb1f319a88305b4e548cd3d812b29a588f165e16947aa8242115e089a`.

The first detached CMake configure attempt is retained as a setup failure: it
stopped because that worktree's submodules were intentionally uninitialized and
executed no build/test. The isolated exact-target compiles followed instead; it is
not relabelled as a successful configure. The preceding version1 live artifact
remains valid only for controller `c198af1c3` and is not upgraded.

Bounded **`development-placement-v2-live-001` passed** with a fresh owned runtime
and private database. Its remote-free controller snapshot is
`41ee7baf9f900cee88f53d7092e9b9b1183d9d1c` (manifest SHA-256
`2338e2d4d2a5013dbd36e4a5e6ae29e0cb9c39c832bf1bf416dac2c24a7e95d3`). The
server was built from detached clean feature revision
`00e01b840271f4d6de0775480f39e6df425f935e` with SHA-256
`41462a4d637eda67e4363f9ebd432182dd30bfee36e62f5d861a9a51f3c01699`; unchanged
API/lobby/DBM and worker hashes match the earlier placement inputs. Local build
preparation materialized the exact recorded submodules and did not include the
preserved working-tree experiments.

Provisioning completed in **11.875s** and bound exact run
`509aeaf290674ae6be2952873d0c1191` into registry v2 (SHA-256
`2a38ea68e15f3fe13af48baa515730ffbbedeeffbb57d98b2af7f5bd3c82ac27`). The
same run identity appears in both immutable pre-dispatch intents and exactly two
server diagnostics, alongside the matching approval, slots0/1, target character/
entity IDs, source182, destination130 and catalog hash. The server logs therefore
independently confirm that the loaded v2 provenance field survived planner→server;
local publication receipts still are not treated as mutation proof.

Normal GM0 **Tester MVIBEYHDOACI / 2097154 / 18014398526259202** and **Tester
HQKFNABPOSUI / 2097155 / 18014398526259203** each independently received
`init_zone` 182→130 at the reviewed position. The **25.703s** ordinary follow-up
again passed received party/chat/disband, independent logout/despawn, exact fresh-
login identity/position and separate-player Say checkpoints. No request was
retried. Provisioning PID26316, normal-runner PID77252 and operator PID451312 each
exited0; all six server closures were observed; both terminal lease snapshots were
strict `clear`; all worker stderr was empty.

Startup took **18.234s** and the complete driver **64.046s**. Private password
scan, exact lease absence, controller re-verification, runtime cleanup and process
inspection passed, with no owned process remaining. Independent inspection bound
all native journals, v2 intents, server records, binaries and cleanup:

- `inspected-evidence.json` SHA-256:
  `6dcf39a0da9ddb50e9859650416e3984bd68b9e687a69cc5abba3ca702286d1d`
- `verification-summary.json` SHA-256:
  `1ec435c9d9fb0a3321e734f11d76722f742d2ec8f5b269cef77bbecb40a269d4`
- `check/development-summary.json` SHA-256:
  `bb2718a2cefa90e105b821ca9c8e855849741e2a38012221f44e15a20e72919e`

This is current version2 provenance/placement evidence on a disposable owned
runtime, not server-side offline exclusion, natural progression, reset authority,
existing shared-deployment safety or graphical attestation.

### Exact registry validation precedes irreversible operator intent

Feature **`ad28c284f`** closes a fail-closed ordering gap in the local operator
helper. Previously it checked approval/run IDs and bot identities but could write
an exclusive intent and dispatch a command before discovering that the reviewed
registry had a server-invalid catalog, destination, missing/extra field or bot-row
shape. `validate_placement_registry()` now mirrors the native v2 parser's exact
eight top-level fields, lowercase approval/provisioning/catalog identities, integer
version/territory, three finite coordinates with absolute value below1000, exact
two three-field generated bot bindings, ID bounds and uniqueness. Slot validation
and the complete registry check happen before capability lookup, operator-state
inspection, file creation or command publication.

From a new remote-free frozen exact commit
`ad28c284fd61c4d97e71cd2e4d022108538fbb60`, provisioning, lease, planner and
operator contracts passed **148 tests in 1.49s**. New negatives cover missing and
extra top-level/bot fields, uppercase/type-confused catalog/run values, absent,
short, boolean, NaN, infinite, out-of-bounds and extremely large coordinates,
invalid ID types/bounds and duplicate names; each proves no request and no intent.
Test-log SHA-256:
`f9ebab7450a42a68284436737e52e8f6475ccbacbfc79385b53fc105c664d85b`.
The source was clean and remote-free after removing pytest's ignored cache.

A read-only invocation of that exact current validator accepted the retained
`development-placement-v2-live-001` registry with the same v2, provisioning run
and SHA-256; artifact-check SHA-256 is
`3a1d89c9fd98011127405ceb213ee48c3361c9dfc66ad91c8836e02ebb123cdf`.
It created no intent, contacted no worker/server and does not upgrade or replay the
prior live run. Native parser contracts remain the independent server boundary;
matching Python logic is not a signature or proof against concurrent registry
replacement after validation. Current graphical execution, reset and broad gates
remain pending. No full gate, soak or platform sweep ran; overall goal remains
incomplete.

## Dedicated provisioning has one cooperative success deadline

Feature **`86caebe3a`** applies the existing `RunDeadline`/`DeadlineWorker`
contract to `provision_development.py`. The product CLI now uses one integer
`--max-seconds` in 1..900 (default 300); direct Python callers retain an explicit
unbounded compatibility default. The budget begins before profile/managed-host
validation and is checked around exclusive credential reservation and lease
acquisition, after worker construction, around each HTTP registration/login,
through every scaled lobby/world/logout RPC and wait, and after exact-owned worker
teardown. It does not restart for the second account.

A call may already be in a file/HTTP/constructor/cleanup operation when
the cooperative budget expires; this is not process preemption or rollback. A
late registration response stays `requested_outcome_unknown` and is never retried.
No subsequent login or character creation can begin. The private generated
credential file remains available; once acquired, both exact account leases remain
held on any expiry. Expiry before lease acquisition correctly has no lease to
retain. A late worker factory is entered and closed by its original context owner.
Only in-budget exact worker teardown permits `deadline.complete()`, lease release,
association generation and `provisioned`. Final lease release/report publication
remain cleanup outside the session-success budget. `run_deadline` records this
boundary separately from overall status.

The new focused file passed **19 tests, 0.30s**. Combined shared-runner deadline,
provisioning, host, binding, placement, worker-exit and baseline contracts passed
**215 tests, 2.10s** in the feature worktree. The same selection from a detached,
clean exact commit `86caebe3a0474d06d32c4743f34f94d904e490ce` passed **215 tests,
2.45s**; clean before/after checks passed, and the harness wall time was **5.890s**.
Artifacts: `.e2e-artifacts/development-provisioning-deadline-clean-001.{json,log}`;
log SHA-256 `ee70e183c94a3b9992ab5aa6dfbdec7ae67a817e6423c1efe10083107945f716`.
Synthetic faults cover late credential write, lease acquisition, worker factory,
registration, authentication, lobby request, world-state wait, logout wait and
worker cleanup, plus invalid limits, CLI defaults and normal/disabled success.

### Current-code bounded live provisioning on an owned disposable runtime

`development-provisioning-deadline-live-001` retained a **failed aggregate**. Its
product CLI did provision normally in **12.015s** with a valid 30-second receipt,
but the one-off verifier read nonexistent journal key `sequence` instead of `seq`
and raised `KeyError`. Both normal server closures were present, exact worker exit
and owned-runtime cleanup succeeded, and no new process remained, but these facts
do not relabel that aggregate. `inspected-failure.json` SHA-256 is
`1f36bb88a450945342b681a751534ad42f2deae188df579cde80d5d412035f16`.

Fresh **`development-provisioning-deadline-live-002` passed** with only that
verifier-key correction, new output/private paths, a newly created private database
and new generated accounts. It used a clean, remote-free snapshot of controller
`79227613b616b59727017e8a23dce5c8d902a971` (source-manifest SHA-256
`80984df099bfa36d6212c00dc68619935f31b9c89e4c8b42cf1567d6d6331437`), unchanged
worker `899cfa747` / SHA-256
`b0400f61813c3ee9c7ae1f1b8bdd945b296d1410628e0bf301d937cc11cd0099`, and the
previously attested clean `e665c041f` backend hashes.

Normal HTTP creation, separate login and encrypted lobby/world entry produced GM0
Gladiators **Tester GMPZZNDDOKIN / 2097153 / 18014398526259201** and
**Tester HVZEDIPUQCOC / 2097154 / 18014398526259202** in private182. The exact
eight native actions are login/logout/close/remove for each bot. Each journal has
one `server_logout_complete` at sequence131 before its local close. The cooperative
receipt is enabled at30s, unexpired and completed; product provisioning took
**11.390s**. Exact worker PID333800 exited0 before lease release; both exact lease
files were absent after success. Worker stderr is empty and a password scan of
retained diagnostic artifacts passed.

Startup took **18.719s** and the whole owned driver **31.922s**, including final
cleanup outside the provisioning success budget. The private runtime is absent;
source re-verification passed; no Sapphire service/worker remained; only pre-existing
MySQL PID7764 remained. `inspected-evidence.json` binds all retained diagnostic
files and has SHA-256
`fd4123d30ecbbebc7bc30f960bccf4d091a00c7410d7b35d57aafdfea91ac061`;
provisioning-summary SHA-256 is
`bbb0885709cf49b9a8f8cc93e084f8bc0991829e5d79a9330da891e3945b1c3a`.

This is current-code positive deadline/provisioning/lifecycle evidence on a fresh
owned runtime. No expiry fault was injected live because an uncertain account
creation deliberately requires retained credentials/leases and manual inspection;
those stop/no-retry paths remain synthetic. It is not gameplay, an existing shared
database, graphical compatibility, character rollback, offline exclusion,
shared-world cleanliness, reset/reprovision authority, hard-kill recovery or crash
consistency. No full gate, soak or platform sweep ran; overall goal remains incomplete.

## Shared CLI cooperative deadline: session success budget

Feature **`5ffe7ad43`** adds `support/development_deadline.py`, focused contracts
and CLI `--max-seconds` (integer1..900, default300). A single budget spans lease
acquisition, worker startup, HTTP, scenarios/reconnects, normal logout and worker
closure; it does not restart per operation. New RPC/wait budgets account for the
worker's deadline scale. Calls begun after expiry and late returns/predicate
success cannot pass. The raw worker's context manager still owns cleanup.

This is a **cooperative session-success budget**, not hard preemption or rollback.
Already-started bounded HTTP/startup/snapshot calls and cleanup can overrun. Final
lease release/report writing remain cleanup outside the accepted-session budget,
and still must succeed for an overall pass. `run_deadline` explicitly separates
limit/expiry/session completion from overall status; actual wall times are kept.
Direct Python callers default to `max_seconds=None` for compatibility and must
opt in to this aggregate budget; their per-step bounds remain. The graphical
bridge's existing independent twenty-minute activity cap remains unchanged.
Neither condition establishes hard-kill/crash-consistent cleanup or offline/reset
authority, and a worker exiting does not prove immediate actor disappearance.

Focused contracts **106 passed, 0.73s**; clean committed selection **78 passed,
0.67s**. Tests cover CLI defaults/explicit limits, strict limit/timeout/scale
validation, scaled delegation and argument preservation, rejected late HTTP/
startup/RPC/snapshot/wait/predicate results, worker-cleanup overrun, retained
leases, no additional operations after expiry and unchanged direct-call defaults.
Existing native protocol CTest **1/1 passed, 0.05s total**; no native code/build
change in this increment. Logs: `development-deadline-contracts-{001,002}.json`,
`development-deadline-clean-timings.json`, `development-deadline-native-tests.log`.

### Expected CLI expiry, but retained diagnostic aggregate failure

`development-deadline-live-001` used frozen controller
`5ffe7ad43d5e3ca88549293ce1360462df8db511`, unchanged equipment worker `899cfa747`
(SHA-256 `b0400f61813c3ee9c7ae1f1b8bdd945b296d1410628e0bf301d937cc11cd0099`)
and unchanged clean backend `e665c041f` with checked hashes. Five pre-connection
GM0 fixtures were prepared; the failed pair was never reused.

The product CLI with `--max-seconds 2` **failed as expected after2.016s** in
`logout_and_independent_despawn`, with `expired:true`, incomplete session-budget
receipt and both leases retained. Raw actions contain exactly two logins, two
Says and one mover logout, with its acknowledgement but **no bot
`server_logout_complete`**. No subsequent close/remove control command, second
logout, mutation or retry was published by the runner after the wait failed.

However, the private diagnostic driver additionally required both actors to
vanish within15s after worker exit. **That postcondition failed**, so its aggregate
remains failed, not green expected-failure evidence. The separate observer saw
mover2097153 despawn first, but witness2097154 despawned only later, during the
observer's own normal logout. Later eventual absence does not upgrade the failed
15-second check or establish immediate offline/session exclusion. Services were
still alive after the CLI returned; the driver, not the CLI, finally disposed of
its owned runtime. Startup **17.250s**, whole failed diagnostic **41.813s**.
The planned within-budget case never executed in this driver.

### Previously unexecuted positive control on fresh resources

`development-deadline-positive-001` used distinct fresh accounts/runtime, the same
frozen code and binary identities, and `--max-seconds 30`. It **passed in11.750s**,
with in-budget session completion, normal bot closure and released leases. Mover
**Tester CBHLJMNNPD /2097153** and witness **Tester ANCOIEFCIG /2097154** each
published only login/Say/logout/close/remove. Raw journals confirm normal server
closure before local close. Separate headless viewer **Tester HMOKNKFECK /
2097155/18014398526259203** retained sampled identity/territory/GM/position/party/
invitation state and logged out normally; owned services stayed alive after CLI
return. Startup **17.031s**, whole control **36.297s**. This is deadline/lifecycle
integration evidence, not new gameplay breadth or graphical agreement.

The private `development-deadline-live-001/inspect-evidence.py` checks both raw
outcomes without merging their statuses, source identity, actor/session order,
viewer samples and cleanup. Final inspection found both owned runtimes absent and
only pre-existing MySQL7764. Only then were the failed run's two exact run-ID
leases manually removed, recorded in `manual-lease-cleanup.json`; the successful
control released its own leases. Failed account profiles were not reused. This
manual disposal-based check is not a generic shared-world offline fence.

Artifacts include frozen source/inputs, both drivers and summaries/journals,
`inspected-evidence.json`, the positive viewer samples/final process snapshot,
and environments `sapphire-e2e-1zdodvf8` / `sapphire-e2e-_avmzeqd`.
Expired CLI summary SHA-256
`9219f4d979323b36e949a605d8c65f7a7b0867ee38ee49ac5fb27ec8f0bb1a59`;
failed diagnostic aggregate
`b9303c465b677bc6bd8e21f2ba7b6d2547149882562fd6b35b1af8e432e63fc2`;
positive CLI summary
`1829c2b1170149df0f38502b2bea8d2e07bf55e2bff586e377629b48a174b5f5`;
positive aggregate
`9e4cde98f06be8b980a5ea46a85eebb5502bba415b55deb21bb3f849f92ff502`.

No immediate-disconnect cleanliness, hard process deadline, all-option live
combination, graphical execution, existing shared deployment, reset/reprovisioning
or broad acceptance claim is made. No full gate/soak/platform sweep ran; original
remaining requirements and overall goal remain incomplete.

## Starter-body round trip: fresh-login mutations and nonempty-bag reconnect

Feature **`899cfa747`**, corrected by **`3420ee4d0`**, adds
`--verify-starter-equipment`, explicitly requiring `--verify-reconnect` and
`--verify-reconnect-inventory`. `support/development_equipment.py` binds exact
received identity/class and complete selected containers, body2983/count1 at
1000:3, empty ordinary bag0:0, and idle nonparty state. `main.cpp` now advertises
the two existing ordinary equipment methods; no server behavior or wire action
was changed. Unsupported workers fail before login. Defaults do not acquire
these inventory operations, and the read-only inventory comparison stays intact.

The corrected scenario explicitly performs **three normal reconnects**:

1. Publish one ordinary unequip, retain its acknowledgement as non-mutation
   evidence, then close/despawn/re-authenticate as `mover-equipment-unequipped`.
   Require newly received complete inventory equal to the planned body-to-bag move.
2. Run the original read-only inventory reconnect as `mover-reconnected`, proving
   that the now-observed nonempty bag persists through another normal login.
3. Recheck exact identity/class/unequipped projection, publish one ordinary
   re-equip, and close/despawn/re-authenticate as `mover-equipment-reequipped`.
   Require newly received inventory equal to the original selected slot/catalog/
   count projection. Only this completed observation marks the round trip verified.

Each reconnect checks independent absence/respawn, identity/position and a
**distinct per-session Say**. Reconnect labels reject aliases/unknown roles before
logout. Session-local sequence/context values may restart; they are not compared
across connections. Both operation receipts keep `inventory_change_verified:false`.
No cache mutation is synthesized from an acknowledgement. Re-equip is a successful
scenario step, never failure cleanup: failed/uncertain publication, observation,
class/identity change or reconnect stops without retry or restoration. Evidence
and leases remain for explicit offline review. Six equipment phases separate
preparation, acknowledgement and fresh-login observation from reconnect time.

### Retained failed live001 and source-supported correction

`development-equipment-live-001`, controller/worker `899cfa747`, **failed** after
one unequip request. It received context1073741825/operation8/error0 at sequence124,
but no current-session inventory update beyond baseline122. The ten-second
mutation observation failed; runner **10.203s**, whole check **33.469s**. No
reconnect/re-equip/retry occurred. Its normal bot closure and post-check viewer
comparison are not established; the separate viewer did log out normally.

Source inspection of `Player::moveItem`, `writeInventory` and `unequipItem` explains
why in-session inventory projection was unsuitable: containers are written, but
that move path does not send their contents to the current session. The failure
does **not** establish that the server failed to mutate inventory. The original
synthetic model updated the client cache immediately, so its passing contracts
were not live mutation evidence. The corrected model separates persisted contents
from deliberately stale current-session caches. Assertions still require the
complete exact projection, now from a genuine fresh login; the server was not
modified to accommodate the framework.

The failed owned runtime was removed; process inspection found only pre-existing
MySQL7764. Its two local failed leases were manually removed **only after** exact
run-ID, runtime-absence and process checks, recorded in `inspected-failure.json`.
The failed result remains unchanged. Fresh live002 used new fixtures, not a retry
against an uncertain character.

### Focused verification and successful live002

Final focused contracts **159 passed, 1.29s**; clean committed-source selection
**99 passed, 0.92s**. Coverage includes acknowledgements without persisted changes,
missing closure/ack, changed identity/class/currency, wrong/occupied slots,
incomplete projections, stale cache separation, three distinct liveness messages,
invalid contexts/session aliases, late results, retained evidence/leases and no
failure restoration. Initial/intermediate results are retained separately in
`development-equipment-contracts-{001,002,003}.json` and clean timing records.
Existing targeted native rewards contracts **1/1 passed, 0.04s total**; 36 committed
test-client/reward-test source files were byte-checked before the focused native
build. This source association is not complete native-build attestation.

**`development-equipment-live-002` passed** via the product CLI. Frozen controller
`3420ee4d0a48b03e37b48cb2dc4c60d24f067844`; native worker
`899cfa747abbb7fc8a6bdcbbd71866d325526171`, SHA-256
`b0400f61813c3ee9c7ae1f1b8bdd945b296d1410628e0bf301d937cc11cd0099`;
unchanged clean backend `e665c041f` with checked hashes.

- Mover **Tester DPLOPOEFCA /2097153/18014398526259201**, class1/GM0/public130.
  Initial five starter equipment rows at sequence122; first fresh login118 has
  body2983/count1 at bag0:0 and no1000:3. Read-only reconnect118 preserves precisely
  that projection. Final fresh login118 restores all original selected rows.
  Equal counters across fresh sessions are valid, not reused mutation evidence.
- Exactly one unequip and one re-equip. Both have context1073741825 in **different
  native sessions**, not duplicate publication in one session. Raw received
  container snapshots independently reconstruct bags0–3/equipment1000/Currency2000
  in all four mover sessions. This adds live nonempty-bag coverage for **one
  starter-body row**, not arbitrary stacks, item instances or nonzero currency.
- Independent witness receives each lifecycle and three distinct fresh-login Say
  messages. Private inventory is proved by the mover's received state, not the
  witness. Separate headless viewer **Tester IBCDBOCDJE /2097155/
  18014398526259203** retained its sampled identity/territory/GM/position/party/
  invitation fields and inventory snapshot; no all-state/continuous-presence claim.
- Runner **29.453s**, startup **18.328s**, whole check **55.250s**. Both ack phases
  **0.015s**; final fresh equipment observation **0.016s**. Other inventory phases
  recorded0.000s at timer resolution, not zero-cost claims. Five normal bot-session
  closures plus viewer closure, worker/lease/runtime cleanup and OS process
  inspection passed. Only pre-existing MySQL7764 remained; no existing DB mutation.

Private artifacts: `.e2e-artifacts/development-equipment-{source,inputs}.json`,
corrected `*-source-002.json`/`*-inputs-002.json`, clean sources, native build/test
logs and source hashes; live001 retained failure; live002 driver, journals,
`inspect-evidence.py`, `inspected-evidence.json`, viewer samples and process list;
environment `sapphire-e2e-ue09d1v4`. CLI summary SHA-256
`88f4c47f9e4af7198e047fafea3c29a193bc4fd7634a17502178298bbb2c6ae5`;
aggregate SHA-256
`c1be3a0bb21b3ef64dc3b0db461b4c0069aa14b0692cbf68c0d5a6489146e9d6`.

At this checkpoint no matching graphical equipment/appearance proof was claimed.
Current policy at `e68038dfd` now requires the ordinary starter-body round trip and
strict fresh-login receipts inside a future graphical companion run, but current
graphical execution and any rendered appearance claim remain pending. Item-instance/
durability, all-character-state, world-restart, crash-consistency, nonzero-currency
live comparison, existing shared deployment, safe general reprovisioning/owned-world
reset and broader original requirements also remain open. No full gate, soak or
platform sweep ran; overall goal is incomplete.

## Shared-development self-Sprint: independently received effect and zero TP

Feature **`06bc49312`** adds `--verify-sprint` to `run_development.py`, documented
in `DEVELOPMENT.md`, with `support/development_sprint.py` and 40 synthetic
contracts in `test_development_sprint.py`. Default runs remain unchanged. One
ordinary self-Sprint is published after existing movement/social checks and
before optional reconnect; the viewer is never a target or controlled participant.

Preflight requires the semantic native method before login. The check binds two
distinct received character/entity/name identities, unique visible non-GM peers,
idle nonparty state, received sequences, naturally available TP>=50 and the
native starting-action pacing guard. Prior Sprint history is rejected. Readiness
has a ten-second success budget; publication/observations share a further ten
seconds. Late success is rejected, without retry or forced interruption of
bounded native calls. No cooldown bypass, grant, reset or resource restoration
is provided; fresh-session readiness is not proof of an earlier Sprint cooldown's
expiry. A server refusal fails the check and retains its local leases.

Both bots must receive the exact action3/self-target/request effect with status50
payload and equal complete effect records, plus **fresh** zero-TP HUD rows. The
mover must also receive fresh group56/3000-centisecond action-start metadata.
Detached baseline histories are retained; only append-only suffixes qualify.
Changed or saturated histories fail rather than clearing caches or accepting
login-era zero TP. The Sprint receipt/publication response alone is insufficient.
This proves received status-application effects and a zero-TP update, **not**
speed, status expiry, exact net TP debit, persistence, rendered agreement or
natural progression. Normal TP regeneration and cooldown behavior are preserved.

Focused contracts **143 passed, 1.07s**; clean committed-source selection
**103 passed, 0.71s**. Negatives cover foreign/changed/duplicate/GM/NPC peers,
transitions/parties/invitations, missing/old/saturated histories, unavailable TP or
pacing, wrong/missing/duplicate effects and start metadata, stale zero TP,
boolean metadata, independent-result disagreement, unchanged sequence, invalid
request IDs and late readiness/publication/observation. Failures never republish;
post-publication negatives assert exactly one cast so an earlier preflight failure
cannot mask them. Initial `development-sprint-contracts-001.json` retains
**3 failed /122 passed**: the synthetic fixture omitted the mover's own actor,
preventing readiness. The fixture was corrected and negative publication-count
assertions strengthened, not the product guard weakened. Corrected intermediate
002 and final003 results are retained.

Targeted native **`sapphire_combat` 1/1 passed, 0.05s total**, including existing
Sprint wire/low-TP/actor/request and combat decoding contracts. The test and
CombatState/Protocol source inputs were byte-compared with committed sources
before building that target in the existing clean source/build area. Native
build/test logs are `development-sprint-native-{build,tests}.log`; the worker
binary and backend remained unchanged. No full native suite was run.

**`development-sprint-live-001` passed** via the product CLI, frozen controller
`06bc4931270b58cf09321daafb184c6eeb7eb67f`, unchanged decline worker `401e93223`
and clean backend `e665c041f` with checked input hashes:

- Three explicitly prepared pre-connection GM0 fixtures, public130; setup is not
  progression. Mover **Tester MJFKDKIFPG /2097153/18014398526259201**, witness
  **Tester BMHMAFOCND /2097154/18014398526259202**; no movement route requested.
- Naturally received **100TP** preceded the single request1. Mover baseline126
  → zero-TP139 → effect141; witness baseline124 → zero-TP126 → effect128.
  Empty baseline combat histories, matching target/source2097153, separate empty
  source-effect array and exact target status50 payload were checked against raw
  `combat_changed` events, not just summaries. Mover start metadata also matched.
- Separate headless viewer **Tester JKNDMBPCGP /2097155/18014398526259203**
  received the same self-targeted effect, not a viewer-targeted action. Its sampled
  identity/territory/GM/position/party/invitation fields remained equal. Resources,
  continuous presence, rendering and all-state invariance are not claimed.
- Natural readiness **2.844s**, independent effect/TP phase **0.031s**, runner
  **14.422s**, startup **19.078s**, whole check **41.141s**. Exactly one Sprint;
  ordinary Say/lifecycle operations otherwise. Three normal server closures,
  worker closure, released leases and removed owned runtime verified. Process
  inspection found only pre-existing MySQL7764; existing database untouched.

Private artifacts: `.e2e-artifacts/development-sprint-{source,inputs}.json`,
`development-sprint-clean-source`, focused results and
`development-sprint-live-001/{driver.py,inspect-evidence.py,inspected-evidence.json,
verification-summary.json,viewer-before-after.json,processes-after.json}`, CLI
summary/journals and environment `sapphire-e2e-cdfkbzbu`. Raw verification also
checked source cleanliness, journal order, actual lease absence and cleanup.
CLI summary SHA-256:
`3f271a7e07125dbfe9a6946e4b31eb9feb80af941415f16bff1dc183ee249c08`;
aggregate SHA-256:
`f6fb529420b6adc9414f75e0864f9fe4e2e1fa9eb1ec149c69f0b8d287e4f8b0`.

At this checkpoint there was no matching graphical Sprint check. Current policy
at `8afbbeb0a` now requires this ordinary bot action and strict received receipts
inside a future graphical companion run, but current graphical execution remains
pending. Existing-shared-deployment verification, reset/reprovisioning closure
and broader acceptance coverage also remain open. No full acceptance/soak/
platform sweep ran; goal is incomplete.

## Graphical-lane witness retirement: normal server closure required

Feature **`5c4d8fa62`** adds `support/client_lifecycle.py::retire_witness` and
uses it at both `run_client_smoke.py` witness retirements. The final witness now
waits for `Bot.logout(wait_server_close=True)` before local close/removal, rather
than stopping at acknowledgement. Successful retirements are recorded in
`witness_retirements`; the final `witness_retirement` phase has its own wall time.
A logout, closure or removal failure propagates without retry and cannot produce
a passing result. The final activity deadline is checked before and after this
retirement; bounded in-flight calls/cleanup are not forcibly interrupted.
`REAL_CLIENT.md` documents the one-receipt ordinary lane and two-receipt
optional-development lane. Receipts are lifecycle reports, not offline locks or
fresh-login persistence proof.

Focused contracts: **76 passed / 14 native-dependent skipped, 2.74s**; clean
committed-source coordinator/contracts: **56 passed, 0.49s**. The new 11 synthetic
contracts exercise real Python `Bot.logout` wait predicates and operation order,
acknowledgement/local-close rejection, failures at all five retirement steps,
no retries, and coordinator terminal failure/cleanup on missing server closure,
failed removal or expiry before/during retirement. Synthetic setup/UI/review
objects are explicitly not graphical attestation. Existing unchanged native
protocol CTest: **1/1 passed, 0.04s total**; no new native build or new native
lifecycle unit coverage is claimed. Logs:
`.e2e-artifacts/client-lifecycle-{contracts-001,clean-timings}.json` and
`client-lifecycle-native-tests.log`.

Bounded **`client-lifecycle-live-001` passed**, using frozen controller
`5c4d8fa626b37f8b07f310ab825737ee4c829692`, unchanged decline worker `401e93223`
and unchanged clean placement backend `e665c041f`, with their recorded binary
hashes checked before startup. This is a headless helper/integration check, not
a rerun of the graphical rehearsal or shared-development acceptance:

- Two newly prepared pre-connection fixtures entered public130 through ordinary
  lobby/world sessions as GM0. Witness **Tester AMOMOHMBCO /2097153/
  18014398526259201** retired in **5.156s**; observer **Tester PHDKHHOKMA /
  2097154/18014398526259202** independently received its exact spawn/despawn.
- Raw witness events advance from `logout_ack` sequence122 to
  `server_logout_complete` sequence128, **5.125s** later, before local close and
  removal. Observer retirement advances131→137 and takes **5.984s**. Each bot's
  action journal contains exactly login/logout/close/remove, once each.
- Observer identity and sampled territory/GM/position/party/invitation state
  remained equal across witness retirement. This is not all-state invariance,
  continuous viewer presence or graphical rendering proof.
- Startup **16.844s**, whole check **29.250s**. Worker closure, owned runtime
  removal and post-cleanup process inspection passed; only pre-existing MySQL7764
  remained. No shared account lease, existing database mutation, reset, gameplay
  mutation, installed-client change or graphical process was involved.

The private `client-lifecycle-live-001/inspect-evidence.py` independently checked
raw events/actions, identities, ordering, observer snapshots, exact frozen source,
runtime absence and process snapshot. Retained artifacts include that script,
`inspected-evidence.json`, `observations.json`, native journals and environment
`sapphire-e2e-aa4xr0jx`. Verification-summary SHA-256:
`bcfee1303b6d9cb1ae6862bde187a680c63110f1e55184737ecb40a4b766b5bb`.

**Still pending:** actual graphical execution of this new coordinator version.
Graphical004's final witness remains acknowledgement/local-close-only evidence;
this change does not retroactively upgrade it. Safe general reprovisioning/reset,
existing shared-deployment verification and the broader original acceptance gaps
remain open. No full gate, soak or platform sweep ran; overall goal is incomplete.

## Owned-world-actor reset follow-up: lifecycle prerequisites, no reset exposed

Review **`377a523c1`** extends `research/development-reset-boundary.md` with a
committed-source assessment of dedicated NPC creation and later work ownership.
The 13-file evidence snapshot is
`.e2e-artifacts/owned-actor-reset-review-001`, from
`2a6d05b95c53c4fb7c8e5fffefa443ef903ada6f`; its manifest SHA-256 is
`aec2de5ab2e7b66c8d2227240fa4956578845f3565790093fdfdebe976cc86f5`.
All retained bytes were checked against that commit, excluding the preserved
scheduler/navigation experiments. `review-summary.json` explicitly records
`source_review_only_reset_not_implemented`.

The layout-based creation factories exist, but do not establish administrative
test ownership/generation. `BNpc::init` resets HP/FSM initialization rather than
providing task/reward retirement. Delayed hostility and fade/removal work retain
actor references; delayed loot has player/table fields without source-actor
provenance. The inspected task interface/manager has enqueue/update, not an
actor-scoped cancellation/quiescence contract. Current action processing and
natural spawn bookkeeping are additional lifecycle surfaces; a world-thread
command or current empty hate list alone does not settle them.

No server command, destructive reset, replay of a failure, general task cancellation
or live probe was added. This is a functional suitability review, not a binary/
vulnerability verdict or proof that all callback producers were audited. No test
suite was run for this documentation-only increment; the source hash check and
`git diff --check` are reproducibility/format checks, not gameplay evidence.

The next required implementation artifact is a default-disabled creation registry
for **new dedicated actor lifetimes**, plus integrated lifetime-scoped work
accounting/exclusion, reward provenance, exact reset semantics and negative
lifecycle tests. Only then can a bounded owned live reset be offered. A new
credential profile or longer timeout cannot supply that missing coordination.
Approved private assets remain available; this is a reset-subtask boundary, not a
claim that all local live work is blocked. Offline character reprovisioning still
separately requires a session fence across its mutation. Overall goal is incomplete.

### Updated shared-development requirement map (scope-preserving checkpoint)

These links consolidate the existing narrow evidence, not a fresh full acceptance
or completion audit. The original plan checklist below still applies.

| Updated requirement | Concrete artifact/evidence | Current boundary |
| --- | --- | --- |
| Dedicated account/character provisioning through ordinary sessions | `provision_development.py`, `support/development_binding.py`, exact-owned-worker exit/deadline receipts, strict producer/consumer terminal exact-lease snapshots, and exact managed-host start/end bindings; bounded planner-only and placement-chain live audits | Current v2 producer→planner→registered-placement path is live-verified on a fresh owned runtime; managed provisioning binding is contract-verified while a managed runner start/end binding is live-verified; expiry/no-retry paths remain synthetic; worker exit, host status, server closure and local lease state grant no adoption/reset authority |
| Targeted preparation, explicitly authorized and auditable | `prepare_development.py`, `DevelopmentBotPlacement.h`, `support/development_operator.py`; `development-placement-v2-live-001` | Current v2 binds the provisioning run ID through planner, immutable intents and exact server diagnostics, with ordinary non-GM received arrival; the operator now rejects the complete malformed schema before intent/dispatch; setup is not progression or general reset |
| Safe targeted reprovisioning of existing characters | `research/development-reset-boundary.md`, inspected lobby/API/session paths | **Pending:** offline/session exclusion spanning the mutation is not implemented |
| Reset only explicitly owned world actors | Committed creation/task/lifetime review above | **Pending:** dedicated creation registration and lifecycle/work fence are not implemented; no reset command offered |
| Normal non-GM bots with separate graphical viewer | `run_development.py`, `run_client_smoke.py`, `support/client_development.py`; client-development-live-004 plus current party/decline/Tell/Sprint/equipment/reconnect/viewer/deadline/inventory/lease/exit policy | Historical narrow owned-guest bridge verified at its version; current coordinator requires a comprehensive party run plus a separate fresh route-free exact-peer decline run, distinct run IDs with exact same ordered dedicated name/entity/character identities and staged-worker digest, exact original-witness identity plus normal closure before reuse, a fresh exact paired-mover final logout witness with newly received non-GM viewer presence, an empty pre-launch baseline plus fresh exact-name graphical spawn, sequence-bound ordinary movement and Say receipts, a run-bound rendered-witness Say challenge, strict outer review plus fresh post-phase logout consumers, and a separate exact-frame manual title-screen review receipt, exact shared-runner protocol/version/hash/no-admin-or-reset metadata, strict reciprocal Tell/Sprint/equipment/reconnect, both ordered run-bound viewer Say checkpoints with stable per-observer spawn tokens and persistent-witness continuity, exact inventory, nested deadlines plus an outer 1200-second receipt that includes final observer-worker exit, a PID-bound observed forced teardown of the still-running title-screen client plus every private database/API/lobby/world generation and lifecycle-file hash, clear leases and exact worker exits, followed by a committed read-only current-result inspector and an exact no-preexisting-Sandbox launch/process-absence/manual-confirmation composite disposal verifier; current graphical execution and disposal remain pending; neither proves the user's existing shared deployment, server-side viewer continuity or rendered-action agreement |
| Short meaningful scenarios and timing | Strict per-waypoint independent movement receipts plus party/Tell/Sprint/equipment/reconnect/viewer checks; separate exact-peer decline and read-only reconnect inventory increments; one current owned-host movement/party/reconnect/inventory run binds the same ready host at start/end and exact terminal service teardown | Bounded CLI/live headless evidence recorded above; cooperating host identity is not server-side exclusion; decline has headless-only live coverage but is now required as a separate fresh current graphical-policy run; all current graphical execution awaits manual approval/assets |
| Reject ambiguous/foreign state, no uncertain mutation retries or foreign cleanup | Native bound party/Tell/placement methods; focused ownership/lifecycle contracts; retained failed leases/results; exact read-only lease inspector | Verified for implemented operations; local clear/retained lease snapshots provide neither server offline proof nor the missing reset/session fence |
| Genuine received evidence and independent observations | Native actions/events, exact peer receipts, strict advancing per-waypoint movement observations, respawn/Say, inventory snapshot reconstruction | Inventory is private acting-client evidence; peer verifies movement/lifecycle/position, not the inventory contents |
| Preserve viewer, private inputs, historical failures and unrelated experiments | Separate viewer profiles; strict no-control endpoint Say/presence receipts; private artifact hashes; failed graphical 001–003 retained; seven experimental paths remain separate | No all-state viewer invariance, server-side session oracle, shared-world cleanliness or crash-consistency claim |
| Separate shared development from isolated acceptance | `DEVELOPMENT.md`, `REAL_CLIENT.md`, summaries with explicit scope; original requirement checklist below | Full gate/soak/platform sweeps remain unauthorized for this iteration; Linux/hosted/broader gameplay gaps remain open |

## Read-only inventory projection across shared reconnect: implemented and live verified

Feature **`d39c1c1266815c044f26f2e07827c52ebde527e1`** adds
`--verify-reconnect-inventory`, requiring explicit `--verify-reconnect`. It adds
no inventory operation, reset or native/server change. Immediately before normal
logout and after fresh authentication of the same mover, the controller requires
complete received containers **0–3, 1000 and 2000** and compares canonical
storage/slot/catalog-ID/count rows. Equipment completeness is checked separately
because native `inventory_ready` covers bags/currency, not equipment.

`inventory_verification` retains both projections, their **session-local** received
sequence numbers, changed slot keys and requested/verified scope. Partial evidence
survives a failure. Missing containers, malformed metadata, changed identity/state,
changed contents and late observations fail without restoration/retry or lease
release. The original independent logout/despawn, fresh identity/position,
respawn/Say and normal cleanup requirements remain. The observer proves the
lifecycle/position, not private inventory contents. Default reconnect is unchanged.
No item-instance IDs, quality, durability/spiritbond, Crystal/armoury/other
containers, quest/EXP or restart/crash persistence are claimed by this option.

Contracts: **117 passed in 0.89s**, including missing individual containers,
nonempty synthetic bag/currency comparisons, changed/added/removed rows, malformed
slots/types/counts, identity/GM/transition changes, late success and no restore/
retry on failure. Clean committed snapshot: **66 passed in 0.59s**, including
reconnect and graphical-bridge policy compatibility; source integrity remained
unchanged. Targeted existing native rewards CTest **1/1, 0.04s total** checks the
underlying decoder, not the new Python orchestration. Logs/timings:
`.e2e-artifacts/development-inventory-{contracts-001,clean-timings}.json` and
`development-inventory-native-{build,tests}.log`. No full gate ran.

Bounded product CLI live check:
`.e2e-artifacts/development-inventory-live-001`. Controller is the feature revision;
worker remains clean `401e93223` / SHA-256
`2ada8b0b3b04734ae6ee3f64313e32aa03a6fc5562d61b132c4e4922e3edbc48`, backend remains
clean `e665c041f`. Separate identities/hashes are in
`development-inventory-inputs.json`; native source bytes were checked against the
committed controller snapshot as well. Preserved experiments were not inputs.

**Tester AFCFNKPCAI / entity2097153 / character18014398526259201** retained five
received starter equipment rows, each count1: **1601, 2983, 3520, 3296, 3750** at
slots **1000:0/3/4/6/7**. All four bags and Currency were received as complete empty
snapshots in both sessions. Before/after sequence numbers are **122** and **118**;
freshness is session-bound, not a false requirement that sequence increase across
new sessions. `inspect-evidence.py` independently reconstructed all six selected
containers from each session's `rewards_changed.snapshot` journal records and
matched both report projections. No item-action publication appears in the action
journal. This is **not** live coverage of nonempty bags, nonzero gil, deliberate
inventory mutations or instance identity; those new-option cases remain synthetic.

Check **17.547s**; startup **17.375s**; complete owned driver **42.266s**. The two
inventory observation phases each recorded **0.000s at the recorded resolution**;
this is not a zero-latency/cost claim. Three normal bot-session server closures,
independent despawn/respawn, worker closure and lease release were inspected. A
third separate headless observer's selected identity/position/territory/rank/
party/invitation fields matched before/after and it closed normally. Owned runtime
cleanup passed; process inspection afterward found only pre-existing MySQL7764.
No graphical client, existing DB access, grants/reset, party/Tell/decline or
movement scenario was added to this check. Three owned pre-connection fixtures
remain administrative setup, not normal provisioning/progression.

`inspected-evidence.json` hashes the exact driver, summaries, native journals,
viewer snapshots, environment logs and process check. Product summary SHA-256:
`b45a0ef893af2c74ef103cf1ac5d62bd9fa6b2d23560c5b04867df21b8c0abdf`;
aggregate SHA-256:
`b59be304cf9aba740ce46ed1b9e0412b70b727166f685025258576293bf904f0`.
General safe reset/reprovisioning, existing shared deployment, broader graphical/
gameplay, Linux, hosted CI and acceptance gaps remain pending. No full acceptance,
soak or platform sweep ran; overall goal remains incomplete.

## Short shared-development exact-peer decline: implemented and live verified

Feature **`401e9322337f1025adac2fca8d0e1c44f6632c12`** adds
`run_development --verify-party-decline`, the advertised native
`decline_party_bound` method, typed context journaling, focused contracts and
`support/development_decline.py`. This is one ordinary invitation and one explicit
rejection between the two dedicated non-GM accounts, not administrative reset.
The native wrapper compares the complete expected party/pending-invite context
on the Asio publication thread before invoking the existing normal decline path.
Its wire bytes remain the ordinary DENY request. Public/server behavior is unchanged.

The controller binds exact received lobby character IDs, entity IDs and names;
requires idle empty parties, unique visible non-GM peers and fresh empty invitation
history; and requires **both** the recipient's received deny reply and the
inviter's independent exact reject update. Local clearing of the pending invite,
publication and invite-result acknowledgements cannot pass the check alone.
Success must occur within the ten-second combined budget, with late observations
rejected; in-flight RPCs retain their bounded worker timeout and cleanup is not
hard-interrupted. Foreign/changed invitations are never declined as cleanup.
Failures retain normal account leases and do not retry uncertain mutations.

`--verify-party-decline` and `--verify-party` are deliberately mutually exclusive
before authentication/artifact creation. Party creation's existing fresh-history
requirement is not weakened or bypassed by clearing state. Separate fresh runs can
reuse the accounts after normal closure. Other optional development checks remain
separate; the viewer is never an invitation target.

Focused Python contracts: **114 passed, 14 native-worker-dependent tests skipped,
3.27s** in `.e2e-artifacts/development-decline-contracts-001.json`. Clean committed
snapshot: **66 passed, 0.77s** in `development-decline-clean-timings.json`, with
snapshot integrity checked afterward. Negative coverage includes missing worker
capability before HTTP login, existing/outgoing/stale invitations, duplicate peers,
foreign/raced inviter, missing/incorrect replies, changed identity/GM/membership,
new foreign invitation, stale sequence and late successful observation. No forced
social cleanup occurs in those cases. Targeted native protocol CTest **1/1 passed,
0.04s total**, including exact ordinary DENY bytes and context-mismatch rejection.
An initial build invocation named a nonexistent test target; that command failed
and its log remains `development-decline-native-build.log`. The corrected targeted
build/test logs are separate; no full native/platform gate ran.

Bounded live `.e2e-artifacts/development-decline-live-001` used the product CLI
from the clean snapshot, the unchanged clean placement backend `e665c041f` and
new worker SHA-256
`2ada8b0b3b04734ae6ee3f64313e32aa03a6fc5562d61b132c4e4922e3edbc48`.
`development-decline-inputs.json` records separate backend/controller/worker
identities and byte comparison of native client/protocol sources against the
committed snapshot. Three new owned pre-connection fixtures are setup, not normal
provisioning or progression. No existing DB or graphical client was used.

The exact inviter was **Tester MPEBJPGHHK / 2097153 / 18014398526259201**;
recipient **Tester OCDIKDNKBE / 2097154 / 18014398526259202**. Received journals
match the full inviter ID/name in the pending request, recipient deny reply at
sequence **124** (baseline120), and inviter reject update at **130** (baseline122).
There was exactly one bound invitation and one bound decline, no party formation
request/disband, and no received nonempty party state. All bots were non-GM.

Decline **0.046s**; normal login/Say/decline/logout check **11.828s**; startup
**17.328s**; complete owned driver **36.500s**. A third **headless** observer,
entity2097155, received no party events; selected identity, territory, rank,
position, party and invitation fields matched before/after. Both bot sessions
and the observer have received normal server closure; worker/leases/runtime
cleanup passed. Process inspection afterward found only pre-existing MySQL7764.
This observer is not graphical evidence for the new flag or all-state invariance.

`inspected-evidence.json` binds the exact driver, reports, native actions/events,
viewer before/after, environment logs and post-cleanup process list. Product
summary SHA-256:
`80ef8492a9af1dd7722ff631f016892ced8803fd995e67bc622aa7f20a2f2c28`;
aggregate SHA-256:
`a499124f6e8b4d5dd29dcf1efe71c2b10b4df39fd384a39fc9e8dd55b0fcbefe`.
No movement/party-creation/Tell/reconnect/placement/graphical scenario was repeated
just to exercise this flag. No acceptance, soak or platform sweep ran. Existing
reset/session-fence, shared deployment, broad gameplay/real-client, Linux and
hosted-CI requirements remain pending; overall goal is incomplete.

## Owned-guest graphical co-presence bridge: live passed, limited scope

Fresh `.e2e-artifacts/client-development-live-004` ran frozen coordinator
**`2a33024b6995e3b5540939f2683c3f4fd9ac152e`**. The matching unmodified DX11
executable, clean placement backend and Tell worker identities remain unchanged.
All staged input hashes and committed source were rechecked after execution;
preserved worktree experiments were excluded. Effective private input manifest
SHA-256: `a11937938c0a59acdd744c54bf063cb248af46d5203a51f7d35b1adee0a0b545`.
The base manifest and private guest-only, individually operated UI relay are
retained separately; no automatic dialogue/attestation logic was added.

The graphical character **Tester HIKOKBAOPC / entity 2097154 / GM rank 0** entered
public130 through its ordinary UI. An independent headless witness received
**1.078566380m** movement and exact `E2E real client verified` Say. Interactive
inspection of `output/review.png` confirmed the named fixture rendered in-world
and `E2E independent witness` rendered in chat, then the ordinary approval CLI
bound the attestation to review SHA-256
`b89aaa67955cd17a2977aa4ef044ebcb093776d20250322b3a9da1c32d6ea3b8`.
Pre-connection placement/opening preparation is not natural progression.

After normal closure of the initial witness, the normal development runner used
only **Tester NAGHBKBACF / 2097153 / character 18014398526259201** and
**Tester PAAPGHLDHM / 2097155 / character 18014398526259203**. The separate graphical
viewer remained in-world and explicitly replied to each newly read nonce through
ordinary Say UI. The received identities and same position matched at both
checkpoints. This runner never authenticated, moved, invited or reset the viewer.

`output/development/development-summary.json` passed in **118.844s**. Inspection
of the corresponding action/event journals independently matched:

- 24 normal movement publications to witness-received positions within 0.15m,
  after each request and before the next, along the catalog's 13-point prefix
  out and back; movement phase **20.172s**.
- Exact two-bot party roster in both sessions, both received party messages with
  matching sender/channel/party identity, and both empty states after disband.
- Two exact nonparty Tell deliveries with newer tokens (**330→332**, **246→248**);
  Tell phase **0.032s**. No Tell was addressed to the viewer.
- Normal mover closure/despawn, fresh authentication of the same character/entity,
  exact position and independent respawn/Say, without a world restart.
- Four exact graphical-viewer Say observations: start **120→172**, **118→170**;
  finish **118→159**, **351→395**. Manual reply waits were **32.000s** and
  **41.812s**, each below its unchanged 60-second bound.
- Three normal bot-session `server_logout_complete` events, explicit worker
  closure and released account leases. No DB access, administrative placement
  wait, reset or world restart was performed by the normal runner.

The original witness authenticated afresh, received the graphical entity's
ordinary logout/despawn, and the server recorded
`[2097154] Zone IPC : StartLogoutCountdown`. `output/logout.png` was separately
inspected and shows the title screen. The final smoke witness then sent logout,
received its acknowledgement and closed locally; unlike the three development
sessions it did not wait for `server_logout_complete`. Do not claim final smoke-
witness persistence from that acknowledgement. Runtime teardown completed, the
owned Sandbox discard dialog was actually inspected and confirmed once, and
post-disposal process inspection found only pre-existing MySQL PID 7764.

Whole manual lane: **726.312s**, with setup **23.984s**, spawn/UI **168.047s**,
graphical movement **66.891s**, Say **79.234s**, review **45.297s**, bridge including
handoff **124.578s**, logout/UI **217.453s**, cleanup **0.828s**. These are monotonic
wall-phase durations including operator waiting and worker unwinding, not CPU
benchmarks. The previously added phase timing and terminal `finished` publication
now have live successful execution evidence.

The 29 manually selected UI requests each have a reply/frame. Two private host
mailbox replacements failed with WinError5 before publication; the previous
published ID was checked unchanged and the pending file explicitly published
under its original unique ID. No additional movement or logout request was
created and no uncertain gameplay mutation was retried. The first logout button
was obscured by the active-help notification; screenshot inspection led to
opening/closing that help window before confirming the still-visible dialog.
`operator-publication-notes.json` preserves these tool-output-derived notes;
they are not labelled native runtime logs.

`inspect-evidence.py` / `inspected-evidence.json` verify raw received evidence,
input/source identity, exact summary associations, review hash, timing totals,
normal graphical logout marker/despawn, cleanup and disposal artifacts. Result
SHA-256: `6993aaa8bb3e3557e712f3184e3630959edf29e6312ac16214cf8e484e54d223`.
Development summary SHA-256:
`c6d65ae5084e4cf5d38562a3df1eb2011a986ac7f7ab2c14479c33c9b453aa4f`.
The earlier three failed attempts below remain failed; this is a fresh run, not
a rewrite or retry of their uncertain state.

**Scope/remaining gaps:** this establishes one matching graphical client's two
fresh endpoint replies around meaningful non-GM bot checks on an owned private
guest runtime, plus the limited original rendering review. It does **not** attest
continuous presence, rendering of added bot actions, quest/scene agreement,
all-state viewer invariance, the user's existing shared database/deployment,
general reset/reprovisioning, broad compatibility, crash consistency, Linux,
hosted execution or acceptance. No full gate, platform sweep or soak was run.
No product code changed in this evidence increment; `REAL_CLIENT.md` records the
observed manual UI caveats and this bounded rehearsal. Overall goal remains
incomplete; reset coordination and the existing acceptance audit gaps persist.

## Corrected graphical guest startup reached; manual spawn deadline retained

Fresh `.e2e-artifacts/client-development-live-003` ran frozen coordinator
`d6838445842e038437e35eb4a1ce13953d81256b` with explicit x64 Release CRTs and the
path-only localized catalog. Guest source verification and all staged input
hashes were inspected again after execution. Effective input manifest SHA-256:
`424e1476042d0a5aaa2aeb12f72f1bcf77913bd0fdafd02fdd905729d4010ec0`.
Native backend/worker identities remain the previously recorded clean placement
backend and Tell worker; preserved working-tree experiments were not inputs.

This attempt passed the earlier packaging blockers: private database/services
started, and the ordinary headless witness reached received ready state in
public territory 130. Its received self spawn is entity **2097153**, named
`Tester OIPOPIJDOA`, level one, **GM rank 0**. Its action journal contains only
`login`; no bot gameplay, party, Tell, placement or reset action was issued.
The exact matching unmodified graphical executable was launched. Actual inspected
screenshots show the title/version, local data-centre selection, introductory
movie, and `Tester LOAKHGCKHE` in the `Sapphire E2E` character list.

Individual screenshot-reviewed UI inputs declined controller calibration,
selected the local data centre, skipped the introductory movie and reached the
first-run character-creation prompt. Proceed entered the creation editor; an
explicit cancel opened its confirmation. There was **no completed graphical
world entry**. The coordinator reached its **twenty-minute activity deadline**
while waiting at `spawn`, then failed and removed its runtime. One late explicit
cancel-confirmation request had no relay reply and was not repeated; no success
is inferred from its publication. Eleven private operator request files and ten
replies/screenshots are retained, including the unanswered request. This is
manual operator progress/deadline evidence, not an autonomous UI or gameplay pass.

`output/result.json` remains **failed**, `failure_stage=spawn`, with
`development_check.status=not_run` and `runtime_removed=true`. Result SHA-256:
`b53e893bb5a30a4a73cf111d68e6e25276c3c9d56a74befde5022125cb0dc7c6`.
The Sandbox discard dialog was inspected and its exact owned OK button confirmed
once. Initial disposal targeting rejected two ambiguous parent/dialog windows
without sending confirmation; inspection identified the dialog's child button.
Subsequent process inspection showed only pre-existing MySQL PID 7764, with no
Sandbox/client/owned test services. `inspected-failure.json` binds the result,
inputs, journals, manual frames/requests, disposal screenshot/confirmation and
post-disposal process list. Whole-runtime cleanup is not normal graphical logout.
The older two setup failures below are unchanged.

**Small diagnostic increment:** `18cf29b55` adds monotonic manual-phase wall
measurements and terminal `finished` status. Results separate setup, entered
manual/scenario phases and client/environment cleanup; unentered phases remain
absent. Phase announcements include the remaining activity budget **at
publication**, not a live countdown. Timing includes operator waiting and worker
unwinding, not gameplay CPU time or acceptance coverage. This instrumentation
was added **after** attempt 003 and is not retroactively attributed to it.

Focused contracts: **46 passed in 0.28s** in
`.e2e-artifacts/client-phase-timing-contracts-2.json`; clean committed snapshot:
**5 passed in 0.15s**, with source unchanged, in
`client-phase-timing-clean-timings.json`. Coverage includes elapsed/phase totals,
zero-length setup, optional development, idempotent finish, post-finish rejection,
source rejection before setup, and startup failure with both successful and
failing cleanup/terminal status. An initial test incorrectly expected eight
one-second advances when it performed seven; the failing result is retained in
`client-phase-timing-contracts.json`. No native code changed. The new timing and
terminal-status code has not had another guest execution.

**Still pending:** a fresh manually attended run reaching actual world entry,
movement/Say/rendering approval, the two fresh viewer replies, normal logout and
successful-run disposal. Assets/guest startup are available; the current blocker
is incomplete manual execution within the existing activity window, not missing
endpoints or a reason to extend deadlines/weaken checks. Existing shared-database
deployment, safe general reset/reprovisioning, broader real-client agreement,
Linux/hosted CI and acceptance gaps remain. No full gate or soak was run.

## Graphical bridge guest attempts: two retained setup failures

Two fresh owned Sandbox attempts reached the guest's frozen-source/client-hash
checks but **failed before graphical-client launch/login**. No normal bot scenario,
viewer challenge, rendering review or gameplay success is claimed.

1. `.e2e-artifacts/client-development-live-001`, coordinator `966a0b9a9`, failed
   during environment staging: the copied catalog retained its host-only
   navigation mesh path. Guest artifact collection could not open it. Result
   SHA-256: `7429827a7dc10ce58e0bd769b7b5c20d3f53009844d686ee5d38928c81103b1e`.
2. `.e2e-artifacts/client-development-live-002`, coordinator `3582fd8b9`, progressed
   past that path after staging an exact mesh copy, then failed `db-initialize`
   with exit **3221225781 / 0xC0000135** (missing runtime dependency). Import-table
   inspection showed MSVC runtime imports; the bundle lacked MSVCP140 and other
   explicit Release CRT staging. This identifies a packaging prerequisite, not
   yet a verified fix for every possible guest loader dependency. Result SHA-256:
   `442aa0e975b482f9a1d978e745e5ce0deff4df36fa76e9deccae6293e2d0b306`.

The second preparation also failed an exact-transform assertion: the catalog
validator had added derived `giver`/`recipient` fields. All original fields,
including route geometry and length, matched, but this was not the promised
path-only transformation. The assertion failure is retained in
`preparation-validation-failure.json`; it is not relabelled as a passing check.

Each effective private bundle records an optional guest-only manual UI relay
and changed bootstrap hashes, while retaining `inputs-base.json`. The relay
accepts individual screenshot-inspected inputs to the exact owned game window;
it does not make automatic dialogue/scene choices. Neither attempt reached that
window, and no game UI input was issued. This private operator tooling is not
part of the default committed coordinator or an autonomous UI proof.

Both guest results recorded `runtime_removed=true`. Each owned Sandbox's discard
dialog was actually inspected and confirmed once; screenshots and confirmation
records are retained. Subsequent process inspection found no Sandbox/client/test
services, only pre-existing MySQL PID 7764. `inspected-failure.json` hashes each
failed result, effective manifest and disposal confirmation. Original installed
client/settings and host networking were untouched. Guest runtime cleanup and
VM disposal are separate evidence; neither failure became a gameplay pass.

**Corrections:** `3582fd8b9` introduced private catalog mesh localization;
`121cb0a40` preserves the raw original catalog (discarding validator-derived
return fields) and adds explicit `--release-crt-dir` packaging without requiring
Debug UCRT or installing anything. The original catalog/mesh and localized
catalog are independently hashed. The original source-route/catalog validation
remains unchanged. **54 focused contracts passed in 0.33s**, including derived-
field preservation and incomplete-runtime-folder rejection, in
`.e2e-artifacts/client-staging-corrections-timings.json`.

A corrected bundle at
`.e2e-artifacts/client-development-corrected-preparation-001` was inspected at
`121cb0a40c946f1a3a353f7328455c65dcfd457f`: every staged input matches its hash,
only the catalog mesh path changes, explicit x64 Release CRTs are present and
Debug UCRT is not required. Manifest SHA-256:
`fafb8d5ef5d8f2f7f6bf5f1d68fe02dce73ed0abad6c3bdb5f6fa26968868c26`.
It remains **prepared_verified_not_executed**. Corrected guest startup, actual
manual graphical co-presence and disposal for a successful run still require
execution. No full gate, platform sweep or expensive soak was run.

## Opt-in graphical co-presence bridge: authored and prepared, not executed

Feature `38242cd85` adds `prepare_client_smoke --development-check`. It preserves
the default manual smoke procedure and the frozen-source/guest-only boundary.
The optional mode stages the validated quest catalog and, after ordinary manual
movement/Say/rendering review, runs the normal two-bot development scenario while
the separate graphical fixture remains in-world. The operator must manually
answer each newly written start/finish Say challenge; no automatic dialogue,
viewer login/control or GM action is added.

The original headless witness logs out through normal server closure before its
account becomes one bot. A second owned non-GM fixture is prepared before its
first connection at a point from the validated short corridor. The graphical
account/name must be distinct from both bots and its credentials never enter the
runner profile. The scenario requests movement, exact party/chat/disband, visible
Tell, reconnect and both viewer checkpoints. Completion requires all subchecks,
released leases, a closed worker and the same non-GM graphical fixture identity.
An independent witness then authenticates afresh for the original graphical
logout observation. These pre-connection fixtures are setup, not provisioning or
natural progression evidence.

`ActivityWorker` caps RPC/observation waits by the remaining original twenty-minute
activity budget, refuses operations after expiry and rejects late successful
responses. HTTP/fixture calls check the deadline between bounded operations;
cleanup is not forcibly interrupted. The graphical process must remain the same
live launched process before and after the bot scenario. The prior rendering
review does **not** verify rendering of added bot actions, and the result says so.

**Focused evidence only:** 42 bridge/manual-lane/guard contracts passed in
**0.23s**; 17 bridge contracts passed in **0.11s** from the prepared clean snapshot
without changing its tracked/ignored state. A **0.015s** native-control-only
probe received worker capabilities, rejected an expired Tell before publication,
and closed the worker. Its action journal is empty; no server/gameplay ran.
Artifacts: `.e2e-artifacts/client-development-focused-timings-2.json`,
`client-development-clean-timings.json` and
`client-development-native-control/verification-summary.json`.

Actual preparation at `.e2e-artifacts/client-development-preparation-001` verified
source revision `38242cd85e707f38895cbfff0be208580c3d864b`, staged input hashes,
explicit opt-in and exact copied catalog hash. Input manifest SHA-256:
`4a1b509b7a04b7d3e44b3e57c2898dbbd3b09c94264bd1dfbb61570a7e900bba`.
`preparation-verification.json` is explicitly `prepared_verified_not_executed`.
No sandbox, graphical client or world was launched for this increment. Networking,
installed client settings and the preserved experiments remain unchanged.

**Still pending:** execution of this exact prepared bridge through the real first-
run UI, manual rendering review, two fresh ordinary Say replies, normal logout,
inspected lifecycle evidence and explicit Sandbox disposal. Preparation and mocks
are not graphical co-presence proof. Even a future passing owned-guest bridge
would not verify the user's existing shared database/deployment, continuous
presence, rendered-action/quest agreement, general resets or full acceptance.

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
No placement/reset, movement, party, reconnect or graphical launch was run for
that live increment. Current policy at `dbca3e6ba` now requires both exact Tell
receipts inside a future graphical companion run, but current graphical execution
remains pending. No full gate, expensive soak or platform sweep was run. The original
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
| Deadlines / cancellation / cleanup | Timers, shared runner/provisioner cooperative whole-session budgets, graphical bridge nested aggregate/outer activity budgets, exact-owned process and isolated service-generation teardown receipts, including strict terminal owned-warm-host lifecycle inspection, redaction, Windows sharing retries; bounded profile deadline scale 1..3 is recorded and adds no retry/sleep; final movement publication waits for its asynchronous zone-socket write; workload cleanup precedes diagnostics and survives sampler/write exceptions | Synthetic faults, positive bounded provisioner/runner sessions, control-only zero/nonzero native exits, exact database/API/lobby/world lifecycle contracts, a controlled live diagnostic-write failure, one intentional owned-world termination, and an older clean scale-1 Windows gate verified; exact current process receipts await a new gate, and neither process exit nor runtime removal is server-offline proof |
| Action/event/server logs / hashes / JUnit | Bounded sanitized journals; runtime/module/worker/catalog/mesh identities | Implemented; hashes do not prove independent compatibility |
| Asset-independent CI | `.github/workflows/test-client.yml`; strict workflow-policy receipt | Pinned/read-only/bounded repository controls verified; hosted run unverified |
| Provisioned gameplay CI | `gameplay-e2e.yml`, `sapphire_gameplay_ci` build target, `run_ci.py`, `CI.md`; strict workflow/process-policy receipts | Authored repository controls are pinned/read-only/bounded and private dispatch remains protected/serialized in YAML; the last fifteen-case Windows gate passed before exact process-generation receipts were required and the older nine-case Linux gate passed, but current gate execution is pending and the expanded Linux gate remains red under delayed scene/action/logout/zoning delivery; hosted execution, actual runner-group/environment policy and ephemeral destruction remain unverified, with no registered runners |
| Independent real-client/golden trace compatibility | Unmodified 3.3 DX11 pilot and committed manual lane: world entry, received movement, bidirectional Say, ordinary logout, and exact-frame reviews; current policy also requires a separate final dedicated-bot co-presence/Say frame | Historical narrow lane live-verified; the new bot-interaction frame and current combined policy await a fresh run, while broader UI/quest compatibility and normalized golden traces remain uncovered |
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
| Bounded queues, deadlines and cancellation | 64 KiB control limit, two-frame send-queue cap, bounded journals, monotonic Python/native timers, shared runner/provisioner whole-session budgets plus graphical nested/outer budgets, recorded deadline scale 1..3, asynchronous final-movement write completion, and explicit `close`/`remove` cancellation of timers/sockets | Verified for implemented paths; timed-out operations are never retried and owned teardown cancels the worker; cooperative budgets are not hard preemption |
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
| Record build/script/fixture/protocol/data/nav identities | gate manifest and summary hashes; current graphical policy additionally binds exact prepared source-manifest bytes/revision, rehashes every staged `input/` file, and strictly consumes the isolated environment's server/worker/script/catalog/committed-combat identities plus its recorded external-navigation digest map; external read-only mappings and game assets remain separately identified/private | Verified for exact staged/environment identities; hashes do not prove external-root completeness, compatibility, signatures, or native build provenance |
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
| Manual/scheduled real-client tier | strict three-frame-review current policy plus historical completed isolated Sandbox lane | Historical lane verified once locally; current combined bot-interaction review policy and scheduled breadth are unverified |
| Untrusted-code isolation/approval | `CI.md` requires workflow-scoped ephemeral VM, protected environment and disposal | Documented; **hosted enforcement unverified** |
| Failure identity, expectation/action/timing and versions | manifests, action plans/outcomes, pytest/JUnit, bounded state dumps and automatic sanitized exact-lease snapshots in shared runner/provisioner summaries | Verified for implemented paths, including current live producer→planner→runner consumption; lease snapshots do not establish server session state |
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

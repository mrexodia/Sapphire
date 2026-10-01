# Separate manual real-client compatibility lane

This is **not** another headless test and does not certify arbitrary UI, quests,
cutscenes, combat, character creation or golden packet layouts. An unmodified
local 3.3 DX11 client is operated through its normal UI. A headless witness checks
received movement, Say and despawn. Rendering requires explicit manual review;
there is no image-recognition oracle or automatic dialogue responder.

## Isolation and prerequisites

Use a trusted checkout on a Windows host with Windows Sandbox already installed,
8 GB available guest memory, working vGPU, Git for Windows, and a complete Python
installation containing the normal E2E dependencies plus Pillow. No download,
service installation, host DLL registration, game patch or host game-profile
change is performed. The guest guard checks Sandbox Documents before setup; it
is an accident-prevention check, **not a security boundary**.

Use the existing private E2E profile (including a validated Ul'dah quest catalog
and compatible server navigation), built servers/scripts/worker and MariaDB.
Supply your legally obtained matching game installation. Currently only the
independently exercised executable hash is accepted:

- version: `2016.07.05.0000.0001`
- DX11 SHA-256: `d818584c782bbe3cacbc2b306391e6f3246bc3065c517a3324784e49d572ba12`

A filename ending in `_original` is not evidence: the bytes must match. The
preparer copies it as `ffxiv_dx11.exe`; it does not patch it. Required neighboring
files are `bink2w64.dll`, `ffxivgame.ver`, `fileinfo.fiin` and `movie/`. Sqpack comes
from the profile. Legacy DirectX DLLs must already exist in host System32;
missing prerequisites fail rather than being silently installed. XAudio/XACT
COM registration happens **inside the disposable guest only**.

```sh
python -m tests.e2e.prepare_client_smoke prepare \
  --profile .e2e-local.json \
  --client '<private-game-directory>/ffxiv_dx11_original.exe' \
  --output .e2e-artifacts/<fresh-private-run>
```

For MSVC-compatible Release builds (including clang-cl), supply the matching
compiler's **x64** runtime folder with `--release-crt-dir`. This copies its DLLs
into the private bundle without requiring Debug UCRT, installing anything or
assuming the Sandbox already has the host's runtime. Missing/incomplete folders
fail; runtime dependency compatibility still requires guest execution.

For Debug builds, also supply the matching compiler's **x64** DebugCRT and CRT
folders using repeated `--crt-dir`. This additionally stages `ucrtbased.dll` from
System32. Conflicting DLL bytes and reused output directories fail. Nothing is
launched by preparation; `inputs.json` says `prepared_not_executed` and hashes the
staged inputs. Preparation also makes an independent shallow checkout of the
current **committed HEAD**, without host working-tree/staged/untracked changes,
submodule fetches, hardlink/alternate dependencies or a configured remote.
`input/source.json` records the revision and materialized source-file hashes;
`inputs.json` binds that manifest. The guest maps this private snapshot read-only
and checks its revision, cleanliness and hashes before fixture/process setup.
Ignored extra files and unexpected materialized submodules are also rejected.

Commit coordinator changes before preparing; uncommitted experiments are
intentionally excluded. The original checkout may change afterward, but **do not
edit the prepared bundle while it is in use**. This is reproducibility checking,
not a signature/security boundary or native-binary source attestation. Native
binaries and external read-only assets retain their separately recorded identities.

Inspect `run.wsb`, then open it yourself. Networking, clipboard, audio/video input
and printer redirection are disabled. Frozen coordinator repository, Python, Git, MariaDB, game data,
navigation and prepared inputs are mapped read-only. Only this run's `output/`
is writable. Both client and services use **guest loopback**, not host services.
The guest creates its own Documents/game settings, client copy, database and
runtime. Do not run `run_client_smoke` directly on the host or weaken the WSB
settings to get a failed run to pass. Do not overlap runs in a reused guest.

## Optional graphical co-presence development check

Add `--development-check` to the **prepare** command to opt into one normal
shared-development scenario inside the same owned guest runtime. Use a worker
supporting bound party methods and `tell_visible`; no older-worker fallback is
provided. The default smoke procedure is unchanged when this flag is absent.

After the usual movement/Say/manual-rendering review, status enters
`development`. Keep the graphical character in-world. Read the host-visible
`output/development/viewer-start.json` and later `viewer-finish.json`, and send
each exact `reply_in_say` through the real client's ordinary Say UI when it
appears. Each checkpoint has the normal runner's **60-second** reply window.
Do not pre-send a finish reply or logout before the coordinator requests it.

The coordinator normally logs out/closes its original headless witness before
reusing that dedicated account as a bot. It creates a second separate non-GM
pre-connection fixture on a validated corridor point, never an invented offset.
The viewer's account/credentials are excluded from the two-account runner profile.
The normal runner performs source-bound movement, party/chat/disband, two
reciprocal visible-only Tell messages, one ordinary self-Sprint, a starter-body
unequip/re-equip round trip, reconnect, a read-only complete received inventory
projection comparison, and the two exact
viewer checkpoints. Sprint must produce matching fresh self-target action3/status50
effects and zero-TP updates on both ordinary bot sessions plus the mover's fresh
group56/recast start; its acknowledgement alone cannot pass. This proves neither
speed nor rendering, status expiry, exact net TP debit, persistence or cooldown
readiness. The equipment operation moves exact starter body item2983 between
body slot1000:3 and empty bag slot0:0, requiring fresh-login projection after each
mutation and a third total reconnect; acknowledgements are explicitly not mutation
evidence. The inventory check covers bags0–3, equipment1000 and Currency2000 by
slot/catalog/count. Neither check claims item-instance identity, appearance,
quality/durability, other containers or world-restart persistence. No GM action,
reset, resource grant/restoration or viewer UI control is performed. Fixture
placement is administrative setup only.

`development_check` in the graphical result references the exact normal-runner
summary and requires every requested subcheck, including two exact reciprocal
received Tell rows bound to the run/peer identities and strict internally
consistent Sprint identities/baselines/request/effect/zero-TP/start observations,
exact starter-body before/unequipped/re-equipped projections and all three
fresh-login lifecycle receipts, an exact unchanged read-only reconnect-inventory
receipt, released leases, the exact versioned
`clear` terminal lease snapshot, a strict normal exit receipt for the exact owned
native worker, and the same non-GM graphical fixture identity at both checkpoints.
The original continuously connected witness must retain the same received viewer
spawn-generation token from start through finish; any viewer despawn/zone loss/
respawn observed by that witness fails before the finish challenge. Legacy
summaries without this continuity evidence, without the terminal snapshot, or with
only `worker_closed:true`,
malformed/nonzero receipts and local process exit without the separate server-
lifecycle observations fail closed. The nested normal-bot scenario also receives
an integer cooperative deadline strictly inside the remaining graphical activity
budget (maximum 900 seconds); bridge success requires its exact enabled,
unexpired, completed deadline receipt. Older graphical evidence without these
receipts is not retroactively upgraded. The original witness then authenticates afresh to verify the graphical client's ordinary
logout. The existing twenty-minute activity budget remains in use: native RPC
and observation waits are capped by its remainder; late successes fail. The nested
runner budget is cooperative rather than hard preemption, and its final cleanup
may exceed that nested success budget while still remaining subject to the outer
activity/lifecycle checks. Bounded HTTP/fixture calls and cleanup are not forcibly
interrupted mid-call.

The development catalog is copied with only `navigation.mesh` localized to an
exact byte-for-byte mesh copy inside the guest input mapping. The untouched
original catalog, both catalog hashes and mesh hash are retained. No corridor,
actor, quest or route-length fields are regenerated or weakened.

The prior screenshot review does **not** certify rendering of these added bot
actions, including Sprint and equipment changes. A current successful bridge would add absence of received viewer despawn/
respawn on one persistent witness between endpoint replies, but not a server-side
continuous-session oracle, continuous rendering, visual quest/combat agreement,
normal opening progression, shared-database cleanliness or full acceptance. One owned-guest bridge has actual graphical
execution and disposal evidence (see below); preparation/contracts alone do not
satisfy those requirements for another deployment or build.

## Manual procedure and machine assertions

Follow `output/status.json`; setup logs are in `output/bootstrap.log`. The
activity deadline is twenty minutes after graphical-client launch, not an
assertion that twenty minutes of gameplay occurred. Each phase publication includes
`activity_remaining_seconds_at_publication` (a snapshot, not a live countdown).
The final result's `timing` separates setup, each entered manual/scenario phase,
and client/environment cleanup. These monotonic wall durations include operator
waiting and worker unwinding, not isolated gameplay CPU time. Unentered phases
are absent, not passing. On completion or failure, `status.json` changes to
`finished`; inspect `result.json` before further input and discard the owned guest.

1. In the real client's ordinary first-run UI choose the local data centre,
   decline character creation if offered, and select the exact fixture name in
   `status.json`. Decline the external Playguide browser prompt. Enter the world.
   First-run input/calibration prompts vary; unknown UI must be inspected, never
   answered automatically. In the exercised first-run UI, closing the welcome/
   character-creation prompt with its visible X returned to the fixture list;
   Proceed instead opened the creation editor. Do not create another character
   when the named fixture already exists. The witness requires exactly one other level-one,
   living, non-GM player in public territory 130, near the fixture position.
2. At `movement`, move that character **1–5 metres** using normal movement keys.
   The witness must receive displacement from the original spawn position.
   Catalog-derived starting placement is fixture setup, **not tested travel**.
3. At `say`, send exactly `E2E real client verified` using ordinary Say. Only a
   received message from the same observed entity satisfies this step. A typo
   does not pass; inspect the input before sending another explicit attempt.
4. The witness sends `E2E independent witness`. At `review`, inspect the private
   `review.png`: the fixture character must be rendered in-world, and the exact
   witness message must be rendered in the game chat log. Compare the fixture
   name against `status.json`. If obscured, missing or wrong, **do not approve**.
   The captured image is not automatically interpreted; its existence proves
   nothing about correct rendering. After actually examining both checks:

   ```sh
   python -m tests.e2e.prepare_client_smoke approve-rendering \
     --output .e2e-artifacts/<fresh-private-run>/output --reviewed-all-checks
   ```

   Approval is an operator attestation bound to this run and exact screenshot
   SHA-256, not an independently computed visual assertion. Stale receipts,
   changed images, wrong phases and incomplete checks are rejected.
5. At `logout`, use the client's normal `/logout` command and confirm. Inspect
   any overlapping first-run help notification before clicking; opening and
   closing its help window can uncover the confirmation buttons. Do not interpret
   a click on an obscured button as successful logout. Leave the process running. The witness must see the same entity disappear, the server
   must have logged that entity's ordinary StartLogoutCountdown request, and the
   graphical process must still be alive. Inspect `logout.png` for the title
   screen separately; the automated conditions do not recognize that image.
   At `witness_retirement`, leave the title screen alone. The coordinator waits
   for the headless witness's normal server connection closure, not only its
   logout acknowledgement, before local close/removal. Failure is not retried;
   late completion cannot pass the twenty-minute activity deadline. In-flight
   bounded calls and final environment cleanup are not forcibly interrupted.
6. Inspect `result.json`: require `status=passed`, all received snapshots,
   manual-review receipt, logout marker, `witness_retirements`, a normal
   `observer_worker_exit` receipt for the exact outer native witness process, and
   `runtime_removed=true`. A nonzero, unknown or unbound outer-worker exit changes
   the terminal result to failed even after successful witness retirement. There
   is one retirement receipt for the ordinary lane;
   with `--development-check` there are two (original witness handoff and final
   `witness-after-development`). Each requires `server_close_observed=true` and
   `native_bot_removed=true`; corroborate with its native journal. These are normal
   session-lifecycle observations, not offline/reset authority, fresh-login
   persistence or crash-consistency proof. Older artifacts without these receipts
   are not upgraded. The runner terminates the remaining title-screen process
   and private services. Process-exit UI is not a tested journey. A cleanup error
   changes the result to failed, not a passing gameplay run with a warning.
7. **Close the owned Sandbox window and confirm its discard dialog.** Guest
   runtime cleanup is not VM disposal. The result deliberately leaves
   `sandbox_disposal=operator_required`; record that separate check. On a crash,
   hard kill, deadline or incomplete output, retain diagnostics and dispose of
   the Sandbox; never infer success from a screenshot, timeout or manifest.

No raw packet submission, game memory modification, GM action, automatic scene
completion, network enablement or host settings workaround is provided.

## Evidence and current verification

The initial independent pilot used a private exploratory UI driver rather than
this committed coordinator. Its outputs are retained under
`.e2e-artifacts/client-sandbox-live-v4/output/`; they are **not public fixtures**.
The pilot's exact observations and limitations are recorded in
`research/e2e-implementation-status.md`. Do not relabel that pilot as an execution
of a later implementation. The committed coordinator was separately rehearsed
successfully at clean `958c123ad`, with private evidence in
`.e2e-artifacts/client-smoke-v1/output/`: 2.638316m observed movement, exact Say,
explicit review of rendered fixture/reply, ordinary logout and whole-runtime
cleanup. Interactive assistant inspection also confirmed the title screen;
the owned Sandbox was discarded and its launcher/client checked exited. These
were operator-driven UI checks, not an image-recognition or autonomous UI test.
The status document records staged identities, review hash and disposal evidence.

The opt-in bridge was exercised at committed `2a33024b6` in
`.e2e-artifacts/client-development-live-004/`: 1.078566m independently received
graphical movement, exact Say/manual rendering review, then 118.844s of normal
bot checks including two manual viewer replies, followed by ordinary graphical
logout/title-screen review and explicit Sandbox disposal. The whole manual lane
took 726.312s including operator waiting; this is not gameplay CPU time. The
bots independently received all 24 requested movement endpoints, exact party/chat/
disband state, bidirectional Tell, reconnect and four viewer reply observations.
The normal runner did not control the viewer. This is one owned private guest,
not the user's existing shared-server deployment or continuous/rendered-action
agreement. Three earlier failed attempts remain failed in the status audit.
Private `inspect-evidence.py` and `inspected-evidence.json` bind the summaries to
received journals, review/input hashes and lifecycle/disposal evidence.

`test_client_snapshot.py` exercises local-only committed-source isolation and
mismatch rejection; it does not launch a client or attest graphical behavior.
`test_client_smoke.py` is asset-independent policy coverage only. It tests
identity/ambiguity, fixture-state guards, movement bounds, finite positions,
review binding and WSB isolation settings. Neither those contracts nor preparing
a WSB file establishes live client, guest orchestration or disposal coverage.

Screenshots, complete inputs, client files, game settings, session-bearing
process arguments and private logs must remain outside git/public CI artifacts.
This manual lane is not added to the ten-case headless CI gate or its public
allowlist. Do not register an asset-bearing runner for untrusted pull requests.

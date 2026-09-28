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

For Debug builds, also supply the matching compiler's **x64** DebugCRT and CRT
folders using repeated `--crt-dir`. This additionally stages `ucrtbased.dll` from
System32. Conflicting DLL bytes and reused output directories fail. Nothing is
launched by preparation; `inputs.json` says `prepared_not_executed` and hashes the
staged inputs. Keep the source checkout unchanged while the guest runs: the
repository is mapped read-only, not snapshotted.

Inspect `run.wsb`, then open it yourself. Networking, clipboard, audio/video input
and printer redirection are disabled. Repository, Python, Git, MariaDB, game data,
navigation and prepared inputs are mapped read-only. Only this run's `output/`
is writable. Both client and services use **guest loopback**, not host services.
The guest creates its own Documents/game settings, client copy, database and
runtime. Do not run `run_client_smoke` directly on the host or weaken the WSB
settings to get a failed run to pass. Do not overlap runs in a reused guest.

## Manual procedure and machine assertions

Follow `output/status.json`; setup logs are in `output/bootstrap.log`. The
activity deadline is twenty minutes after graphical-client launch, not an
assertion that twenty minutes of gameplay occurred.

1. In the real client's ordinary first-run UI choose the local data centre,
   decline character creation if offered, and select the exact fixture name in
   `status.json`. Decline the external Playguide browser prompt. Enter the world.
   First-run input/calibration prompts vary; unknown UI must be inspected, never
   answered automatically. The witness requires exactly one other level-one,
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
5. At `logout`, use the client's normal `/logout` command and confirm. Leave the
   process running. The witness must see the same entity disappear, the server
   must have logged that entity's ordinary StartLogoutCountdown request, and the
   graphical process must still be alive. Inspect `logout.png` for the title
   screen separately; the automated conditions do not recognize that image.
6. Inspect `result.json`: require `status=passed`, all received snapshots,
   manual-review receipt, logout marker, and `runtime_removed=true`. The runner
   terminates the remaining title-screen process and closes the witness and
   private services. Process-exit UI is not a tested journey. A cleanup error
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

`test_client_smoke.py` is asset-independent policy coverage only. It tests
identity/ambiguity, fixture-state guards, movement bounds, finite positions,
review binding and WSB isolation settings. Neither those contracts nor preparing
a WSB file establishes live client, guest orchestration or disposal coverage.

Screenshots, complete inputs, client files, game settings, session-bearing
process arguments and private logs must remain outside git/public CI artifacts.
This manual lane is not added to the seven-case headless CI gate or its public
allowlist. Do not register an asset-bearing runner for untrusted pull requests.

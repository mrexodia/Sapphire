# Fast shared-server development lane

This lane connects two normal non-GM bots to an **already-running local development
server**. It does not create a disposable environment, install/migrate a database,
change server/client configuration, restart a process, or perform administrative
resets. It is explicitly `shared-development-not-acceptance` evidence.

Use this lane for short development feedback and watching bots from a graphical
client. Keep the existing isolated pytest lane for clean regression/acceptance;
do not point its `Environment` fixture at a shared database. No full acceptance
run is required to use this lane.

## Prepare once

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
  --artifacts .e2e-artifacts/dev-provision-001
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
login, refreshed-lobby/world confirmation and logout stages. Errors preserve the
credential file and local leases; inspect partial results instead of retrying
creation or deleting characters automatically. No old character/account is
modified, reset or removed. Account creation is sequential, not a claim of
multi-process allocation safety. Interrupted/hard-killed runs may lack a complete
summary; retained credentials/leases do not prove crash consistency.

**Provisioned is not public-world ready.** Fresh characters normally enter the
opening territory. This command does not skip openings, teleport, grant levels,
reset quests, or assert that the shared smoke preconditions hold. Its summary
always says `ready_for_shared_checks: false`. Complete the opening or explicitly
prepare public-world fixtures with your development tools before running the
shared checks. Targeted administrative placement/reprovisioning is still pending.

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

## Evidence and limitations

`development-summary.json` records worker/catalog hashes, entities, scope,
completion/error stage, lease disposition, elapsed time and phase durations:
HTTP login, lobby/world entry, initial witness checks, Say, optional movement,
logout/despawn and account release. `worker_session_including_close` is an
inclusive parent timing; do not add it to its child phases.

A configured protocol and successful session are not a server binary fingerprint.
The report explicitly leaves `server_identity_verified` false. Passing proves
only the checks actually executed against that shared world. It does not prove
isolation, fixture reset, persistence across restart, combat/progression, capacity,
graphical-client compatibility, or acceptance coverage.

World reset commands and reprovisioning of existing characters remain separate
follow-up work. New-account provisioning is described above. A future reset must
be development-only, explicitly targeted, require
exclusive ownership/offline actors as appropriate, and record administrative
preparation separately from normal gameplay evidence. Broad world resets must not
interrupt a human viewer or be silently run between tests.

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
python -m pytest tests/e2e/test_development.py tests/e2e/test_development_provisioning.py -q
```

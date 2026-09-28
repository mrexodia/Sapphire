# Sapphire headless E2E tests

This is an external client, not an in-process server bot. Tests use normal HTTP,
lobby, zone and chat connections. The current worker deliberately accepts only
loopback endpoints and at most 64 bots per process.

## Verified scope

The Windows/3.3 implementation has been exercised against isolated local API,
lobby, world and MariaDB processes with matching game data:

- Invalid credentials are rejected.
- Genuine HTTP login, encrypted lobby negotiation, character selection and world
  handoff succeed with non-GM accounts.
- Readiness requires zone initialization, self-spawn **and the server clearing
  BetweenAreas after the normal FINISH_LOADING command**. A connected socket or
  self-spawn alone is insufficient.
- Both zone and chat keepalive responses are observed.
- A second bot observes another bot spawning, walking a one-metre segment, and
  despawning after logout.
- The moved position survives a world-process restart and a new HTTP/lobby login.

The worker also decodes quests/completion flags and scenes, and supports explicit
scene responses, but **a complete quest/reward journey has not yet been verified**.
The source-derived `scene_catalog/due_diligence.json` is not evidence of a passing
quest test. General navigation, combat, scene yields, autonomous exploration,
soak/load policies and real-client/UI compatibility are not implemented yet.

Asset-independent tests are not labeled as gameplay coverage. See the
[implementation status](../../research/e2e-implementation-status.md) for the
outstanding checklist.

## Build the worker without server/database/assets

From the repository root, with submodules initialized:

```sh
cmake -S src/test_client -B build-e2e -DCMAKE_BUILD_TYPE=Debug
cmake --build build-e2e --config Debug
ctest --test-dir build-e2e -C Debug --output-on-failure
python -m pip install -r tests/e2e/requirements.txt
```

For a single-config generator:

```sh
python -m pytest tests/e2e/test_worker.py \
  --e2e-worker build-e2e/sapphire_test_client --junitxml=build-e2e/contracts.xml
```

On Windows, append `.exe`. With the Visual Studio generator the executable is
`build-e2e/Debug/sapphire_test_client.exe`. Ninja builds place it directly in
`build-e2e/`. Both Clang/Ninja and MSVC/Visual Studio builds have passed locally.
Linux CI is configured but has not been run in this implementation session.

To include the worker in the normal Sapphire build, configure with
`-DSAPPHIRE_BUILD_TEST_CLIENT=ON`. It is off by default.

The CTest executable verifies explicit header/layout fixtures, all split points
of a sample TCP frame, one-byte reads, coalesced frames, bounded parsing, lobby
cipher roundtrips and OS-generated session token format/independence. The Python
contract tests cover control errors, connection failures, pre-readiness action
rejection, worker death, scene selection, redaction and setup checks. These do
not replace the live suite.

## Run the live suite

1. Build Sapphire's `api`, `lobby`, `server`, `dbm` and native script modules.
2. Supply matching FFXIV 3.3 game data and a MariaDB installation. Do not put assets
   or credentials in git or public CI artifacts.
3. Copy `tests/e2e/profile.example.json` to `.e2e-local.json` and edit its paths.
   Profiles must point to binaries you trust. The root `.gitignore` excludes local
   `.e2e-*.json` profiles and `.e2e-artifacts/`.
4. Run:

```sh
python -m pytest tests/e2e/test_live.py --e2e-profile .e2e-local.json \
  -v --junitxml=build-e2e/live.xml
```

Missing required assets, missing binaries or setup errors **fail** an explicitly
requested live run. Without `--e2e-profile`, live tests are explicitly skipped.
Do not interpret such a run as live coverage.

The runner:

- Creates a new temporary runtime and private MariaDB data directory on unique
  loopback ports. It does not connect to the development database.
- Copies executables rather than symlinking them, because Sapphire loads config
  relative to the executable. It never copies the development `bin/config`.
- Initializes, migrates and checks a new `sapphire_e2e_<uuid>` schema via `dbm`.
- Generates test-specific configs with `DefaultGMRank=0`,
  `AllowNoSessionConnect=false` and script hot swap disabled.
- Provisions fresh account/character fixtures, then uses the normal HTTP login.
- Places fixtures in public Ul'dah (130), with opening progression initialized,
  **before their first world connection**. This is fixture setup, not coverage of
  character creation, the opening quest, or travel into Ul'dah. Opening territory
  182 is private and is not appropriate for two-player replication assertions.
- Uses no GM movement or quest completion commands during tested journeys.
- Stops only the processes it owns, redacts credentials/session identifiers from
  collected text logs, and removes the private runtime/database on teardown.

Live tests currently use the already-built server binaries. `manifest.json`
records their hashes, script hashes, worker hash, source revision/dirty status,
fixture version and paths. A source build hash is not automatically proof the
server executable matches every current source file. Rebuild relevant targets
before testing source changes.

A run interrupted by forcibly terminating the Python process may leave its
private temporary directory/processes behind. Normal test failure, setup failure,
and Python interruption paths run cleanup. Never point the harness at a shared
DB data directory.

The source includes a Linux bootstrap path, but the provisioned environment has
only been validated on Windows so far. Linux requires the corresponding MariaDB
command-line tools and permissions to start a private user-owned database.

## Scenario API

Synchronous Python methods keep authored scenarios simple; worker I/O, keepalives
and movement run independently in an asynchronous C++ event loop.

```python
from tests.e2e.support.worker import Bot

fixture = environment.fresh_character()
bot = Bot(worker, "player")
state = bot.login_via_lobby(fixture["auth"], fixture["name"])
# login_via_lobby also waits for server-observed world readiness.

bot.walk_to([43.0, 4.0, -157.6])
# This only confirms all movement samples were SENT.
# Assert the resulting position with an independent observer bot.

bot.logout()   # Waits for a received logout acknowledgement, then closes sockets.
bot.close()    # Removes the bot from the worker.
```

Additional actions: `wait_world_ready`, `walk_route`, `interact`,
`choose_dialogue`, `expect_quest_active`, `expect_quest_complete`.
Use `worker.wait_state(...)` for bounded predicates against received state. Event
notifications wake waits; snapshots also cover observations received before the
wait was registered. No automatic gameplay retry is performed after a timeout.

Movement is interpolated at 100ms intervals, with per-waypoint distance <=100m
and speed <=6m/s. It is not a general collision simulator. `predicted_position`
is distinct from `observed_position` and other bots' received actor positions.

`choose_dialogue` requires a versioned catalog entry and passes the exact observed
event ID, scene ID and unique scene token back to the worker. Unknown choices or
scenes raise `UnsupportedScene`; stale tokens are rejected. One/two-result scene
returns are supported; scene yield/resume is not supported. There is no default
"always accept" behavior and no unrestricted raw-packet command.

`close` cancels pending connection/movement timers and closes sockets; `remove`
also releases the bot. End-of-input shuts down all worker-owned connections.

## Local quest metadata / navigation feasibility

The optional `sapphire_test_catalog` target is available only in a full Sapphire
build, since it links the existing game-data and navigation libraries:

```sh
cmake -S . -B build -DSAPPHIRE_BUILD_TEST_CLIENT=ON
cmake --build build --target sapphire_test_catalog --config Debug
bin/sapphire_test_catalog <game/sqpack>
bin/sapphire_test_catalog <game/sqpack> <mesh-root> <private-output.json>
```

Add `.exe` on Windows. The first form prints limited Due Diligence metadata. The
second attempts a navmesh route between its two NPCs and writes JSON only after a
successful path query. Failure to load the mesh or find a path is an error, not a
straight-line fallback. Generated data is local asset-derived material; do not
publish bulk game data as CI artifacts.

Current local evidence: both NPCs resolve to territory 130 and the quest has level
1/no previous-quest requirements. However, the available `w1t1.nav` fails the
current `PathFinder` tile-data load. Regenerating a compatible mesh in a separate
test asset directory is the next step, followed by route validation and live
quest/reward/persistence assertions. The tool does not modify the existing mesh.

## Artifacts and CI

Each live run writes `.e2e-artifacts/sapphire-e2e-*/`:

- `manifest.json`: build/fixture/runtime identity.
- Redacted API/lobby/world/database setup logs.
- Per-test `events.jsonl`: the last 2048 received semantic/packet-summary events.
- Per-test `actions.jsonl`: the last 2048 semantic actions, omitting authentication
  arguments; safe movement/interaction/scene arguments are retained.
- Per-test `worker-stderr.log`: bounded worker diagnostics.

JUnit output goes to the path selected with `--junitxml`. Never upload the private
runtime, raw database, game assets, local profiles or unredacted configs.

`.github/workflows/test-client.yml` builds and tests the asset-independent client
on Linux and Windows. It does **not** provision game data, run gameplay tests, or
claim real-client compatibility. Full gameplay CI requires a trusted, suitably
provisioned runner with appropriate isolation from untrusted PR code.

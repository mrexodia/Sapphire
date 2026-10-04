# Sapphire bot tests

Headless bots that play against a **running local Sapphire development server**
through the normal HTTP, lobby, zone and chat connections. They are ordinary
non-GM clients: nothing is injected into the server, and every assertion is made
on state the bots *received*, usually confirmed by a second bot.

Two ways to use them:

- **Automated:** `pytest tests/e2e` runs the scenarios as regression tests.
- **Watchable:** `python -m tests.e2e.scenario say_and_walk` runs one scenario and
  leaves the bots standing in the world so you can look at them from your own
  character.

The tests never start, stop, migrate or reset your database or server processes.

## Setup

1. **Build** the server as usual. The bot worker `sapphire_test_client` and the
   small `sapphire_test_*_catalog` tools are built by default next to the server
   binaries.

2. **Migrate** your database (`dbm --mode migrate ...`). The bots rely on the
   `charainfo.Online` column the world maintains.

3. **Enable the bot API** in `api.ini` and restart the API process:

   ```ini
   [Development]
   BotApi = true
   ```

   This exposes `/sapphire-api/dev/createBot`, `listBots` and `purgeBots`,
   protected by the server secret from `global.ini`. Bot accounts are named
   `bot_<random>` and their characters are plain non-GM characters, so they are
   easy to spot and safe to delete. Do not enable this on a public server.

4. **Write a profile** describing your stack. Copy `profile.example.json` to
   `.e2e-dev.json` (ignored by git) and adjust:

   ```json
   {
     "api": "http://127.0.0.1:80",
     "secret": "default",
     "worker": "../../bin/sapphire_test_client.exe",
     "server_dir": "../../bin"
   }
   ```

   Relative paths resolve from the profile's directory. `server_dir` is the
   server's working directory, used only to read `data/` for combat scenarios.
   The optional `*_catalog` entries point at generated content catalogs (see
   below); scenarios that need a missing catalog fail with a clear message.

5. **Run** with the stack up:

   ```powershell
   python -m pip install -r tests/e2e/requirements.txt
   python -m pytest tests/e2e --e2e-profile .e2e-dev.json
   python -m tests.e2e.scenario say_and_walk --profile .e2e-dev.json
   ```

Each pytest session purges offline `bot_*` accounts at start and end. Pass
`--e2e-keep-bots` to keep them for a look in game, and
`python -m tests.e2e.scenario --purge --list` to clean up later.

## Soak runs

`python -m tests.e2e.scenario soak --duration 3600 --bots 3 --profile .e2e-dev.json`
cycles login, chat, walking, a gil shop open/close and logout for an hour. After
each cycle it logs the world process's resident memory (needs `pip install psutil`),
the slowest login and shop round trip and any keepalive replies that went missing,
and appends the same numbers to `soak.jsonl` in the worker's artifacts directory.
A world that grows without bound or stops finishing events shows up there.

## Watching bots from your own character

Log in with your own (GM or not) character, then start a scenario. Bots are
created in the public city that matches their class, at the class's creation
position, with the opening already done. The default is a Gladiator in Ul'dah,
Steps of Nald (territory 130) near (42, 4, -158). Teleport there and you will see
them spawn, chat and walk. The scenario prints every bot's name, territory and
position as it goes. Press Ctrl+C to log the bots out.

Scenarios live in `scenarios.py`; add one by decorating a function with
`@scenario` and returning the bots it leaves logged in. The pytest wrappers in
`test_live.py` reuse the same functions.

## What the scenarios cover

| File | Scenario |
|---|---|
| `test_live.py` | rejected credentials, login/keepalive/logout, Say and walking observed by a second bot, party of up to eight with chat, leadership, kick, disband |
| `test_live_quest.py` | Motivational Speaking and Gil for Gold through their real scene exchanges, rewards, inventory move/swap/split/merge/discard, gil shop sale and purchases, persistence through a fresh login |
| `test_live_shop.py` | gil shop buyback as the real client sends it: the sold item comes back for the sale price, phantom entries move nothing, the window stays open |
| `test_live_zoning.py` | Return action, the Ul'dah to Central Thanalan exit crossing, discovery, cross-zone party chat and Tells |
| `test_live_creation.py` | character creation through the lobby, the Ul'dah opening scenes, ring choice, Wymond's closed exits and arrival area with the warp back and their sequence gating, starter gear round trips, duplicate-name rejection, deletion |
| `test_live.py::test_soak_cycles` | one short pass of the `soak` scenario below, so the loop is known to work before an hour-long run |
| `test_live_combat*.py`, `test_live_combo.py`, `test_live_progression.py`, `test_live_high_level_combat.py`, `test_live_aggro.py`, `test_live_player_defeat.py` | Fast Blade, Bootshine, Blizzard, combos, EXP and level progression, natural aggro, leash and player defeat with homepoint return |

The combat scenarios need the world to have loaded a navmesh for Central
Thanalan (`w1f2`); without one enemies attack but never move. The tests check the
world log for `No navmesh found for TerritoryType#141` and fail fast with that
reason. Point `MeshPath` in world.ini at a mesh set the current loader accepts
(the tile-cache format produced by `sapphire_test_navbuild`).

The character-creation scenario plays the Ul'dah opening and needs
`SkipOpening = false` in world.ini; it fails with that message otherwise.

Enemies respawn on their own (15s for the starter marmots, 60s for the level-14
enemies) and heal fully when they retreat, so scenarios wait for a healthy enemy
or rotate across spawns rather than resetting the world.

Persistence is checked by logging out and back in, not by restarting the world.
A scenario that fails leaves the bot's `actions.jsonl` and `events.jsonl`
journals under the artifacts directory for the test.

## Bot worker

`src/test_client/` is a C++ client controlled over stdin/stdout with JSON lines.
`support/worker.py` wraps it: `Worker` owns the process and `Bot` exposes
semantic actions (`login_via_lobby`, `walk_to`, `say`, `interact`,
`choose_dialogue`, `invite_party`, `fast_blade`, ...) plus `expect_*` helpers
that wait on received state. The worker only connects to loopback or private-network
addresses and hosts at most 64 bots per process.

The worker is part of the normal build (`SAPPHIRE_BUILD_TEST_CLIENT`, on by
default) and lands next to the server binaries. The wire and worker unit tests
need no game data or database:

```powershell
ctest --test-dir build --output-on-failure
python -m pytest tests/e2e/test_worker.py tests/e2e/test_combat_policy.py --e2e-worker bin/sapphire_test_client.exe
```

## Content catalogs

Quests, shops, zone transitions, combat actions and enemy spawns are resolved
from your game data rather than hard-coded. Generate the catalogs once from the
full build (they need the game data path and the exported navmesh):

```powershell
bin/sapphire_test_catalog <game/sqpack> <navi root> build-e2e/motivational-speaking.json 65686
bin/sapphire_test_catalog <game/sqpack> <navi root> build-e2e/gil-for-gold.json 65687
bin/sapphire_test_shop_catalog <game/sqpack> <navi root> build-e2e/shop-catalog.json
bin/sapphire_test_transitions <game/sqpack> <navi root> build-e2e/uldah-central-transition.json
bin/sapphire_test_combat_catalog <game/sqpack> build-e2e/combat-catalog.json
bin/sapphire_test_respawn_catalog <game/sqpack> build-e2e/respawn-catalog.json
bin/sapphire_test_pursuit_catalog <game/sqpack> <navi root> build-e2e/pursuit-catalog.json
bin/sapphire_test_opening_quest_catalog <game/sqpack> <navi root> build-e2e/coming-to-uldah.json
```

Point the matching `*_catalog` profile entries at the outputs. Scene choices for
quests are in `scene_catalog/*.json`; an unknown scene stops the bot rather
than being acknowledged blindly.

## Design notes

- Bots are external clients and never GM. A command being sent, acknowledged or
  logged is not success; the received state is.
- A mutation whose outcome is uncertain (quest acceptance, item transactions) is
  never retried automatically.
- The bot fixture API is the only server-side helper. It creates and deletes
  `bot_*` accounts and refuses to delete a character the world still has online.
- `research/autonomous-testing-plan.md` is the original, broader design this
  grew out of.

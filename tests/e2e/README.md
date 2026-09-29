# Sapphire headless E2E tests

This is an external client, not an in-process server bot. Tests use normal HTTP,
lobby, zone and chat connections. The current worker deliberately accepts only
loopback endpoints and at most 64 bots per process.

## Verified scope

The Windows/3.3 implementation has been exercised against isolated local API,
lobby, world and MariaDB processes with matching game data:

- Invalid credentials are rejected.
- Genuine HTTP login, encrypted lobby negotiation, character selection and world
  handoff succeed with non-GM accounts. A separate case starts with an account that
  has no characters, reserves a name and finalizes canonical Ul'dah starters through
  lobby operations, refreshes each isolated account's character list, and enters
  the normal private opening territory.
- Readiness requires zone initialization, self-spawn **and the server clearing
  BetweenAreas after the normal FINISH_LOADING command**. A connected socket or
  self-spawn alone is insufficient.
- Both zone and chat keepalive responses are observed.
- A second bot observes another bot spawning, walking a one-metre segment, and
  despawning after logout.
- The moved position survives a world-process restart and a new HTTP/lobby login.
- Another bot receives the sender's ordinary Say message.
- **Motivational Speaking (65686)**: cancellation leaves quest/reward state unchanged;
  acceptance, a roughly 152m navmesh route, explicit completion scene, 50 XP and two
  potions are verified. A nearby bot independently observes arrival.
- Quest completion, tracked bag item counts/currencies and XP survive world restart and
  a fresh HTTP/lobby login. Completion-list bit order has a regression fixture.
- **Gil for Gold (65687)** follows the first quest without seeded completion or a
  position reset. The chain checks its observed prerequisite, reconnects with the
  quest active, walks another 86.8m, cancels/acknowledges a hand-over, then chooses
  three ethers rather than the alternative potions. Both completions and cumulative
  rewards survive world restart.
- A three-client zoning test walks a verified approach into an actual exit volume,
  crosses from Ul'dah to Central Thanalan, observes departure and arrival from
  separate bots, checks destination chat/keepalives and reloads the new territory
  and position after world restart.
- The chain test moves the earned ether stack to an observed empty ordinary bag
  slot, verifies exact placement through a fresh login and again after world
  restart, preserving all other tracked slots and rewards. It then swaps the
  occupied ether and potion slots and verifies the exact exchange after another
  restart. Finally it discards the relocated ether stack, waits for a committed
  received deletion, checks every tracked slot for unintended changes, and verifies
  the deletion plus retained quest progress after the final restart.

- Four newly created characters spanning Gladiator, Pugilist and Thaumaturge start
  Ul'dah event 1245187 through its source-defined
  enter-territory operation and exercise all explicit ring results 1..4. Each
  receives scenes 0 then 1, exactly one corresponding item 4423..4426, and the
  scene-40 continuation through fresh authentication and a shared world restart.
  Before each distinct class journey, the client moves the observed starter main
  hand (Gladiator 1601, Pugilist 1680 or Thaumaturge 2055) to an observed-empty
  ordinary-bag slot. Fresh authentication proves each unequip, then a class/item-
  bound operation moves the same weapon back to the observed-empty main hand;
  restart proves every exact final equipment state.
  Receipts are never treated as mutation proof. The first character then walks a
  source-generated ~9.84m route to Wymond and accepts Coming to Ul'dah (66130)
  through explicit scenes 0/1/2. Active sequence 255, position and opening sequence
  2 (scene 40→30) survive restart. The generated giver-to-Momodi route fails closed
  as `incomplete navigation corridor`, so turn-in, the quest's 50 EXP/103 gil and
  public-Ul'dah travel are not claimed. This covers one starter-weapon round trip
  for each of three Ul'dah starting classes and the supported opening subset, not
  other slots/items, appearance breadth, other cities/classes or the complete opening.
- A level-one Gladiator waits for naturally regenerated TP and performs paced Fast
  Blades until an observed nearby level-one marmot is defeated. An independent bot
  verifies every matching result/committed HP decrease, the first natural retaliation,
  zero target HP and delayed removal. The fighter receives exactly 50 EXP and the
  server's enabled `testTable` loot pools; exact rewards survive a fresh login.
  The same case creates a normal level-one Pugilist fixture, follows a roaming
  natural target through bounded received-position movement observed by a witness,
  and verifies Bootshine (53), its committed damage and action-start metadata on
  both clients. A normal Thaumaturge then casts source-defined Blizzard (142) from
  independently observed range with received MP; both clients verify its damage,
  committed HP and status effect, while the caster receives matching source
  integrity and cast/recast metadata. Enemies, skills and resources are not granted
  or modified.
- A separate fresh level-one Gladiator uses ordinary Fast Blade against an observed
  natural level-14 enemy and runs a complete ~50.69m source-navmesh route. Both
  clients observe pursuit beyond 35m and the enemy's natural retreat to its bound
  spawn while the fighter survives. The fighter returns normally, re-engages once,
  and walks the existing ten-metre route without further attacks; fighter and
  stationary observer receive every retaliation effect and exact committed HP
  through zero. The defeated fighter then sends the bounded return command, reaches
  its source-bound Ul'dah homepoint at full HP, is observed there by a third client,
  and preserves that position/HP after restart. Both clients also receive the
  leashed enemy's ordinary HUD update restoring 237/237 HP. This proves one
  leash/position/health reset, not general aggro policy, raises or death penalties.

The source-derived `scene_catalog/due_diligence.json` remains unverified: its NPCs
are not connected by the available regenerated mesh. General navigation/combat
and scene yields remain unsupported. A separate [manual real-client lane](REAL_CLIENT.md)
now has a live-verified coordinator and narrow independent evidence for world
entry, movement, bidirectional Say and logout—not general UI/quest compatibility
or automated rendering checks.

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
python -m pytest tests/e2e/test_worker.py tests/e2e/test_policy.py tests/e2e/test_ci.py \
  tests/e2e/test_soak.py tests/e2e/test_client_smoke.py tests/e2e/test_workload_cleanup.py \
  tests/e2e/test_combat_policy.py tests/e2e/test_inventory_policy.py tests/e2e/test_minimize.py \
  --e2e-worker build-e2e/sapphire_test_client --junitxml=build-e2e/contracts.xml
```

On Windows, append `.exe`. With the Visual Studio generator the executable is
`build-e2e/Debug/sapphire_test_client.exe`. Ninja builds place it directly in
`build-e2e/`. Both Clang/Ninja and MSVC/Visual Studio builds have passed locally.
GNU/Linux builds and all six CTest executables pass under Ubuntu 22.04/WSL.
Python contracts also pass in a network-isolated Linux container. WSL's current
loopback fails even a Python-only socket check; no host networking was changed to
work around that. Hosted CI has not been run in this implementation session.

To include the worker in the normal Sapphire build, configure with
`-DSAPPHIRE_BUILD_TEST_CLIENT=ON`. It is off by default.

CTest verifies explicit header/layout fixtures, split/coalesced TCP frames,
bounded parsing, lobby cipher roundtrips, OS-generated tokens, quest flag order,
deferred inventory transaction publication, XP snapshots, and complete versus
partial/disconnected navigation paths using synthetic geometry. Combat tests check
request byte offsets, observed-target/resource/range guards, bounded result histories,
and that effects alone never invent committed HP. A concurrent allocator test
requires one database seed observation and unique contiguous IDs across 64 threads.
Database binding tests compile actual application binding code against a borrowed-stream connector double;
they check byte preservation, rebinding, partial failures and balanced C++
allocations. They do not replace live SQL/persistence verification. The Python
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
4. For quest coverage, generate the private route catalogs below and add absolute
   paths as `quest_catalog` (65686) and `follow_up_catalog` (65687) in the profile.
   Requested quest tests fail if their catalog is absent. Use `-k single` to select
   only the first quest.
5. For zoning, generate the transition catalog below and set `transition_catalog`.
   Set `navigation` to a private compatible server mesh root for the tested maps.
6. For combat, generate the action catalog below, set `combat_catalog`, and supply
   the compatible Central Thanalan mesh in `navigation`.
7. For the chained inventory/economy path, generate the source-bound shop catalog
   below and set `shop_catalog`.
8. For the player-defeat return path, generate the source-bound respawn catalog
   below and set `respawn_catalog`; generate the bounded pursuit catalog below and
   set `pursuit_catalog`.
9. For the creation/opening path, generate the source-bound opening quest catalog
   below and set `opening_quest_catalog`.
10. Run:

```sh
python -m pytest tests/e2e/test_live.py tests/e2e/test_live_quest.py \
  tests/e2e/test_live_zoning.py tests/e2e/test_live_combat.py \
  tests/e2e/test_live_player_defeat.py tests/e2e/test_live_creation.py \
  --e2e-profile .e2e-local.json -v --junitxml=build-e2e/live.xml
```

Select only `test_live.py` for the smaller login/movement/social smoke slice.

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
- Provisions fresh account/character fixtures for scenarios that need controlled
  public placement, then uses the normal HTTP login. The creation scenario instead
  provisions only an empty account and performs reserve/finalize/list/select through
  the encrypted lobby connection.
- By default places ordinary fixtures in public Ul'dah (130), with opening progression
  initialized **before their first world connection**. That remains fixture setup,
  not evidence of travel into Ul'dah. The dedicated creation case verifies the ring
  branch and source-routed Coming to Ul'dah acceptance in private territory 182;
  the missing giver-to-recipient corridor blocks turn-in and travel to the public
  territory. Territory 182 is not
  appropriate for two-player replication assertions.
  Quest fixtures start at the catalog's first walkable waypoint; this is not proof
  of travel from character creation to the quest giver. Quest state is never seeded.
- Uses no GM movement or quest completion commands during tested journeys.
- Stops only the processes it owns, redacts credentials/session identifiers from
  collected text logs, and removes the private runtime/database on teardown.
  Transient Windows file-sharing failures get bounded cleanup retries; persistent
  cleanup failures remain errors, not ignored successes.

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

Additional actions: `wait_world_ready`, `walk_route`, `interact`, `choose_dialogue`,
`wait_event_finished`, `expect_quest_active`, `expect_quest_complete`,
`reward_snapshot`, `expect_rewards`, `request_item_move`, `request_item_swap`,
`request_item_split`, `request_item_merge`, `discard_item`, `cross_exit`, `say`,
`expect_say`, `wait_fast_blade_ready`, and
`fast_blade`.
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

`discard_item(storage, slot, expected_item)` supports whole stacks in ordinary
bags only. It requires a matching observed item identity; it cannot discard
currency/equipment or select an arbitrary inventory operation. A request-level
acknowledgement alone is not deletion evidence.

`request_item_move(storage, slot, destination_storage, destination_slot, expected_item)`
requests a whole-stack move to an observed **empty** ordinary bag slot. Both bags
must have complete received snapshots; same-slot moves, occupied destinations,
non-bag storage, invalid indexes and item mismatches fail before sending. The
caller cannot select a count or arbitrary operation. The receipt says
`acknowledged=true, inventory_change_verified=false`: the current server queues
that acknowledgement **before attempting the move**, and publishes no slot delta.
Neither that receipt nor successful request serialization changes the worker's
inventory. `rewards.operation_batches` retains at most 128 received context/type/
error records; these are acknowledgements, not universal commit records.

`request_item_swap(storage, slot, destination_storage, destination_slot,
expected_item, expected_destination_item)` swaps two observed **occupied** ordinary
bag slots. Both identities/counts and complete bag snapshots are required. Equal
identities are rejected so the bounded regression has an unambiguous exact-map
result. The caller still cannot choose counts or an arbitrary operation, and the
operation-9 acknowledgement is not mutation evidence.

`request_item_split(...)` requires an exact observed source count, a positive
strictly smaller split count and an observed empty ordinary-bag destination.
`request_item_merge(...)` requires exact observed source/destination counts and the
same item identity in distinct ordinary-bag slots. Operation-10/12 acknowledgements
are non-mutation evidence, just like move/swap acknowledgements; only later complete
snapshots establish either result.

The chain regression earns its three ethers normally, requests the move to bag 3,
slot 24, logs out and authenticates again. Complete received snapshots must then
show the source absent, that exact destination holding all three ethers, and every
other tracked slot unchanged—not merely equal bag totals. The nearby observer
checks identity/position/despawn/reappearance, not private inventory contents.
The same placement and unchanged rewards/quest completions are checked after an
orderly world restart. `inventory-move.json` records those observations.

The reloaded client then swaps the occupied ether and potion slots. It normally
logs out, the world restarts, and a fresh authentication must show both exact
identities/counts exchanged with every other tracked slot unchanged.
`inventory-swap.json` records the operation-9 acknowledgement separately from the
post-restart map. Next, one earned three-item stack is split 3→2+1 into an observed
empty slot. A world restart/fresh authentication must show both exact stacks and
every other slot unchanged. The one-item stack is then merged back; another restart
must restore the exact pre-split map. `inventory-split-merge.json` separates both
acknowledgements from those snapshots. The discard test subsequently deletes the
merged ether stack and verifies that deletion across the next restart. One remaining two-potion stack is then split,
verified after another restart, and the character walks a source-derived route to
an observed gil-shop actor. An independent client verifies arrival. The worker
opens only the matching received shop scenes, sells the observed one-item ordinary-
bag stack, and requires the exact item decrease and 28-gil increase. From the
refreshed received shop scene it then buys source-listed item 5890 for exactly eight
gil, requiring the new item and 20-gil balance immediately and after fresh
authentication plus a world restart. `gil-shop-sale.json` records those snapshots;
the operation-10 acknowledgement remains explicitly separate
from mutation evidence. The server split implementation creates the new persistent
item directly at the requested slot; it no longer aliases an `addItem()` auto-slot
into a second destination. The first zero-to-nonzero currency credit was also fixed
not to inherit the generic item factory's default quantity of one, and the item
manager is initialized before persisted currencies can be materialized at startup.
No database mutation, grant, optimistic slot update, forced resync or fabricated
server response supplies gameplay evidence.

This covers an ordinary empty-destination whole-stack move, a two-occupied-slot
swap, one partial split, one no-overflow same-item merge, discard, one exact
single-item sale and one exact single-item purchase—not equipment or currency-
container moves, overflow merges, item use, arbitrary shops/items or quantities,
immediate operation publication, crash
consistency or independent real-client inventory presentation.

`close` cancels pending connection/movement timers and closes sockets; `remove`
also releases the bot. End-of-input shuts down all worker-owned connections.

## Local quest metadata / navigation feasibility

The optional `sapphire_test_catalog` target is available only in a full Sapphire
build, since it links the existing game-data and navigation libraries:

```sh
cmake -S . -B build -DSAPPHIRE_BUILD_TEST_CLIENT=ON
cmake --build build --target sapphire_test_navbuild sapphire_test_catalog --config Debug
bin/sapphire_test_navbuild bin/navi/w1t1/w1t1.obj .e2e-assets/uldah-v1 w1t1
bin/sapphire_test_catalog <game/sqpack> .e2e-assets/uldah-v1/navi build-e2e/quest.json 65686
bin/sapphire_test_catalog <game/sqpack> .e2e-assets/uldah-v1/navi build-e2e/follow-up.json 65687
```

Add `.exe` on Windows. The builder reuses the existing exporter, requires a new
output directory, and refuses overwrites. It copies collision geometry into that
private directory and emits current TSET tiles. Original OBJ/mesh hashes were
checked unchanged. The bundled legacy MSET mesh is not rewritten.

The catalog loads through `NaviProvider` and extracts quest prerequisites, rewards,
actor identities and a versioned Detour route. It requires a complete corridor,
rejects truncation/off-mesh links and samples polygon surfaces at approximately
0.5m spacing. Endpoints must be within 2m of the selected NPCs. Partial paths or
missing meshes fail, with no straight-line fallback. The Python scenario rechecks
route bounds/length/endpoints. The verified 65686 route contains 322 waypoints.

Set `quest_catalog` and `follow_up_catalog` to the corresponding generated JSON
paths. Manifests record both catalog hashes and their navigation mesh hashes.
The follow-up starts at the previous route's endpoint and has 186 waypoints;
loading it requires the prerequisite to have been observed complete. Generated routes, collision geometry and meshes are private
asset-derived material; keep them under ignored directories, not public artifacts.
Due Diligence (default quest ID 65685 if omitted) still fails the complete-corridor
requirement; it is not counted as coverage.

## Source-bound gil-shop sale and purchase

The full-build shop tool extracts the sale value for the normally earned potion,
finds ordinary gil-shop event handlers in territory 130, and selects a complete
bounded Detour corridor from the verified Gil for Gold recipient. It has no
straight-line fallback and refuses missing actors, missing prices, partial routes,
steps over two metres, or routes over 500 metres.

```sh
cmake --build build --target sapphire_test_shop_catalog --config Debug
bin/sapphire_test_shop_catalog <game/sqpack> .e2e-assets/uldah-v2/navi build-e2e/shop.json
```

Use `.exe` on Windows and set `shop_catalog` to the absolute output path. The
verified private catalog binds potion 4551 to one sale for 28 gil, ENpc base
1009247/layout 4757046/event 262468, a 641-point route of approximately 302.30m,
and that shop's source-listed index-zero item 5890 for an eight-gil purchase.
Python validates both exact transactions, the event family, route continuity, and
endpoint range. This does not establish arbitrary quantities/items, other shops,
currency-container manipulation, concurrent transactions, or real-client shop UI.

## Curated exit crossing

The full-build metadata tool reads the same LGB exit/pop-range data used by
Sapphire. Required layers must parse. Unsupported optional planner layers are
explicitly listed in the output, matching the server's fallback to its three
required layers. The curated profile supports enabled ordinary box exits from
territory 130, not arbitrary teleports, housing, tilted volumes or general triggers.

```sh
cmake --build build --target sapphire_test_transitions sapphire_test_navbuild --config Debug
bin/sapphire_test_transitions <game/sqpack> .e2e-assets/uldah-v1/navi build-e2e/transition.json 2377056
bin/sapphire_test_navbuild bin/navi/w1f2/w1f2.obj .e2e-assets/central-v1 w1f2
```

Use `.exe` on Windows. Set `transition_catalog` to the generated JSON. The verified
approach has 41 points over 18.64m. Its start is outside the exit volume; its end
is on the navmesh inside a conservative inner volume. Box centers are projected
onto actual ground, not treated as foot height. The worker also checks its current
territory, idle state and physical position before sending the ordinary ZoneJump.
Readiness still requires received initialization/self-spawn/cleared BetweenAreas.

Create a **new private** server navigation root containing the generated
`w1t1/w1t1.nav` and `w1f2/w1f2.nav`, and set `navigation` to that root. Do not overwrite
`bin/navi`. The runner hashes those meshes; the latest live world logs confirm both
territories initialize with `NAVI`. Other maps are not thereby validated. A
manifest path/hash alone is not evidence that a server successfully loaded a mesh.
Destination observers start at the catalog pop point in a whitelisted public
territory before their first connection; the traveler crosses only through packets.

## Opening quest acceptance catalog

```sh
cmake --build build --target sapphire_test_opening_quest_catalog --config Debug
bin/sapphire_test_opening_quest_catalog <game/sqpack> <mesh-root> build-e2e/coming-to-uldah.json
```

Use `.exe` on Windows and set `opening_quest_catalog` to the absolute output path.
The generator binds quest 66130, Wymond layout 3969639, Momodi layout 3969632,
source reward metadata and a complete ~9.84m route from the canonical Ul'dah opening
start to Wymond. It also attempts the giver-to-recipient route and records
`incomplete navigation corridor` without retaining a partial route. The live case
therefore proves acceptance and persistence only; it must not send fabricated
movement or claim the 50 EXP/103 gil turn-in.

## Initial combat regression

```sh
cmake --build build --target sapphire_test_combat_catalog --config Debug
bin/sapphire_test_combat_catalog <game/sqpack> build-e2e/combat-catalog.json
```

Use `.exe` on Windows and set `combat_catalog` to the absolute output path. The
validator requires supported level-one Gladiator/Fast Blade, Pugilist/Bootshine
and Thaumaturge/Blizzard metadata (received TP or MP, exact cast/recast and source-
defined range). This is not independent client evidence.

`test_live_combat.py` places fresh characters one metre laterally from a spawn in
the unchanged staged Central Thanalan population before their first connection.
This is explicit non-overlapping player fixture setup, not a tested journey,
curated route, enemy relocation or general navigation assertion. It requires actual `NAVI` initialization in the
world log, then observes a living level-one marmot within two units and natural
TP regeneration before requesting the action. The worker refuses targets beyond
three units from its position estimate, wrong classes/kinds, dead actors and
insufficient received TP; Fast Blade is no longer artificially restricted to
level-one targets. A conservative 2.5-second request guard is extended from
the received action-start recast; this is not a general cooldown scheduler. Snapshot
`combat.starting_action_guard_remaining_ms` exposes that **local** guard, rounded up so
positive sub-millisecond waits never appear ready. `Bot.wait_fast_blade_ready()`
uses state notifications (including ordinary heartbeat replies), received TP and
estimated range; it neither sleeps a fixed recast interval nor retries actions.
It is not a server-ready acknowledgement or independent range proof.

The live test makes at most 16 requests with distinct request/result IDs and at
least 2.5 seconds between attempts, checking each received group-58/250-centisecond
start. Before every attack the observer independently confirms range and target HP.
Both clients must receive identical damage effects and matching-result HP integrity;
acknowledgements and effects alone cannot pass. Both must also observe the first
positive natural marmot retaliation against the initially full-health fighter,
including its exact committed HP result. Subsequent HP regeneration is not mistaken
for absence of damage. The final committed integrity must report zero target HP,
and both clients must observe the server's delayed target removal.

A second source-defined population binding is used for Bootshine. Because the
natural target may roam during the preceding defeat flow, the Pugilist follows at
most six received positions within 20m using ordinary movement; a witness verifies
each reached point. Both clients then require action 53's identical effect and exact
committed HP decrease, plus group-58/250-centisecond start metadata.

A third normal fixture uses source-defined Thaumaturge work index 5 and Blizzard
142 (cost type 3/value 4, 2.5s cast/recast, 25-unit range). The request requires a
living received target, at least four received MP and bounded estimated range; the
witness independently observes actual range. Both clients require the identical
18/19-damage result and exact committed HP. The caster additionally receives the
matching source integrity, action start and Blizzard's status-176 effect. Natural
MP regeneration can overlap the cast, so this does not claim an exact committed MP
cost. These are two additional starter abilities, not combo, positional-bonus,
interrupt, elemental-state or general combat coverage.

The matching local catalog supplies level-one `BaseExp` and Gladiator `WorkIndex`.
Received rewards must be exactly 50 EXP, no level/currency change, one five-item
choice from loot pool 8/9, items 5016 and 12728, and one to three item 4551. A fresh
HTTP/lobby/world login must return the identical full inventory/EXP state. Rapid
loot initially exposed duplicate process-local item IDs because asynchronous inserts
made repeated `MAX(ItemId)` queries stale. `ItemIdAllocator` now seeds once and
serializes monotonic IDs; a 64-thread native contract and the fresh-login assertion
cover the fix. This does not claim collision safety across multiple world processes.

`test_live_player_defeat.py` uses unchanged natural population layout 3749193
(base 302, level 14). If that natural target roams while TP regenerates, the
fighter follows at most six received positions within 20m and the witness verifies
each reached point. One received/range-checked Fast Blade establishes ordinary
hostility. The fighter follows a source-generated ~50.69m navmesh route; the
stationary witness verifies arrival, the received enemy position exceeds 35m from
spawn, and the enemy must naturally return within two metres of its bound spawn
while the fighter remains alive. The fighter walks the reverse route, re-engages
once and follows the source-generated ten-metre route. Both clients must then
observe the hostile enemy move at least two metres toward that endpoint before the
defeat may pass. For every
retaliation, the worker records the target's received HP immediately before and after the matching integrity
packet, so intervening natural regeneration cannot be mistaken for damage. Both
clients require the identical effect sequence and exact committed decrease through
zero HP. The worker then permits only received-dead state in Central Thanalan with
canonical homepoint 9 to send `REVIVE/Return`; it does not expose arbitrary revive
or teleport arguments. The fighter must transition to the generated homepoint-9
pop range in Ul'dah with full HP, disappear from the old observer, appear alive to a
pre-positioned destination observer, and reload the same position/full HP after
logout and world restart. The worker decodes bounded ordinary HUD-parameter updates;
after the retreat both clients must receive the same enemy HP restoration to
237/237 before re-engagement. It does not infer healing from position or server
logs. This proves one position-and-health leash reset, but does not claim automatic
aggro, raises, death penalties, general pursuit/leash policy or general combat.

Generate the private binding from matching game data:

```sh
cmake --build build --target sapphire_test_respawn_catalog --config Debug
bin/sapphire_test_respawn_catalog <game/sqpack> build-e2e/respawn.json
```

Use `.exe` on Windows and set `respawn_catalog` to the absolute output path. The
verified catalog resolves Gladiator homepoint 9 through Aetheryte metadata to the
single source pop range 3693863 in territory 130. It contains no invented return
position and is not a general respawn or teleport catalog.

Generate the pursuit binding from the staged unchanged population and matching
private Central Thanalan mesh:

```sh
cmake --build build --target sapphire_test_pursuit_catalog --config Debug
bin/sapphire_test_pursuit_catalog <mesh-root> data/bnpcs/w1f2/w1f2.json build-e2e/pursuit.json
```

The validator fixes natural layout 3749193/base 302/level 14, requires complete
continuous ten-metre pursuit and 45..70m leash routes starting beside it, and
preflight requires their mesh to match the staged server mesh. This proves one
observed pursuit/retreat/position-and-health reset response, not general pathfinding
or aggro/leash policy.

The artifact manifest hashes the action catalog and staged player-action/population
files. Bounded event journals include decoded effects, HP integrity and action-start
recast metadata. `combat-defeat-rewards.json` records every verified pre/post HP,
natural TP, guard/timing, retaliation, death/removal, received rewards and the exact
fresh-login snapshot, supplementing rather than replacing raw journals. Earlier
failed overlap and duplicate-ID runs remain retained and are not counted as passing.
This slice does **not** prove damage-formula correctness, combos, general cooldown
scheduling, general aggro/leash policy, arbitrary abilities, production loot-table selection
or real-client combat presentation.

## Bounded exploration, soak and replay

These modes use the same isolated environment and observed-state API. A validated
local `quest_catalog` is required even though policies do not complete quests:
movement stays on the first nine points of that known route.

```sh
python -m tests.e2e.run_workload --profile .e2e-local.json \
  --mode explore --seed 42 --bots 2 --steps 12 --duration 120
python -m tests.e2e.run_workload --profile .e2e-local.json \
  --mode soak --seed 7 --bots 4 --steps 120 --duration 300
python -m tests.e2e.run_workload --profile .e2e-local.json \
  --mode replay --plan .e2e-artifacts/<run>/plan.json
```

- Exploration chooses seeded, allowlisted walk/Say/heartbeat/reconnect actions.
  Reconnect observes despawn, performs new HTTP/lobby login, and checks identity
  and persisted position. Unknown actions/parameters are rejected.
- Soak ramps 2..32 bots and executes distinct actors concurrently in bounded
  rounds. Supported actions are walk/Say/heartbeat; reconnect is serial-only.
- Plans allow at most 1000 total actions and a 1..3600s **action** time budget.
  Setup and teardown have their own bounds and are excluded from that budget.
  Exhausting the budget is a failure, not a silently successful short run.
- Every round checks readiness, non-GM status, territory, no unexpected scene,
  and server liveness. Movement and Say assertions come from another bot.
- New plans are version 2. Replay preserves semantic decisions and route identity,
  not packet timing, credentials or ephemeral actor IDs. Version-1 plans still
  replay unpaced; pacing requires v2 so older executors cannot silently ignore it.
  Recorded duration/ramp/pacing/minimum-span limits are reused unless explicitly
  overridden. Unknown fields and no-op walks are rejected. Soak plans start with
  one walk and one Say per bot, then use seeded choices. Scheduling is not
  deterministic.

### Failed-plan minimization

A failed unpaced exploration or soak plan can be reduced through fresh isolated
replays:

```sh
python -m tests.e2e.run_minimize --profile .e2e-local.json \
  --plan .e2e-artifacts/<failed-run>/plan.json \
  --output .e2e-artifacts/minimized-plan.json --max-attempts 32
```

The original plan is rerun as the baseline; historical failure artifacts alone
are not trusted. Each candidate provisions and cleans a separate environment.
Only a workflow action failure with the same failing semantic action and exact
normalized assertion text is accepted. Normalization removes only the ephemeral
worker state dump after `; state=`. Passing candidates, different failures,
setup/cleanup/artifact failures, missing outcomes and unverified runtime removal
are rejected. Exploration removes ordered actions; soak removes complete actor
rounds. Every candidate is revalidated, so no-op walks, broken actor ordering or
invalid limits are never executed or accepted.

`--max-attempts` (1..100) bounds actual isolated executions, including the
baseline. The report records every candidate hash, retained original indexes,
accepted signature, artifact directory, whether the budget was exhausted and
whether no single remaining valid action/round can be removed. Output overwrite
is refused. The minimized plan remains a semantic reproduction aid—not packet or
scheduling determinism, proof of root cause, or a passing test. Paced/minimum-span
plans are deliberately rejected because deleting rounds would weaken their
sustained-work claim.

### Sustained, paced workloads

A timeout is an upper bound, not proof of a long run. Use an explicit pacing floor
and a required **first-to-last successful action span**:

```sh
python -m tests.e2e.run_workload --profile .e2e-local.json --mode soak \
  --seed 2026 --bots 8 --steps 488 --round-interval 30 \
  --min-active-seconds 1800 --duration 2100
```

This schedules 61 full-population rounds across at least 30 minutes. All bots
perform genuine supported actions in every round; setup, ramp and teardown do
not count, and no sleep is appended after the final action to pad the result.
Pacing is deliberate workload think-time, not a substitute for received-state
assertions. Every bot must have walk/Say coverage. Slow rounds shift subsequent
starts rather than causing catch-up bursts. The action budget remains capped at
1000 and the overall workflow budget at 3600 seconds.

During paced idle periods, two-second checkpoints verify process liveness, every
bot's identity/readiness/non-GM/territory/scene state, and ring-observer visibility.
Each bot's zone and chat heartbeat counters must advance within 15 seconds;
resets, stale channels and monitoring gaps fail explicitly. `checkpoints.json`
and `rounds.json` retain this evidence, including on failure. These monitoring
limits are part of the v2 executor profile, not user-tunable ways to hide stalls.
A passed paced workload still covers only walk/Say/keepalive traffic in one area,
not broad gameplay or a server-capacity benchmark.

Verified locally: two-bot exploration/replay, four-bot/120-action soak, and a
sixteen-bot/960-action soak plus fresh replay of the same plan (about five minutes
each including setup/teardown). A one-second-budget run fails with a retained
diagnostic plan and cleans up. These are bounded smoke results, **not**
large-population capacity or long-duration stability evidence.

Separately, the paced command above passed at clean revision `063ea281b`:
488 successful actions, 61 full eight-bot rounds, **1805.281s of activity**, and
966 liveness checkpoints (`sapphire-e2e-q0klh2yf`). Each bot participated for at
least 1803.078s; both received keepalive channels advanced throughout. This is
30-minute low-rate town-workflow coverage, not an overnight or capacity claim.
World first/last five-minute median RSS originally rose from 370,196,480 to
400,510,976 bytes. The subsequent investigation found unowned BLOB streams in
normal autosaves and added operation-scoped ownership (`0a73d4f8c`).

The **full, byte-identical 30-minute plan** then replayed successfully at clean
revision `fe411dbb9` (`sapphire-e2e-c1p7inqh`): 488 actions, 1805.218s of activity,
969 liveness checkpoints and verified cleanup. World first/last five-minute
median RSS was 370,262,016 / 370,253,824 bytes; private commit was
356,487,168 / 356,458,496. The earlier increasing trend did not recur. An
empty-server control, a populated original-binary control and a native allocation
regression test support the ownership diagnosis. This finite matched-plan
comparison is not proof of leak-freedom for every path or a capacity benchmark.

Resource samples cover API/lobby/world/DB plus worker/runner;
CPU deltas and peak RSS are reported separately. On Windows, samples additionally
record `private_commit_bytes` (and its peak), distinct from resident working set.
This field is omitted elsewhere, not substituted with Linux USS or VMS.
Action-duration percentiles
include walking and event waits, not pure network RTT or server tick latency.
State waits use bot-specific event versions; unrelated responses or another bot's
events do not trigger repeated snapshot requests. This reduces load-generator
work without weakening the independent observer assertions.

### Empty-server resource control

```sh
python -m tests.e2e.run_idle_control --profile .e2e-local.json --duration 600
```

This creates the same isolated server/database environment but no worker,
character fixture or successful login. Its 10..900-second observation window
checks process liveness and samples resources. It writes `control.json` and
`control-resources.jsonl`, separate from workload results, and reports `observed`
only when the window, measurements and cleanup succeed. Unavailable process
samples or sampling gaps exceeding five seconds are failures, not zero memory
or evidence of stability. Cleanup precedes artifact writes, so a
write failure does not strand servers. This control is **not gameplay coverage**;
compare its trace with a populated workload, matching actual staged binaries and
inputs. RSS or private-commit growth alone cannot identify allocation ownership
or prove a leak. Normal allocator retention and warm-up need to be distinguished.

## Artifacts and CI

Each live run writes `.e2e-artifacts/sapphire-e2e-*/`:

- `manifest.json`: build/fixture/runtime identity.
- Redacted API/lobby/world/database setup logs.
- Per-test `events.jsonl`: the last 2048 received semantic/packet-summary events.
- Per-test `actions.jsonl`: the last 2048 semantic actions, omitting authentication
  arguments; safe movement/interaction/scene arguments are retained.
- Per-test `worker-stderr.log`: bounded worker diagnostics.

Workload runs additionally save `plan.json`, per-action `outcomes.json`,
`rounds.json`, liveness `checkpoints.json`, `resources.jsonl` (one-second process samples), and `result.json` with status,
failure stage, action durations and resource summaries. An unavailable process is
explicitly marked; the final sample can observe the already-closed worker.

Workload teardown precedes final report aggregation and diagnostic writes, even
when sampler shutdown raises or is interrupted. `runtime_removed=true` requires
an actual absence check of the whole private root after cleanup. Sampler,
cleanup, summary and artifact failures produce a failed result/nonzero CLI exit;
secondary errors do not overwrite the original failure stage. Final artifacts
use temporary files and atomic replacement, so a failed write cannot leave a
partially published canonical `result.json` claiming success. Other diagnostic
writes are still attempted independently. If even `result.json` cannot be
published, inspect the failed CLI result; missing output is never success.
This does not establish recovery from process hard kills, unresponsive OS calls,
or every failure inside an individual process's teardown.

JUnit output goes to the path selected with `--junitxml`. Never upload the private
runtime, raw database, game assets, local profiles or unredacted configs.

`.github/workflows/test-client.yml` builds and tests the asset-independent client
on Linux and Windows. It does **not** provision game data, run gameplay tests, or
claim real-client compatibility. The opt-in `gameplay-e2e.yml` workflow and
`python -m tests.e2e.run_ci` entry point implement a separate seven-case gameplay
gate, with strict preflight, no skips, staged-input identity and cleanup checks.
Only an allowlisted summary is publishable; raw pytest/JUnit and gameplay logs
stay private. See [CI.md](CI.md) for runner access restrictions, approval settings,
VM disposal requirements and local rehearsal commands. Local rebuilt-binary
rehearsal passes; a protected GitHub runner execution remains unverified.

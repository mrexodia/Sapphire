# End-to-end bot scenarios

Bots that play the game against a running development server: they log in
through the lobby like a real client, walk, talk, trade, fight and zone, and
every check is made on what the server sent back. The runner is one binary next
to the server, `bin/sapphire_e2e`, and a scenario is a short C++ class in
`scenarios/<group>/<Name>.cpp`.

```
bin/sapphire_e2e --list
bin/sapphire_e2e common.SayAndWalk --hold     # watch the bots from your own character
bin/sapphire_e2e --filter combat.             # one group
bin/sapphire_e2e                              # everything
ctest -L e2e                                  # the same, one ctest entry per scenario
```

## Setup

Run the stack as usual (api, lobby, world, MariaDB). The runner reads the
server's own config next to it: `global.ini` for the API address (`RestHost`,
`RestPort`), the secret and `DataPath`; `world.ini` for `MeshPath`. Nothing else
to configure. From another directory pass `--server-dir <path to bin>`.

Bots are throwaway `bot_` accounts created through `/sapphire-api/dev/*`,
guarded by the server secret. The runner purges offline bot accounts before and
after a run; `--keep-bots` skips that, which also protects a `bot_` account you
use yourself in game. Logged-in characters are never purged.

The character-creation scenario plays the Ul'dah opening and needs
`SkipOpening = false` in world.ini. Combat scenarios need the Central Thanalan
navmesh (`w1f2`) loaded by the world; the runner reads the same meshes.

## Writing a scenario

```cpp
#include "../../harness/Context.h"
#include "../../harness/Scenario.h"

using namespace Sapphire::E2E;

class SayHello : public Scenario
{
  void run( Context& ctx ) override
  {
    auto& talker = ctx.spawnCharacter( "talker" );
    auto& listener = ctx.spawnCharacter( "listener" );
    const auto actor = Bot::entity( talker.snapshot() );
    listener.waitState( [ & ]( const Json& s ) { return Bot::actor( s, actor ) != nullptr; }, "listener sees the talker" );
    talker.say( "hello" );
    listener.expectSay( actor, "hello" );
  }
};

EXPOSE_SCENARIO( SayHello );
```

Drop the file under `scenarios/<group>/`, rebuild `sapphire_e2e`, and it is
`group.SayHello` in `--list` and ctest. The pieces:

- `Context` gives the server (`server()`: create fixtures, log in again), the
  game data (`data()`), the command-line options and `log()`. `spawnCharacter`
  creates a fresh non-GM character past the opening and logs the bot in;
  `spawn` gives a bot you log in yourself (lobby creation, fresh logins).
- `Bot` is the character. Its calls send a request and wait for the received
  state to show the outcome; sending is never success. `waitState( predicate,
  description, timeout )` is the general form, `snapshot()` the current state,
  and the readers (`Bot::entity`, `position`, `actor`, `scene`, `gil`,
  `inventory`) pick fields out of it.
- `expect( condition, message )` fails the scenario. Anything that throws
  (protocol error, timeout) fails it too; the runner prints the bots' last
  journal events and writes full journals under `bin/log/e2e/<run>/<scenario>/`.
- `GameData` and `Content` resolve NPCs, shops, exits, ranges and walking
  routes from the game data and the navmesh at run time. There are no catalog
  files to generate.

Design rules that kept the scenarios honest: bots are external clients and
never GM; a mutation whose outcome is uncertain is never retried; persistence is
checked by logging out and back in; enemies respawn and heal on their own, so
scenarios wait for a healthy one instead of resetting the world.

## Layout

```
client/     the headless FFXIV 3.3 client (lobby, zone and chat connections,
            received state, request builders) and the synchronous Bot facade
harness/    Scenario registry, Config, Server (fixture API), GameData, Content,
            Context, navmesh routes
scenarios/  common, party, shop, quest, zoning, creation, combat
runner/     main.cpp
```

`sapphire_e2e_protocol` (the request builders and state trackers) has unit
tests under `tests/protocol/` that need no server or game data.

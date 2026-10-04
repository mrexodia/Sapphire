// The living Return action: a character standing in Central Thanalan casts
// Return (action 6) and lands at its Ul'dah homepoint. An observer at the
// source receives the cast and the departure exactly once, another at the
// destination receives the arrival, and the destination survives a fresh
// login. The action's timing comes from the Action sheet, not from the client.
#include "../../harness/Content.h"
#include "../../harness/Context.h"
#include "../../harness/Scenario.h"
#include "../../harness/Transitions.h"
#include <cmath>

using namespace Sapphire::E2E;

class LivingReturn : public Scenario
{
  struct ActionMetadata
  {
    uint32_t action = 0, castMs = 0, recastMs = 0, recastGroup = 0;
    int classJob = 0, level = 0;
    bool targetEnemy = false;
  };

  static ActionMetadata returnAction( GameData& data )
  {
    auto row = data.row< Excel::Action >( 6 );
    if( !row )
      throw Failure( "Action 6 (Return) is missing from the game data" );
    const auto& a = row->data();
    return { 6, a.CastTime * 100u, a.RecastTime * 100u, a.RecastGroup, a.UseClassJob, a.Level, a.SelectEnemy != 0 };
  }

  static double dist( const Point& a, const Point& b )
  {
    return std::hypot( a[ 0 ] - b[ 0 ], a[ 1 ] - b[ 1 ], a[ 2 ] - b[ 2 ] );
  }

  static bool standsAt( const Json& state, uint32_t entity, const Point& position )
  {
    const auto* row = Bot::actor( state, entity );
    return row && dist( row->at( "position" ).get< Point >(), position ) < 0.15;
  }

  static size_t occurrences( const Json& rows, const Json& row )
  {
    size_t n = 0;
    for( const auto& candidate : rows )
      if( candidate == row )
        ++n;
    return n;
  }

  void run( Context& ctx ) override
  {
    auto& data = ctx.data();
    const auto crossing = uldahCentralThanalanCrossing( data );
    const auto& start = crossing.outbound.destination;   // the pop range just inside Central Thanalan
    const auto home = homepoint( data, 9 );
    const auto metadata = returnAction( data );
    expect( metadata.action == 6 && metadata.classJob == 0 && metadata.level == 0, "Return is a level-zero action of no class" );
    expect( metadata.castMs == 5000 && metadata.recastMs == 900000, "Return casts for 5 s and recasts after 15 min" );
    expect( metadata.recastGroup == 57 && !metadata.targetEnemy, "Return uses recast group 57 and targets no enemy" );

    CharacterOptions atStart;
    atStart.position = start.position;
    atStart.territory = start.territory;
    CharacterOptions atHome;
    atHome.position = home.popRange.position;
    atHome.territory = home.territory;
    auto& player = ctx.spawnCharacter( "living-returner", atStart );
    auto& source = ctx.spawnCharacter( "living-return-source", atStart );
    auto& destination = ctx.spawnCharacter( "living-return-destination", atHome );
    const auto state = player.snapshot();
    const auto entity = Bot::entity( state );
    expect( state.at( "territory" ) == CentralThanalan::Territory && state.at( "homepoint" ) == 9 && home.aetheryte == 9,
            "the returner starts in Central Thanalan bound to the Ul'dah homepoint" );
    const auto destinationState = destination.snapshot();
    source.waitState( [ & ]( const Json& s ) { return standsAt( s, entity, start.position ); }, "living Return source independently observed" );
    expect( Bot::actor( destinationState, entity ) == nullptr, "the destination observer must not see the returner before the cast" );

    const auto result = player.castReturn();
    expect( result.request > 0 && result.state.at( "territory" ) == home.territory, "the returner lands in the homepoint's territory" );
    expect( dist( Bot::position( result.state ), home.popRange.position ) < 0.15, "the returner lands on the homepoint pop range" );
    expect( result.cast == Json{ { "source", entity }, { "action", 6 }, { "action_key", 6 }, { "kind", 1 },
                                 { "cast_seconds", metadata.castMs / 1000.0 }, { "target", entity } },
            "exact received Return cast, got " + result.cast.dump() );
    expect( result.start == Json{ { "source", entity }, { "action", 6 }, { "group", metadata.recastGroup },
                                  { "recast_centiseconds", metadata.recastMs / 10 } },
            "exact received Return recast start, got " + result.start.dump() );
    const auto sourceAfter = source.waitState( [ & ]( const Json& s ) {
      return occurrences( s.at( "combat" ).at( "casts" ), result.cast ) > 0 && Bot::actor( s, entity ) == nullptr;
    }, "independently received living Return cast and source departure" );
    expect( occurrences( sourceAfter.at( "combat" ).at( "casts" ), result.cast ) == 1, "the source observer received the cast exactly once" );
    const auto arrival = destination.waitState( [ & ]( const Json& s ) { return standsAt( s, entity, home.popRange.position ); },
                                                "living Return destination independently observed" );
    ctx.log( "destination witness saw the returner at " + arrival.at( "actors" ).at( std::to_string( entity ) ).at( "position" ).dump() );

    const auto fixture = ctx.fixture( player );
    player.logout();
    destination.waitState( [ & ]( const Json& s ) { return Bot::actor( s, entity ) == nullptr; }, "living Return destination cleanup" );
    source.logout();
    destination.logout();
    auto& reloaded = ctx.spawn( "living-return-reloaded" );
    const auto persisted = reloaded.loginViaLobby( ctx.server().relogin( fixture ), fixture.name );
    expect( persisted.at( "territory" ) == home.territory && dist( Bot::position( persisted ), home.popRange.position ) < 0.15,
            "the Return destination survives a fresh login" );
    reloaded.logout();
  }
};

EXPOSE_SCENARIO( LivingReturn );

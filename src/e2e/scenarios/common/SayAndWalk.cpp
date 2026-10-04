// Two bots: one says a line and walks a short segment, the other confirms it
// saw both. Watchable: run with --hold and stand near the Ul'dah bot spawn.
#include "../../harness/Context.h"
#include "../../harness/Scenario.h"
#include <cmath>

using namespace Sapphire::E2E;

class SayAndWalk : public Scenario
{
  void run( Context& ctx ) override
  {
    auto& mover = ctx.spawnCharacter( "mover" );
    auto& observer = ctx.spawnCharacter( "observer" );
    const auto moverState = mover.snapshot();
    const auto actor = Bot::entity( moverState );
    observer.waitState( [ & ]( const Json& s ) { return Bot::actor( s, actor ) != nullptr; }, "observer sees the mover" );

    const std::string message = "Hello from the Sapphire bots";
    mover.say( message );
    observer.expectSay( actor, message );
    ctx.log( "observer received the Say" );

    auto destination = Bot::position( moverState );
    destination[ 0 ] += 3.0f;
    mover.walkTo( destination );
    observer.waitState( [ & ]( const Json& s ) {
      const auto* row = Bot::actor( s, actor );
      if( !row ) return false;
      const auto p = row->at( "position" ).get< Point >();
      return std::hypot( p[ 0 ] - destination[ 0 ], p[ 1 ] - destination[ 1 ], p[ 2 ] - destination[ 2 ] ) < 0.1;
    }, "observer sees the mover arrive" );
    ctx.log( "observer saw the mover walk" );
    mover.walkTo( Bot::position( moverState ) );
    ctx.log( "mover walked back" );
  }
};

EXPOSE_SCENARIO( SayAndWalk );

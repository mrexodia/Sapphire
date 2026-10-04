// Movement is received by an observer, the mover's despawn too, and the final
// position survives a fresh login.
#include "../../harness/Context.h"
#include "../../harness/Scenario.h"
#include <cmath>

using namespace Sapphire::E2E;

class MovementPersistence : public Scenario
{
  void run( Context& ctx ) override
  {
    auto& mover = ctx.spawnCharacter( "mover" );
    auto& observer = ctx.spawnCharacter( "observer" );
    const auto moverState = mover.snapshot();
    const auto actor = Bot::entity( moverState );
    observer.waitState( [ & ]( const Json& s ) { return Bot::actor( s, actor ) != nullptr; }, "mover spawn" );
    mover.say( "Sapphire E2E observer check" );
    observer.expectSay( actor, "Sapphire E2E observer check" );

    // A deliberately small starter-area segment, not a claim of general pathfinding.
    auto destination = Bot::position( moverState );
    destination[ 0 ] += 1.0f;
    mover.walkTo( destination );
    observer.waitState( [ & ]( const Json& s ) {
      const auto* row = Bot::actor( s, actor );
      if( !row ) return false;
      const auto p = row->at( "position" ).get< Point >();
      return std::hypot( p[ 0 ] - destination[ 0 ], p[ 1 ] - destination[ 1 ], p[ 2 ] - destination[ 2 ] ) < 0.1;
    }, "movement received by observer" );

    const auto fixture = ctx.fixture( mover );
    mover.logout();
    observer.waitState( [ & ]( const Json& s ) { return Bot::actor( s, actor ) == nullptr; }, "mover despawn", 30 );
    observer.logout();

    auto& reconnected = ctx.spawn( "reconnected" );
    const auto state = reconnected.loginViaLobby( ctx.server().relogin( fixture ), fixture.name );
    const auto p = Bot::position( state );
    expect( std::hypot( p[ 0 ] - destination[ 0 ], p[ 1 ] - destination[ 1 ], p[ 2 ] - destination[ 2 ] ) < 0.1,
            "the position after a fresh login must be where the mover stopped" );
    reconnected.logout();
  }
};

EXPOSE_SCENARIO( MovementPersistence );

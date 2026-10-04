// Three bots form a party, chat in it and hand over leadership. Watchable.
#include "../../harness/Context.h"
#include "../../harness/Scenario.h"

using namespace Sapphire::E2E;

class Party : public Scenario
{
  void run( Context& ctx ) override
  {
    auto& leader = ctx.spawnCharacter( "leader" );
    auto& member = ctx.spawnCharacter( "member" );
    auto& third = ctx.spawnCharacter( "third" );
    const auto leaderState = leader.snapshot();
    const auto memberState = member.snapshot();
    const auto thirdState = third.snapshot();
    const auto memberName = ctx.fixture( member ).name;
    const auto thirdName = ctx.fixture( third ).name;
    for( const auto* state : { &memberState, &thirdState } )
    {
      const auto actor = Bot::entity( *state );
      leader.waitState( [ & ]( const Json& s ) { return Bot::actor( s, actor ) != nullptr; }, "leader sees the other bot" );
    }

    leader.inviteParty( Bot::entity( memberState ), memberName );
    member.acceptParty( 2 );
    ctx.log( "member joined" );
    leader.inviteParty( Bot::entity( thirdState ), thirdName );
    third.acceptParty( 3 );
    ctx.log( "third joined" );

    leader.partyChat( "Party formed by the Sapphire bots" );
    member.expectPartyChat( leaderState, "Party formed by the Sapphire bots" );
    third.expectPartyChat( leaderState, "Party formed by the Sapphire bots" );
    ctx.log( "party chat delivered to both members" );

    leader.changePartyLeader( Bot::entity( memberState ), memberName );
    ctx.log( "leadership handed to the member" );
  }
};

EXPOSE_SCENARIO( Party );

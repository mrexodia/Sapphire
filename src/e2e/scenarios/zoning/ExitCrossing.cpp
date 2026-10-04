// A normal physical exit crossing from Ul'dah into Central Thanalan with
// independent observers on both sides; then party chat and Tells across the
// zone boundary, the two map discoveries (on arrival and after a walk into the
// second discovery box), the walk back and the reverse crossing. Territory,
// position, discoveries and rewards must all survive a fresh login.
#include "../../harness/Content.h"
#include "../../harness/Context.h"
#include "../../harness/Scenario.h"
#include "../../harness/Transitions.h"
#include <cmath>
#include <map>

using namespace Sapphire::E2E;

class ExitCrossing : public Scenario
{
  static double dist( const Point& a, const Point& b )
  {
    return std::hypot( a[ 0 ] - b[ 0 ], a[ 1 ] - b[ 1 ], a[ 2 ] - b[ 2 ] );
  }

  static bool standsAt( const Json& state, uint32_t entity, const Point& position )
  {
    const auto* row = Bot::actor( state, entity );
    return row && dist( row->at( "position" ).get< Point >(), position ) < 0.15;
  }

  static Point witnessed( const Json& state, uint32_t entity )
  {
    return state.at( "actors" ).at( std::to_string( entity ) ).at( "position" ).get< Point >();
  }

  static unsigned count( const Json& state ) { return state.at( "party" ).at( "count" ).get< unsigned >(); }

  static std::map< uint32_t, int > territories( const Json& state )
  {
    std::map< uint32_t, int > rows;
    for( const auto& row : state.at( "party" ).at( "members" ) )
      rows[ row.at( "entity_id" ).get< uint32_t >() ] = row.at( "territory" ).get< int >();
    return rows;
  }

  static bool sameChannel( const Sapphire::Testing::PartyChannel& sent, const Json& received )
  {
    return received.at( "party_id" ) == sent.partyId && received.at( "channel" ) == sent.chatChannel;
  }

  static bool idleArrival( const Json& state )
  {
    return state.at( "scene" ).is_null() && state.at( "event_id" ).is_null() && state.at( "gm_rank" ) == 0;
  }

  static void expectLiveChannels( Bot& bot, const Json& since, const std::string& description )
  {
    const auto heartbeats = since.at( "heartbeats" );
    bot.waitState( [ & ]( const Json& s ) {
      return s.at( "heartbeats" ).at( "zone" ) > heartbeats.at( "zone" ) && s.at( "heartbeats" ).at( "chat" ) > heartbeats.at( "chat" );
    }, description );
  }

  void run( Context& ctx ) override
  {
    auto& data = ctx.data();
    const auto catalog = uldahCentralThanalanCrossing( data );
    const auto& destination = catalog.outbound.destination;
    const auto& returnDestination = catalog.back.destination;
    ctx.log( "exit " + std::to_string( catalog.outbound.exit.id ) + " -> pop " + std::to_string( destination.id ) + " in territory " +
             std::to_string( destination.territory ) + "; approach " + std::to_string( catalog.routeLength ).substr( 0, 5 ) +
             " m, discovery walk " + std::to_string( catalog.second.routeLength ).substr( 0, 5 ) + " m, return walk " +
             std::to_string( catalog.returnRouteLength ).substr( 0, 5 ) + " m" );

    CharacterOptions atRoute;
    atRoute.position = catalog.route.front();
    CharacterOptions atDestination;
    atDestination.position = destination.position;
    atDestination.territory = destination.territory;
    CharacterOptions atSecondBox;
    atSecondBox.position = catalog.second.route.back();
    atSecondBox.territory = destination.territory;
    auto& player = ctx.spawnCharacter( "traveler", atRoute );
    auto& source = ctx.spawnCharacter( "source-observer", atRoute );
    auto& target = ctx.spawnCharacter( "target-observer", atDestination );
    auto& discoveryObserver = ctx.spawnCharacter( "discovery-observer", atSecondBox );
    auto state = player.snapshot();
    expect( state.at( "territory" ) == Uldah::Territory && state.at( "scene" ).is_null(), "the traveler starts idle in Ul'dah" );
    const auto actor = Bot::entity( state );
    const auto fixture = ctx.fixture( player );
    const auto sourceFixture = ctx.fixture( source );
    const auto sourceState = source.snapshot();
    const auto sourceId = Bot::entity( sourceState );
    const auto targetState = target.snapshot();
    expect( targetState.at( "territory" ) == destination.territory && targetState.at( "scene" ).is_null(), "the target observer stands idle in Central Thanalan" );
    expect( Bot::actor( targetState, actor ) == nullptr, "the target observer must not see the traveler before the crossing" );
    source.waitState( [ & ]( const Json& s ) { return Bot::actor( s, actor ) != nullptr; }, "traveler visible in source territory" );
    player.waitState( [ & ]( const Json& s ) {
      const auto* row = Bot::actor( s, sourceId );
      return row && row->at( "name" ) == sourceFixture.name;
    }, "source observer visible by exact name" );
    player.inviteParty( sourceId, sourceFixture.name );
    source.acceptParty();
    player.waitState( [ & ]( const Json& s ) { return count( s ) == 2; }, "traveler received source party membership" );
    const auto before = player.rewardSnapshot( 1 );  // the Gladiator fixture's observed class work index

    // The source observer stays outside the trigger; it must not ignore its own
    // automatic-exit obligation merely to watch the traveler disappear.
    player.walkRoute( catalog.route, 2.0f, 60 );
    source.waitState( [ & ]( const Json& s ) { return standsAt( s, actor, catalog.route.back() ); }, "traveler physically reached exit" );
    state = player.crossExit( catalog.outbound.exit, destination.territory );
    expect( idleArrival( state ), "the traveler arrives idle and non-GM" );
    expect( state.at( "central_thanalan_discovery" ) == false, "no discovery before the request" );
    expect( dist( Bot::position( state ), destination.position ) < 0.15, "the traveler arrives on the destination pop range" );
    source.waitState( [ & ]( const Json& s ) { return Bot::actor( s, actor ) == nullptr; }, "traveler left source territory" );
    const auto targetArrival = target.waitState( [ & ]( const Json& s ) { return standsAt( s, actor, destination.position ); },
                                                 "traveler arrived in destination territory" );
    expect( source.snapshot().at( "territory" ) == Uldah::Territory, "the source observer stays in Ul'dah" );
    ctx.log( "crossed into Central Thanalan; both observers agree" );

    // UpdateParty redacts detailed fields for a remote-zone member (territory 0)
    // while retaining exact entity/name identity. Each side must receive its own
    // current territory and the other's explicitly redacted remote detail.
    const std::map< uint32_t, int > playerExpected{ { actor, CentralThanalan::Territory }, { sourceId, 0 } };
    const std::map< uint32_t, int > sourceExpected{ { actor, 0 }, { sourceId, Uldah::Territory } };
    auto rosterIs = []( const std::map< uint32_t, int >& expected ) {
      return [ expected ]( const Json& s ) { return count( s ) == 2 && territories( s ) == expected; };
    };
    const auto playerParty = player.waitState( rosterIs( playerExpected ), "cross-territory party roster update" );
    const auto sourceParty = source.waitState( rosterIs( sourceExpected ), "cross-territory party roster update" );
    expect( playerParty.at( "party" ).at( "leader_index" ) == 0 && sourceParty.at( "party" ).at( "leader_index" ) == 0, "the traveler stays leader" );
    expect( playerParty.at( "party" ).at( "chat_channel" ) == sourceParty.at( "party" ).at( "chat_channel" ), "both sides keep the chat channel" );
    auto sent = source.partyChat( "source to remote traveler party message" );
    expect( sameChannel( sent, player.expectPartyChat( sourceState, "source to remote traveler party message" ) ), "party chat crosses the zone boundary" );
    sent = player.partyChat( "traveler to remote source party message" );
    expect( sameChannel( sent, source.expectPartyChat( state, "traveler to remote source party message" ) ), "party chat crosses the zone boundary" );
    source.tell( actor, fixture.name, "source to remote traveler exact tell" );
    const auto sourceToTraveler = player.expectTell( sourceState, "source to remote traveler exact tell" );
    expect( sourceToTraveler.at( "party_id" ) == playerParty.at( "party" ).at( "id" ), "a party Tell across zones carries the party id" );
    player.tell( sourceId, sourceFixture.name, "traveler to remote source exact tell" );
    const auto travelerToSource = source.expectTell( state, "traveler to remote source exact tell" );
    expect( travelerToSource.at( "party_id" ) == sourceParty.at( "party" ).at( "id" ), "a party Tell across zones carries the party id" );
    source.partyChat( "source liveness before cross-zone nonparty tell" );
    player.expectPartyChat( sourceState, "source liveness before cross-zone nonparty tell" );
    source.leaveParty();
    for( auto* bot : { &source, &player } )
      bot->waitState( [ & ]( const Json& s ) { return count( s ) == 0 && s.at( "party" ).at( "id" ) == 0; }, "cross-zone party disband before nonparty Tell" );
    player.tellRemote( sourceId, sourceFixture.name, "traveler to cross-zone nonparty source" );
    expect( source.expectTell( state, "traveler to cross-zone nonparty source" ).at( "party_id" ) == 0, "a Tell outside a party carries no party id" );
    source.tellRemote( actor, fixture.name, "source to cross-zone nonparty traveler" );
    expect( player.expectTell( sourceState, "source to cross-zone nonparty traveler" ).at( "party_id" ) == 0, "a Tell outside a party carries no party id" );
    ctx.log( "cross-zone party chat and Tells delivered" );

    player.expectRewards( before, 1 );
    const auto firstReply = player.discoverCentralThanalan( catalog.arrival.range.id, catalog.arrival.partId, witnessed( targetArrival, actor ),
                                                            catalog.arrival.mapId ).at( "discovery_reply" );
    auto afterDiscovery = before;
    afterDiscovery.exp += catalog.arrival.levelOneExp;
    player.expectRewards( afterDiscovery, 1 );
    player.walkRoute( catalog.second.route, 2.0f, 330 );
    const auto secondArrival = discoveryObserver.waitState( [ & ]( const Json& s ) { return standsAt( s, actor, catalog.second.route.back() ); },
                                                            "traveler independently observed in second discovery box" );
    const auto secondReply = player.discoverCentralThanalan( catalog.second.range.id, catalog.second.partId, witnessed( secondArrival, actor ),
                                                             catalog.second.mapId ).at( "discovery_reply" );
    afterDiscovery.exp += catalog.second.levelOneExp;
    state = player.expectRewards( afterDiscovery, 1 );
    ctx.log( "discoveries " + firstReply.dump() + " and " + secondReply.dump() + " rewarded" );
    player.say( "E2E destination chat after zoning" );
    discoveryObserver.expectSay( Bot::entity( state ), "E2E destination chat after zoning" );
    expectLiveChannels( player, state, "both channels remain live after zoning" );
    expect( count( source.snapshot() ) == 0 && count( player.snapshot() ) == 0, "nobody is grouped any more" );

    player.walkRoute( catalog.returnRoute, 2.0f, 330 );
    const auto reverseSource = target.waitState( [ & ]( const Json& s ) { return standsAt( s, actor, catalog.returnRoute.back() ); },
                                                 "traveler independently observed reaching reverse exit", 30 );
    const auto returned = player.crossExit( catalog.back.exit, returnDestination.territory );
    expect( returned.at( "territory" ) == returnDestination.territory && returnDestination.territory == Uldah::Territory, "the reverse exit leads back to Ul'dah" );
    expect( idleArrival( returned ), "the traveler returns idle and non-GM" );
    expect( dist( Bot::position( returned ), returnDestination.position ) < 0.15, "the traveler returns onto the reverse destination pop range" );
    target.waitState( [ & ]( const Json& s ) { return Bot::actor( s, actor ) == nullptr; }, "traveler left reverse source territory", 30 );
    const auto returnArrival = source.waitState( [ & ]( const Json& s ) { return standsAt( s, actor, returnDestination.position ); },
                                                 "traveler independently observed returning to Ul'dah", 30 );
    ctx.log( "returned to Ul'dah; witnessed leaving at " + Json( witnessed( reverseSource, actor ) ).dump() + ", arriving at " +
             Json( witnessed( returnArrival, actor ) ).dump() );
    player.expectRewards( afterDiscovery, 1 );
    player.say( "E2E Ul'dah chat after reverse zoning" );
    source.expectSay( Bot::entity( returned ), "E2E Ul'dah chat after reverse zoning" );
    expectLiveChannels( player, returned, "both channels remain live after reverse zoning" );

    player.logout();
    source.waitState( [ & ]( const Json& s ) { return Bot::actor( s, actor ) == nullptr; }, "returned traveler session cleanup", 30 );
    for( auto* bot : { &source, &target, &discoveryObserver } )
      bot->logout();
    auto& reloaded = ctx.spawn( "traveler-reloaded" );
    state = reloaded.loginViaLobby( ctx.server().relogin( fixture ), fixture.name );
    expect( state.at( "territory" ) == returnDestination.territory && dist( Bot::position( state ), returnDestination.position ) < 0.15,
            "territory and position after the return crossing survive a fresh login" );
    expect( state.at( "central_thanalan_discovery" ) == true && state.at( "central_thanalan_discoveries" ) == Json::array( { 1, 3 } ),
            "both discoveries survive a fresh login, got " + state.at( "central_thanalan_discoveries" ).dump() );
    reloaded.expectRewards( afterDiscovery, 1 );
    reloaded.logout();
  }
};

EXPOSE_SCENARIO( ExitCrossing );

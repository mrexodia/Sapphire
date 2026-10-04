// The party roster through its whole life: Tells before grouping, a declined
// invite, two then three members, leadership transfer and what the old leader
// may no longer do, a kick, the protocol's exact eight-member limit, an offline
// member's retained identity and the Tell it cannot receive, a rejoin after a
// fresh login, a rejected ninth invite and the disband. Every member must
// independently receive the same identities, leader and channel.
#include "../../harness/Context.h"
#include "../../harness/Scenario.h"
#include "../../client/Protocol.h"
#include <set>

using namespace Sapphire::E2E;

class Roster : public Scenario
{
  using Identity = std::pair< uint32_t, std::string >;

  static std::set< Identity > members( const Json& state )
  {
    std::set< Identity > rows;
    for( const auto& row : state.at( "party" ).at( "members" ) )
      rows.insert( { row.at( "entity_id" ).get< uint32_t >(), row.at( "name" ).get< std::string >() } );
    return rows;
  }

  static unsigned count( const Json& state ) { return state.at( "party" ).at( "count" ).get< unsigned >(); }

  static const Json& leaderOf( const Json& state )
  {
    const auto& party = state.at( "party" );
    return party.at( "members" )[ party.at( "leader_index" ).get< size_t >() ];
  }

  static const Json* rosterRow( const Json& state, uint32_t entity )
  {
    for( const auto& row : state.at( "party" ).at( "members" ) )
      if( row.at( "entity_id" ) == entity )
        return &row;
    return nullptr;
  }

  static bool sameChannel( const Sapphire::Testing::PartyChannel& sent, const Json& received )
  {
    return received.at( "party_id" ) == sent.partyId && received.at( "channel" ) == sent.chatChannel;
  }

  // The client refuses a request its received state does not allow; the
  // refusal has to name the missing evidence.
  template< class F >
  static void expectRefused( F&& request, const std::string& fragment )
  {
    try
    {
      request();
    }
    catch( const Sapphire::Testing::ProtocolError& error )
    {
      expect( std::string( error.what() ).find( fragment ) != std::string::npos,
              "the refusal must mention '" + fragment + "', got: " + error.what() );
      return;
    }
    throw Failure( "the request was not refused ('" + fragment + "')" );
  }

  void run( Context& ctx ) override
  {
    auto& leader = ctx.spawnCharacter( "party-leader" );
    auto& member = ctx.spawnCharacter( "party-member" );
    auto& third = ctx.spawnCharacter( "party-third" );
    std::vector< Bot* > extras;
    for( int i = 0; i < 5; ++i )
      extras.push_back( &ctx.spawnCharacter( "party-extra-" + std::to_string( i ) ) );
    auto& outsider = ctx.spawnCharacter( "party-outsider" );

    const auto leaderState = leader.snapshot(), memberState = member.snapshot(), thirdState = third.snapshot();
    std::vector< Json > extraStates;
    for( auto* bot : extras )
      extraStates.push_back( bot->snapshot() );
    const auto outsiderState = outsider.snapshot();
    const auto leaderName = ctx.fixture( leader ).name, memberName = ctx.fixture( member ).name, thirdName = ctx.fixture( third ).name;
    const auto leaderId = Bot::entity( leaderState ), memberId = Bot::entity( memberState ), thirdId = Bot::entity( thirdState );

    auto sees = []( Bot& bot, uint32_t entity, const std::string& name, const std::string& description ) {
      bot.waitState( [ & ]( const Json& s ) {
        const auto* row = Bot::actor( s, entity );
        return row && row->at( "name" ) == name;
      }, description );
    };
    sees( leader, memberId, memberName, "party target received by leader" );
    sees( member, leaderId, leaderName, "party inviter received by member" );
    sees( leader, thirdId, thirdName, "third party target received by leader" );

    leader.tell( memberId, memberName, "leader to member exact tell" );
    expect( member.expectTell( leaderState, "leader to member exact tell" ).at( "party_id" ) == 0, "a Tell outside a party carries no party id" );
    member.tell( leaderId, leaderName, "member to leader exact tell" );
    expect( leader.expectTell( memberState, "member to leader exact tell" ).at( "party_id" ) == 0, "a Tell outside a party carries no party id" );

    leader.inviteParty( memberId, memberName );
    const auto declined = member.declineParty();
    expect( declined == Json{ { "result", 0 }, { "auth_type", 1 }, { "answer", 0 }, { "name", leaderName } }, "exact decline reply" );
    const auto memberCharacterId = memberState.at( "characters" )[ 0 ].at( "character_id" ).get< uint64_t >();
    leader.waitState( [ & ]( const Json& s ) {
      return s.at( "party_invite_update" ) == Json{ { "character_id", memberCharacterId }, { "auth_type", 1 }, { "result", 5 }, { "name", memberName } } &&
             count( s ) == 0;
    }, "leader received exact party decline" );
    expect( count( member.snapshot() ) == 0, "declining leaves the member ungrouped" );
    ctx.log( "invite declined" );

    leader.inviteParty( memberId, memberName );
    const auto memberParty = member.acceptParty( 2 );
    const auto leaderParty = leader.waitState( [ & ]( const Json& s ) { return count( s ) == 2; }, "leader received two-member party state" );
    const std::set< Identity > expected{ { leaderId, leaderName }, { memberId, memberName } };
    for( const auto* state : { &leaderParty, &memberParty } )
    {
      const auto& party = state->at( "party" );
      expect( party.at( "id" ) != 0 && party.at( "chat_channel" ) != 0 && party.at( "leader_index" ) == 0,
              "a formed party has an id, a chat channel and the inviter as leader" );
      expect( members( *state ) == expected, "both members receive the same two identities" );
    }
    expect( leaderParty.at( "party" ).at( "chat_channel" ) == memberParty.at( "party" ).at( "chat_channel" ), "both members share the chat channel" );
    auto sent = leader.partyChat( "leader to member party message" );
    expect( sameChannel( sent, member.expectPartyChat( leaderParty, "leader to member party message" ) ), "party chat arrives on the channel it was sent to" );
    sent = member.partyChat( "member to leader party message" );
    expect( sameChannel( sent, leader.expectPartyChat( memberParty, "member to leader party message" ) ), "party chat arrives on the channel it was sent to" );
    const auto originalId = leaderParty.at( "party" ).at( "id" ).get< uint64_t >();
    const auto originalChannel = leaderParty.at( "party" ).at( "chat_channel" ).get< uint64_t >();
    auto sameParty = [ & ]( const Json& s ) {
      return s.at( "party" ).at( "id" ) == originalId && s.at( "party" ).at( "chat_channel" ) == originalChannel;
    };
    ctx.log( "two-member party formed" );

    leader.inviteParty( thirdId, thirdName );
    const auto thirdParty = third.acceptParty( 3 );
    auto expectedThree = expected;
    expectedThree.insert( { thirdId, thirdName } );
    for( auto* bot : { &leader, &member, &third } )
    {
      const auto joined = bot->waitState( [ & ]( const Json& s ) { return count( s ) == 3; }, "received three-member party state" );
      expect( sameParty( joined ), "the party keeps its id and channel when a member joins" );
      expect( members( joined ) == expectedThree, "every member receives the three identities" );
    }
    leader.changePartyLeader( memberId, memberName );
    for( auto* bot : { &leader, &member, &third } )
    {
      const auto changed = bot->waitState( [ & ]( const Json& s ) { return count( s ) > 0 && leaderOf( s ).at( "entity_id" ) == memberId; },
                                           "received transferred party leadership" );
      expect( leaderOf( changed ).at( "name" ) == memberName, "the new leader carries the member's name" );
    }
    ctx.log( "leadership transferred to the member" );
    expectRefused( [ & ] { leader.inviteParty( thirdId, thirdName ); }, "received party leadership" );
    sent = third.partyChat( "third member party message" );
    for( auto* receiver : { &leader, &member } )
      expect( sameChannel( sent, receiver->expectPartyChat( thirdParty, "third member party message" ) ), "party chat arrives on the channel it was sent to" );
    expectRefused( [ & ] { leader.kickPartyMember( thirdId, thirdName ); }, "received leadership" );
    member.kickPartyMember( thirdId, thirdName );
    third.waitState( [ & ]( const Json& s ) { return count( s ) == 0; }, "kicked member received empty party state" );
    for( auto* bot : { &leader, &member } )
    {
      const auto remaining = bot->waitState( [ & ]( const Json& s ) { return count( s ) == 2; }, "received roster after third member leaves" );
      expect( sameParty( remaining ), "the party keeps its id and channel after a kick" );
      expect( members( remaining ) == expected, "the kicked member left the roster" );
      expect( leaderOf( remaining ).at( "entity_id" ) == memberId, "the leader is unchanged by a kick" );
    }
    ctx.log( "third member kicked" );

    // Re-add the kicked client, then expand through the protocol's exact
    // eight-member roster limit. Every member independently receives the same
    // identities and leader.
    auto expectedFull = expected;
    struct Joiner { Bot* bot; std::string name; const Json* state; };
    std::vector< Joiner > expansion{ { &third, thirdName, &thirdState } };
    for( size_t i = 0; i < extras.size(); ++i )
      expansion.push_back( { extras[ i ], ctx.fixture( *extras[ i ] ).name, &extraStates[ i ] } );
    Json lastJoined;
    unsigned expectedCount = 3;
    for( const auto& joiner : expansion )
    {
      member.inviteParty( Bot::entity( *joiner.state ), joiner.name );
      lastJoined = joiner.bot->acceptParty( expectedCount++ );
      expectedFull.insert( { Bot::entity( *joiner.state ), joiner.name } );
    }
    std::vector< Bot* > partyBots{ &leader, &member, &third };
    partyBots.insert( partyBots.end(), extras.begin(), extras.end() );
    for( auto* bot : partyBots )
    {
      const auto full = bot->waitState( [ & ]( const Json& s ) { return count( s ) == 8; }, "received full eight-member party roster" );
      expect( sameParty( full ), "the full party keeps its id and channel" );
      expect( members( full ) == expectedFull, "every member receives the eight identities" );
      expect( leaderOf( full ).at( "entity_id" ) == memberId, "the leader is unchanged by joins" );
    }
    sent = extras.back()->partyChat( "full roster party message" );
    for( size_t i = 0; i + 1 < partyBots.size(); ++i )
      expect( sameChannel( sent, partyBots[ i ]->expectPartyChat( lastJoined, "full roster party message" ) ), "party chat reaches the full roster" );
    ctx.log( "eight-member roster complete" );

    // Ordinary logout retains exact offline membership, then a fresh
    // HTTP/lobby/world session restores the same member identity and party
    // channel without a retry.
    const auto rejoinFixture = ctx.fixture( *extras.back() );
    const auto rejoinEntity = Bot::entity( extraStates.back() );
    extras.back()->logout();
    for( size_t i = 0; i + 1 < partyBots.size(); ++i )
    {
      const auto offline = partyBots[ i ]->waitState( [ & ]( const Json& s ) {
        const auto* row = rosterRow( s, rejoinEntity );
        return count( s ) == 8 && row && row->at( "territory" ) == 0;
      }, "received offline full-party member identity" );
      expect( members( offline ) == expectedFull, "an offline member keeps its identity in the roster" );
    }
    member.waitState( [ & ]( const Json& s ) { return Bot::actor( s, rejoinEntity ) == nullptr; }, "offline tell target despawned" );
    expect( member.tellOffline( rejoinEntity, rejoinFixture.name, "offline member exact tell" ) == Json{ { "name", rejoinFixture.name } },
            "a Tell to the offline member names it as unavailable" );
    auto& rejoined = ctx.spawn( "party-extra-rejoined" );
    const auto rejoinedState = rejoined.loginViaLobby( ctx.server().relogin( rejoinFixture ), rejoinFixture.name );
    expect( Bot::entity( rejoinedState ) == rejoinEntity, "a fresh login keeps the entity id" );
    const auto rejoinedFull = rejoined.waitState( [ & ]( const Json& s ) { return count( s ) == 8; }, "rejoined client received full party" );
    expect( sameParty( rejoinedFull ), "the rejoined member is back in the same party and channel" );
    expect( members( rejoinedFull ) == expectedFull, "the rejoined member receives the eight identities" );
    for( size_t i = 0; i + 1 < partyBots.size(); ++i )
      partyBots[ i ]->waitState( [ & ]( const Json& s ) {
        const auto* row = rosterRow( s, rejoinEntity );
        return row && row->at( "territory" ) == 130;
      }, "received rejoined party member detail" );
    partyBots.back() = &rejoined;
    sent = rejoined.partyChat( "rejoined full roster party message" );
    for( size_t i = 0; i + 1 < partyBots.size(); ++i )
      expect( sameChannel( sent, partyBots[ i ]->expectPartyChat( rejoinedFull, "rejoined full roster party message" ) ), "party chat from the rejoined member reaches the roster" );
    ctx.log( "offline member rejoined" );

    const auto outsiderId = Bot::entity( outsiderState );
    const auto outsiderName = ctx.fixture( outsider ).name;
    sees( member, outsiderId, outsiderName, "ninth exact player received by full-party leader" );
    expectRefused( [ & ] { member.inviteParty( outsiderId, outsiderName ); }, "party invite requires" );
    expectRefused( [ & ] { leader.disbandParty(); }, "received leadership" );
    member.disbandParty();
    for( auto* bot : partyBots )
      bot->waitState( [ & ]( const Json& s ) { return count( s ) == 0; }, "received explicit full-party disband" );
    ctx.log( "party disbanded" );
    // Every logout is published before any acknowledgement is awaited: serial
    // waits can leave later requests behind unrelated per-session teardown.
    ctx.logoutAll( 35 );
  }
};

EXPOSE_SCENARIO( Roster );

// The Steps of Nald chain: Motivational Speaking (65686) then Gil for Gold
// (65687) through their real scene exchanges, including cancelling the offer and
// the hand-over, reconnecting while the quest is active and choosing the ether
// reward. The earned ether stack is then moved to an empty bag slot, which only
// a fresh login can prove (the server acknowledges before it mutates).
#include "QuestSteps.h"

using namespace Sapphire::E2E;
using namespace Sapphire::E2E::QuestSteps;

class GilForGold : public Scenario
{
  // Move the whole ether stack to bag 3 slot 24 and reconnect; the observer sees
  // the quester leave and come back at the same spot. Returns the new quester
  // and the layout the fresh login showed.
  static std::pair< Bot*, Json > moveRewardAndVerifyReconnect( Context& ctx, Bot& player, Bot& observer, const Fixture& fixture,
                                                                const Bot::Rewards& expected, size_t workIndex,
                                                                const std::vector< uint32_t >& quests )
  {
    auto state = player.expectRewards( expected, workIndex );
    const auto before = Bot::inventory( state );
    const auto stacks = bagStacks( before, GoldScenes::Ether );
    expect( stacks.size() == 1 && stacks[ 0 ].second.at( "count" ) == 3, "one stack of three ethers in the bags" );
    const auto& [ source, item ] = stacks[ 0 ];
    const std::string destination = Bot::slotKey( 3, 24 );
    expect( source != destination && !before.contains( destination ), "the destination slot is empty" );
    expect( state.at( "rewards" ).at( "containers" ).at( "3" ) == true, "bag 3 was received completely" );
    const auto actor = Bot::entity( state );
    const auto observed = observer.waitState( [ & ]( const Json& s ) { return Bot::actor( s, actor ) != nullptr; },
                                              "inventory subject visible before move" );
    const auto position = Bot::actor( observed, actor )->at( "position" ).get< Point >();

    auto expectedInventory = before;
    auto moved = expectedInventory.at( source );
    expectedInventory.erase( source );
    moved[ "storage" ] = 3;
    moved[ "slot" ] = 24;
    expectedInventory[ destination ] = moved;
    // The server sends only a pre-operation acknowledgement; it is not a move.
    player.requestItemMove( item.at( "storage" ), item.at( "slot" ), 3, 24, GoldScenes::Ether );

    player.logout();
    observer.waitState( [ & ]( const Json& s ) { return Bot::actor( s, actor ) == nullptr; }, "move session removed", 30 );
    auto& reconnected = ctx.spawn( "quester-moved" );
    state = reconnected.loginViaLobby( ctx.server().relogin( fixture ), fixture.name );
    expect( Bot::entity( state ) == actor && dist( Bot::position( state ), position ) < 0.15,
            "the reconnected character keeps its entity id and position" );
    observer.waitState( [ & ]( const Json& s ) {
      const auto* row = Bot::actor( s, actor );
      return row && dist( row->at( "position" ).get< Point >(), position ) < 0.15;
    }, "moved-item character reconnect observed" );
    expectState( reconnected, expected, workIndex, expectedInventory, quests, "ether stack after the move and a fresh login" );
    return { &reconnected, expectedInventory };
  }

  void run( Context& ctx ) override
  {
    auto& data = ctx.data();
    const auto speaking = questJourney( data, Uldah::MotivationalSpeaking, Uldah::Territory );
    const auto gold = questJourney( data, Uldah::GilForGold, Uldah::Territory );
    ctx.log( "Motivational Speaking " + std::to_string( speaking.giver.baseId ) + " -> " + std::to_string( speaking.recipient.baseId ) +
             " (" + std::to_string( static_cast< int >( speaking.routeLength ) ) + " m), Gil for Gold " +
             std::to_string( gold.giver.baseId ) + " -> " + std::to_string( gold.recipient.baseId ) + " (" +
             std::to_string( static_cast< int >( gold.routeLength ) ) + " m)" );
    expect( speaking.optionalItems.empty() && speaking.classJob == 1, "Motivational Speaking has no optional rewards" );
    expect( speaking.exp == 50 && speaking.gil == 0 && speaking.items.size() == 1 &&
            speaking.items[ 0 ].id == SpeakingScenes::Potion && speaking.items[ 0 ].count == 2,
            "Motivational Speaking pays 50 exp and two potions" );

    CharacterOptions options;
    options.position = speaking.route.front();
    auto& player = ctx.spawnCharacter( "quester", options );
    auto& observer = ctx.spawnCharacter( "quest-observer", options );
    const auto fixture = ctx.fixture( player );
    const auto before = player.rewardSnapshot( speaking.workIndex );
    expect( before.level == 1 && before.exp == 0, "a fresh character starts at level 1 without exp" );

    auto rewards = completeMotivationalSpeaking( ctx, player, &observer, speaking, before, true );
    Bot* quester = &completeGilForGold( ctx, player, &observer, fixture, gold, speaking, rewards, true );
    ctx.log( "both quests complete; rewards " + describe( rewards ) );
    const std::vector< uint32_t > quests{ speaking.quest, gold.quest };
    auto [ moved, movedInventory ] = moveRewardAndVerifyReconnect( ctx, *quester, observer, fixture, rewards, gold.workIndex, quests );
    quester = moved;

    const auto actor = Bot::entity( quester->snapshot() );
    quester->logout();
    observer.waitState( [ & ]( const Json& s ) { return Bot::actor( s, actor ) == nullptr; }, "quester session cleanup", 30 );
    observer.logout();

    auto& reloaded = ctx.spawn( "quest-reloaded" );
    reloaded.loginViaLobby( ctx.server().relogin( fixture ), fixture.name );
    for( const auto quest : quests )
      reloaded.expectQuestComplete( quest );
    auto state = reloaded.expectRewards( rewards, gold.workIndex );
    for( const auto quest : quests )
      expect( !questActive( state, quest ), "completed quests are not active after a fresh login" );
    expectInventory( reloaded, movedInventory, "moved ether stack after the final fresh login" );
    reloaded.logout();
  }
};

EXPOSE_SCENARIO( GilForGold );

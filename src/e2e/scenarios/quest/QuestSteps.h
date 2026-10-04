#pragma once
// Steps the quest scenarios share: the scene answers of the two Steps of Nald
// quests, the walk between their NPCs, inventory bookkeeping over the received
// snapshot, and the fresh login that is the only proof an inventory operation
// took effect (the server acknowledges before it mutates).
#include "../../harness/Content.h"
#include "../../harness/Context.h"
#include "../../harness/Scenario.h"
#include <cmath>
#include <future>
#include <string>
#include <utility>
#include <vector>

namespace Sapphire::E2E::QuestSteps
{
  // Scene answers as the real client sends them (from the quest scripts,
  // derived from src/scripts/quest/subquest/uldah/SubWil001.cpp and SubWil002.cpp).
  namespace SpeakingScenes
  {
    constexpr uint32_t Quest = Uldah::MotivationalSpeaking;
    constexpr uint32_t OfferScene = 0, CompleteScene = 1;
    inline const std::vector< uint32_t > Accept{ 1 }, Cancel{ 0 }, CompleteWithoutOptionalItem{ 1, 0 };
    constexpr uint32_t Potion = 4551;   // the fixed reward, two of them
  }
  namespace GoldScenes
  {
    constexpr uint32_t Quest = Uldah::GilForGold;
    constexpr uint32_t OfferScene = 0, HandOverScene = 1, AcknowledgeScene = 99, CompleteScene = 100;
    constexpr uint32_t Ether = 4555;    // the optional reward the scenarios pick, three of them
    // The completion result carries the chosen item id, not an index.
    inline const std::vector< uint32_t > Accept{ 1 }, Cancel{ 0 }, HandOver{ 1 }, Acknowledge{ 0 }, CompleteWithEther{ 1, Ether };
  }

  inline double dist( const Point& a, const Point& b )
  {
    return std::sqrt( std::pow( a[ 0 ] - b[ 0 ], 2 ) + std::pow( a[ 1 ] - b[ 1 ], 2 ) + std::pow( a[ 2 ] - b[ 2 ], 2 ) );
  }

  inline std::string questKey( uint32_t quest ) { return std::to_string( quest & 0xffff ); }
  inline bool questActive( const Json& s, uint32_t quest ) { return s.at( "quests" ).contains( questKey( quest ) ); }
  inline bool questComplete( const Json& s, uint32_t quest )
  {
    const auto& complete = s.at( "complete_quests" );
    return complete.contains( questKey( quest ) ) && complete.at( questKey( quest ) ) == true;
  }

  // Answer one expected scene; a different scene is a failure, not a guess.
  inline Json answer( Bot& bot, uint32_t eventId, uint32_t sceneId, const std::vector< uint32_t >& results )
  {
    auto state = bot.waitScene( eventId, sceneId, "scene " + std::to_string( eventId ) + ":" + std::to_string( sceneId ) );
    bot.chooseScene( state, results );
    return state;
  }

  // -- inventory bookkeeping over the received snapshot ----------------------

  inline Json slotRow( uint32_t storage, uint32_t slot, uint32_t id, uint32_t count )
  {
    return Json{ { "storage", storage }, { "slot", slot }, { "id", id }, { "count", count } };
  }

  inline std::pair< uint32_t, uint32_t > splitKey( const std::string& key )
  {
    const auto colon = key.find( ':' );
    return { static_cast< uint32_t >( std::stoul( key.substr( 0, colon ) ) ), static_cast< uint32_t >( std::stoul( key.substr( colon + 1 ) ) ) };
  }

  // Stacks of one item in the ordinary bags (storage 0..3), in key order.
  inline std::vector< std::pair< std::string, Json > > bagStacks( const Json& inventory, uint32_t item )
  {
    std::vector< std::pair< std::string, Json > > rows;
    for( const auto& [ key, row ] : inventory.items() )
      if( row.at( "storage" ).get< uint32_t >() <= 3 && row.at( "id" ) == item )
        rows.emplace_back( key, row );
    return rows;
  }

  // Occupied ordinary bag slots holding anything but `item`, in key order.
  inline std::vector< std::pair< std::string, Json > > otherBagStacks( const Json& inventory, uint32_t item )
  {
    std::vector< std::pair< std::string, Json > > rows;
    for( const auto& [ key, row ] : inventory.items() )
      if( row.at( "storage" ).get< uint32_t >() <= 3 && row.at( "id" ) != item )
        rows.emplace_back( key, row );
    return rows;
  }

  // The last empty ordinary bag slot (bag 3 slot 24 downwards), away from the quest rewards.
  inline std::string lastEmptyBagSlot( const Json& inventory )
  {
    for( int bag = 3; bag >= 0; --bag )
      for( int slot = 24; slot >= 0; --slot )
        if( !inventory.contains( Bot::slotKey( bag, slot ) ) )
          return Bot::slotKey( bag, slot );
    throw Failure( "no empty ordinary bag slot" );
  }

  // The client drops zero-count rows (RewardsState::apply), so an empty purse has no row.
  inline void setGil( Json& inventory, uint32_t gil )
  {
    if( gil ) inventory[ "2000:0" ] = slotRow( 2000, 0, 1, gil );
    else inventory.erase( "2000:0" );
  }

  inline std::string describe( const Bot::Rewards& rewards )
  {
    Json brief{ { "exp", rewards.exp }, { "level", rewards.level }, { "items", Json::object() }, { "currencies", Json::object() } };
    for( const auto& [ id, count ] : rewards.items ) brief[ "items" ][ std::to_string( id ) ] = count;
    for( const auto& [ id, count ] : rewards.currencies ) brief[ "currencies" ][ std::to_string( id ) ] = count;
    return brief.dump();
  }

  inline uint32_t gilOf( const Bot::Rewards& rewards )
  {
    auto it = rewards.currencies.find( 1 );
    return it == rewards.currencies.end() ? 0 : it->second;
  }

  // Reward maps hold only present stacks, so a count reaching zero drops its key.
  inline void addItem( Bot::Rewards& rewards, uint32_t id, int delta )
  {
    const int count = static_cast< int >( rewards.items[ id ] ) + delta;
    expect( count >= 0, "reward bookkeeping went negative for item " + std::to_string( id ) );
    if( count == 0 ) rewards.items.erase( id );
    else rewards.items[ id ] = static_cast< uint32_t >( count );
  }

  // A stack that enters the bags for the first time (purchase, unequip).
  inline void setNewItem( Bot::Rewards& rewards, uint32_t id, uint32_t count )
  {
    expect( !rewards.items.count( id ), "item " + std::to_string( id ) + " must be absent from the bags before it is added" );
    rewards.items[ id ] = count;
  }

  inline void addGil( Bot::Rewards& rewards, int delta )
  {
    const int gil = static_cast< int >( gilOf( rewards ) ) + delta;
    expect( gil >= 0, "gil bookkeeping went negative" );
    if( gil == 0 ) rewards.currencies.erase( 1 );
    else rewards.currencies[ 1 ] = static_cast< uint32_t >( gil );
  }

  // The received inventory must equal the expected layout exactly; the diff is the failure message.
  inline Json expectInventory( Bot& bot, const Json& expected, const std::string& what, double timeout = 10 )
  {
    try
    {
      return bot.waitState( [ & ]( const Json& s ) {
        return s.at( "rewards" ).at( "inventory_ready" ).get< bool >() && Bot::inventory( s ) == expected;
      }, what, timeout );
    }
    catch( const Timeout& )
    {
      const auto actual = Bot::inventory( bot.snapshot() );
      Json missing = Json::object(), unexpected = Json::object();
      for( const auto& [ key, row ] : expected.items() )
        if( !actual.contains( key ) || actual.at( key ) != row ) missing[ key ] = row;
      for( const auto& [ key, row ] : actual.items() )
        if( !expected.contains( key ) || expected.at( key ) != row ) unexpected[ key ] = row;
      throw Failure( bot.name() + ": " + what + ": inventory differs; expected but not received " + missing.dump() +
                     ", received but not expected " + unexpected.dump() );
    }
  }

  // Exact rewards, exact layout and the completed quests, as every fresh login must show.
  inline Json expectState( Bot& bot, const Bot::Rewards& rewards, size_t workIndex, const Json& inventory,
                           const std::vector< uint32_t >& completedQuests, const std::string& what )
  {
    try
    {
      bot.expectRewards( rewards, workIndex );
    }
    catch( const Timeout& )
    {
      throw Failure( bot.name() + ": " + what + ": rewards differ; expected " + describe( rewards ) + ", received " +
                     describe( Bot::rewardValues( bot.snapshot(), workIndex ) ) );
    }
    auto state = expectInventory( bot, inventory, what );
    for( const auto quest : completedQuests )
      bot.expectQuestComplete( quest );
    return state;
  }

  // -- logins -----------------------------------------------------------------

  // Log the bot out and log the same character in as a new bot.
  inline Bot& relogin( Context& ctx, Bot& bot, const Fixture& fixture, const std::string& name )
  {
    bot.logout();
    auto& next = ctx.spawn( name );
    next.loginViaLobby( ctx.server().relogin( fixture ), fixture.name );
    return next;
  }

  // Relogin that proves the previous inventory operation and the quest state persisted.
  inline Bot& reloginAndVerify( Context& ctx, Bot& bot, const Fixture& fixture, const std::string& name, const Bot::Rewards& rewards,
                                size_t workIndex, const Json& inventory, const std::vector< uint32_t >& completedQuests )
  {
    auto& next = relogin( ctx, bot, fixture, name );
    expectState( next, rewards, workIndex, inventory, completedQuests, "state after the fresh login as " + name );
    return next;
  }

  // -- walking ------------------------------------------------------------------

  // The quester walks the route; when an observer is given it walks alongside and
  // must see the quester arrive within interaction range of the recipient.
  inline void walkRoute( Bot& player, Bot* observer, const std::vector< Point >& route, const Point& destinationNpc,
                         double timeout = 180 )
  {
    if( observer )
    {
      // Ordinary interpolated movement for both clients, keeping the observer nearby.
      auto playerWalk = std::async( std::launch::async, [ & ] { player.walkRoute( route, 6.0f, timeout ); } );
      auto observerWalk = std::async( std::launch::async, [ & ] { observer->walkRoute( route, 6.0f, timeout ); } );
      playerWalk.wait();
      observerWalk.wait();
      playerWalk.get();
      observerWalk.get();
      const auto actor = Bot::entity( player.snapshot() );
      observer->waitState( [ & ]( const Json& s ) {
        const auto* row = Bot::actor( s, actor );
        return row && dist( row->at( "position" ).get< Point >(), route.back() ) < 0.15;
      }, "quester arrived as observed by a second client" );
    }
    else
      player.walkRoute( route, 6.0f, timeout );
    expect( dist( route.back(), destinationNpc ) <= 2, "the route ends within interaction range of the NPC" );
  }

  // -- the quests ---------------------------------------------------------------

  // Motivational Speaking from its giver: with `thorough`, cancelling the offer
  // first must grant nothing. Returns the rewards the completion must have paid.
  inline Bot::Rewards completeMotivationalSpeaking( Context& ctx, Bot& player, Bot* observer, const QuestJourney& journey,
                                                    const Bot::Rewards& before, bool thorough )
  {
    using namespace SpeakingScenes;
    expect( journey.quest == Quest, "the journey is Motivational Speaking" );
    auto state = player.snapshot();
    expect( !questActive( state, Quest ) && !questComplete( state, Quest ), "a fresh character has not touched the quest" );
    expect( dist( Bot::position( state ), journey.giver.position ) <= 2, "the quester starts within interaction range of the giver" );

    if( thorough )
    {
      // Cancellation must not grant acceptance, completion or rewards.
      player.interact( journey.giver.id, Quest );
      answer( player, Quest, OfferScene, Cancel );
      state = player.waitEventFinished();
      expect( !questActive( state, Quest ) && !questComplete( state, Quest ), "cancelling the offer leaves the quest untouched" );
      expect( player.rewardSnapshot( journey.workIndex ) == before, "cancelling the offer pays nothing" );
    }

    player.interact( journey.giver.id, Quest );
    answer( player, Quest, OfferScene, Accept );
    player.expectQuestActive( Quest, 255 );
    player.waitEventFinished();
    ctx.log( "Motivational Speaking accepted; walking " + std::to_string( static_cast< int >( journey.routeLength ) ) + " m to the recipient" );

    walkRoute( player, observer, journey.route, journey.recipient.position );
    player.interact( journey.recipient.id, Quest );
    answer( player, Quest, CompleteScene, CompleteWithoutOptionalItem );
    player.expectQuestComplete( Quest );
    state = player.waitEventFinished();
    expect( !questActive( state, Quest ), "a completed quest is no longer active" );

    auto expected = before;
    expected.exp += journey.exp;
    for( const auto& item : journey.items )
      addItem( expected, item.id, static_cast< int >( item.count ) );
    if( journey.gil )
      addGil( expected, static_cast< int >( journey.gil ) );
    player.expectRewards( expected, journey.workIndex );
    return expected;
  }

  // Gil for Gold from where Motivational Speaking ended. With `thorough`, the
  // offer and the hand-over are cancelled first and the quester reconnects while
  // the quest is active. `rewards` holds the rewards before and, on return,
  // after. Returns the quester (a new bot after the reconnect).
  inline Bot& completeGilForGold( Context& ctx, Bot& player, Bot* observer, const Fixture& fixture, const QuestJourney& journey,
                                  const QuestJourney& previous, Bot::Rewards& rewards, bool thorough )
  {
    using namespace GoldScenes;
    const auto before = rewards;
    auto state = player.snapshot();
    const auto actor = Bot::entity( state );
    expect( journey.quest == Quest && journey.previousQuests == std::array< uint32_t, 3 >{ previous.quest, 0, 0 },
            "Gil for Gold requires exactly Motivational Speaking" );
    expect( questComplete( state, previous.quest ), "the prerequisite quest is complete" );
    expect( journey.classJob == previous.classJob && journey.classJob == 1, "both quests are Gladiator quests" );
    expect( journey.workIndex == previous.workIndex, "both quests pay into the same exp slot" );
    // Independent authored expectation for this small known quest, not only the shared calculation.
    expect( journey.exp == 50 && journey.gil == 0 && journey.items.empty(), "Gil for Gold pays 50 exp and no fixed items" );
    expect( journey.optionalItems.size() == 2 && journey.optionalItems[ 0 ].id == SpeakingScenes::Potion &&
            journey.optionalItems[ 0 ].count == 3 && journey.optionalItems[ 1 ].id == Ether && journey.optionalItems[ 1 ].count == 3,
            "Gil for Gold offers three potions or three ethers" );
    // Shared giver/recipient must connect without teleporting or unverified bridging.
    expect( dist( previous.route.back(), journey.route.front() ) < 0.01 && journey.giver.id == previous.recipient.id,
            "Gil for Gold starts at the NPC Motivational Speaking ended at" );
    expect( !questActive( state, Quest ) && !questComplete( state, Quest ), "Gil for Gold has not been touched yet" );

    if( thorough )
    {
      player.interact( journey.giver.id, Quest );
      answer( player, Quest, OfferScene, Cancel );
      state = player.waitEventFinished();
      expect( !questActive( state, Quest ) && !questComplete( state, Quest ), "cancelling the offer leaves the quest untouched" );
      expect( player.rewardSnapshot( journey.workIndex ) == before, "cancelling the offer pays nothing" );
    }
    player.interact( journey.giver.id, Quest );
    answer( player, Quest, OfferScene, Accept );
    player.expectQuestActive( Quest, 255 );
    player.waitEventFinished();

    Bot* quester = &player;
    if( thorough )
    {
      // Reconnect while active: neither fixture edits nor optimistic acceptance count.
      expect( observer != nullptr, "the thorough journey needs an observer" );
      player.logout();
      observer->waitState( [ & ]( const Json& s ) { return Bot::actor( s, actor ) == nullptr; }, "active quest session cleanup", 30 );
      quester = &ctx.spawn( "quester-active-reconnect" );
      state = quester->loginViaLobby( ctx.server().relogin( fixture ), fixture.name );
      expect( Bot::entity( state ) == actor, "the reconnected character keeps its entity id" );
      expect( dist( Bot::position( state ), journey.route.front() ) < 0.15, "the reconnected character stands where it logged out" );
      quester->expectQuestActive( Quest, 255 );
      quester->expectQuestComplete( previous.quest );
      quester->expectRewards( before, journey.workIndex );
    }
    ctx.log( "Gil for Gold accepted; walking " + std::to_string( static_cast< int >( journey.routeLength ) ) + " m to the recipient" );
    walkRoute( *quester, observer, journey.route, journey.recipient.position );

    if( thorough )
    {
      // Cancelling the hand-over triggers a separate acknowledgement scene, not success.
      quester->interact( journey.recipient.id, Quest );
      answer( *quester, Quest, HandOverScene, Cancel );
      answer( *quester, Quest, AcknowledgeScene, Acknowledge );
      state = quester->waitEventFinished();
      expect( !questComplete( state, Quest ), "cancelling the hand-over does not complete the quest" );
      quester->expectQuestActive( Quest, 255 );
      expect( quester->rewardSnapshot( journey.workIndex ) == before, "cancelling the hand-over pays nothing" );
    }
    quester->interact( journey.recipient.id, Quest );
    answer( *quester, Quest, HandOverScene, HandOver );
    answer( *quester, Quest, CompleteScene, CompleteWithEther );
    quester->expectQuestComplete( Quest );
    state = quester->waitEventFinished();
    expect( !questActive( state, Quest ), "a completed quest is no longer active" );

    rewards.exp += 50;
    addItem( rewards, Ether, 3 );
    quester->expectRewards( rewards, journey.workIndex );
    return *quester;
  }

  // Both quests without the negative checks: how the inventory and shop scenarios
  // earn their potions and ethers.
  inline Bot& earnQuestRewards( Context& ctx, Bot& player, const Fixture& fixture, const QuestJourney& speaking,
                                const QuestJourney& gold, Bot::Rewards& rewards )
  {
    rewards = completeMotivationalSpeaking( ctx, player, nullptr, speaking, rewards, false );
    return completeGilForGold( ctx, player, nullptr, fixture, gold, speaking, rewards, false );
  }
}

// Inventory operations on an earned reward stack: swap with another bag item,
// split 3 into 2+1 and merge back, then discard while a second client watches.
// Each operation is proven only through a fresh login, because the server
// acknowledges inventory operations before it carries them out. The stack is
// earned by completing Motivational Speaking and Gil for Gold first.
#include "QuestSteps.h"

using namespace Sapphire::E2E;
using namespace Sapphire::E2E::QuestSteps;

class RewardInventory : public Scenario
{
  void run( Context& ctx ) override
  {
    auto& data = ctx.data();
    const auto speaking = questJourney( data, Uldah::MotivationalSpeaking, Uldah::Territory );
    const auto gold = questJourney( data, Uldah::GilForGold, Uldah::Territory );
    const auto workIndex = gold.workIndex;

    CharacterOptions options;
    options.position = speaking.route.front();
    auto& first = ctx.spawnCharacter( "inventory-quester", options );
    const auto fixture = ctx.fixture( first );
    auto rewards = first.rewardSnapshot( workIndex );
    Bot* player = &earnQuestRewards( ctx, first, fixture, speaking, gold, rewards );
    const std::vector< uint32_t > quests{ speaking.quest, gold.quest };
    ctx.log( "quests complete; rewards " + describe( rewards ) );

    // Swap: the ether stack and the first other occupied bag slot trade places.
    {
      auto state = player->expectRewards( rewards, workIndex );
      const auto before = Bot::inventory( state );
      const auto sources = bagStacks( before, GoldScenes::Ether );
      const auto destinations = otherBagStacks( before, GoldScenes::Ether );
      expect( sources.size() == 1 && sources[ 0 ].second.at( "count" ) == 3 && !destinations.empty(),
              "one ether stack of three and another bag item to swap with" );
      const auto& [ source, sourceItem ] = sources[ 0 ];
      const auto& [ destination, destinationItem ] = destinations[ 0 ];
      expect( source != destination && sourceItem.at( "id" ) != destinationItem.at( "id" ), "two different stacks" );
      auto expectedInventory = before;
      auto swappedSource = sourceItem, swappedDestination = destinationItem;
      swappedSource[ "storage" ] = destinationItem.at( "storage" );
      swappedSource[ "slot" ] = destinationItem.at( "slot" );
      swappedDestination[ "storage" ] = sourceItem.at( "storage" );
      swappedDestination[ "slot" ] = sourceItem.at( "slot" );
      expectedInventory[ destination ] = swappedSource;
      expectedInventory[ source ] = swappedDestination;
      const auto entity = Bot::entity( state );
      // The bot has walked since login: where it stands is its predicted position (own movement is not echoed).
      const auto position = Bot::predicted( state );
      player->requestItemSwap( sourceItem.at( "storage" ), sourceItem.at( "slot" ), destinationItem.at( "storage" ),
                               destinationItem.at( "slot" ), sourceItem.at( "id" ), destinationItem.at( "id" ) );
      player = &relogin( ctx, *player, fixture, "inventory-swapped" );
      state = player->snapshot();
      expect( Bot::entity( state ) == entity && dist( Bot::position( state ), position ) < 0.15,
              "the character keeps its entity id and position across the swap relogin" );
      expectState( *player, rewards, workIndex, expectedInventory, quests, "swapped stacks after a fresh login" );
      ctx.log( "swap " + source + " <-> " + destination + " persisted" );
    }

    // Split one ether off into the last empty slot, then merge it back.
    {
      auto state = player->expectRewards( rewards, workIndex );
      const auto before = Bot::inventory( state );
      const auto stacks = bagStacks( before, GoldScenes::Ether );
      expect( stacks.size() == 1 && stacks[ 0 ].second.at( "count" ) == 3, "one ether stack of three before the split" );
      const auto& [ source, item ] = stacks[ 0 ];
      const auto empty = lastEmptyBagSlot( before );
      const auto [ destinationStorage, destinationSlot ] = splitKey( empty );
      auto splitInventory = before;
      splitInventory[ source ][ "count" ] = 2;
      splitInventory[ empty ] = slotRow( destinationStorage, destinationSlot, GoldScenes::Ether, 1 );
      player->requestItemSplit( item.at( "storage" ), item.at( "slot" ), destinationStorage, destinationSlot, GoldScenes::Ether, 3, 1 );
      player = &reloginAndVerify( ctx, *player, fixture, "inventory-split", rewards, workIndex, splitInventory, quests );
      ctx.log( "split " + source + " -> " + empty + " persisted" );

      player->requestItemMerge( destinationStorage, destinationSlot, item.at( "storage" ), item.at( "slot" ), GoldScenes::Ether, 1, 2 );
      player = &reloginAndVerify( ctx, *player, fixture, "inventory-merged", rewards, workIndex, before, quests );
      ctx.log( "merge back into " + source + " persisted" );
    }

    // Discard the whole stack with a fresh independent observer watching the session.
    {
      auto state = player->snapshot();
      auto inventory = Bot::inventory( state );
      const auto stacks = bagStacks( inventory, GoldScenes::Ether );
      expect( stacks.size() == 1 && stacks[ 0 ].second.at( "count" ) == 3, "one ether stack of three before the discard" );
      const auto& [ key, item ] = stacks[ 0 ];
      const auto actor = Bot::entity( state );
      CharacterOptions observerOptions;
      observerOptions.position = Bot::predicted( state );
      auto& observer = ctx.spawnCharacter( "inventory-observer", observerOptions );
      observer.waitState( [ & ]( const Json& s ) { return Bot::actor( s, actor ) != nullptr; }, "inventory subject visible" );

      player->discardItem( item.at( "storage" ), item.at( "slot" ), GoldScenes::Ether );
      inventory.erase( key );
      expectInventory( *player, inventory, "received inventory after the discard" );
      auto remaining = rewards;
      remaining.items.erase( GoldScenes::Ether );
      player->expectRewards( remaining, workIndex );

      player->logout();
      observer.waitState( [ & ]( const Json& s ) { return Bot::actor( s, actor ) == nullptr; }, "inventory session cleanup", 30 );
      observer.logout();
      auto& reloaded = ctx.spawn( "inventory-reloaded" );
      reloaded.loginViaLobby( ctx.server().relogin( fixture ), fixture.name );
      expectState( reloaded, remaining, workIndex, inventory, quests, "discarded stack gone after a fresh login" );
      reloaded.logout();
    }
  }
};

EXPOSE_SCENARIO( RewardInventory );

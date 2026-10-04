// A quest-reward potion funds a shopping trip: sell one potion at the nearest
// gil shop, buy a stack of the cheapest consumable and use it (the item action
// effect reaches a second client), liquidate the stack, then buy level-1
// equipment piece by piece: legs, feet and body at the first vendor, head, ear,
// neck and wrist at other vendors, funded by reselling purchases and the starter
// gear. Every purchase is equipped and unequipped, and every inventory change is
// proven through a fresh login because the server acknowledges before it mutates.
//
// Several of those logins happen while the shop window is still open
// (regression for events surviving logout: Player::clearEvents on logout).
//
// What to buy, where and for how much comes from the Shop/Item sheets and the
// navmesh at run time (ShopJourney); the gil totals asserted along the way are
// the Python suite's authored expectations for this game data.
#include "../../harness/ShopJourney.h"
#include "QuestSteps.h"

using namespace Sapphire::E2E;
using namespace Sapphire::E2E::QuestSteps;

class ShopPurchases : public Scenario
{
  Context* m_ctx = nullptr;
  Fixture m_fixture;
  size_t m_workIndex = 0;
  std::vector< uint32_t > m_quests;
  ShopJourney m_plan;
  Bot* m_bot = nullptr;
  Bot::Rewards m_rewards;   // what the character must own now
  Json m_inventory;         // and where exactly

  static constexpr uint32_t GearStorage = 1000;

  // -- bookkeeping checked against the received state ---------------------------

  void verify( const std::string& what )
  {
    expectState( *m_bot, m_rewards, m_workIndex, m_inventory, m_quests, what );
  }

  void loginAgain( const std::string& name )
  {
    m_bot = &m_ctx->spawn( name );
    m_bot->loginViaLobby( m_ctx->server().relogin( m_fixture ), m_fixture.name );
    verify( "state after the fresh login as " + name );
  }

  void relogin( const std::string& name )
  {
    m_bot->logout();
    loginAgain( name );
  }

  void expectGil( uint32_t gil, const std::string& what )
  {
    expect( gilOf( m_rewards ) == gil, what + ": expected " + std::to_string( gil ) + " gil, bookkeeping says " + std::to_string( gilOf( m_rewards ) ) );
  }

  void openShop( const ShopRoute& stop ) { m_bot->openGilShop( stop.shop.layoutId, stop.shop.eventId ); }

  // Sell the single item in `key`; the shop re-lists afterwards.
  void sell( uint32_t shopId, const std::string& key, uint32_t item, uint32_t gil )
  {
    const auto [ storage, slot ] = splitKey( key );
    expect( m_inventory.contains( key ) && m_inventory.at( key ).at( "id" ) == item && m_inventory.at( key ).at( "count" ) == 1,
            "one " + std::to_string( item ) + " sits in " + key + " before the sale" );
    // The previous command's re-list must have arrived; the sale names the current listing.
    m_bot->waitScene( shopId, 40, "gil-shop listing before the sale" );
    m_bot->sellShopItem( storage, slot, item );
    addItem( m_rewards, item, -1 );
    addGil( m_rewards, static_cast< int >( gil ) );
    m_inventory.erase( key );
    setGil( m_inventory, gilOf( m_rewards ) );
    verify( "rewards and layout after selling " + std::to_string( item ) );
  }

  // Buy a listing; exactly one new stack appears and nothing else moves. Returns its slot key.
  std::string buy( const ShopListing& listing, uint32_t quantity )
  {
    m_bot->buyShopItem( listing.shopId, listing.item, quantity );
    setNewItem( m_rewards, listing.item, quantity );
    addGil( m_rewards, -static_cast< int >( listing.price * quantity ) );
    Json state;
    try
    {
      state = m_bot->expectRewards( m_rewards, m_workIndex );
    }
    catch( const Timeout& )
    {
      throw Failure( "rewards after buying " + std::to_string( listing.item ) + " differ; expected " + describe( m_rewards ) +
                     ", received " + describe( Bot::rewardValues( m_bot->snapshot(), m_workIndex ) ) );
    }
    const auto purchased = Bot::inventory( state );
    auto existing = m_inventory;
    setGil( existing, gilOf( m_rewards ) );
    std::vector< std::string > added;
    for( const auto& [ key, row ] : purchased.items() )
      if( !existing.contains( key ) )
        added.push_back( key );
    expect( added.size() == 1, "a purchase adds exactly one stack (added " + std::to_string( added.size() ) + ")" );
    const auto& row = purchased.at( added[ 0 ] );
    expect( row.at( "id" ) == listing.item && row.at( "count" ) == quantity, "the new stack is the bought item in the bought quantity" );
    auto rest = purchased;
    rest.erase( added[ 0 ] );
    expect( rest == existing, "nothing but the purse and the new stack changed on purchase" );
    m_inventory = purchased;
    m_ctx->log( "bought " + std::to_string( quantity ) + "x " + std::to_string( listing.item ) + " for " +
                std::to_string( listing.price * quantity ) + " gil into " + added[ 0 ] );
    return added[ 0 ];
  }

  // Acknowledged only; the following relogin proves it.
  void unequip( uint32_t gearSlot, const std::string& destination, uint32_t item )
  {
    const auto [ storage, slot ] = splitKey( destination );
    m_bot->requestItemUnequip( gearSlot, storage, slot, item );
    m_inventory.erase( Bot::slotKey( GearStorage, gearSlot ) );
    m_inventory[ destination ] = slotRow( storage, slot, item, 1 );
    setNewItem( m_rewards, item, 1 );
  }

  void equip( const std::string& key, uint32_t item, uint32_t gearSlot )
  {
    const auto row = m_inventory.at( key );
    m_bot->requestShopItemEquip( row.at( "storage" ), row.at( "slot" ), item, gearSlot );
    m_inventory.erase( key );
    m_inventory[ Bot::slotKey( GearStorage, gearSlot ) ] = slotRow( GearStorage, gearSlot, item, 1 );
    addItem( m_rewards, item, -1 );
  }

  // The single bag stack of an item, which must hold exactly one.
  std::string singleBagStack( uint32_t item )
  {
    const auto matches = bagStacks( m_inventory, item );
    expect( matches.size() == 1 && matches[ 0 ].second.at( "count" ) == 1, "exactly one " + std::to_string( item ) + " in the bags" );
    return matches[ 0 ].first;
  }

  // Walk to another vendor while a fresh observer standing there watches the arrival.
  void walkToVendor( const ShopRoute& stop, const std::string& observerName, double timeout )
  {
    CharacterOptions options;
    options.position = stop.route.back();
    auto& observer = m_ctx->spawnCharacter( observerName, options );
    const auto actor = Bot::entity( m_bot->snapshot() );
    m_bot->walkRoute( stop.route, 6.0f, timeout );
    observer.waitState( [ & ]( const Json& s ) {
      const auto* row = Bot::actor( s, actor );
      return row && dist( row->at( "position" ).get< Point >(), stop.route.back() ) < 0.15;
    }, observerName + " sees the shopper arrive", 30 );
    observer.logout();
  }

  // Buy one piece, relogin, equip it into its (empty) gear slot, relogin.
  void buyAndEquip( const ShopRoute& stop, const ShopListing& listing, const std::string& label )
  {
    openShop( stop );
    const auto key = buy( listing, 1 );
    m_bot->exitGilShop( stop.shop.eventId );
    relogin( "shop-" + label + "-equipment-purchased" );
    expect( !m_inventory.contains( Bot::slotKey( GearStorage, listing.gearSlot() ) ), "the " + label + " gear slot is empty" );
    equip( key, listing.item, listing.gearSlot() );
    relogin( "shop-" + label + "-equipment-equipped" );
  }

  void run( Context& ctx ) override
  {
    m_ctx = &ctx;
    auto& data = ctx.data();
    const auto speaking = questJourney( data, Uldah::MotivationalSpeaking, Uldah::Territory );
    const auto gold = questJourney( data, Uldah::GilForGold, Uldah::Territory );
    m_workIndex = gold.workIndex;
    m_quests = { speaking.quest, gold.quest };
    m_plan = planShopJourney( data, Uldah::Territory, npcPlacement( data, Uldah::Territory, Uldah::StepsOfNaldQuestNpc ).position );
    const auto& plan = m_plan;
    ctx.log( "shop " + std::to_string( plan.shop.shop.eventId ) + " (" + std::to_string( static_cast< int >( plan.shop.length ) ) +
             " m): potion sells for " + std::to_string( plan.saleGil ) + ", buy " + std::to_string( plan.purchaseQuantity ) + "x " +
             std::to_string( plan.purchase.item ) + " at " + std::to_string( plan.purchase.price ) + ", equipment " +
             std::to_string( plan.equipment.item ) + "/" + std::to_string( plan.secondEquipment.item ) + "/" +
             std::to_string( plan.thirdEquipment.item ) + "; head " + std::to_string( plan.head.item ) + " at shop " +
             std::to_string( plan.headShop.shop.eventId ) + ", ear " + std::to_string( plan.ear.item ) + " at " +
             std::to_string( plan.earShop.shop.eventId ) + ", neck " + std::to_string( plan.neck.item ) + " and wrist " +
             std::to_string( plan.wrist.item ) + " at " + std::to_string( plan.neckShop.shop.eventId ) );

    // Earn the potions (and ethers, discarded again) by completing both quests.
    CharacterOptions options;
    options.position = speaking.route.front();
    auto& first = ctx.spawnCharacter( "shopper", options );
    m_fixture = ctx.fixture( first );
    m_rewards = first.rewardSnapshot( m_workIndex );
    m_bot = &earnQuestRewards( ctx, first, m_fixture, speaking, gold, m_rewards );
    {
      auto state = m_bot->snapshot();
      m_inventory = Bot::inventory( state );
      const auto ethers = bagStacks( m_inventory, GoldScenes::Ether );
      expect( ethers.size() == 1, "one ether stack to discard" );
      const auto& [ key, row ] = ethers[ 0 ];
      m_bot->discardItem( row.at( "storage" ), row.at( "slot" ), GoldScenes::Ether );
      m_inventory.erase( key );
      m_rewards.items.erase( GoldScenes::Ether );
      verify( "rewards after discarding the ethers" );
    }

    // Split the two potions so one can be sold; the split is proven by a fresh login.
    auto state = m_bot->snapshot();
    expect( state.at( "territory" ) == Uldah::Territory && dist( Bot::position( state ), plan.shop.route.front() ) < 0.15,
            "the shopper stands at the quest NPC the shop route starts from" );
    const auto potions = bagStacks( m_inventory, plan.saleItem );
    expect( potions.size() == 1 && potions[ 0 ].second.at( "count" ) == 2, "two potions in one stack" );
    const auto& [ potionKey, potionRow ] = potions[ 0 ];
    const auto potionSplit = lastEmptyBagSlot( m_inventory );
    {
      const auto [ storage, slot ] = splitKey( potionSplit );
      m_inventory[ potionKey ][ "count" ] = 1;
      m_inventory[ potionSplit ] = slotRow( storage, slot, plan.saleItem, 1 );
      m_bot->requestItemSplit( potionRow.at( "storage" ), potionRow.at( "slot" ), storage, slot, plan.saleItem, 2, 1 );
      relogin( "shop-split-reloaded" );
    }

    // Walk to the vendor, watched by an independent client standing there.
    CharacterOptions observerOptions;
    observerOptions.position = plan.shop.route.back();
    auto& observer = ctx.spawnCharacter( "shop-observer", observerOptions );
    const auto actor = Bot::entity( m_bot->snapshot() );
    m_bot->walkRoute( plan.shop.route, 6.0f, 180 );
    observer.waitState( [ & ]( const Json& s ) {
      const auto* row = Bot::actor( s, actor );
      return row && dist( row->at( "position" ).get< Point >(), plan.shop.route.back() ) < 0.15;
    }, "shop arrival observed by independent client", 30 );
    expect( dist( plan.shop.route.back(), plan.shop.shop.position ) <= 2, "the route ends within interaction range of the vendor" );

    // Sell one potion, buy the consumable stack, use one and let the observer receive the effect.
    openShop( plan.shop );
    sell( plan.shop.shop.eventId, potionSplit, plan.saleItem, plan.saleGil );
    const auto vfxKey = buy( plan.purchase, plan.purchaseQuantity );
    m_bot->exitGilShop( plan.shop.shop.eventId );
    const auto [ vfxStorage, vfxSlot ] = splitKey( vfxKey );
    // The client's item-action request builder is bound to this consumable (InventoryActions.cpp).
    expect( plan.purchase.item == 5890, "the cheapest consumable is the shop VFX item the client can use" );
    const auto used = m_bot->useShopVfxItem( vfxStorage, vfxSlot, plan.purchaseQuantity );
    expect( used.request > 0, "the item use carries a request id" );
    const Json expectedEffect{ { "source", actor }, { "target", actor }, { "action", plan.purchase.item }, { "kind", 1 },
                               { "request", 0 }, { "result", 0 },
                               { "effects", Json::array( { Json{ { "type", 54 }, { "value", plan.itemActionArg }, { "flag", 0 }, { "args", { 0, 0, 0 } } } } ) },
                               { "source_effects", Json::array() } };
    expect( used.effect == expectedEffect, "the item action effect is exactly the item's VFX: received " + used.effect.dump() );
    const auto observerEffect = observer.waitState( [ & ]( const Json& s ) {
      for( const auto& row : s.at( "combat" ).at( "effects" ) )
        if( row == used.effect ) return true;
      return false;
    }, "independently received exact shop VFX item effect" );
    expect( observerEffect.at( "phase" ) == "ready" && observerEffect.at( "gm_rank" ) == 0, "the observer is an ordinary player" );
    verify( "rewards unchanged by the item use" );

    m_bot->logout();
    observer.waitState( [ & ]( const Json& s ) { return Bot::actor( s, actor ) == nullptr; }, "shopper session cleanup", 30 );
    observer.logout();
    loginAgain( "shop-reloaded" );

    // The stack survived a login unchanged; split it into three single items, each proven by a login.
    {
      const auto firstEmpty = lastEmptyBagSlot( m_inventory );
      const auto [ storage, slot ] = splitKey( firstEmpty );
      m_bot->requestItemSplit( vfxStorage, vfxSlot, storage, slot, plan.purchase.item, 3, 1 );
      m_inventory[ vfxKey ][ "count" ] = 2;
      m_inventory[ firstEmpty ] = slotRow( storage, slot, plan.purchase.item, 1 );
      relogin( "shop-stack-reloaded-1" );
    }
    {
      const auto secondEmpty = lastEmptyBagSlot( m_inventory );
      const auto [ storage, slot ] = splitKey( secondEmpty );
      m_bot->requestItemSplit( vfxStorage, vfxSlot, storage, slot, plan.purchase.item, 2, 1 );
      m_inventory[ vfxKey ][ "count" ] = 1;
      m_inventory[ secondEmpty ] = slotRow( storage, slot, plan.purchase.item, 1 );
      relogin( "shop-stack-reloaded-2" );
    }

    // Liquidate the three singles and the remaining potion.
    const auto shopId = plan.shop.shop.eventId;
    openShop( plan.shop );
    const auto vfxStacks = bagStacks( m_inventory, plan.purchase.item );
    expect( vfxStacks.size() == 3, "three single consumables to sell" );
    for( const auto& [ key, row ] : vfxStacks )
    {
      expect( row.at( "count" ) == 1, "each consumable stack holds one" );
      sell( shopId, key, plan.purchase.item, plan.purchase.price );
    }
    sell( shopId, singleBagStack( plan.saleItem ), plan.saleItem, plan.saleGil );
    expectGil( 56, "after liquidating the consumables and the second potion" );

    // First equipment piece (legs): buy, swap it for the starter piece, resell it.
    const auto& legs = plan.equipment;
    const auto legsKey = buy( legs, 1 );
    m_bot->exitGilShop( shopId );
    relogin( "shop-equipment-reloaded" );
    const auto legsGearKey = Bot::slotKey( GearStorage, legs.gearSlot() );
    expect( m_inventory.at( legsGearKey ) == slotRow( GearStorage, legs.gearSlot(), plan.starterLegs, 1 ), "the starter legs are equipped" );
    unequip( legs.gearSlot(), lastEmptyBagSlot( m_inventory ), plan.starterLegs );
    relogin( "shop-gear-empty-reloaded" );
    equip( legsKey, legs.item, legs.gearSlot() );
    relogin( "shop-gear-equipped-reloaded" );
    const auto legsSaleKey = lastEmptyBagSlot( m_inventory );
    unequip( legs.gearSlot(), legsSaleKey, legs.item );
    relogin( "shop-purchased-leg-unequipped" );
    openShop( plan.shop );
    sell( shopId, legsSaleKey, legs.item, legs.price );
    relogin( "shop-purchased-leg-sold" );   // logs out with the shop window open
    expectGil( 56, "after reselling the legs" );

    // Second piece (feet), the same way.
    const auto& feet = plan.secondEquipment;
    openShop( plan.shop );
    const auto feetKey = buy( feet, 1 );
    m_bot->exitGilShop( shopId );
    relogin( "shop-second-equipment-purchased" );
    const auto feetGearKey = Bot::slotKey( GearStorage, feet.gearSlot() );
    expect( m_inventory.at( feetGearKey ) == slotRow( GearStorage, feet.gearSlot(), plan.starterFeet, 1 ), "the starter feet are equipped" );
    unequip( feet.gearSlot(), lastEmptyBagSlot( m_inventory ), plan.starterFeet );
    relogin( "shop-second-gear-empty" );
    equip( feetKey, feet.item, feet.gearSlot() );
    relogin( "shop-second-gear-equipped" );
    const auto feetSaleKey = lastEmptyBagSlot( m_inventory );
    unequip( feet.gearSlot(), feetSaleKey, feet.item );
    relogin( "shop-purchased-feet-unequipped" );
    openShop( plan.shop );
    sell( shopId, feetSaleKey, feet.item, feet.price );
    relogin( "shop-purchased-feet-sold" );   // shop window open
    expectGil( 56, "after reselling the feet" );

    // The starter legs fund the third piece (body).
    openShop( plan.shop );
    sell( shopId, singleBagStack( plan.starterLegs ), plan.starterLegs, plan.starterLegsGil );
    relogin( "shop-starter-leg-sold" );   // shop window open
    expectGil( 101, "after selling the starter legs" );
    const auto& body = plan.thirdEquipment;
    openShop( plan.shop );
    const auto bodyKey = buy( body, 1 );
    m_bot->exitGilShop( shopId );
    relogin( "shop-third-equipment-purchased" );
    const auto bodyGearKey = Bot::slotKey( GearStorage, body.gearSlot() );
    expect( m_inventory.at( bodyGearKey ) == slotRow( GearStorage, body.gearSlot(), plan.starterBody, 1 ), "the starter body is equipped" );
    unequip( body.gearSlot(), lastEmptyBagSlot( m_inventory ), plan.starterBody );
    relogin( "shop-third-gear-empty" );
    equip( bodyKey, body.item, body.gearSlot() );
    relogin( "shop-third-gear-equipped" );
    // Gil cannot be moved like an item; the attempt is acknowledged and changes nothing.
    m_bot->requestCurrencyMoveRejection( gilOf( m_rewards ) );
    relogin( "shop-currency-move-rejected" );

    // The starter body funds the head piece at another vendor.
    openShop( plan.shop );
    sell( shopId, singleBagStack( plan.starterBody ), plan.starterBody, plan.starterBodyGil );
    relogin( "shop-starter-body-sold" );   // shop window open
    expectGil( 101, "after selling the starter body" );
    walkToVendor( plan.headShop, "head-shop-observer", 90 );
    buyAndEquip( plan.headShop, plan.head, "head" );

    // The starter feet fund the ear piece at the next vendor.
    openShop( plan.headShop );
    sell( plan.headShop.shop.eventId, singleBagStack( plan.starterFeet ), plan.starterFeet, plan.starterFeetGil );
    relogin( "shop-starter-feet-sold" );   // shop window open
    expectGil( 102, "after selling the starter feet" );
    walkToVendor( plan.earShop, "ear-shop-observer", 90 );
    buyAndEquip( plan.earShop, plan.ear, "ear" );

    // Liquidate the ear, head and body pieces into fixed bag-1 slots, then sell them.
    const std::vector< std::pair< const ShopListing*, uint32_t > > liquidation{ { &plan.ear, 24 }, { &plan.head, 23 }, { &body, 22 } };
    for( const auto& [ listing, slot ] : liquidation )
    {
      unequip( listing->gearSlot(), Bot::slotKey( 1, slot ), listing->item );
      relogin( "shop-liquidation-unequipped-" + std::to_string( listing->gearSlot() ) );
    }
    openShop( plan.earShop );
    for( const auto& [ listing, slot ] : liquidation )
      sell( plan.earShop.shop.eventId, Bot::slotKey( 1, slot ), listing->item, listing->price );
    relogin( "shop-later-equipment-sold" );   // shop window open
    expectGil( 208, "after liquidating the ear, head and body pieces" );

    // Neck piece at the last vendor, resold from a fixed slot; then the wrist piece at the same vendor.
    walkToVendor( plan.neckShop, "neck-shop-observer", 60 );
    buyAndEquip( plan.neckShop, plan.neck, "neck" );
    const auto neckSaleKey = Bot::slotKey( 1, 21 );
    unequip( plan.neck.gearSlot(), neckSaleKey, plan.neck.item );
    relogin( "shop-neck-equipment-unequipped" );
    openShop( plan.neckShop );
    sell( plan.neckShop.shop.eventId, neckSaleKey, plan.neck.item, plan.neck.price );
    relogin( "shop-neck-equipment-sold" );   // shop window open
    expectGil( 208, "after reselling the neck piece" );
    expect( plan.wrist.shopId == plan.neckShop.shop.eventId, "the wrist piece is listed by the neck vendor" );
    buyAndEquip( plan.neckShop, plan.wrist, "wrist" );
    ctx.log( "journey complete; rewards " + describe( m_rewards ) );
    m_bot->logout();
  }
};

EXPOSE_SCENARIO( ShopPurchases );

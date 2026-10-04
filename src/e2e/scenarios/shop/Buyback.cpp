// Gil shop buyback as the real client sends it (capture of 2026-10-04): the
// five-result command [0, 3, index, count, unit price]. The sold item comes
// back for the sale price, phantom entries move nothing, the window stays open.
//
// A fresh character owns nothing to sell but its starter gear, so the body
// piece is unequipped first. Unequip acknowledgements are not mutation proof;
// a fresh login shows where the piece went.
#include "../../harness/Content.h"
#include "../../harness/Context.h"
#include "../../harness/Scenario.h"
#include <Common.h>

using namespace Sapphire::E2E;

class Buyback : public Scenario
{
  static std::map< std::string, Json > bagStacks( const Json& state, uint32_t item )
  {
    std::map< std::string, Json > rows;
    for( const auto& [ key, row ] : Bot::inventory( state ).items() )
      if( row.at( "storage" ).get< uint32_t >() <= 3 && row.at( "id" ) == item )
        rows[ key ] = row;
    return rows;
  }

  void run( Context& ctx ) override
  {
    auto& data = ctx.data();
    const auto start = npcPlacement( data, Uldah::Territory, Uldah::StepsOfNaldQuestNpc ).position;
    const auto shop = nearestGilShop( data, Uldah::Territory, start );
    ctx.log( "gil shop " + std::to_string( shop.shop.eventId ) + " at vendor " + std::to_string( shop.shop.layoutId ) );

    CharacterOptions options;
    options.position = shop.route.back();
    auto& player = ctx.spawnCharacter( "buyback-shopper", options );
    auto state = player.snapshot();
    const auto fixture = ctx.fixture( player );
    const auto inventory = Bot::inventory( state );
    expect( Bot::gil( state ) == 0, "a fresh character starts without gil" );

    const auto bodyKey = Bot::slotKey( 1000, Sapphire::Common::GearSetSlot::Body );
    expect( inventory.contains( bodyKey ), "the starter gear includes a body piece" );
    const uint32_t item = inventory.at( bodyKey ).at( "id" ).get< uint32_t >();
    const auto price = itemPrice( data, item );
    expect( bagStacks( state, item ).empty(), "the body piece is only equipped, not in a bag" );

    const auto destination = Bot::emptyBagSlot( inventory );
    const auto storage = std::stoul( destination.substr( 0, destination.find( ':' ) ) );
    const auto slot = std::stoul( destination.substr( destination.find( ':' ) + 1 ) );
    player.requestItemUnequip( Sapphire::Common::GearSetSlot::Body, storage, slot, item );
    player.logout( 10, true );

    auto& seller = ctx.spawn( "buyback-shopper-selling" );
    state = seller.loginViaLobby( ctx.server().relogin( fixture ), fixture.name );
    state = seller.waitState( []( const Json& s ) { return s.at( "rewards" ).at( "inventory_ready" ).get< bool >(); }, "inventory after relogin" );
    expect( Bot::inventory( state ).value( destination, Json::object() ).value( "id", 0u ) == item,
            "after a fresh login the body piece is in the bag slot it was unequipped to" );

    seller.openGilShop( shop.shop.layoutId, shop.shop.eventId );
    seller.sellShopItem( storage, slot, item );
    state = seller.waitState( [ & ]( const Json& s ) { return Bot::gil( s ) == price; }, "sale paid out" );
    expect( bagStacks( state, item ).empty(), "the sold piece left the bags" );

    // Buyback of a phantom entry: must re-list, must not move gil.
    state = seller.shopBuybackRequest( shop.shop.eventId, 5, 1, price );
    expect( Bot::gil( state ) == price, "a phantom buyback must not move gil" );

    seller.shopBuybackRequest( shop.shop.eventId, 0, 1, price );
    state = seller.waitState( [ & ]( const Json& s ) { return Bot::gil( s ) == 0; }, "buyback charged the sale price" );
    auto stacks = bagStacks( state, item );
    expect( stacks.size() == 1 && stacks.begin()->second.at( "count" ) == 1, "the bought-back piece is back in a bag" );

    // The entry is gone from the list: buying it back again must not move anything.
    state = seller.shopBuybackRequest( shop.shop.eventId, 0, 1, price );
    expect( Bot::gil( state ) == 0 && bagStacks( state, item ).size() == 1, "a repeated buyback must not move anything" );

    // The window still works normally afterwards.
    seller.exitGilShop( shop.shop.eventId );
    seller.openGilShop( shop.shop.layoutId, shop.shop.eventId );
    seller.exitGilShop( shop.shop.eventId );
    seller.logout( 10, true );

    // The item survives a fresh login as an ordinary bag item.
    auto& reloaded = ctx.spawn( "buyback-shopper-reloaded" );
    state = reloaded.loginViaLobby( ctx.server().relogin( fixture ), fixture.name );
    state = reloaded.waitState( []( const Json& s ) { return s.at( "rewards" ).at( "inventory_ready" ).get< bool >(); }, "inventory after fresh login" );
    expect( bagStacks( state, item ).size() == 1 && Bot::gil( state ) == 0, "the bought-back piece persisted" );
    reloaded.logout();
  }
};

EXPOSE_SCENARIO( Buyback );

#include "ShopJourney.h"
#include <algorithm>
#include <limits>
#include <optional>
#include <stdexcept>

namespace Sapphire::E2E
{
  namespace
  {
    struct Listing
    {
      ShopListing listing;
      uint8_t equipLevel = 0;
      uint8_t itemClass = 0;
      uint16_t action = 0;
    };

    // Every priced item a gil shop lists, with the Item fields the selection reads.
    std::vector< Listing > listings( GameData& data, uint32_t shopId )
    {
      auto shop = data.row< Excel::Shop >( shopId );
      if( !shop )
        throw std::runtime_error( "gil shop " + std::to_string( shopId ) + " has no Shop row" );
      std::vector< Listing > rows;
      for( uint32_t index = 0; index < std::size( shop->data().Item ); ++index )
      {
        auto shopItem = data.row< Excel::ShopItem >( shop->data().Item[ index ] );
        if( !shopItem )
          continue;
        const auto itemId = static_cast< uint32_t >( shopItem->data().ItemId );
        auto item = data.row< Excel::Item >( itemId );
        if( !item || !item->data().Price )
          continue;
        Listing row;
        row.listing = { shopId, index, itemId, item->data().Price, item->data().Slot, item->data().StackMax };
        row.equipLevel = item->data().EquipLevel;
        row.itemClass = item->data().Class;
        row.action = item->data().Action;
        rows.push_back( row );
      }
      return rows;
    }

    // Level-1 equipment anyone can wear: a single-stack item of an equip slot.
    bool wearable( const Listing& row )
    {
      return row.listing.stackMax == 1 && row.listing.sourceSlot > 0 && row.listing.sourceSlot <= 13 && row.equipLevel <= 1 &&
             row.itemClass == 0;
    }

    // Cheapest wearable of one slot that the funds cover, preferring the lower item id on a tie.
    std::optional< ShopListing > cheapestOfSlot( const std::vector< Listing >& rows, uint32_t slot, uint32_t funds )
    {
      std::optional< ShopListing > best;
      for( const auto& row : rows )
      {
        if( !wearable( row ) || row.listing.sourceSlot != slot || row.listing.price > funds )
          continue;
        if( !best || row.listing.price < best->price || ( row.listing.price == best->price && row.listing.item < best->item ) )
          best = row.listing;
      }
      return best;
    }

    struct RoutedListing
    {
      ShopRoute stop;
      ShopListing listing;
    };

    // Across all vendors: the cheapest wearable of a slot with a complete route
    // from `from`; ties go to the shorter walk, then the lower item id.
    RoutedListing cheapestRoutedOfSlot( GameData& data, uint16_t territory, const std::vector< GameData::GilShop >& vendors,
                                        uint32_t slot, uint32_t funds, const Point& from, const char* what )
    {
      std::optional< RoutedListing > best;
      for( const auto& vendor : vendors )
      {
        auto candidate = cheapestOfSlot( listings( data, vendor.eventId ), slot, funds );
        if( !candidate )
          continue;
        try
        {
          auto route = boundedRoute( data, territory, from, vendor.position );
          const auto length = data.routeLength( route );
          if( !best || candidate->price < best->listing.price ||
              ( candidate->price == best->listing.price && length < best->stop.length ) ||
              ( candidate->price == best->listing.price && length == best->stop.length && candidate->item < best->listing.item ) )
            best = RoutedListing{ { vendor, std::move( route ), length }, *candidate };
        }
        catch( const std::exception& )
        {
          // No complete corridor to this vendor; never pick a partial route.
        }
      }
      if( !best )
        throw std::runtime_error( std::string( "no complete affordable route to a vendor listing " ) + what + " equipment" );
      return *best;
    }
  }

  ShopJourney planShopJourney( GameData& data, uint16_t territory, const Point& start )
  {
    ShopJourney plan;
    plan.saleGil = itemPrice( data, plan.saleItem );
    plan.starterLegsGil = itemPrice( data, plan.starterLegs );
    plan.starterBodyGil = itemPrice( data, plan.starterBody );
    plan.starterFeetGil = itemPrice( data, plan.starterFeet );

    const auto vendors = data.gilShops( territory );
    plan.shop = nearestGilShop( data, territory, start );
    if( plan.shop.length > 500 )
      throw std::runtime_error( "the nearest gil shop is further than the 500 m walking budget" );
    const auto rows = listings( data, plan.shop.shop.eventId );

    // The potion's price funds the consumable; four potions' worth bounds the equipment candidates.
    constexpr std::array< uint32_t, 5 > starterItems{ 1601, 2983, 3520, 3296, 3750 };
    std::vector< ShopListing > equipmentCandidates;
    std::optional< ShopListing > purchase, equipment;
    for( const auto& row : rows )
    {
      const auto& listing = row.listing;
      if( wearable( row ) && listing.price <= plan.saleGil * 4u &&
          std::find( starterItems.begin(), starterItems.end(), listing.item ) == starterItems.end() )
      {
        equipmentCandidates.push_back( listing );
        if( !equipment || listing.price < equipment->price )
          equipment = listing;
      }
      if( listing.price <= plan.saleGil && ( !purchase || listing.price < purchase->price ) )
        purchase = listing;
    }
    if( !purchase )
      throw std::runtime_error( "the selected gil shop has no item the potion's price covers" );
    if( !equipment || equipment->sourceSlot < 2 )
      throw std::runtime_error( "the selected gil shop has no affordable level-1 equipment" );
    plan.purchase = *purchase;
    plan.equipment = *equipment;

    std::optional< ShopListing > second;
    for( const auto& candidate : equipmentCandidates )
      if( candidate.sourceSlot != plan.equipment.sourceSlot &&
          ( !second || candidate.price < second->price || ( candidate.price == second->price && candidate.item < second->item ) ) )
        second = candidate;
    if( !second || second->sourceSlot < 2 || second->price > plan.saleGil * 2u )
      throw std::runtime_error( "the selected gil shop has no second affordable equipment slot" );
    plan.secondEquipment = *second;

    // Funds after reselling both pieces and the starter legs: two potions plus the legs.
    const uint32_t thirdFunds = plan.saleGil * 2u + plan.starterLegsGil;
    std::optional< ShopListing > third;
    for( const auto& candidate : equipmentCandidates )
      if( candidate.sourceSlot != plan.equipment.sourceSlot && candidate.sourceSlot != plan.secondEquipment.sourceSlot &&
          candidate.price <= thirdFunds &&
          ( !third || candidate.price < third->price || ( candidate.price == third->price && candidate.item < third->item ) ) )
        third = candidate;
    if( !third || third->sourceSlot < 2 )
      throw std::runtime_error( "the selected gil shop has no third affordable equipment slot" );
    plan.thirdEquipment = *third;

    // Head (slot 3) after selling the starter body, ear (slot 9) after the starter
    // feet, neck (slot 10) after liquidating the third, head and ear pieces; wrist
    // (slot 11) at the neck vendor after reselling the neck piece.
    const uint32_t headFunds = thirdFunds - plan.thirdEquipment.price + plan.starterBodyGil;
    auto head = cheapestRoutedOfSlot( data, territory, vendors, 3, headFunds, plan.shop.shop.position, "head" );
    plan.headShop = head.stop;
    plan.head = head.listing;
    const uint32_t earFunds = headFunds - plan.head.price + plan.starterFeetGil;
    auto ear = cheapestRoutedOfSlot( data, territory, vendors, 9, earFunds, plan.headShop.shop.position, "ear" );
    plan.earShop = ear.stop;
    plan.ear = ear.listing;
    const uint32_t neckFunds = earFunds - plan.ear.price + plan.thirdEquipment.price + plan.head.price + plan.ear.price;
    auto neck = cheapestRoutedOfSlot( data, territory, vendors, 10, neckFunds, plan.earShop.shop.position, "neck" );
    plan.neckShop = neck.stop;
    plan.neck = neck.listing;
    const uint32_t wristFunds = neckFunds;
    auto wrist = cheapestOfSlot( listings( data, plan.neckShop.shop.eventId ), 11, wristFunds );
    if( !wrist )
      throw std::runtime_error( "the neck vendor lists no affordable wrist equipment" );
    plan.wrist = *wrist;

    // The consumable is bought as the largest stack the potion pays for.
    plan.purchaseQuantity = std::min< uint32_t >( plan.purchase.stackMax, plan.saleGil / plan.purchase.price );
    if( plan.purchaseQuantity < 2 || plan.purchaseQuantity > 99 )
      throw std::runtime_error( "the selected consumable lacks a bounded multi-quantity purchase" );
    auto purchasedItem = data.row< Excel::Item >( plan.purchase.item );
    auto itemAction = data.row< Excel::ItemAction >( purchasedItem->data().Action );
    if( !itemAction )
      throw std::runtime_error( "the selected consumable has no ItemAction row" );
    plan.itemActionRow = purchasedItem->data().Action;
    plan.itemActionType = itemAction->data().Action;
    plan.itemActionArg = itemAction->data().Calcu0Arg[ 0 ];
    return plan;
  }
}

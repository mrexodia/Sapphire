#include "ShopMgr.h"

#include <Exd/ExdData.h>
#include <Actor/Player.h>
#include <Inventory/Item.h>
#include <Common.h>
#include <Service.h>
#include <limits>

using namespace Sapphire;
using namespace Sapphire::World::Manager;

void ShopMgr::cacheShop( uint32_t shopId )
{
  auto& exdData = Common::Service< Data::ExdData >::ref();
  auto itemShopList = exdData.getRows< Excel::Shop >();
  uint8_t count = 0;
  for( const auto& [ itemShop, shop ] : itemShopList )
  {
    if( shopId == itemShop )
    {
      for( auto shopItemId : shop->data().Item )
      {
        auto shopItem = exdData.getRow< Excel::ShopItem >( shopItemId );
        if( !shopItem )
          continue;

        auto item = exdData.getRow< Excel::Item >( shopItem->data().ItemId );
        if( !item || item->data().Price == 0 )
          continue;
        
        if( count >= 40 )
          break;
        
        m_shopItemPrices[ shopId ][ count ] = item->data().Price;
        count++;
      }
      Logger::debug( "ShopMgr: cached itemShop {0} with {1} items", shopId, count );
      break;
    }
  }
}

uint32_t ShopMgr::getShopItemPrices( uint32_t shopId, uint8_t index )
{
  if( index >= 40 )
    return 0;

  auto it = m_shopItemPrices.find( shopId );
  if( it != m_shopItemPrices.end() )
  {
    return it->second[ index ];
  }
  else
  {
    cacheShop( shopId );
    return getShopItemPrices( shopId, index );
  }

}

bool ShopMgr::purchaseGilShopItem( Entity::Player& player, uint32_t shopId, uint16_t itemId, uint32_t quantity )
{
  if( quantity == 0 )
    return false;

  auto& exdData = Common::Service< Data::ExdData >::ref();
  auto shop = exdData.getRow< Excel::Shop >( shopId );
  bool listed = false;
  if( shop )
  {
    for( auto shopItemId : shop->data().Item )
    {
      auto shopItem = exdData.getRow< Excel::ShopItem >( shopItemId );
      if( shopItem && shopItem->data().ItemId == itemId )
      {
        listed = true;
        break;
      }
    }
  }
  if( !listed )
    return false;

  auto item = exdData.getRow< Excel::Item >( itemId );
  if( !item )
    return false;

  const uint64_t total = static_cast< uint64_t >( item->data().Price ) * quantity;
  if( total > std::numeric_limits< uint32_t >::max() )
    return false;
  const auto price = static_cast< uint32_t >( total );

  if( player.getCurrency( Common::CurrencyType::Gil ) < price )
    return false;

  if( !player.addItem( itemId, quantity ) )
    return false;

  player.removeCurrency( Common::CurrencyType::Gil, price );

  return true;
}

bool ShopMgr::sellGilShopItem( Entity::Player& player, uint16_t container, uint8_t fromSlot, uint16_t itemId, uint32_t quantity )
{
  auto& exdData = Common::Service< Data::ExdData >::ref();

  auto item = exdData.getRow< Excel::Item >( itemId );
  if( !item )
    return false;

  auto payback = ( item->data().Price ) * quantity;

  auto inventoryItem = player.getItemAt( container, fromSlot );

  // todo: adding stack remove
  if( quantity != 1 || !inventoryItem || inventoryItem->getId() != itemId )
    return false;

  player.discardItem( ( Common::InventoryType )container, fromSlot );
  player.addSoldItem( itemId, quantity );

  player.addCurrency( Common::CurrencyType::Gil, payback );

  return true;
}

bool ShopMgr::buybackGilShopItem( Entity::Player& player, uint32_t index, uint32_t quantity )
{
  auto& soldItems = *player.getSoldItems();
  if( quantity == 0 || index >= soldItems.size() )
    return false;

  auto& entry = soldItems[ index ];
  const auto itemId = entry.first;
  if( quantity > entry.second )
    return false;

  auto& exdData = Common::Service< Data::ExdData >::ref();
  auto item = exdData.getRow< Excel::Item >( itemId );
  if( !item )
    return false;

  // The window shows the same unit price the sale paid out, so buying back is gil-neutral.
  const uint64_t total = static_cast< uint64_t >( item->data().Price ) * quantity;
  if( total > std::numeric_limits< uint32_t >::max() )
    return false;
  const auto price = static_cast< uint32_t >( total );

  if( player.getCurrency( Common::CurrencyType::Gil ) < price )
    return false;

  if( !player.addItem( itemId, quantity ) )
    return false;

  player.removeCurrency( Common::CurrencyType::Gil, price );

  if( quantity == entry.second )
    soldItems.erase( soldItems.begin() + index );
  else
    entry.second -= static_cast< uint8_t >( quantity );

  return true;
}

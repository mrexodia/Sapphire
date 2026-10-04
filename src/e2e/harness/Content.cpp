#include "Content.h"
#include <limits>
#include <stdexcept>

namespace Sapphire::E2E
{
  ShopRoute nearestGilShop( GameData& data, uint16_t territory, const Point& from )
  {
    ShopRoute best;
    best.length = std::numeric_limits< double >::infinity();
    for( const auto& shop : data.gilShops( territory ) )
    {
      try
      {
        auto route = data.route( territory, from, shop.position );
        const auto length = data.routeLength( route );
        if( length < best.length || ( length == best.length && shop.eventId < best.shop.eventId ) )
          best = { shop, std::move( route ), length };
      }
      catch( const std::exception& )
      {
        // No complete corridor to this vendor; never pick a partial route.
      }
    }
    if( best.route.empty() )
      throw std::runtime_error( "no gil shop with a complete walking route in territory " + std::to_string( territory ) );
    return best;
  }

  GameData::LevelRow npcPlacement( GameData& data, uint16_t territory, uint32_t baseId )
  {
    for( const auto& level : data.levels( territory ) )
      if( level.baseId == baseId )
        return level;
    throw std::runtime_error( "NPC " + std::to_string( baseId ) + " has no placement in territory " + std::to_string( territory ) );
  }

  uint32_t itemPrice( GameData& data, uint32_t itemId )
  {
    auto item = data.row< Excel::Item >( itemId );
    if( !item || !item->data().Price )
      throw std::runtime_error( "item " + std::to_string( itemId ) + " has no gil price" );
    return item->data().Price;
  }
}

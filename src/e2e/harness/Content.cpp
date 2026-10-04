#include "Content.h"
#include <cmath>
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

  std::vector< Point > boundedRoute( GameData& data, uint16_t territory, const Point& from, const Point& to, double maxLength )
  {
    auto route = data.route( territory, from, to );
    if( route.size() < 2 )
      throw std::runtime_error( "route has fewer than two waypoints" );
    double length = 0;
    for( size_t i = 1; i < route.size(); ++i )
    {
      const double step = std::sqrt( std::pow( route[ i ][ 0 ] - route[ i - 1 ][ 0 ], 2 ) + std::pow( route[ i ][ 1 ] - route[ i - 1 ][ 1 ], 2 ) +
                                     std::pow( route[ i ][ 2 ] - route[ i - 1 ][ 2 ], 2 ) );
      if( !std::isfinite( step ) || step > 2 )
        throw std::runtime_error( "route contains an unsupported jump" );
      length += step;
    }
    if( length > maxLength )
      throw std::runtime_error( "route of " + std::to_string( length ) + " m exceeds the " + std::to_string( maxLength ) + " m budget" );
    return route;
  }

  QuestJourney questJourney( GameData& data, uint32_t questId, uint16_t territory )
  {
    auto quest = data.row< Excel::Quest >( questId );
    if( !quest )
      throw std::runtime_error( "quest " + std::to_string( questId ) + " is missing from the game data" );
    const auto& q = quest->data();
    QuestJourney journey;
    journey.quest = questId;
    journey.level = q.ClassLevel;
    for( size_t i = 0; i < journey.previousQuests.size(); ++i )
      journey.previousQuests[ i ] = q.PrevQuest[ i ];
    journey.gil = q.Reward.Gil;
    auto growth = data.row< Excel::ParamGrow >( q.ClassLevel );
    if( !growth )
      throw std::runtime_error( "quest " + std::to_string( questId ) + " has no ParamGrow row for level " + std::to_string( q.ClassLevel ) );
    // The world pays quest exp as the level's event exp scaled by the quest's bonus percentage.
    journey.exp = ( q.Reward.ExpBonus * growth->data().BaseExp * growth->data().EventExpRate ) / 100;
    auto startingClass = data.row< Excel::ClassJob >( 1 );
    if( !startingClass )
      throw std::runtime_error( "ClassJob row 1 (Gladiator) is missing" );
    journey.classJob = 1;
    journey.workIndex = static_cast< size_t >( startingClass->data().WorkIndex );
    for( size_t i = 0; i < std::size( q.Reward.Item ); ++i )
      if( q.Reward.Item[ i ] )
        journey.items.push_back( { q.Reward.Item[ i ], q.Reward.ItemNum[ i ] } );
    for( size_t i = 0; i < std::size( q.Reward.OptionalItem ); ++i )
      if( q.Reward.OptionalItem[ i ] )
        journey.optionalItems.push_back( { q.Reward.OptionalItem[ i ], q.Reward.OptionalItemNum[ i ] } );

    // Exactly one placement per NPC, so the route endpoints name the actors to talk to.
    for( auto [ role, baseId ] : { std::pair{ "giver", q.Client }, std::pair{ "recipient", q.Finish } } )
    {
      size_t placements = 0;
      for( const auto& level : data.levels( territory ) )
        placements += level.baseId == baseId;
      if( placements != 1 )
        throw std::runtime_error( std::string( "quest " ) + std::to_string( questId ) + " " + role + " NPC " + std::to_string( baseId ) +
                                  " has " + std::to_string( placements ) + " placements in territory " + std::to_string( territory ) );
    }
    journey.giver = npcPlacement( data, territory, q.Client );
    journey.recipient = npcPlacement( data, territory, q.Finish );
    journey.route = boundedRoute( data, territory, journey.giver.position, journey.recipient.position );
    journey.routeLength = data.routeLength( journey.route );
    return journey;
  }
}

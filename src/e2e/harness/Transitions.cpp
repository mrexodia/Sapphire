#include "Transitions.h"
#include "Content.h"
#include <DetourNavMeshQuery.h>
#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace Sapphire::E2E
{
  static double horizontal( const Point& a, const Point& b )
  {
    return std::hypot( a[ 0 ] - b[ 0 ], a[ 2 ] - b[ 2 ] );
  }

  static void require( bool condition, const std::string& what )
  {
    if( !condition )
      throw std::runtime_error( what );
  }

  Point walkableSurface( GameData& data, uint16_t territory, const Point& point, const Point& extents )
  {
    dtNavMeshQuery query;
    require( !dtStatusFailed( query.init( data.navi( territory ).getNavMesh(), 4096 ) ), "navigation query unavailable" );
    dtQueryFilter filter;
    filter.setIncludeFlags( 0xffff );
    dtPolyRef ref = 0;
    Point nearest{};
    const auto status = query.findNearestPoly( point.data(), extents.data(), &filter, &ref, nearest.data() );
    require( !dtStatusFailed( status ) && ref, "no walkable surface near " + std::to_string( point[ 0 ] ) + ", " +
                                              std::to_string( point[ 1 ] ) + ", " + std::to_string( point[ 2 ] ) +
                                              " in territory " + std::to_string( territory ) );
    return nearest;
  }

  // An enabled ordinary box exit with one destination pop range and a yaw-only transform.
  static Transition transition( GameData& data, uint16_t territory, uint32_t exitId, uint32_t expectedPop )
  {
    const auto& object = data.object( territory, exitId );
    require( object.kind == LayoutObject::Kind::ExitRange, "layout object " + std::to_string( exitId ) + " is not an exit" );
    require( object.enabled && object.shape == 1 && object.exitType == 1,
             "exit " + std::to_string( exitId ) + " is not an enabled ordinary box exit" );
    require( object.targetPop == expectedPop, "exit " + std::to_string( exitId ) + " no longer lands on pop " + std::to_string( expectedPop ) );
    require( std::abs( object.rotation[ 0 ] ) <= 0.0001f && std::abs( object.rotation[ 2 ] ) <= 0.0001f,
             "exit " + std::to_string( exitId ) + " has an unsupported transform" );
    for( const auto scale : object.scale )
      require( scale > 0 && scale <= 100, "exit " + std::to_string( exitId ) + " has an unsupported scale" );
    Transition result;
    result.exit = object.asExit();
    std::vector< const LayoutObject* > pops;
    for( const auto* pop : data.objects( object.targetTerritory, LayoutObject::Kind::PopRange ) )
      if( pop->id == object.targetPop )
        pops.push_back( pop );
    require( pops.size() == 1, "exit " + std::to_string( exitId ) + " must resolve exactly one destination pop range" );
    result.destination = *pops[ 0 ];
    return result;
  }

  // The walkable point at an exit's centre, inside a rotation-independent inner volume.
  static Point exitCore( GameData& data, const Testing::ExitRange& exit )
  {
    const auto radius = std::min( exit.scale[ 0 ], exit.scale[ 2 ] ) * 0.5f;
    const auto core = walkableSurface( data, exit.territory, exit.position, { radius, exit.scale[ 1 ] * 0.5f, radius } );
    require( horizontal( core, exit.position ) <= radius && std::abs( core[ 1 ] - exit.position[ 1 ] ) <= exit.scale[ 1 ] * 0.5f,
             "walkable endpoint of exit " + std::to_string( exit.id ) + " is outside its conservative volume" );
    return core;
  }

  static Discovery discovery( GameData& data, const LayoutObject& range )
  {
    auto territory = data.row< Excel::TerritoryType >( range.territory );
    auto map = territory ? data.row< Excel::Map >( territory->data().Map ) : nullptr;
    require( territory && map, "discovery map metadata unavailable for territory " + std::to_string( range.territory ) );
    const auto part = static_cast< uint32_t >( range.discoveryIndex );
    const auto flag = map->data().DiscoveryFlag;
    // A required map part that does not on its own complete the map.
    require( part < 32 && ( flag & ( uint32_t{ 1 } << part ) ) && flag != ( uint32_t{ 1 } << part ),
             "map range " + std::to_string( range.id ) + " is not a required, non-completing map part" );
    auto growth = data.row< Excel::ParamGrow >( 1 );
    require( growth != nullptr, "level-one growth row unavailable" );
    Discovery result;
    result.range = range;
    result.mapId = territory->data().Map;
    result.partId = part;
    result.levelOneExp = static_cast< uint32_t >( growth->data().NextExp * 5 / 100 );
    return result;
  }

  static bool insideBox( const LayoutObject& box, const Point& point )
  {
    const auto dx = point[ 0 ] - box.position[ 0 ], dz = point[ 2 ] - box.position[ 2 ];
    const auto localX = std::cos( box.rotation[ 1 ] ) * dx - std::sin( box.rotation[ 1 ] ) * dz;
    const auto localZ = std::sin( box.rotation[ 1 ] ) * dx + std::cos( box.rotation[ 1 ] ) * dz;
    return std::abs( localX ) <= box.scale[ 0 ] * 0.5f && std::abs( localZ ) <= box.scale[ 2 ] * 0.5f &&
           std::abs( point[ 1 ] - box.position[ 1 ] ) <= box.scale[ 1 ] * 0.5f;
  }

  ZoningCatalog uldahCentralThanalanCrossing( GameData& data )
  {
    ZoningCatalog catalog;
    catalog.outbound = transition( data, Uldah::Territory, Zoning::OutboundExit, Zoning::OutboundPop );
    const auto& exit = catalog.outbound.exit;
    require( exit.targetTerritory == CentralThanalan::Territory, "exit " + std::to_string( exit.id ) + " does not lead to Central Thanalan" );

    // Approach from outside the full circumscribed box, whatever the yaw, onto real ground.
    const auto approachDistance = std::hypot( exit.scale[ 0 ], exit.scale[ 2 ] ) + 2;
    Point start = exit.position;
    start[ 0 ] -= static_cast< float >( std::cos( exit.rotation[ 1 ] ) * approachDistance );
    start[ 2 ] += static_cast< float >( std::sin( exit.rotation[ 1 ] ) * approachDistance );
    start = walkableSurface( data, exit.territory, start, { 1, 8, 1 } );
    require( horizontal( start, exit.position ) > std::hypot( exit.scale[ 0 ], exit.scale[ 2 ] ),
             "the approach to exit " + std::to_string( exit.id ) + " does not begin outside its volume" );
    catalog.route = data.route( exit.territory, start, exitCore( data, exit ) );
    catalog.routeLength = data.routeLength( catalog.route );

    // Arrival: exactly one enabled discovery cylinder contains the destination pop range.
    const auto arrival = catalog.outbound.destination.position;
    std::vector< const LayoutObject* > cylinders;
    for( const auto* range : data.objects( exit.targetTerritory, LayoutObject::Kind::MapRange ) )
    {
      if( !range->enabled || !range->discoveryEnabled || range->shape != 3 )
        continue;
      if( range->scale[ 0 ] <= 0 || range->scale[ 1 ] <= 0 || range->scale[ 2 ] <= 0 )
        continue;
      if( horizontal( arrival, range->position ) <= std::min( range->scale[ 0 ], range->scale[ 2 ] ) * 0.5f &&
          std::abs( arrival[ 1 ] - range->position[ 1 ] ) <= range->scale[ 1 ] * 0.5f )
        cylinders.push_back( range );
    }
    require( cylinders.size() == 1, "the arrival must lie in exactly one enabled discovery cylinder" );
    require( cylinders[ 0 ]->id == Zoning::ArrivalDiscovery && cylinders[ 0 ]->discoveryIndex == 1,
             "the arrival discovery is no longer range " + std::to_string( Zoning::ArrivalDiscovery ) + " part 1" );
    catalog.arrival = discovery( data, *cylinders[ 0 ] );

    // The second discovery: a distinct box reached on foot from the arrival.
    const auto& box = data.object( exit.targetTerritory, Zoning::SecondDiscovery );
    require( box.kind == LayoutObject::Kind::MapRange && box.enabled && box.discoveryEnabled && box.shape == 1 && box.discoveryIndex == 3,
             "map range " + std::to_string( Zoning::SecondDiscovery ) + " is not the enabled discovery box of part 3" );
    require( box.scale[ 0 ] > 0 && box.scale[ 1 ] > 0 && box.scale[ 2 ] > 0 &&
             horizontal( arrival, box.position ) > std::hypot( box.scale[ 0 ], box.scale[ 2 ] ),
             "the second discovery box is not distinct from the arrival" );
    catalog.second = discovery( data, box );
    const auto discoveryStart = walkableSurface( data, exit.targetTerritory, arrival, { 8, 80, 8 } );
    const auto discoveryEnd = walkableSurface( data, exit.targetTerritory, box.position, { 8, 80, 8 } );
    require( insideBox( box, discoveryEnd ), "the second discovery route does not end inside its box" );
    catalog.second.route = data.route( exit.targetTerritory, discoveryStart, discoveryEnd );
    catalog.second.routeLength = data.routeLength( catalog.second.route );
    require( catalog.second.route.size() >= 2 && catalog.second.route.size() <= 1000 && catalog.second.routeLength > 0,
             "invalid second discovery route" );
    const auto& first = catalog.second.route.front();
    require( std::hypot( first[ 0 ] - arrival[ 0 ], first[ 1 ] - arrival[ 1 ], first[ 2 ] - arrival[ 2 ] ) <= 0.15,
             "the second discovery route does not start at the arrival" );

    // Back into Ul'dah from the second discovery box.
    catalog.back = transition( data, exit.targetTerritory, Zoning::ReturnExit, Zoning::ReturnPop );
    require( catalog.back.exit.targetTerritory == Uldah::Territory, "the reverse exit does not lead back to Ul'dah" );
    catalog.returnRoute = data.route( exit.targetTerritory, discoveryEnd, exitCore( data, catalog.back.exit ) );
    catalog.returnRouteLength = data.routeLength( catalog.returnRoute );
    require( std::isfinite( catalog.returnRouteLength ) && catalog.returnRouteLength > 5 && catalog.returnRouteLength <= 500,
             "the return route is incomplete or exceeds the distance budget" );
    return catalog;
  }

  Homepoint homepoint( GameData& data, uint32_t aetheryte )
  {
    auto row = data.row< Excel::Aetheryte >( aetheryte );
    require( row != nullptr, "aetheryte " + std::to_string( aetheryte ) + " is missing" );
    Homepoint result;
    result.aetheryte = aetheryte;
    result.territory = row->data().TerritoryType;
    const auto pop = row->data().PopRange[ 0 ];
    require( result.territory != 0 && pop != 0, "aetheryte " + std::to_string( aetheryte ) + " has no pop range" );
    std::vector< const LayoutObject* > matches;
    for( const auto* object : data.objects( result.territory, LayoutObject::Kind::PopRange ) )
      if( object->id == pop )
        matches.push_back( object );
    require( matches.size() == 1, "homepoint pop range " + std::to_string( pop ) + " must resolve exactly once" );
    result.popRange = *matches[ 0 ];
    return result;
  }
}

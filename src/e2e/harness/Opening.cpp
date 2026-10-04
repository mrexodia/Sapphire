#include "Opening.h"
#include <cmath>
#include <map>
#include <stdexcept>

namespace Sapphire::E2E
{
  using namespace UldahOpening;

  static void require( bool condition, const std::string& what )
  {
    if( !condition )
      throw std::runtime_error( what );
  }

  static double dist( const Point& a, const Point& b )
  {
    return std::hypot( a[ 0 ] - b[ 0 ], a[ 1 ] - b[ 1 ], a[ 2 ] - b[ 2 ] );
  }

  static GameData::LevelRow level( GameData& data, uint32_t id, uint32_t expectedBase )
  {
    auto row = data.row< Excel::Level >( id );
    require( row && row->data().TerritoryType == Territory, "Level row " + std::to_string( id ) + " is not in territory 182" );
    require( expectedBase == 0 || row->data().BaseId == expectedBase,
             "Level row " + std::to_string( id ) + " no longer places NPC " + std::to_string( expectedBase ) );
    const auto& level = row->data();
    return { id, level.BaseId, level.EventHandler, { level.TransX, level.TransY, level.TransZ }, level.RotY };
  }

  // The event ranges the opening script knows and the Level rows it returns the player to.
  static OpeningRange openingRange( GameData& data, uint32_t id, bool mustBeClosed )
  {
    static const std::map< uint32_t, uint32_t > returnLevels{
      { 4101537, 4101685 }, { 4101525, 4101680 }, { 4101535, 4101681 }, { 4101587, 4101691 } };
    const auto& object = data.object( Territory, id );
    require( object.kind == LayoutObject::Kind::EventRange && object.shape == 1,
             "opening range " + std::to_string( id ) + " is not a box event range" );
    require( !mustBeClosed || !object.enabled, "opening exit range " + std::to_string( id ) + " is not closed in the layout" );
    OpeningRange result;
    result.range = object;
    result.returnLevel = returnLevels.at( id );
    result.returnPosition = level( data, result.returnLevel, 0 ).position;
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

  OpeningCatalog uldahOpening( GameData& data )
  {
    auto quest = data.row< Excel::Quest >( ComingToUldah );
    require( quest && quest->data().Client == WymondBase && quest->data().Finish == MomodiBase,
             "Coming to Ul'dah no longer binds Wymond and Momodi" );
    OpeningCatalog catalog;
    catalog.giver = level( data, WymondLayout, WymondBase );
    catalog.recipient = level( data, MomodiLayout, MomodiBase );
    auto growth = data.row< Excel::ParamGrow >( quest->data().ClassLevel );
    require( growth != nullptr, "Coming to Ul'dah level data missing" );
    catalog.rewardExp = quest->data().Reward.ExpBonus * growth->data().BaseExp * growth->data().EventExpRate / 100;
    catalog.rewardGil = quest->data().Reward.Gil;

    for( const auto item : RingItems )
    {
      auto row = data.row< Excel::Item >( item );
      require( row && row->data().Slot == 12 && row->data().StackMax == 1, "opening ring " + std::to_string( item ) + " is not a single ring item" );
    }
    // The other closed exits must still be closed boxes; the scenario only walks into one of them.
    for( const auto id : { 4101525u, 4101535u } )
      openingRange( data, id, true );
    catalog.closedExit = openingRange( data, ClosedExit, true );
    catalog.arrivalArea = openingRange( data, ArrivalArea, false );

    // Routes use the instance's own navmesh; the start is where a new character stands.
    catalog.rangeRoute = data.route( Territory, Start, catalog.closedExit.range.position );
    catalog.rangeRouteLength = data.routeLength( catalog.rangeRoute );
    require( insideBox( catalog.closedExit.range, catalog.rangeRoute.back() ), "the closed-exit route does not end inside the range box" );
    require( dist( catalog.rangeRoute.back(), catalog.closedExit.range.position ) <= 0.25, "the closed-exit route does not reach the range centre" );
    require( dist( catalog.closedExit.returnPosition, catalog.rangeRoute.back() ) >= 1, "the closed exit's return spot must be distinct from the range" );
    catalog.approachRoute = data.route( Territory, Start, catalog.giver.position );
    catalog.approachRouteLength = data.routeLength( catalog.approachRoute );
    require( dist( catalog.approachRoute.front(), Start ) <= 1 && dist( catalog.approachRoute.back(), catalog.giver.position ) <= 2,
             "the approach does not bind the start position and Wymond" );
    return catalog;
  }
}

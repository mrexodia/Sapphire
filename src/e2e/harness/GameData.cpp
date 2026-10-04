#include "GameData.h"
#include "NavigationRoute.h"
#include <GameData.h>
#include <File.h>
#include <datReader/DatCategories/bg/lgb.h>
#include <cmath>
#include <cstring>
#include <stdexcept>

namespace Sapphire::E2E
{
  static Point toPoint( const vec3& v ) { return { v.x, v.y, v.z }; }

  Testing::ExitRange LayoutObject::asExit() const
  {
    if( kind != Kind::ExitRange )
      throw std::logic_error( "layout object " + std::to_string( id ) + " is not an exit range" );
    Testing::ExitRange exit;
    exit.id = id;
    exit.territory = territory;
    exit.enabled = enabled;
    exit.shape = shape;
    exit.exitType = exitType;
    exit.targetTerritory = targetTerritory;
    exit.targetPop = targetPop;
    exit.position = position;
    exit.rotation = rotation;
    exit.scale = scale;
    return exit;
  }

  GameData::GameData( std::filesystem::path dataPath, std::filesystem::path meshPath ) :
    m_dataPath( std::move( dataPath ) ), m_meshPath( std::move( meshPath ) )
  {
    if( !m_exd.init( m_dataPath.string() ) )
      throw std::runtime_error( "cannot initialize game data at " + m_dataPath.string() + " (DataPath in global.ini)" );
  }

  std::string GameData::internalName( uint16_t territory )
  {
    auto row = m_exd.getRow< Excel::TerritoryType >( territory );
    if( !row )
      throw std::runtime_error( "territory " + std::to_string( territory ) + " has no TerritoryType row" );
    return row->getString( row->data().Name );
  }

  const std::vector< LayoutObject >& GameData::layout( uint16_t territory )
  {
    auto cached = m_layouts.find( territory );
    if( cached != m_layouts.end() )
      return cached->second;

    auto row = m_exd.getRow< Excel::TerritoryType >( territory );
    if( !row )
      throw std::runtime_error( "territory " + std::to_string( territory ) + " has no TerritoryType row" );
    auto path = row->getString( row->data().LVB );
    const auto level = path.find( "/level/" );
    if( level == std::string::npos )
      throw std::runtime_error( "territory " + std::to_string( territory ) + " has no level path" );
    path = "bg/" + path.substr( 0, level ) + "/level/";

    std::vector< LayoutObject > objects;
    LGB_GROUP::AssetTypeFilter filter = []( eAssetType type )
    {
      return type == eAssetType::EventNPC || type == eAssetType::EventObject || type == eAssetType::ExitRange ||
             type == eAssetType::PopRange || type == eAssetType::MapRange || type == eAssetType::EventRange;
    };
    // The same layers the world's InstanceObjectCache reads; planner is optional.
    for( const auto* name : { "bg", "planmap", "planevent", "planner" } )
    {
      const auto filePath = path + name + ".lgb";
      if( !m_exd.getGameData()->doesFileExist( filePath ) )
      {
        if( std::string( name ) == "planner" )
          continue;
        throw std::runtime_error( "missing level layer " + filePath );
      }
      auto section = m_exd.getGameData()->getFile( filePath )->access_data_sections().at( 0 );
      if( section.size() < sizeof( LGB_FILE_HEADER ) || std::memcmp( section.data(), "LGB1", 4 ) ||
          std::memcmp( section.data() + 12, "LGP1", 4 ) )
      {
        if( std::string( name ) == "planner" )
          continue;
        throw std::runtime_error( "unsupported level layer " + filePath );
      }
      LGB_FILE lgb( section.data(), name, &filter );
      for( const auto& group : lgb.groups )
        for( const auto& entry : group.entries )
        {
          LayoutObject object;
          object.id = entry->header.InstanceID;
          object.territory = territory;
          object.position = toPoint( entry->header.Transformation.Translation );
          object.rotation = toPoint( entry->header.Transformation.Rotation );
          object.scale = toPoint( entry->header.Transformation.Scale );
          switch( entry->getType() )
          {
            case eAssetType::EventNPC:
              object.kind = LayoutObject::Kind::EventNpc;
              object.baseId = std::static_pointer_cast< EventNPCEntry >( entry )->header.BaseId;
              break;
            case eAssetType::EventObject:
              object.kind = LayoutObject::Kind::EventObject;
              object.baseId = std::static_pointer_cast< EventObjectEntry >( entry )->header.BaseId;
              break;
            case eAssetType::ExitRange:
            {
              const auto& exit = std::static_pointer_cast< ExitRangeEntry >( entry )->header;
              object.kind = LayoutObject::Kind::ExitRange;
              object.enabled = exit.triggerBoxType.enabled != 0;
              object.shape = static_cast< int >( exit.triggerBoxType.triggerBoxShape );
              object.exitType = static_cast< int >( exit.exitType );
              object.targetTerritory = exit.destTerritoryType;
              object.targetPop = exit.destInstanceObjectId;
              break;
            }
            case eAssetType::PopRange:
              object.kind = LayoutObject::Kind::PopRange;
              break;
            case eAssetType::MapRange:
            {
              const auto& range = std::static_pointer_cast< MapRangeEntry >( entry )->header;
              object.kind = LayoutObject::Kind::MapRange;
              object.enabled = range.triggerBoxType.enabled != 0;
              object.shape = static_cast< int >( range.triggerBoxType.triggerBoxShape );
              object.discoveryEnabled = range.discoveryEnabled != 0;
              object.discoveryIndex = range.discoveryIndex;
              break;
            }
            case eAssetType::EventRange:
            {
              const auto& range = std::static_pointer_cast< EventRangeEntry >( entry )->header;
              object.kind = LayoutObject::Kind::EventRange;
              object.enabled = range.triggerBox.enabled != 0;
              object.shape = static_cast< int >( range.triggerBox.triggerBoxShape );
              break;
            }
            default:
              continue;
          }
          objects.push_back( object );
        }
    }
    return m_layouts[ territory ] = std::move( objects );
  }

  const LayoutObject& GameData::object( uint16_t territory, uint32_t id )
  {
    for( const auto& object : layout( territory ) )
      if( object.id == id )
        return object;
    throw std::runtime_error( "layout object " + std::to_string( id ) + " is not in territory " + std::to_string( territory ) );
  }

  std::vector< const LayoutObject* > GameData::objects( uint16_t territory, LayoutObject::Kind kind )
  {
    std::vector< const LayoutObject* > result;
    for( const auto& object : layout( territory ) )
      if( object.kind == kind )
        result.push_back( &object );
    return result;
  }

  Point GameData::levelPosition( uint32_t levelId )
  {
    auto row = m_exd.getRow< Excel::Level >( levelId );
    if( !row )
      throw std::runtime_error( "Level row " + std::to_string( levelId ) + " is missing" );
    return { row->data().TransX, row->data().TransY, row->data().TransZ };
  }

  const std::vector< GameData::LevelRow >& GameData::levels( uint16_t territory )
  {
    auto cached = m_levels.find( territory );
    if( cached != m_levels.end() )
      return cached->second;
    std::vector< LevelRow > rows;
    for( auto id : m_exd.getIdList< Excel::Level >() )
    {
      auto row = m_exd.getRow< Excel::Level >( id );
      if( !row || row->data().TerritoryType != territory )
        continue;
      const auto& level = row->data();
      rows.push_back( { id, level.BaseId, level.EventHandler, { level.TransX, level.TransY, level.TransZ }, level.RotY } );
    }
    return m_levels[ territory ] = std::move( rows );
  }

  std::vector< GameData::GilShop > GameData::gilShops( uint16_t territory )
  {
    std::vector< GilShop > shops;
    for( const auto& level : levels( territory ) )
    {
      auto npc = m_exd.getRow< Excel::ENpcBase >( level.baseId );
      if( !npc )
        continue;
      for( const auto& handler : npc->data().EventHandler )
        if( ( handler.EventHandler >> 16 ) == 4 )
          shops.push_back( { level.id, level.baseId, handler.EventHandler, level.position } );
    }
    return shops;
  }

  Common::Navi::NaviProvider& GameData::navi( uint16_t territory )
  {
    auto cached = m_navi.find( territory );
    if( cached != m_navi.end() )
      return *cached->second;
    const auto name = internalName( territory );
    auto provider = std::make_unique< Common::Navi::NaviProvider >( name );
    if( !provider->init( m_meshPath.string() ) )
      throw std::runtime_error( "no navmesh for " + name + " (territory " + std::to_string( territory ) + ") under " +
                                m_meshPath.string() + "; check MeshPath in world.ini" );
    return *( m_navi[ territory ] = std::move( provider ) );
  }

  std::vector< Point > GameData::route( uint16_t territory, const Point& from, const Point& to )
  {
    return Testing::navigationRoute( *navi( territory ).getNavMesh(), from, to );
  }

  double GameData::routeLength( const std::vector< Point >& route )
  {
    double length = 0;
    for( size_t i = 1; i < route.size(); ++i )
      length += std::sqrt( std::pow( route[ i ][ 0 ] - route[ i - 1 ][ 0 ], 2 ) + std::pow( route[ i ][ 1 ] - route[ i - 1 ][ 1 ], 2 ) +
                           std::pow( route[ i ][ 2 ] - route[ i - 1 ][ 2 ], 2 ) );
    return length;
  }
}

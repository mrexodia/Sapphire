#pragma once
// The game's own data as the server reads it: EXD sheets, territory layouts
// (LGB) and the navmeshes the world loaded. Scenarios resolve NPCs, shops,
// exits, ranges and walking routes from here instead of from catalog files.
#include <Exd/ExdData.h>
#include <Navi/NaviProvider.h>
#include <array>
#include <filesystem>
#include <map>
#include <memory>
#include <string>
#include <vector>
#include "../client/TransitionActions.h"

namespace Sapphire::E2E
{
  using Point = std::array< float, 3 >;

  struct LayoutObject
  {
    enum class Kind { EventNpc, EventObject, ExitRange, PopRange, MapRange, EventRange };
    Kind kind;
    uint32_t id = 0;         // instance (layout) id
    uint16_t territory = 0;
    Point position{}, rotation{}, scale{};
    uint32_t baseId = 0;     // ENpc / EObj base id
    bool enabled = false;    // trigger boxes
    int shape = 0;           // TriggerBoxShape: 1 box, 3 cylinder
    int exitType = 0;        // ExitRange
    uint16_t targetTerritory = 0;
    uint32_t targetPop = 0;
    bool discoveryEnabled = false;  // MapRange
    int discoveryIndex = 0;

    Testing::ExitRange asExit() const;
  };

  class GameData
  {
  public:
    GameData( std::filesystem::path dataPath, std::filesystem::path meshPath );

    Data::ExdData& exd() { return m_exd; }
    template< class Row > auto row( uint32_t id ) { return m_exd.getRow< Row >( id ); }

    // All event NPCs, objects and ranges of a territory's required layout layers.
    const std::vector< LayoutObject >& layout( uint16_t territory );
    const LayoutObject& object( uint16_t territory, uint32_t id );
    std::vector< const LayoutObject* > objects( uint16_t territory, LayoutObject::Kind kind );
    // Level-sheet position of an actor placement (Level row id = layout id).
    Point levelPosition( uint32_t levelId );
    struct LevelRow
    {
      uint32_t id = 0;        // layout id
      uint32_t baseId = 0;    // ENpc / EObj base id
      uint32_t eventHandler = 0;
      Point position{};
      float rotation = 0;
    };
    // Every Level row of a territory (one scan of the sheet, cached).
    const std::vector< LevelRow >& levels( uint16_t territory );
    // Gil shops (event handler type 4) an NPC of the territory offers.
    struct GilShop { uint32_t layoutId = 0, baseId = 0, eventId = 0; Point position{}; };
    std::vector< GilShop > gilShops( uint16_t territory );

    // The navmesh the world uses for a territory ("w1t1" etc. from TerritoryType).
    Common::Navi::NaviProvider& navi( uint16_t territory );
    std::string internalName( uint16_t territory );
    // The navmesh folder name for a territory, from its level path ("w1t1").
    std::string meshName( uint16_t territory );
    // A complete walkable route; throws when the corridor is incomplete.
    std::vector< Point > route( uint16_t territory, const Point& from, const Point& to );
    double routeLength( const std::vector< Point >& route );

  private:
    std::filesystem::path m_dataPath, m_meshPath;
    Data::ExdData m_exd;
    std::map< uint16_t, std::vector< LayoutObject > > m_layouts;
    std::map< uint16_t, std::vector< LevelRow > > m_levels;
    std::map< uint16_t, std::unique_ptr< Common::Navi::NaviProvider > > m_navi;
  };
}

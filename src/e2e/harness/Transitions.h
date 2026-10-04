#pragma once
// Zoning content resolved from the territory layouts and navmeshes: the exit
// the zoning scenarios cross from Ul'dah into Central Thanalan, its reverse,
// the walking approaches into both exit volumes, the map-discovery ranges on
// the far side and the homepoint pop range the Return action lands on. The
// ids name the content under test; every transform and route comes from the
// game data at run time, with the same selection rules the old transition
// catalog used.
#include "GameData.h"
#include <vector>

namespace Sapphire::E2E
{
  struct Transition
  {
    Testing::ExitRange exit;
    LayoutObject destination;       // the pop range in exit.targetTerritory the exit lands on
  };

  struct Discovery
  {
    LayoutObject range;             // the MapRange trigger box or cylinder
    uint32_t mapId = 0;             // Map of the range's territory
    uint32_t partId = 0;            // range.discoveryIndex
    uint32_t levelOneExp = 0;       // 5% of a level-one character's next-level EXP
    std::vector< Point > route;     // walked approach; empty when the arrival already lies inside
    double routeLength = 0;
  };

  struct ZoningCatalog
  {
    Transition outbound;            // Steps of Nald -> Central Thanalan
    std::vector< Point > route;     // from outside the exit volume into its conservative core
    double routeLength = 0;
    Discovery arrival;              // the cylinder around the arrival pop range (part 1)
    Discovery second;               // box 4204061 (part 3), walked from the arrival
    Transition back;                // Central Thanalan -> Steps of Nald
    std::vector< Point > returnRoute;  // from the second discovery box into the reverse exit
    double returnRouteLength = 0;
  };

  namespace Zoning
  {
    constexpr uint32_t OutboundExit = 2377056;     // Ul'dah gate into Central Thanalan
    constexpr uint32_t OutboundPop = 2372271;
    constexpr uint32_t ReturnExit = 2372269;       // the gate back into Ul'dah
    constexpr uint32_t ReturnPop = 2377058;
    constexpr uint32_t ArrivalDiscovery = 3643706; // part 1
    constexpr uint32_t SecondDiscovery = 4204061;  // part 3
  }

  ZoningCatalog uldahCentralThanalanCrossing( GameData& data );

  struct Homepoint
  {
    uint32_t aetheryte = 0;
    uint16_t territory = 0;
    LayoutObject popRange;
  };

  // Where a Return lands for a character bound to the aetheryte (Ul'dah: 9).
  Homepoint homepoint( GameData& data, uint32_t aetheryte = 9 );

  // The closest walkable point to `point` within `extents` on a territory's navmesh.
  Point walkableSurface( GameData& data, uint16_t territory, const Point& point, const Point& extents );
}

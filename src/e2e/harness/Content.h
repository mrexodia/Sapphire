#pragma once
// Content lookups scenarios share: which shop to use, where a quest's NPCs
// stand, how to walk there. Everything is resolved from the game data at run
// time; nothing is hard-coded beyond the ids that name the content under test.
#include "GameData.h"
#include <vector>

namespace Sapphire::E2E
{
  struct ShopRoute
  {
    GameData::GilShop shop;
    std::vector< Point > route;   // from the start position to the vendor
    double length = 0;
  };

  // The gil shop with the shortest complete walking route from `from` in the
  // territory; the Ul'dah scenarios start at the Steps of Nald quest NPC.
  ShopRoute nearestGilShop( GameData& data, uint16_t territory, const Point& from );

  // Where an NPC (ENpcBase id) stands in a territory, from the Level sheet.
  GameData::LevelRow npcPlacement( GameData& data, uint16_t territory, uint32_t baseId );

  // Unit price of an item, as the gil shop sells and buys it.
  uint32_t itemPrice( GameData& data, uint32_t itemId );

  namespace Uldah
  {
    constexpr uint16_t Territory = 130;            // Steps of Nald
    constexpr uint16_t OpeningTerritory = 182;     // the opening's instanced copy
    constexpr uint32_t StepsOfNaldQuestNpc = 1001289;  // the shop scenarios' walking start
  }
  namespace CentralThanalan
  {
    constexpr uint16_t Territory = 141;
  }
}

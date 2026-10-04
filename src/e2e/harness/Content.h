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

  // A complete walking route whose steps and total length stay within the
  // bounds the scenarios walk (no jumps over 2 m, at most `maxLength` m).
  std::vector< Point > boundedRoute( GameData& data, uint16_t territory, const Point& from, const Point& to,
                                     double maxLength = 500 );

  // A quest as the scenarios walk it: rewards from the Quest sheet, the giver
  // and recipient placements from the Level sheet and the route between them.
  struct QuestJourney
  {
    struct ItemReward { uint32_t id = 0, count = 0; };
    uint32_t quest = 0;
    uint16_t level = 0;                       // Quest.ClassLevel
    std::array< uint32_t, 3 > previousQuests{};
    uint8_t classJob = 1;                     // the fixtures are Gladiators
    size_t workIndex = 0;                     // ClassJob.WorkIndex: the exp array slot the client receives
    uint32_t exp = 0, gil = 0;
    std::vector< ItemReward > items, optionalItems;
    GameData::LevelRow giver, recipient;      // Level rows: id is the layout id to interact with
    std::vector< Point > route;               // giver to recipient
    double routeLength = 0;
  };
  QuestJourney questJourney( GameData& data, uint32_t questId, uint16_t territory );

  namespace Uldah
  {
    constexpr uint16_t Territory = 130;            // Steps of Nald
    constexpr uint16_t OpeningTerritory = 182;     // the opening's instanced copy
    constexpr uint32_t StepsOfNaldQuestNpc = 1001289;  // the shop scenarios' walking start
    constexpr uint32_t MotivationalSpeaking = 65686;   // SubWil001, first of the Steps of Nald chain
    constexpr uint32_t GilForGold = 65687;             // SubWil002, follows Motivational Speaking
  }
  namespace CentralThanalan
  {
    constexpr uint16_t Territory = 141;
  }
}

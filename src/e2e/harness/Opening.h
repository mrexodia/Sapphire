#pragma once
// The Ul'dah opening (the instanced Steps of Nald, territory 182) as the
// creation scenario drives it: the arrival-area and closed city-exit event
// ranges the opening script reacts to, the Level rows it warps the player back
// to, Wymond's placement for Coming to Ul'dah and the walking routes from the
// instance's start position. Ids name the content under test; transforms,
// positions and routes come from the game data at run time.
#include "GameData.h"
#include <array>
#include <vector>

namespace Sapphire::E2E
{
  namespace UldahOpening
  {
    constexpr uint16_t Territory = 182;
    constexpr uint32_t EventId = 1245187;
    constexpr uint32_t ComingToUldah = 66130;
    constexpr uint32_t WymondLayout = 3969639, WymondBase = 1003987;
    constexpr uint32_t MomodiLayout = 3969632, MomodiBase = 1003988;
    constexpr uint32_t ArrivalArea = 4101587;   // leaving it before Wymond was spoken to
    constexpr uint32_t ClosedExit = 4101537;    // a city exit the opening keeps shut
    constexpr uint32_t RangeScene = 20;         // Wymond's line for both ranges
    constexpr std::array< uint32_t, 4 > RingItems{ 4423, 4424, 4425, 4426 };
    constexpr Point Start{ 42.0f, 4.0f, -157.6f };  // where a new character stands
  }

  struct OpeningRange
  {
    LayoutObject range;
    uint32_t returnLevel = 0;      // Level row the script warps back to
    Point returnPosition{};
  };

  struct OpeningCatalog
  {
    OpeningRange arrivalArea;
    OpeningRange closedExit;
    std::vector< Point > rangeRoute;     // Start -> inside the closed exit's box
    double rangeRouteLength = 0;
    GameData::LevelRow giver;            // Wymond
    GameData::LevelRow recipient;        // Momodi
    std::vector< Point > approachRoute;  // Start -> Wymond
    double approachRouteLength = 0;
    uint32_t rewardExp = 0, rewardGil = 0;
  };

  OpeningCatalog uldahOpening( GameData& data );
}

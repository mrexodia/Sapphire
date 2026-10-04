#pragma once
#include "Protocol.h"
#include <array>
#include <cstdint>

namespace Sapphire::Testing
{
  // An exit range of the territory layout (LGB ExitRange entry).
  struct ExitRange
  {
    uint32_t id = 0;
    uint16_t territory = 0;
    bool enabled = false;
    int shape = 0;
    int exitType = 0;
    uint16_t targetTerritory = 0;
    uint32_t targetPop = 0;
    std::array< float, 3 > position{}, rotation{}, scale{};
  };

  // The client's zone-jump request for standing inside an enabled box exit.
  Bytes exitRangeRequest(uint16_t territory, const std::array<float, 3>& position, const ExitRange& exit);
}

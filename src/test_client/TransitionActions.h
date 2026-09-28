#pragma once
#include "Protocol.h"
#include <nlohmann/json.hpp>

namespace Sapphire::Testing
{
  Bytes exitRangeRequest(uint16_t territory, const std::array<float, 3>& position,
                         const nlohmann::json& exit);
}

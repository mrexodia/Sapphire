#pragma once
#include "Protocol.h"
#include <nlohmann/json.hpp>

namespace Sapphire::Testing
{
  Bytes returnHomepointRequest(uint32_t entity, uint16_t territory, uint8_t homepoint,
                               const nlohmann::json& actors);
}

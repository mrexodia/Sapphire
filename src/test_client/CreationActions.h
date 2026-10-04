#pragma once
#include "Protocol.h"
#include <string>
#include <array>
#include <nlohmann/json.hpp>

namespace Sapphire::Testing
{
  std::string canonicalUldahCreationPayload(uint8_t classJob);
  Bytes openingWithinRangeRequest(uint16_t territory, uint32_t eventId, uint32_t param,
                                  const std::array<float, 3>& current,
                                  const std::array<float, 3>& position);
  Bytes openingOutsideRangeRequest(uint16_t territory, uint32_t eventId, uint32_t param,
                                  const std::array<float, 3>& current,
                                  const std::array<float, 3>& position);
  Bytes centralThanalanDiscoveryRequest(uint16_t territory, uint32_t layoutId,
                                        const std::array<float, 3>& receivedPosition);
  Bytes characterDeleteRequest(uint32_t requestNumber, uint32_t clientTime,
                               const nlohmann::json& character, const std::string& expectedName);
}

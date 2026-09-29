#pragma once
#include "Protocol.h"
#include <string>
#include <array>

namespace Sapphire::Testing
{
  std::string canonicalUldahCreationPayload(uint8_t classJob);
  Bytes openingWithinRangeRequest(uint16_t territory, uint32_t eventId, uint32_t param,
                                  const std::array<float, 3>& current,
                                  const std::array<float, 3>& position);
  Bytes centralThanalanDiscoveryRequest(uint16_t territory, uint32_t layoutId,
                                        const std::array<float, 3>& receivedPosition);
}

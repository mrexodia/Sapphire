#pragma once
#include "Protocol.h"

namespace Sapphire::Testing
{
  // Gil shop scene-40 commands as the real client sends them (255-result returns).
  Bytes shopSaleReturn(uint32_t eventId, uint16_t storage, uint16_t slot, uint16_t itemId);
  Bytes shopPurchaseReturn(uint32_t eventId, uint16_t itemId, uint32_t quantity);
}

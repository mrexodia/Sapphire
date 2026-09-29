#pragma once
#include "Protocol.h"

namespace Sapphire::Testing
{
  Bytes shopSaleReturn(uint32_t eventId, uint16_t storage, uint16_t slot, uint16_t itemId);
  Bytes shopPurchaseReturn(uint32_t eventId);
  Bytes shopEquipmentPurchaseReturn(uint32_t eventId);
  Bytes shopSecondEquipmentPurchaseReturn(uint32_t eventId);
  Bytes shopThirdEquipmentPurchaseReturn(uint32_t eventId);
  Bytes shopHeadEquipmentPurchaseReturn(uint32_t eventId);
  Bytes shopEarEquipmentPurchaseReturn(uint32_t eventId);
}

#pragma once
#include "Protocol.h"
#include <nlohmann/json.hpp>

namespace Sapphire::Testing
{
  // Full-stack discard from an observed ordinary bag slot only. No state prediction.
  Bytes discardItemRequest(const nlohmann::json& rewards, uint32_t entity, uint32_t context,
                           uint32_t storage, uint32_t slot, uint32_t expectedItem);
  // Unequip one observed equipment stack to an empty ordinary bag slot.
  Bytes unequipItemRequest(const nlohmann::json& rewards, uint32_t entity, uint32_t context,
                           uint32_t gearSlot, uint32_t expectedItem,
                           uint32_t destinationStorage, uint32_t destinationSlot);
  // Whole stack to an observed empty ordinary bag slot. Receipt is NOT mutation proof.
  Bytes moveItemRequest(const nlohmann::json& rewards, uint32_t entity, uint32_t context,
                        uint32_t storage, uint32_t slot, uint32_t expectedItem,
                        uint32_t destinationStorage, uint32_t destinationSlot);
  // Swap two observed occupied ordinary bag slots. Receipt is NOT mutation proof.
  Bytes swapItemRequest(const nlohmann::json& rewards, uint32_t entity, uint32_t context,
                        uint32_t storage, uint32_t slot, uint32_t expectedItem,
                        uint32_t destinationStorage, uint32_t destinationSlot,
                        uint32_t expectedDestinationItem);
  // Split part of one observed stack into an observed empty ordinary bag slot.
  Bytes splitItemRequest(const nlohmann::json& rewards, uint32_t entity, uint32_t context,
                         uint32_t storage, uint32_t slot, uint32_t expectedItem,
                         uint32_t expectedCount, uint32_t splitCount,
                         uint32_t destinationStorage, uint32_t destinationSlot);
  // Merge one observed stack into another observed stack of the same item.
  Bytes mergeItemRequest(const nlohmann::json& rewards, uint32_t entity, uint32_t context,
                         uint32_t storage, uint32_t slot, uint32_t expectedItem,
                         uint32_t expectedCount, uint32_t destinationStorage,
                         uint32_t destinationSlot, uint32_t expectedDestinationCount);
}

#include "InventoryActions.h"
#include <Network/PacketDef/Zone/ClientZoneDef.h>

namespace Sapphire::Testing
{
  Bytes discardItemRequest(const nlohmann::json& rewards, uint32_t entity, uint32_t context,
                           uint32_t storage, uint32_t slot, uint32_t expectedItem)
  {
    if(storage > 3 || slot >= 25 || !expectedItem || !rewards.at("inventory_ready").get<bool>())
      throw ProtocolError("discard requires an observed item in an ordinary bag slot");
    const auto key = std::to_string(storage) + ":" + std::to_string(slot);
    const auto& inventory = rewards.at("inventory");
    if(!inventory.contains(key) || inventory.at(key).at("id") != expectedItem || inventory.at(key).at("count") == 0)
      throw ProtocolError("discard item identity does not match observed inventory");
    Wire::WorldPackets::Client::FFXIVIpcClientInventoryItemOperation p{};
    p.ContextId = context;
    p.OperationType = Common::ITEM_OPERATION_TYPE_DELETEITEM;
    p.SrcActorId = entity; p.SrcStorageId = storage; p.SrcContainerIndex = static_cast<int16_t>(slot);
    p.SrcStack = inventory.at(key).at("count"); p.SrcCatalogId = expectedItem;
    return objectBytes(p);
  }
  Bytes moveItemRequest(const nlohmann::json& rewards, uint32_t entity, uint32_t context,
                        uint32_t storage, uint32_t slot, uint32_t expectedItem,
                        uint32_t destinationStorage, uint32_t destinationSlot)
  {
    if(storage > 3 || destinationStorage > 3 || slot >= 25 || destinationSlot >= 25 ||
       (storage == destinationStorage && slot == destinationSlot) || !expectedItem ||
       !rewards.at("inventory_ready").get<bool>())
      throw ProtocolError("move requires distinct observed ordinary bag slots");
    const auto key = std::to_string(storage) + ":" + std::to_string(slot);
    const auto destination = std::to_string(destinationStorage) + ":" + std::to_string(destinationSlot);
    const auto& inventory = rewards.at("inventory");
    if(!inventory.contains(key) || inventory.at(key).at("id") != expectedItem || inventory.at(key).at("count") == 0 ||
       inventory.contains(destination))
      throw ProtocolError("move requires a matching observed source stack and empty destination");
    for(auto bag : {storage, destinationStorage})
      if(!rewards.at("containers").contains(std::to_string(bag)) ||
         rewards.at("containers").at(std::to_string(bag)) != true)
        throw ProtocolError("move requires complete source and destination snapshots");
    Wire::WorldPackets::Client::FFXIVIpcClientInventoryItemOperation p{};
    std::memset(&p, 0, sizeof(p));
    p.ContextId = context; p.OperationType = Common::ITEM_OPERATION_TYPE_MOVEITEM;
    p.SrcActorId = p.DstActorId = entity;
    p.SrcStorageId = storage; p.SrcContainerIndex = static_cast<int16_t>(slot);
    p.SrcStack = inventory.at(key).at("count"); p.SrcCatalogId = expectedItem;
    p.DstStorageId = destinationStorage; p.DstContainerIndex = static_cast<int16_t>(destinationSlot);
    // Destination is empty; do not request a split, merge or catalog replacement.
    return objectBytes(p);
  }
}

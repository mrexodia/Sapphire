#include "InventoryActions.h"
#include <Network/PacketDef/Zone/ClientZoneDef.h>
#include <cstring>

namespace Sapphire::Testing
{
  Bytes shopVfxItemRequest(const nlohmann::json& rewards, uint32_t entity, uint32_t request,
                           uint32_t storage, uint32_t slot, uint32_t expectedCount)
  {
    constexpr uint32_t supportedItem = 5890;
    if(!entity || !request || request > 65535 || storage > 3 || slot >= 25 ||
       expectedCount != 3 || !rewards.at("inventory_ready").get<bool>())
      throw ProtocolError("shop VFX item requires the exact received purchased stack");
    const auto key = std::to_string(storage) + ":" + std::to_string(slot);
    const auto& inventory = rewards.at("inventory");
    if(!inventory.contains(key) || inventory.at(key).at("id") != supportedItem ||
       inventory.at(key).at("count") != expectedCount)
      throw ProtocolError("shop VFX item identity/count does not match received inventory");
    Wire::WorldPackets::Client::FFXIVIpcActionRequest p{};
    std::memset(&p, 0, sizeof(p));
    p.ActionKind = Common::ACTION_KIND_ITEM; p.ActionKey = supportedItem;
    p.RequestId = request; p.Target = entity; p.Arg = (storage << 16) | slot;
    return objectBytes(p);
  }
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
  Bytes unequipItemRequest(const nlohmann::json& rewards, uint32_t entity, uint32_t context,
                           uint32_t gearSlot, uint32_t expectedItem,
                           uint32_t destinationStorage, uint32_t destinationSlot)
  {
    constexpr uint32_t gearStorage = 1000;
    if(gearSlot > Common::GearSetSlot::SoulCrystal || destinationStorage > 3 ||
       destinationSlot >= 25 || !expectedItem || !rewards.at("inventory_ready").get<bool>())
      throw ProtocolError("unequip requires an observed equipment slot and empty ordinary bag slot");
    const auto key = std::to_string(gearStorage) + ":" + std::to_string(gearSlot);
    const auto destination = std::to_string(destinationStorage) + ":" + std::to_string(destinationSlot);
    const auto& inventory = rewards.at("inventory");
    if(!inventory.contains(key) || inventory.at(key).at("id") != expectedItem ||
       inventory.at(key).at("count") == 0 || inventory.contains(destination))
      throw ProtocolError("unequip source/destination does not match observed inventory");
    for(auto storage : {gearStorage, destinationStorage})
      if(!rewards.at("containers").contains(std::to_string(storage)) ||
         rewards.at("containers").at(std::to_string(storage)) != true)
        throw ProtocolError("unequip requires complete equipment and destination snapshots");
    Wire::WorldPackets::Client::FFXIVIpcClientInventoryItemOperation p{};
    p.ContextId = context; p.OperationType = Common::ITEM_OPERATION_TYPE_MOVEITEM;
    p.SrcActorId = p.DstActorId = entity;
    p.SrcStorageId = gearStorage; p.SrcContainerIndex = static_cast<int16_t>(gearSlot);
    p.SrcStack = inventory.at(key).at("count"); p.SrcCatalogId = expectedItem;
    p.DstStorageId = destinationStorage; p.DstContainerIndex = static_cast<int16_t>(destinationSlot);
    return objectBytes(p);
  }
  Bytes equipShopItemRequest(const nlohmann::json& rewards, uint32_t entity, uint32_t context,
                             uint32_t storage, uint32_t slot, uint32_t expectedItem,
                             uint32_t gearSlot)
  {
    constexpr uint32_t gearStorage = 1000;
    const bool supported = (expectedItem == 3286 && gearSlot == Common::GearSetSlot::Legs) ||
                           (expectedItem == 3748 && gearSlot == Common::GearSetSlot::Feet) ||
                           (expectedItem == 2967 && gearSlot == Common::GearSetSlot::Body);
    if(rewards.value("class_job", 0u) != 1 || storage > 3 || slot >= 25 || !supported ||
       !rewards.at("inventory_ready").get<bool>())
      throw ProtocolError("shop equipment requires an exact supported received Gladiator item/slot");
    const auto key = std::to_string(storage) + ":" + std::to_string(slot);
    const auto destination = std::to_string(gearStorage) + ":" + std::to_string(gearSlot);
    const auto& inventory = rewards.at("inventory");
    if(!inventory.contains(key) || inventory.at(key).at("id") != expectedItem ||
       inventory.at(key).at("count") != 1 || inventory.contains(destination))
      throw ProtocolError("shop equipment source/destination does not match received inventory");
    for(auto container : {storage, gearStorage})
      if(!rewards.at("containers").contains(std::to_string(container)) ||
         rewards.at("containers").at(std::to_string(container)) != true)
        throw ProtocolError("shop equipment requires complete bag and equipment snapshots");
    Wire::WorldPackets::Client::FFXIVIpcClientInventoryItemOperation p{};
    p.ContextId = context; p.OperationType = Common::ITEM_OPERATION_TYPE_MOVEITEM;
    p.SrcActorId = p.DstActorId = entity;
    p.SrcStorageId = storage; p.SrcContainerIndex = static_cast<int16_t>(slot);
    p.SrcStack = 1; p.SrcCatalogId = expectedItem;
    p.DstStorageId = gearStorage; p.DstContainerIndex = static_cast<int16_t>(gearSlot);
    return objectBytes(p);
  }
  Bytes reequipStarterItemRequest(const nlohmann::json& rewards, uint32_t entity, uint32_t context,
                                  uint32_t storage, uint32_t slot, uint32_t expectedItem,
                                  uint32_t gearSlot)
  {
    constexpr uint32_t gearStorage = 1000;
    const auto classJob = rewards.value("class_job", 0u);
    uint32_t starterItem = 0;
    if(classJob == 1 || classJob == 2 || classJob == 7)
    {
      if(gearSlot == Common::GearSetSlot::MainHand)
        starterItem = classJob == 1 ? 1601u : classJob == 2 ? 1680u : 2055u;
      else if(gearSlot == Common::GearSetSlot::Body) starterItem = 2983;
      else if(gearSlot == Common::GearSetSlot::Hands) starterItem = 3520;
      else if(gearSlot == Common::GearSetSlot::Legs) starterItem = 3296;
      else if(gearSlot == Common::GearSetSlot::Feet) starterItem = 3750;
      else if((gearSlot == Common::GearSetSlot::Ring1 || gearSlot == Common::GearSetSlot::Ring2) &&
              (expectedItem == 4423 || expectedItem == 4424 ||
               expectedItem == 4425 || expectedItem == 4426))
        starterItem = expectedItem;
    }
    if(storage > 3 || slot >= 25 || !starterItem || expectedItem != starterItem ||
       !rewards.at("inventory_ready").get<bool>())
      throw ProtocolError("re-equip supports only matching Ul'dah starter equipment");
    const auto key = std::to_string(storage) + ":" + std::to_string(slot);
    const auto destination = std::to_string(gearStorage) + ":" + std::to_string(gearSlot);
    const auto& inventory = rewards.at("inventory");
    if(!inventory.contains(key) || inventory.at(key).at("id") != expectedItem ||
       inventory.at(key).at("count") != 1 || inventory.contains(destination))
      throw ProtocolError("re-equip source/destination does not match observed inventory");
    for(auto container : {storage, gearStorage})
      if(!rewards.at("containers").contains(std::to_string(container)) ||
         rewards.at("containers").at(std::to_string(container)) != true)
        throw ProtocolError("re-equip requires complete bag and equipment snapshots");
    Wire::WorldPackets::Client::FFXIVIpcClientInventoryItemOperation p{};
    p.ContextId = context; p.OperationType = Common::ITEM_OPERATION_TYPE_MOVEITEM;
    p.SrcActorId = p.DstActorId = entity;
    p.SrcStorageId = storage; p.SrcContainerIndex = static_cast<int16_t>(slot);
    p.SrcStack = 1; p.SrcCatalogId = starterItem;
    p.DstStorageId = gearStorage; p.DstContainerIndex = static_cast<int16_t>(gearSlot);
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
  Bytes swapItemRequest(const nlohmann::json& rewards, uint32_t entity, uint32_t context,
                        uint32_t storage, uint32_t slot, uint32_t expectedItem,
                        uint32_t destinationStorage, uint32_t destinationSlot,
                        uint32_t expectedDestinationItem)
  {
    if(storage > 3 || destinationStorage > 3 || slot >= 25 || destinationSlot >= 25 ||
       (storage == destinationStorage && slot == destinationSlot) || !expectedItem ||
       !expectedDestinationItem || expectedItem == expectedDestinationItem ||
       !rewards.at("inventory_ready").get<bool>())
      throw ProtocolError("swap requires distinct observed occupied ordinary bag slots");
    const auto key = std::to_string(storage) + ":" + std::to_string(slot);
    const auto destination = std::to_string(destinationStorage) + ":" + std::to_string(destinationSlot);
    const auto& inventory = rewards.at("inventory");
    if(!inventory.contains(key) || !inventory.contains(destination) ||
       inventory.at(key).at("id") != expectedItem || inventory.at(key).at("count") == 0 ||
       inventory.at(destination).at("id") != expectedDestinationItem ||
       inventory.at(destination).at("count") == 0)
      throw ProtocolError("swap requires matching observed source and destination stacks");
    for(auto bag : {storage, destinationStorage})
      if(!rewards.at("containers").contains(std::to_string(bag)) ||
         rewards.at("containers").at(std::to_string(bag)) != true)
        throw ProtocolError("swap requires complete source and destination snapshots");
    Wire::WorldPackets::Client::FFXIVIpcClientInventoryItemOperation p{};
    std::memset(&p, 0, sizeof(p));
    p.ContextId = context; p.OperationType = Common::ITEM_OPERATION_TYPE_SWAPITEM;
    p.SrcActorId = p.DstActorId = entity;
    p.SrcStorageId = storage; p.SrcContainerIndex = static_cast<int16_t>(slot);
    p.SrcStack = inventory.at(key).at("count"); p.SrcCatalogId = expectedItem;
    p.DstStorageId = destinationStorage; p.DstContainerIndex = static_cast<int16_t>(destinationSlot);
    p.DstStack = inventory.at(destination).at("count"); p.DstCatalogId = expectedDestinationItem;
    return objectBytes(p);
  }
  Bytes splitItemRequest(const nlohmann::json& rewards, uint32_t entity, uint32_t context,
                         uint32_t storage, uint32_t slot, uint32_t expectedItem,
                         uint32_t expectedCount, uint32_t splitCount,
                         uint32_t destinationStorage, uint32_t destinationSlot)
  {
    if(storage > 3 || destinationStorage > 3 || slot >= 25 || destinationSlot >= 25 ||
       (storage == destinationStorage && slot == destinationSlot) || !expectedItem ||
       !expectedCount || !splitCount || splitCount >= expectedCount ||
       !rewards.at("inventory_ready").get<bool>())
      throw ProtocolError("split requires a partial observed ordinary-bag stack and empty destination");
    const auto key = std::to_string(storage) + ":" + std::to_string(slot);
    const auto destination = std::to_string(destinationStorage) + ":" + std::to_string(destinationSlot);
    const auto& inventory = rewards.at("inventory");
    if(!inventory.contains(key) || inventory.at(key).at("id") != expectedItem ||
       inventory.at(key).at("count") != expectedCount || inventory.contains(destination))
      throw ProtocolError("split source/destination does not match observed inventory");
    for(auto bag : {storage, destinationStorage})
      if(!rewards.at("containers").contains(std::to_string(bag)) ||
         rewards.at("containers").at(std::to_string(bag)) != true)
        throw ProtocolError("split requires complete source and destination snapshots");
    Wire::WorldPackets::Client::FFXIVIpcClientInventoryItemOperation p{};
    p.ContextId = context; p.OperationType = Common::ITEM_OPERATION_TYPE_SPLITITEM;
    p.SrcActorId = p.DstActorId = entity;
    p.SrcStorageId = storage; p.SrcContainerIndex = static_cast<int16_t>(slot);
    p.SrcStack = expectedCount; p.SrcCatalogId = expectedItem;
    p.DstStorageId = destinationStorage; p.DstContainerIndex = static_cast<int16_t>(destinationSlot);
    p.DstStack = splitCount; p.DstCatalogId = expectedItem;
    return objectBytes(p);
  }
  Bytes mergeItemRequest(const nlohmann::json& rewards, uint32_t entity, uint32_t context,
                         uint32_t storage, uint32_t slot, uint32_t expectedItem,
                         uint32_t expectedCount, uint32_t destinationStorage,
                         uint32_t destinationSlot, uint32_t expectedDestinationCount)
  {
    if(storage > 3 || destinationStorage > 3 || slot >= 25 || destinationSlot >= 25 ||
       (storage == destinationStorage && slot == destinationSlot) || !expectedItem ||
       !expectedCount || !expectedDestinationCount || !rewards.at("inventory_ready").get<bool>())
      throw ProtocolError("merge requires distinct observed ordinary-bag stacks");
    const auto key = std::to_string(storage) + ":" + std::to_string(slot);
    const auto destination = std::to_string(destinationStorage) + ":" + std::to_string(destinationSlot);
    const auto& inventory = rewards.at("inventory");
    if(!inventory.contains(key) || !inventory.contains(destination) ||
       inventory.at(key).at("id") != expectedItem || inventory.at(key).at("count") != expectedCount ||
       inventory.at(destination).at("id") != expectedItem ||
       inventory.at(destination).at("count") != expectedDestinationCount)
      throw ProtocolError("merge stacks do not match observed inventory");
    for(auto bag : {storage, destinationStorage})
      if(!rewards.at("containers").contains(std::to_string(bag)) ||
         rewards.at("containers").at(std::to_string(bag)) != true)
        throw ProtocolError("merge requires complete source and destination snapshots");
    Wire::WorldPackets::Client::FFXIVIpcClientInventoryItemOperation p{};
    p.ContextId = context; p.OperationType = Common::ITEM_OPERATION_TYPE_MERGEITEM;
    p.SrcActorId = p.DstActorId = entity;
    p.SrcStorageId = storage; p.SrcContainerIndex = static_cast<int16_t>(slot);
    p.SrcStack = expectedCount; p.SrcCatalogId = expectedItem;
    p.DstStorageId = destinationStorage; p.DstContainerIndex = static_cast<int16_t>(destinationSlot);
    p.DstStack = expectedDestinationCount; p.DstCatalogId = expectedItem;
    return objectBytes(p);
  }
}

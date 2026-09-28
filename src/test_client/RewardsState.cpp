#include "RewardsState.h"
#include <Network/PacketDef/Zone/ServerZoneDef.h>
#include <Network/CommonActorControl.h>

namespace Sapphire::Testing
{
  namespace WS = Wire::WorldPackets::Server;
  RewardsState::RewardsState() : m_state{
    {"inventory", Json::object()}, {"containers", Json::object()}, {"inventory_ready", false},
    {"operation_batches", Json::array()},
    {"exp_by_index", Json::array()}, {"level_by_index", Json::array()}, {"exp_by_class", Json::object()},
    {"class_job", nullptr}, {"level", nullptr}} {}

  void RewardsState::stage(std::map<uint32_t, Slots>& pending, uint32_t context, uint32_t storage,
                           uint16_t index, uint32_t item, uint32_t count)
  {
    if(pending.size() >= 128 && !pending.count(context)) throw ProtocolError("inventory context limit exceeded");
    auto& slots = pending[context];
    if(slots.size() >= 256) throw ProtocolError("inventory snapshot too large");
    slots[std::to_string(storage) + ":" + std::to_string(index)] =
      {{"storage", storage}, {"slot", index}, {"id", item}, {"count", count}};
  }
  void RewardsState::apply(const Slots& slots)
  {
    for(const auto& [key, item] : slots)
    {
      if(item["id"] == 0 || item["count"] == 0) m_state["inventory"].erase(key);
      else m_state["inventory"][key] = item;
    }
  }
  bool RewardsState::receive(uint16_t opcode, const Bytes& data)
  {
    constexpr auto off = sizeof(Wire::FFXIVARR_IPC_HEADER);
    if(opcode == WS::FFXIVIpcNormalItem::_ServerIpcType)
    {
      auto p = readObject<WS::FFXIVIpcNormalItem>(data, off);
      stage(m_initial, p.contextId, p.item.storageId, p.item.containerIndex, p.item.catalogId, p.item.stack);
    }
    else if(opcode == WS::FFXIVIpcGilItem::_ServerIpcType)
    {
      auto p = readObject<WS::FFXIVIpcGilItem>(data, off);
      stage(m_initial, p.contextId, p.item.storageId, p.item.containerIndex, p.item.catalogId, p.item.stack);
    }
    else if(opcode == WS::FFXIVIpcItemSize::_ServerIpcType)
    {
      auto p = readObject<WS::FFXIVIpcItemSize>(data, off);
      if(p.size < 0 || p.size > 256) throw ProtocolError("invalid inventory snapshot count");
      auto it = m_initial.find(p.contextId);
      Slots slots = it == m_initial.end() ? Slots{} : it->second;
      if(slots.size() != static_cast<size_t>(p.size)) throw ProtocolError("incomplete inventory snapshot");
      for(const auto& entry : slots)
        if(entry.second["storage"] != p.storageId) throw ProtocolError("inventory context/storage mismatch");
      for(auto it = m_state["inventory"].begin(); it != m_state["inventory"].end();)
      {
        if(it.value()["storage"] == p.storageId) it = m_state["inventory"].erase(it);
        else ++it;
      }
      apply(slots); m_initial.erase(p.contextId);
      m_state["containers"][std::to_string(p.storageId)] = true;
      bool ready = true;
      for(auto id : {0, 1, 2, 3, 2000}) ready &= m_state["containers"].contains(std::to_string(id));
      m_state["inventory_ready"] = ready;
    }
    else if(opcode == WS::FFXIVIpcUpdateItem::_ServerIpcType)
    {
      auto p = readObject<WS::FFXIVIpcUpdateItem>(data, off);
      stage(m_updates, p.contextId, p.item.storageId, p.item.containerIndex, p.item.catalogId, p.item.stack);
    }
    else if(opcode == WS::FFXIVIpcItemOperation::_ServerIpcType)
    {
      auto p = readObject<WS::FFXIVIpcItemOperation>(data, off);
      if(p.operationType == Common::ITEM_OPERATION_TYPE_UPDATEITEM && p.srcContainerIndex >= 0)
        stage(m_updates, p.contextId, p.srcStorageId, p.srcContainerIndex, p.srcCatalogId, p.srcStack);
      else if(p.operationType == Common::ITEM_OPERATION_TYPE_CREATEITEM && p.dstContainerIndex >= 0)
        stage(m_updates, p.contextId, p.dstStorageId, p.dstContainerIndex, p.dstCatalogId, p.dstStack);
      else if(p.operationType == Common::ITEM_OPERATION_TYPE_DELETEITEM && p.srcContainerIndex >= 0)
        stage(m_updates, p.contextId, p.srcStorageId, p.srcContainerIndex, 0, 0);
      else throw ProtocolError("unsupported inventory operation");
    }
    else if(opcode == WS::FFXIVIpcItemOperationBatch::_ServerIpcType)
    {
      auto p = readObject<WS::FFXIVIpcItemOperationBatch>(data, off);
      auto& history = m_state["operation_batches"];
      history.push_back({{"context", p.contextId}, {"operation", p.operationType}, {"error", p.errorType}});
      if(history.size() > 128) history.erase(history.begin());
      // A batch without staged mutations is only an acknowledgement (moves use
      // this path in the current server). Never derive changes from a request.
      if(p.errorType) { m_updates.erase(p.contextId); throw ProtocolError("server rejected inventory operation"); }
      auto it = m_updates.find(p.contextId);
      if(it != m_updates.end()) { apply(it->second); m_updates.erase(it); }
    }
    else if(opcode == WS::FFXIVIpcPlayerStatus::_ServerIpcType)
    {
      auto p = readObject<WS::FFXIVIpcPlayerStatus>(data, off);
      m_state["class_job"] = p.ClassJob;
      m_state["exp_by_index"] = p.Exp;
      m_state["level_by_index"] = p.Lv;
      m_state["exp_by_class"] = Json::object();
    }
    else if(opcode == WS::FFXIVIpcPlayerStatusUpdate::_ServerIpcType)
    {
      auto p = readObject<WS::FFXIVIpcPlayerStatusUpdate>(data, off);
      m_state["class_job"] = p.ClassJob; m_state["level"] = p.Lv;
      m_state["exp_by_class"][std::to_string(p.ClassJob)] = p.Exp;
    }
    else if(opcode == WS::FFXIVIpcActorControlSelf::_ServerIpcType)
    {
      auto p = readObject<WS::FFXIVIpcActorControlSelf>(data, off);
      if(p.category != Network::ActorControl::UpdateUiExp) return false;
      m_state["exp_by_class"][std::to_string(p.param1)] = p.param2;
    }
    else return false;
    return true;
  }
}

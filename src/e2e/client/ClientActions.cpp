// Requests the client sends on behalf of a scenario. Each validates against the
// received state before publishing, exactly as the control protocol did, and
// never predicts the outcome: the Bot facade waits for the server's answer.
#include "Client.h"
#include "CreationActions.h"
#include "InventoryActions.h"
#include "ShopActions.h"
#include "RespawnActions.h"
#include "TransitionActions.h"
#include "PartyActions.h"
#include "ChatActions.h"
#include <Network/PacketDef/Zone/ClientZoneDef.h>
#include <cmath>

namespace Sapphire::Testing
{
  namespace WC = Wire::WorldPackets::Client;

  Json Client::snapshot() const
  {
    auto state = m_state; state["seq"] = m_seq; state["moving"] = m_moving;
    state["rewards"] = m_rewards.state(); state["combat"] = m_combat.state();
    state["combat"]["starting_action_guard_remaining_ms"] =
      startingActionGuardRemainingMs(m_startingActionReady, std::chrono::steady_clock::now());
    return state;
  }

  void Client::requireReady() const
  {
    if(m_state["phase"] != "ready") throw ProtocolError("action requires a world-ready bot");
  }

  void Client::requireIdle(const char* what) const
  {
    requireReady();
    if(m_moving || !m_state["event_id"].is_null())
      throw ProtocolError(std::string(what) + " requires an idle character (no movement or event in progress)");
  }

  void Client::requireScene(const SceneRef& scene) const
  {
    const auto& current = m_state["scene"];
    if(current.is_null() || current.at("token") != scene.token || current.at("event_id") != scene.eventId ||
       current.at("scene_id") != scene.sceneId)
      throw ProtocolError("scene identity/token mismatch: the scene changed before it was answered");
  }

  uint32_t Client::nextInventoryContext()
  {
    if(m_inventoryContext == 0xffffffff) throw ProtocolError("inventory context budget exhausted");
    return ++m_inventoryContext;
  }

  uint32_t Client::nextActionRequest()
  {
    if(m_actionRequest >= 65535) throw ProtocolError("action request budget exhausted");
    return ++m_actionRequest;
  }

  void Client::armDeadline(unsigned seconds, const char* reason)
  {
    if(seconds < 30 || seconds > 90) throw ProtocolError("deadline must be 30..90 seconds");
    m_deadline.expires_from_now(std::chrono::seconds(seconds));
    m_deadline.async_wait([self = shared_from_this(), reason](auto ec) { if(!ec) self->fail(reason); });
  }

  void Client::walkTo(const Point& destination, float speed)
  {
    requireReady();
    if(m_moving || !m_state["scene"].is_null()) throw ProtocolError("movement/event already in progress");
    float distance = 0;
    for(size_t i = 0; i < 3; ++i)
    {
      if(!std::isfinite(destination[i])) throw ProtocolError("nonfinite waypoint");
      distance += std::pow(destination[i] - m_predicted[i], 2);
    }
    if(!std::isfinite(speed) || speed <= 0 || speed > 6 || distance > 100 * 100)
      throw ProtocolError("waypoint exceeds 100m or speed outside (0,6]");
    m_destination = destination; m_speed = speed; m_moving = true;
    // Include the first tick in the cadence, also when chaining short waypoints.
    m_movement.expires_from_now(std::chrono::milliseconds(100));
    m_movement.async_wait([self = shared_from_this()](auto ec) {
      if(ec) return;
      try { self->moveStep(); } catch(const std::exception& e) { self->fail(e.what()); }
    });
  }

  void Client::say(const std::string& message)
  {
    requireReady();
    if(message.empty() || message.size() > 128 || message[0] == '!' ||
       !std::all_of(message.begin(), message.end(), [](unsigned char c) { return c >= 32 && c <= 126; }))
      throw ProtocolError("say requires 1..128 printable ASCII characters, not a debug command");
    WC::FFXIVIpcChatHandler p{};
    p.clientTimeValue = timeSeconds(); p.position.originEntityId = m_entity;
    std::copy(m_predicted.begin(), m_predicted.end(), p.position.pos);
    p.chatType = Common::ChatType::Say; copyText(p.message, message);
    sendZone(p._ServerIpcType, objectBytes(p));
  }

  void Client::logout()
  {
    requireReady();
    m_movement.cancel(); m_moving = false;
    // Sapphire 3.3 registers logoutHandler under StartLogoutCountdown.
    sendZone(WC::ClientZoneIpcType::StartLogoutCountdown, Bytes(8, 0)); phase("logging_out");
  }

  void Client::interact(uint32_t actorId, uint32_t eventId)
  {
    requireIdle("interact");
    WC::FFXIVIpcEventHandlerTalk p{};
    p.actorId = actorId; p.eventId = eventId;
    sendZone(p._ServerIpcType, objectBytes(p));
  }

  void Client::chooseScene(const SceneRef& scene, const std::vector<uint32_t>& results)
  {
    requireReady();
    requireScene(scene);
    if(results.empty() || results.size() > 8) throw ProtocolError("only explicit one to eight-result scenes supported");
    // The real client picks the packet by result count: two slots for ordinary
    // answers, eight for shop commands such as buyback.
    if(results.size() <= 2)
    {
      WC::FFXIVIpcReturnEventScene2 p{};
      p.handlerId = scene.eventId; p.sceneId = static_cast<uint16_t>(scene.sceneId); p.numOfResults = static_cast<uint8_t>(results.size());
      std::copy(results.begin(), results.end(), p.results);
      sendZone(p._ServerIpcType, objectBytes(p));
    }
    else
    {
      WC::FFXIVIpcReturnEventScene8 p{};
      p.handlerId = scene.eventId; p.sceneId = static_cast<uint16_t>(scene.sceneId); p.numOfResults = static_cast<uint8_t>(results.size());
      std::copy(results.begin(), results.end(), p.results);
      sendZone(p._ServerIpcType, objectBytes(p));
    }
    m_state["scene"] = nullptr;
  }

  void Client::startUldahOpening()
  {
    requireReady();
    if(m_moving || !m_state["event_id"].is_null() || !m_state["scene"].is_null() || m_state["territory"] != 182)
      throw ProtocolError("Ul'dah opening requires an idle character in opening territory 182");
    WC::FFXIVIpcEnterTerritoryHandler p{};
    p.eventId = 1245187;
    sendZone(p._ServerIpcType, objectBytes(p));
  }

  void Client::enterOpeningRange(uint32_t eventId, uint32_t param, const Point& position)
  {
    requireReady();
    if(m_moving || !m_state["event_id"].is_null() || !m_state["scene"].is_null())
      throw ProtocolError("opening range requires an idle character");
    auto payload = openingWithinRangeRequest(m_state["territory"], eventId, param, m_predicted, position);
    sendZone(WC::FFXIVIpcEventHandlerWithinRange::_ServerIpcType, payload);
  }

  void Client::leaveOpeningRange(uint32_t eventId, uint32_t param, const Point& position)
  {
    requireReady();
    if(m_moving || !m_state["event_id"].is_null() || !m_state["scene"].is_null())
      throw ProtocolError("opening range requires an idle character");
    auto payload = openingOutsideRangeRequest(m_state["territory"], eventId, param, m_predicted, position);
    sendZone(WC::FFXIVIpcEventHandlerOutsideRange::_ServerIpcType, payload);
  }

  void Client::discoverCentralThanalan(uint32_t layout, uint32_t part, const Point& receivedPosition)
  {
    requireReady();
    if(m_moving || !m_state["event_id"].is_null() || m_state["territory"] != 141)
      throw ProtocolError("discovery requires an idle character in territory 141");
    if((layout != 3643706 || part != 1) && (layout != 4204061 || part != 3))
      throw ProtocolError("unsupported discovery layout/part identity");
    if(std::find(m_state["discovery_requests_sent"].begin(), m_state["discovery_requests_sent"].end(), layout) !=
         m_state["discovery_requests_sent"].end() ||
       std::find(m_state["central_thanalan_discoveries"].begin(),
                 m_state["central_thanalan_discoveries"].end(), part) !=
         m_state["central_thanalan_discoveries"].end())
      throw ProtocolError("discovery part was already requested or received");
    if(std::sqrt(std::pow(receivedPosition[0]-m_predicted[0], 2) +
                 std::pow(receivedPosition[1]-m_predicted[1], 2) +
                 std::pow(receivedPosition[2]-m_predicted[2], 2)) > 0.15f)
      throw ProtocolError("discovery witness does not match the actor's predicted endpoint");
    auto payload = centralThanalanDiscoveryRequest(m_state["territory"], layout, receivedPosition);
    m_state["discovery_requests_sent"].push_back(layout);
    sendZone(WC::FFXIVIpcNewDiscovery::_ServerIpcType, payload);
  }

  void Client::sellShopItem(const SceneRef& scene, uint16_t storage, uint16_t slot, uint32_t item)
  {
    requireReady();
    requireScene(scene);
    if(scene.sceneId != 40 || (scene.eventId >> 16) != 4)
      throw ProtocolError("shop sale requires the matching received gil-shop scene 40");
    if(storage > 3 || slot >= 25 || item > 0xffff)
      throw ProtocolError("shop sale supports one observed single-item ordinary-bag stack");
    const auto key = std::to_string(storage) + ":" + std::to_string(slot);
    const auto& inventory = m_rewards.state()["inventory"];
    if(!inventory.contains(key) || inventory.at(key).at("storage") != storage ||
       inventory.at(key).at("slot") != slot || inventory.at(key).at("id") != item ||
       inventory.at(key).at("count") != 1)
      throw ProtocolError("shop sale source does not match the complete received inventory");
    sendZone(WC::FFXIVIpcReturnEventScene255::_ServerIpcType,
             shopSaleReturn(scene.eventId, storage, slot, static_cast<uint16_t>(item)));
    m_state["scene"] = nullptr;
  }

  void Client::buyShopItem(const SceneRef& scene, uint32_t shopId, uint32_t itemId, uint32_t quantity)
  {
    requireReady();
    requireScene(scene);
    if(scene.sceneId != 40 || scene.eventId != shopId || (shopId >> 16) != 4)
      throw ProtocolError("shop purchase requires the matching received gil-shop scene 40");
    if(itemId == 0 || itemId > 0xffff) throw ProtocolError("shop purchase item id out of range");
    sendZone(WC::FFXIVIpcReturnEventScene255::_ServerIpcType,
             shopPurchaseReturn(shopId, static_cast<uint16_t>(itemId), quantity));
    m_state["scene"] = nullptr;
  }

  void Client::inviteParty(uint32_t target, const std::string& name)
  {
    requireReady();
    const auto& party = m_state["party"];
    const auto count = party.at("count").get<uint8_t>();
    const auto leaderIndex = party.at("leader_index").get<size_t>();
    const auto isLeader = count == 0 ||
      (leaderIndex < party.at("members").size() &&
       party.at("members")[leaderIndex].value("entity_id", 0u) == m_entity);
    if(m_moving || !m_state["event_id"].is_null() || count >= 8 || !isLeader)
      throw ProtocolError("party invite requires an idle ungrouped character or received party leadership");
    auto payload = partyInviteRequest(m_state["actors"], target, name);
    sendZone(WC::FFXIVIpcInvite::_ServerIpcType, payload);
  }

  void Client::acceptParty()
  {
    requireReady();
    if(m_moving || !m_state["event_id"].is_null() || m_state["party"].at("count") != 0)
      throw ProtocolError("party reply requires an idle ungrouped character");
    auto payload = partyAcceptRequest(m_state["pending_party_invite"]);
    m_state["pending_party_invite"] = nullptr;
    m_state["party_invite_reply"] = nullptr;
    sendZone(WC::FFXIVIpcInviteReply::_ServerIpcType, payload);
  }

  void Client::declineParty()
  {
    requireReady();
    if(m_moving || !m_state["event_id"].is_null() || m_state["party"].at("count") != 0)
      throw ProtocolError("party reply requires an idle ungrouped character");
    auto payload = partyDeclineRequest(m_state["pending_party_invite"]);
    m_state["pending_party_invite"] = nullptr;
    m_state["party_invite_reply"] = nullptr;
    sendZone(WC::FFXIVIpcInviteReply::_ServerIpcType, payload);
  }

  void Client::leaveParty()
  {
    requireIdle("party leave");
    sendZone(WC::FFXIVIpcPcPartyLeave::_ServerIpcType, partyLeaveRequest(m_state["party"], m_entity));
  }

  void Client::disbandParty()
  {
    requireIdle("party disband");
    sendZone(WC::FFXIVIpcPcPartyDisband::_ServerIpcType, partyDisbandRequest(m_state["party"], m_entity));
  }

  void Client::kickPartyMember(uint32_t target, const std::string& name)
  {
    requireIdle("party kick");
    sendZone(WC::FFXIVIpcPcPartyKick::_ServerIpcType, partyKickRequest(m_state["party"], m_entity, target, name));
  }

  void Client::changePartyLeader(uint32_t target, const std::string& name)
  {
    requireIdle("party leader change");
    sendZone(WC::FFXIVIpcPcPartyChangeLeader::_ServerIpcType,
             partyChangeLeaderRequest(m_state["party"], m_entity, target, name));
  }

  PartyChannel Client::partyChat(const std::string& message)
  {
    requireIdle("party chat");
    auto payload = partyChatRequest(m_state["party"], m_entity, message);
    sendChat(WC::FFXIVIpcChatToChannel::_ServerIpcType, payload);
    return {m_state["party"].at("id").get<uint64_t>(), m_state["party"].at("chat_channel").get<uint64_t>()};
  }

  void Client::tell(uint32_t target, const std::string& targetName, const std::string& message, bool expectOffline)
  {
    requireIdle("tell");
    bool allowRemoteParty = false;
    if(!expectOffline && !m_state["actors"].contains(std::to_string(target)))
    {
      const auto& party = m_state["party"];
      for(auto it = m_state["party_chat"].rbegin(); it != m_state["party_chat"].rend(); ++it)
        if(it->value("actor", 0u) == target && it->value("name", "") == targetName &&
           it->value("party_id", uint64_t{0}) == party.value("id", uint64_t{0}) &&
           it->value("channel", uint64_t{0}) == party.value("chat_channel", uint64_t{0}) &&
           it->value("token", uint64_t{0}) <= m_seq && m_seq - it->value("token", uint64_t{0}) <= 16)
        {
          allowRemoteParty = true;
          break;
        }
    }
    auto payload = tellRequest(m_state["actors"], m_state["party"], target, targetName, message, expectOffline, allowRemoteParty);
    if(expectOffline)
    {
      m_state["tell_not_found"] = nullptr;
      m_state["offline_tell_pending"] = true;
    }
    sendChat(WC::FFXIVIpcChatTo::_ServerIpcType, payload);
  }

  void Client::tellRemote(uint32_t target, const std::string& name, const std::string& message)
  {
    requireIdle("remote tell");
    auto payload = remoteTellRequest(m_state["actors"], m_state["known_players"], m_state["party"],
                                     m_state["party_chat"], m_state["tells"], m_seq, target, name, message);
    sendChat(WC::FFXIVIpcChatTo::_ServerIpcType, payload);
  }

  void Client::tellVisible(uint32_t target, const std::string& name, const std::string& message)
  {
    requireReady();
    auto payload = visibleTellRequest(m_state, m_moving, {{"target", target}, {"name", name}, {"message", message}});
    sendChat(WC::FFXIVIpcChatTo::_ServerIpcType, payload);
  }

  uint32_t Client::castReturn()
  {
    requireIdle("living Return");
    if(std::chrono::steady_clock::now() < m_startingActionReady) throw ProtocolError("starting-action recast pending");
    const auto request = nextActionRequest();
    auto payload = livingReturnRequest(m_entity, request, m_state.at("territory"), m_state.at("homepoint"), m_state["actors"]);
    sendZone(WC::FFXIVIpcActionRequest::_ServerIpcType, payload);
    m_startingActionReady = std::chrono::steady_clock::now() + std::chrono::milliseconds(5000);
    return request;
  }

  uint32_t Client::sprint()
  {
    requireIdle("Sprint");
    if(std::chrono::steady_clock::now() < m_startingActionReady) throw ProtocolError("starting-action recast pending");
    const auto request = nextActionRequest();
    sendZone(WC::FFXIVIpcActionRequest::_ServerIpcType, sprintRequest(m_entity, request, m_state["actors"]));
    m_startingActionReady = std::chrono::steady_clock::now() + std::chrono::milliseconds(2500);
    return request;
  }

  uint32_t Client::starterAction(StarterAction action, uint32_t target)
  {
    requireIdle("combat action");
    if(std::chrono::steady_clock::now() < m_startingActionReady) throw ProtocolError("starting-action recast pending");
    const auto request = nextActionRequest();
    Bytes payload;
    switch(action)
    {
      case StarterAction::FastBlade:
        payload = fastBladeRequest(m_entity, request, target, m_predicted, m_state["actors"], m_rewards.state());
        break;
      case StarterAction::SavageBlade:
        if(target != m_fastBladeComboTarget || std::chrono::steady_clock::now() > m_fastBladeComboDeadline)
          throw ProtocolError("Savage Blade requires unexpired received Fast Blade combo readiness");
        payload = savageBladeRequest(m_entity, request, target, m_predicted, m_state["actors"], m_rewards.state(), m_combat.state());
        m_fastBladeComboTarget = 0;
        m_fastBladeComboDeadline = {};
        break;
      case StarterAction::Bootshine:
        payload = bootshineRequest(m_entity, request, target, m_predicted, m_state["actors"], m_rewards.state());
        break;
      case StarterAction::TrueStrike:
        payload = trueStrikeRequest(m_entity, request, target, m_predicted, m_state["actors"], m_rewards.state());
        break;
      case StarterAction::Blizzard:
        payload = blizzardRequest(m_entity, request, target, m_predicted, m_state["actors"], m_rewards.state());
        break;
    }
    sendZone(WC::FFXIVIpcActionRequest::_ServerIpcType, payload);
    // Conservative request pacing; the received ActionStart moves this deadline forward.
    m_startingActionReady = std::chrono::steady_clock::now() + std::chrono::milliseconds(2500);
    return request;
  }

  void Client::returnHomepoint(unsigned deadlineSeconds)
  {
    requireIdle("homepoint return");
    if(m_state["homepoint"].is_null()) throw ProtocolError("return requires a received homepoint");
    auto payload = returnHomepointRequest(m_entity, m_state.at("territory").get<uint16_t>(),
                                          m_state.at("homepoint").get<uint8_t>(), m_state.at("actors"));
    sendZone(WC::FFXIVIpcClientTrigger::_ServerIpcType, payload);
    phase("zoning");
    armDeadline(deadlineSeconds, "homepoint return deadline exceeded");
  }

  void Client::crossExit(const ExitRange& exit, unsigned deadlineSeconds)
  {
    requireIdle("exit crossing");
    auto payload = exitRangeRequest(m_state.at("territory"), m_predicted, exit);
    sendZone(WC::FFXIVIpcZoneJump::_ServerIpcType, payload);
    phase("zoning");
    armDeadline(deadlineSeconds, "territory transition deadline exceeded");
  }

  uint32_t Client::useShopVfxItem(uint32_t storage, uint32_t slot, uint32_t expectedCount)
  {
    requireIdle("item action");
    const auto request = nextActionRequest();
    sendZone(WC::FFXIVIpcActionRequest::_ServerIpcType,
             shopVfxItemRequest(m_rewards.state(), m_entity, request, storage, slot, expectedCount));
    return request;
  }

  uint32_t Client::discardItem(uint32_t storage, uint32_t slot, uint32_t expectedItem)
  {
    requireIdle("inventory operation");
    const auto context = nextInventoryContext();
    sendZone(WC::FFXIVIpcClientInventoryItemOperation::_ServerIpcType,
             discardItemRequest(m_rewards.state(), m_entity, context, storage, slot, expectedItem));
    return context;
  }

  uint32_t Client::unequipItem(uint32_t gearSlot, uint32_t expectedItem, uint32_t destinationStorage, uint32_t destinationSlot)
  {
    requireIdle("inventory operation");
    const auto context = nextInventoryContext();
    sendZone(WC::FFXIVIpcClientInventoryItemOperation::_ServerIpcType,
             unequipItemRequest(m_rewards.state(), m_entity, context, gearSlot, expectedItem, destinationStorage, destinationSlot));
    return context;
  }

  uint32_t Client::equipShopItem(uint32_t storage, uint32_t slot, uint32_t expectedItem, uint32_t gearSlot)
  {
    requireIdle("inventory operation");
    const auto context = nextInventoryContext();
    sendZone(WC::FFXIVIpcClientInventoryItemOperation::_ServerIpcType,
             equipShopItemRequest(m_rewards.state(), m_entity, context, storage, slot, expectedItem, gearSlot));
    return context;
  }

  uint32_t Client::reequipStarterItem(uint32_t storage, uint32_t slot, uint32_t expectedItem, uint32_t gearSlot)
  {
    requireIdle("inventory operation");
    const auto context = nextInventoryContext();
    sendZone(WC::FFXIVIpcClientInventoryItemOperation::_ServerIpcType,
             reequipStarterItemRequest(m_rewards.state(), m_entity, context, storage, slot, expectedItem, gearSlot));
    return context;
  }

  uint32_t Client::currencyMoveRejection(uint32_t expectedGil)
  {
    requireIdle("inventory operation");
    const auto context = nextInventoryContext();
    sendZone(WC::FFXIVIpcClientInventoryItemOperation::_ServerIpcType,
             currencyMoveRejectionRequest(m_rewards.state(), m_entity, context, expectedGil));
    return context;
  }

  uint32_t Client::moveItem(uint32_t storage, uint32_t slot, uint32_t expectedItem,
                            uint32_t destinationStorage, uint32_t destinationSlot)
  {
    requireIdle("inventory operation");
    const auto context = nextInventoryContext();
    sendZone(WC::FFXIVIpcClientInventoryItemOperation::_ServerIpcType,
             moveItemRequest(m_rewards.state(), m_entity, context, storage, slot, expectedItem, destinationStorage, destinationSlot));
    return context;
  }

  uint32_t Client::swapItem(uint32_t storage, uint32_t slot, uint32_t expectedItem,
                            uint32_t destinationStorage, uint32_t destinationSlot, uint32_t expectedDestinationItem)
  {
    requireIdle("inventory operation");
    const auto context = nextInventoryContext();
    sendZone(WC::FFXIVIpcClientInventoryItemOperation::_ServerIpcType,
             swapItemRequest(m_rewards.state(), m_entity, context, storage, slot, expectedItem,
                             destinationStorage, destinationSlot, expectedDestinationItem));
    return context;
  }

  uint32_t Client::splitItem(uint32_t storage, uint32_t slot, uint32_t expectedItem, uint32_t expectedCount,
                             uint32_t splitCount, uint32_t destinationStorage, uint32_t destinationSlot)
  {
    requireIdle("inventory operation");
    const auto context = nextInventoryContext();
    sendZone(WC::FFXIVIpcClientInventoryItemOperation::_ServerIpcType,
             splitItemRequest(m_rewards.state(), m_entity, context, storage, slot, expectedItem, expectedCount,
                              splitCount, destinationStorage, destinationSlot));
    return context;
  }

  uint32_t Client::mergeItem(uint32_t storage, uint32_t slot, uint32_t expectedItem, uint32_t expectedCount,
                             uint32_t destinationStorage, uint32_t destinationSlot, uint32_t expectedDestinationCount)
  {
    requireIdle("inventory operation");
    const auto context = nextInventoryContext();
    sendZone(WC::FFXIVIpcClientInventoryItemOperation::_ServerIpcType,
             mergeItemRequest(m_rewards.state(), m_entity, context, storage, slot, expectedItem, expectedCount,
                              destinationStorage, destinationSlot, expectedDestinationCount));
    return context;
  }
}

#include "PartyActions.h"
#include <Common.h>
#include <Network/PacketDef/Zone/ClientZoneDef.h>
#include <algorithm>
#include <cctype>
#include <cstring>

namespace Sapphire::Testing
{
  static void requireName(const std::string& name)
  {
    if(name.empty() || name.size() >= 32 ||
       !std::all_of(name.begin(), name.end(), [](unsigned char c) { return c >= 0x20 && c <= 0x7e; }))
      throw ProtocolError("party operation requires a bounded received ASCII character name");
  }

  Bytes partyInviteRequest(const nlohmann::json& actors, uint32_t targetEntity,
                           const std::string& targetName)
  {
    requireName(targetName);
    const auto key = std::to_string(targetEntity);
    if(!targetEntity || !actors.is_object() || !actors.contains(key) ||
       actors.at(key).value("kind", 0) != 1 || actors.at(key).value("name", "") != targetName)
      throw ProtocolError("party invite target must match a received player spawn");
    Wire::WorldPackets::Client::FFXIVIpcInvite packet{};
    packet.AuthType = Common::HierarchyType::PCPARTY;
    std::memcpy(packet.TargetName, targetName.data(), targetName.size());
    return objectBytes(packet);
  }

  static Bytes partyReplyRequest(const nlohmann::json& pendingInvite, Common::InviteReplyType answer,
                                 const char* operation)
  {
    if(!pendingInvite.is_object() || pendingInvite.value("auth_type", 0) != Common::HierarchyType::PCPARTY ||
       pendingInvite.value("result", 0) != Common::InviteUpdateType::NEW_INVITE ||
       !pendingInvite.contains("character_id") || !pendingInvite.at("character_id").is_number_unsigned() ||
       pendingInvite.at("character_id").get<uint64_t>() == 0)
      throw ProtocolError(std::string(operation) + " requires an exact received pending invite");
    requireName(pendingInvite.value("name", ""));
    Wire::WorldPackets::Client::FFXIVIpcInviteReply packet{};
    packet.InviteCharacterID = pendingInvite.at("character_id");
    packet.AuthType = Common::HierarchyType::PCPARTY;
    packet.Answer = answer;
    return objectBytes(packet);
  }

  Bytes partyAcceptRequest(const nlohmann::json& pendingInvite)
  {
    return partyReplyRequest(pendingInvite, Common::InviteReplyType::ACCEPT, "party acceptance");
  }

  Bytes partyDeclineRequest(const nlohmann::json& pendingInvite)
  {
    return partyReplyRequest(pendingInvite, Common::InviteReplyType::DENY, "party decline");
  }

  static void requireMembership(const nlohmann::json& party, uint32_t selfEntity,
                                const char* operation)
  {
    if(!party.is_object() || party.value("id", uint64_t{0}) == 0 || party.value("count", 0) < 2 ||
       !party.contains("members") || !party.at("members").is_array() ||
       std::none_of(party.at("members").begin(), party.at("members").end(),
         [selfEntity](const auto& member) { return member.value("entity_id", 0u) == selfEntity; }))
      throw ProtocolError(std::string(operation) + " requires received membership for this player");
  }

  Bytes partyLeaveRequest(const nlohmann::json& party, uint32_t selfEntity)
  {
    requireMembership(party, selfEntity, "party leave");
    Wire::WorldPackets::Client::FFXIVIpcPcPartyLeave packet{};
    return objectBytes(packet);
  }

  static void requireLeaderTarget(const nlohmann::json& party, uint32_t selfEntity,
                                  uint32_t targetEntity, const std::string& targetName,
                                  const char* operation)
  {
    requireMembership(party, selfEntity, operation);
    requireName(targetName);
    const auto leaderIndex = party.value("leader_index", size_t{8});
    const auto& members = party.at("members");
    if(leaderIndex >= members.size() || members[leaderIndex].value("entity_id", 0u) != selfEntity ||
       targetEntity == selfEntity ||
       std::none_of(members.begin(), members.end(), [&](const auto& member) {
         return member.value("entity_id", 0u) == targetEntity && member.value("name", "") == targetName;
       }))
      throw ProtocolError(std::string(operation) + " requires received leadership and exact target membership");
  }

  Bytes partyChangeLeaderRequest(const nlohmann::json& party, uint32_t selfEntity,
                                 uint32_t targetEntity, const std::string& targetName)
  {
    requireLeaderTarget(party, selfEntity, targetEntity, targetName, "party leader change");
    Wire::WorldPackets::Client::FFXIVIpcPcPartyChangeLeader packet{};
    copyText(packet.NextLeaderCharacterName, targetName);
    return objectBytes(packet);
  }

  Bytes partyKickRequest(const nlohmann::json& party, uint32_t selfEntity,
                         uint32_t targetEntity, const std::string& targetName)
  {
    requireLeaderTarget(party, selfEntity, targetEntity, targetName, "party kick");
    if(party.value("count", 0) < 3)
      throw ProtocolError("party kick requires a received roster of at least three members");
    Wire::WorldPackets::Client::FFXIVIpcPcPartyKick packet{};
    copyText(packet.LeaveCharacterName, targetName);
    return objectBytes(packet);
  }

  Bytes partyChatRequest(const nlohmann::json& party, uint32_t selfEntity,
                         const std::string& message)
  {
    requireMembership(party, selfEntity, "party chat");
    if(!party.contains("chat_channel") || !party.at("chat_channel").is_number_unsigned() ||
       party.at("chat_channel").get<uint64_t>() == 0)
      throw ProtocolError("party chat requires the exact received channel");
    if(message.empty() || message.size() > 128 || message[0] == '!' ||
       !std::all_of(message.begin(), message.end(), [](unsigned char c) { return c >= 32 && c <= 126; }))
      throw ProtocolError("party chat requires 1..128 printable ASCII characters, not a debug command");
    Wire::WorldPackets::Client::FFXIVIpcChatToChannel packet{};
    packet.channelID = party.at("chat_channel");
    copyText(packet.message, message);
    return objectBytes(packet);
  }
}

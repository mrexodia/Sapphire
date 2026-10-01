#include "ChatActions.h"
#include <Common.h>
#include <Network/PacketDef/Zone/ClientZoneDef.h>
#include <algorithm>

namespace Sapphire::Testing
{
  Bytes tellRequest(const nlohmann::json& actors, const nlohmann::json& party,
                    uint32_t targetEntity, const std::string& targetName,
                    const std::string& message, bool expectOffline, bool allowRemoteParty)
  {
    const auto key = std::to_string(targetEntity);
    if(!targetEntity || targetName.empty() || targetName.size() >= 32)
      throw ProtocolError("tell target requires a bounded received identity");
    const auto spawned = actors.is_object() && actors.contains(key) &&
                         actors.at(key).value("kind", 0) == 1 &&
                         actors.at(key).value("name", "") == targetName;
    if(expectOffline)
    {
      if(!party.is_object() || !party.contains("members") || !party.at("members").is_array())
        throw ProtocolError("offline tell target requires exact received party identity");
      const auto member = std::find_if(party.at("members").begin(), party.at("members").end(),
        [&](const auto& row) { return row.value("entity_id", 0u) == targetEntity &&
                                      row.value("name", "") == targetName; });
      if(member == party.at("members").end() || spawned || member->value("territory", 1) != 0)
        throw ProtocolError("offline tell target state does not match received evidence");
    }
    else if(!spawned)
    {
      if(!allowRemoteParty || !party.is_object() || !party.contains("members") ||
         !party.at("members").is_array())
        throw ProtocolError("online tell target must match an exact received player spawn");
      const auto member = std::find_if(party.at("members").begin(), party.at("members").end(),
        [&](const auto& row) { return row.value("entity_id", 0u) == targetEntity &&
                                      row.value("name", "") == targetName &&
                                      row.value("character_id", uint64_t{0}) != 0 &&
                                      row.value("territory", 1) == 0; });
      if(member == party.at("members").end())
        throw ProtocolError("remote tell target must match exact redacted party identity");
    }
    if(!std::all_of(targetName.begin(), targetName.end(), [](unsigned char c) { return c >= 0x20 && c <= 0x7e; }))
      throw ProtocolError("tell target requires a bounded received ASCII name");
    if(message.empty() || message.size() > 128 || message[0] == '!' ||
       !std::all_of(message.begin(), message.end(), [](unsigned char c) { return c >= 0x20 && c <= 0x7e; }))
      throw ProtocolError("tell requires 1..128 printable ASCII characters, not a debug command");
    Wire::WorldPackets::Client::FFXIVIpcChatTo packet{};
    packet.type = static_cast<uint8_t>(Common::ChatType::Tell);
    copyText(packet.toName, targetName);
    copyText(packet.message, message);
    return objectBytes(packet);
  }

  Bytes visibleTellRequest(const nlohmann::json& state, bool moving,
                           const nlohmann::json& args)
  {
    if(!args.is_object() || args.size() != 3 || !args.contains("target") ||
       !args.at("target").is_number_integer() || args.at("target") <= 0 ||
       args.at("target") > uint64_t{0xffffffff} || !args.contains("name") ||
       !args.at("name").is_string() || !args.contains("message") || !args.at("message").is_string())
      throw ProtocolError("visible Tell requires exactly target uint32, name and message");
    if(state.at("phase") != "ready" || state.at("gm_rank") != 0 || moving ||
       state.at("between_areas") != false || !state.at("event_id").is_null() ||
       !state.at("scene").is_null() || !state.at("pending_party_invite").is_null() ||
       state.at("party").at("id") != 0 || state.at("party").at("count") != 0 ||
       !state.at("party").at("members").empty())
      throw ProtocolError("visible Tell requires an idle non-GM nonparty sender");
    const auto target = args.at("target").get<uint32_t>();
    const auto name = args.at("name").get<std::string>();
    const auto& actors = state.at("actors");
    size_t matches = 0;
    for(auto it = actors.begin(); it != actors.end(); ++it)
      if(it.value().value("kind", 0) == 1 && it.value().value("name", "") == name) ++matches;
    const auto key = std::to_string(target);
    if(target == state.at("entity_id") || matches != 1 || !actors.contains(key) ||
       actors.at(key).at("gm_rank") != 0)
      throw ProtocolError("visible Tell requires one separate non-GM player identity");
    return tellRequest(actors, state.at("party"), target, name, args.at("message"), false, false);
  }

  Bytes remoteTellRequest(const nlohmann::json& actors, const nlohmann::json& knownPlayers,
                          const nlohmann::json& party, const nlohmann::json& partyChat,
                          const nlohmann::json& tells, uint64_t currentToken,
                          uint32_t targetEntity, const std::string& targetName,
                          const std::string& message)
  {
    const auto key = std::to_string(targetEntity);
    if(!targetEntity || actors.contains(key) || !knownPlayers.is_object() ||
       !knownPlayers.contains(key) || knownPlayers.at(key).value("name", "") != targetName ||
       knownPlayers.at(key).value("spawned", true) ||
       party.value("id", uint64_t{0}) != 0 || party.value("count", 0) != 0)
      throw ProtocolError("remote nonparty tell requires one exact prior received spawn and current disband");
    const auto recent = [&](const nlohmann::json& rows, bool partyEvidence)
    {
      if(!rows.is_array()) return false;
      for(auto it = rows.rbegin(); it != rows.rend(); ++it)
      {
        const auto token = it->value("token", uint64_t{0});
        if(it->value("actor", 0u) == targetEntity && it->value("name", "") == targetName &&
           it->value("character_id", uint64_t{0}) != 0 && token && token <= currentToken &&
           currentToken - token <= 16 && (!partyEvidence || it->value("party_id", uint64_t{0}) != 0))
          return true;
      }
      return false;
    };
    if(!recent(partyChat, true) && !recent(tells, false))
      throw ProtocolError("remote nonparty tell requires recent exact received liveness evidence");
    if(targetName.empty() || targetName.size() >= 32 ||
       !std::all_of(targetName.begin(), targetName.end(), [](unsigned char c) { return c >= 0x20 && c <= 0x7e; }) ||
       message.empty() || message.size() > 128 || message[0] == '!' ||
       !std::all_of(message.begin(), message.end(), [](unsigned char c) { return c >= 0x20 && c <= 0x7e; }))
      throw ProtocolError("remote tell requires bounded printable identity and message");
    Wire::WorldPackets::Client::FFXIVIpcChatTo packet{};
    packet.type = static_cast<uint8_t>(Common::ChatType::Tell);
    copyText(packet.toName, targetName);
    copyText(packet.message, message);
    return objectBytes(packet);
  }
}

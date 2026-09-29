#include "ChatActions.h"
#include <Common.h>
#include <Network/PacketDef/Zone/ClientZoneDef.h>
#include <algorithm>

namespace Sapphire::Testing
{
  Bytes tellRequest(const nlohmann::json& actors, uint32_t targetEntity,
                    const std::string& targetName, const std::string& message)
  {
    const auto key = std::to_string(targetEntity);
    if(!targetEntity || targetName.empty() || targetName.size() >= 32 ||
       !actors.is_object() || !actors.contains(key) ||
       actors.at(key).value("kind", 0) != 1 || actors.at(key).value("name", "") != targetName)
      throw ProtocolError("tell target must match an exact received player spawn");
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
}

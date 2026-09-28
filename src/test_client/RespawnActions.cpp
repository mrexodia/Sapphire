#include "RespawnActions.h"
#include <Network/CommonActorControl.h>
#include <Network/PacketDef/Zone/ClientZoneDef.h>

namespace Sapphire::Testing
{
  Bytes returnHomepointRequest(uint32_t entity, uint16_t territory, uint8_t homepoint,
                               const nlohmann::json& actors)
  {
    const auto self = std::to_string(entity);
    if(!entity || territory != 141 || homepoint != 9 || !actors.contains(self) ||
       actors.at(self).at("hp") != 0)
      throw ProtocolError("return supports one defeated Central Thanalan character with Ul'dah homepoint");
    Wire::WorldPackets::Client::FFXIVIpcClientTrigger packet{};
    packet.Id = Network::ActorControl::PacketCommand::REVIVE;
    packet.Arg0 = static_cast<uint8_t>(Common::ResurrectType::Return);
    return objectBytes(packet);
  }
}

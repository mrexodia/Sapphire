#include "CreationActions.h"
#include <nlohmann/json.hpp>
#include <Network/PacketDef/Zone/ClientZoneDef.h>
#include <cmath>

namespace Sapphire::Testing
{
  std::string canonicalUldahCreationPayload(uint8_t classJob)
  {
    if(classJob != 1 && classJob != 2 && classJob != 7)
      throw ProtocolError("creation supports only the three source-defined Ul'dah starting classes");
    nlohmann::json look = {"1","0","1","50","1","1","1","1","0","0","0","1","1",
                           "1","1","1","1","1","0","0","0","0","0","0","0","0"};
    nlohmann::json content = nlohmann::json::array({look, "1", "1", "1", "1",
                                                     std::to_string(classJob), "1"});
    return nlohmann::json({{"content", content}}).dump();
  }

  Bytes openingWithinRangeRequest(uint16_t territory, uint32_t eventId, uint32_t param,
                                  const std::array<float, 3>& current,
                                  const std::array<float, 3>& position)
  {
    float distance = 0;
    for(size_t i = 0; i < 3; ++i)
    {
      if(!std::isfinite(current[i]) || !std::isfinite(position[i]))
        throw ProtocolError("opening range requires finite received geometry");
      distance += std::pow(current[i] - position[i], 2);
    }
    if(territory != 182 || eventId != 1245187 || param != 4101537 || distance > 0.15f * 0.15f)
      throw ProtocolError("unsupported or unreached opening range");
    Wire::WorldPackets::Client::FFXIVIpcEventHandlerWithinRange packet{};
    packet.param1 = param; packet.eventId = eventId;
    packet.position.x = position[0]; packet.position.y = position[1]; packet.position.z = position[2];
    return objectBytes(packet);
  }
}

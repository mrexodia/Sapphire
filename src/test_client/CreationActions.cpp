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

  Bytes centralThanalanDiscoveryRequest(uint16_t territory, uint32_t layoutId,
                                        const std::array<float, 3>& receivedPosition)
  {
    // Source LGB MapRange 3643706 is the sole enabled discovery sphere containing
    // the supported territory-141 arrival pop. Its full diameters are 140/23.2278/140.
    constexpr std::array<float, 3> center{-90.4246521f, 16.7652493f, 297.3623962f};
    constexpr float horizontalRadius = 70.0f;
    constexpr float verticalRadius = 11.6139154f;
    for(float value : receivedPosition)
      if(!std::isfinite(value)) throw ProtocolError("discovery requires a finite received position");
    const auto horizontal = std::hypot(receivedPosition[0] - center[0],
                                       receivedPosition[2] - center[2]);
    if(territory != 141 || layoutId != 3643706 || horizontal > horizontalRadius ||
       std::abs(receivedPosition[1] - center[1]) > verticalRadius)
      throw ProtocolError("unsupported or unreached discovery range");
    Wire::WorldPackets::Client::FFXIVIpcNewDiscovery packet{};
    packet.LayoutId = layoutId;
    packet.PositionX = receivedPosition[0];
    packet.PositionY = receivedPosition[1];
    packet.PositionZ = receivedPosition[2];
    return objectBytes(packet);
  }
}

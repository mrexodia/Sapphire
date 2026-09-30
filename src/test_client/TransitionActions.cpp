#include "TransitionActions.h"
#include <Network/PacketDef/Zone/ClientZoneDef.h>
#include <cmath>
#include <algorithm>

namespace Sapphire::Testing
{
  Bytes exitRangeRequest(uint16_t territory, const std::array<float, 3>& position,
                         const nlohmann::json& exit)
  {
    if(exit.at("territory") != territory || exit.at("enabled") != true ||
       exit.at("shape") != 1 || exit.at("exit_type") != 1 ||
       !exit.at("id").is_number_integer() || !exit.at("target_territory").is_number_integer() ||
       !exit.at("target_pop").is_number_integer())
      throw ProtocolError("unsupported exit range/profile");
    const auto id = exit.at("id").get<uint32_t>();
    const auto targetTerritory = exit.at("target_territory").get<uint16_t>();
    const auto targetPop = exit.at("target_pop").get<uint32_t>();
    const bool supported =
      (territory == 130 && id == 2377056 && targetTerritory == 141 && targetPop == 2372271) ||
      (territory == 141 && id == 2372269 && targetTerritory == 130 && targetPop == 2377058);
    if(!supported) throw ProtocolError("unsupported exit range/profile");
    const auto center = exit.at("position").get<std::array<float, 3>>();
    const auto scale = exit.at("scale").get<std::array<float, 3>>();
    const auto rotation = exit.at("rotation").get<std::array<float, 3>>();
    for(size_t i = 0; i < 3; ++i)
      if(!std::isfinite(position[i]) || !std::isfinite(center[i]) || !std::isfinite(scale[i]) ||
         !std::isfinite(rotation[i]) || scale[i] <= 0 || scale[i] > 100)
        throw ProtocolError("invalid exit transform");
    if(std::abs(rotation[0]) > 0.0001f || std::abs(rotation[2]) > 0.0001f ||
       std::hypot(position[0]-center[0], position[2]-center[2]) > std::min(scale[0], scale[2]) * 0.5f ||
       std::abs(position[1]-center[1]) > scale[1] * 0.5f)
      throw ProtocolError("player has not reached the conservative exit volume");
    Wire::WorldPackets::Client::FFXIVIpcZoneJump p{};
    p.ExitBox = exit.at("id"); p.X = position[0]; p.Y = position[1]; p.Z = position[2];
    return objectBytes(p);
  }
}

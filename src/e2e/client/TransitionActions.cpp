#include "TransitionActions.h"
#include <Network/PacketDef/Zone/ClientZoneDef.h>
#include <cmath>
#include <algorithm>

namespace Sapphire::Testing
{
  Bytes exitRangeRequest(uint16_t territory, const std::array<float, 3>& position, const ExitRange& exit)
  {
    if(exit.territory != territory || !exit.enabled || exit.shape != 1 || exit.exitType != 1 ||
       !exit.id || !exit.targetTerritory || !exit.targetPop)
      throw ProtocolError("unsupported exit range: only enabled box exits of the current territory");
    for(size_t i = 0; i < 3; ++i)
      if(!std::isfinite(position[i]) || !std::isfinite(exit.position[i]) || !std::isfinite(exit.scale[i]) ||
         !std::isfinite(exit.rotation[i]) || exit.scale[i] <= 0 || exit.scale[i] > 100)
        throw ProtocolError("invalid exit transform");
    if(std::abs(exit.rotation[0]) > 0.0001f || std::abs(exit.rotation[2]) > 0.0001f ||
       std::hypot(position[0]-exit.position[0], position[2]-exit.position[2]) > std::min(exit.scale[0], exit.scale[2]) * 0.5f ||
       std::abs(position[1]-exit.position[1]) > exit.scale[1] * 0.5f)
      throw ProtocolError("player has not reached the conservative exit volume");
    Wire::WorldPackets::Client::FFXIVIpcZoneJump p{};
    p.ExitBox = exit.id; p.X = position[0]; p.Y = position[1]; p.Z = position[2];
    return objectBytes(p);
  }
}

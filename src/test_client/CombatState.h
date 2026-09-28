#pragma once
#include "Protocol.h"
#include <nlohmann/json.hpp>

namespace Sapphire::Testing
{
  class CombatState
  {
  public:
    CombatState();
    bool receive(uint16_t opcode, uint32_t source, const Bytes& ipcData);
    const nlohmann::json& state() const { return m_state; }
  private:
    nlohmann::json m_state;
  };
  // Deliberately narrow initial combat profile: living Gladiator, Fast Blade,
  // observed nearby level-one battle NPC. No arbitrary ability/raw-packet API.
  Bytes fastBladeRequest(uint32_t entity, uint32_t request, uint32_t target,
                         const std::array<float, 3>& position,
                         const nlohmann::json& actors, const nlohmann::json& rewards);
}

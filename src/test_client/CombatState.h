#pragma once
#include "Protocol.h"
#include <nlohmann/json.hpp>
#include <chrono>

namespace Sapphire::Testing
{
  class CombatState
  {
  public:
    CombatState();
    bool receive(uint16_t opcode, uint32_t source, const Bytes& ipcData);
    void annotateLatestIntegrity(uint32_t previousHp);
    const nlohmann::json& state() const { return m_state; }
  private:
    nlohmann::json m_state;
  };
  // Local conservative pacing guard, not a received server-ready acknowledgement.
  uint32_t startingActionGuardRemainingMs(std::chrono::steady_clock::time_point ready,
                                    std::chrono::steady_clock::time_point now);
  // Deliberately narrow profiles for source-defined starter progression actions.
  // No arbitrary ability/raw-packet API.
  Bytes sprintRequest(uint32_t entity, uint32_t request, const nlohmann::json& actors);
  Bytes livingReturnRequest(uint32_t entity, uint32_t request, uint16_t territory,
                            uint8_t homepoint, const nlohmann::json& actors);
  Bytes fastBladeRequest(uint32_t entity, uint32_t request, uint32_t target,
                         const std::array<float, 3>& position,
                         const nlohmann::json& actors, const nlohmann::json& rewards);
  Bytes bootshineRequest(uint32_t entity, uint32_t request, uint32_t target,
                         const std::array<float, 3>& position,
                         const nlohmann::json& actors, const nlohmann::json& rewards);
  Bytes trueStrikeRequest(uint32_t entity, uint32_t request, uint32_t target,
                          const std::array<float, 3>& position,
                          const nlohmann::json& actors, const nlohmann::json& rewards);
  Bytes blizzardRequest(uint32_t entity, uint32_t request, uint32_t target,
                        const std::array<float, 3>& position,
                        const nlohmann::json& actors, const nlohmann::json& rewards);
}

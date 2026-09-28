#pragma once
#include "Protocol.h"
#include <nlohmann/json.hpp>
#include <map>

namespace Sapphire::Testing
{
  // Observations only: no gameplay commands and no optimistic reward increments.
  class RewardsState
  {
  public:
    RewardsState();
    bool receive(uint16_t opcode, const Bytes& ipcData);
    const nlohmann::json& state() const { return m_state; }
  private:
    using Json = nlohmann::json;
    using Slots = std::map<std::string, Json>;
    void stage(std::map<uint32_t, Slots>& pending, uint32_t context, uint32_t storage,
               uint16_t index, uint32_t item, uint32_t count);
    void apply(const Slots& slots);
    Json m_state;
    std::map<uint32_t, Slots> m_initial, m_updates;
  };
}

#pragma once
#include "Protocol.h"
#include <nlohmann/json.hpp>
#include <string>

namespace Sapphire::Testing
{
  Bytes tellRequest(const nlohmann::json& actors, const nlohmann::json& party,
                    uint32_t targetEntity, const std::string& targetName,
                    const std::string& message, bool expectOffline = false,
                    bool allowRemoteParty = false);
  Bytes visibleTellRequest(const nlohmann::json& state, bool moving,
                           const nlohmann::json& args);
  Bytes remoteTellRequest(const nlohmann::json& actors, const nlohmann::json& knownPlayers,
                          const nlohmann::json& party, const nlohmann::json& partyChat,
                          const nlohmann::json& tells, uint64_t currentToken,
                          uint32_t targetEntity, const std::string& targetName,
                          const std::string& message);
}

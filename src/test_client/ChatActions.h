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
}

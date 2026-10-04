#pragma once
#include "Protocol.h"
#include <nlohmann/json.hpp>
#include <string>

namespace Sapphire::Testing
{
  Bytes partyInviteRequest(const nlohmann::json& actors, uint32_t targetEntity,
                           const std::string& targetName);
  Bytes partyAcceptRequest(const nlohmann::json& pendingInvite);
  Bytes partyDeclineRequest(const nlohmann::json& pendingInvite);
  Bytes partyLeaveRequest(const nlohmann::json& party, uint32_t selfEntity);
  Bytes partyDisbandRequest(const nlohmann::json& party, uint32_t selfEntity);
  Bytes partyChangeLeaderRequest(const nlohmann::json& party, uint32_t selfEntity,
                                 uint32_t targetEntity, const std::string& targetName);
  Bytes partyKickRequest(const nlohmann::json& party, uint32_t selfEntity,
                         uint32_t targetEntity, const std::string& targetName);
  Bytes partyChatRequest(const nlohmann::json& party, uint32_t selfEntity,
                         const std::string& message);
}

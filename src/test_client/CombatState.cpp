#include "CombatState.h"
#include <Network/PacketDef/Zone/ClientZoneDef.h>
#include <Network/PacketDef/Zone/ServerZoneDef.h>
#include <cmath>
#include <Network/CommonActorControl.h>

namespace Sapphire::Testing
{
  using Json = nlohmann::json;
  namespace WS = Wire::WorldPackets::Server;
  CombatState::CombatState() : m_state{{"effects", Json::array()}, {"integrities", Json::array()}, {"starts", Json::array()}} {}
  static void append(Json& array, Json value)
  {
    array.push_back(std::move(value));
    if(array.size() > 128) array.erase(array.begin());
  }
  static Json effects(const Common::CalcResult& result)
  {
    Json values = Json::array();
    for(const auto& effect : result.CalcResultTg)
      if(effect.Type) values.push_back({{"type", effect.Type}, {"value", effect.Value}, {"flag", effect.Flag},
                                       {"args", {effect.Arg0, effect.Arg1, effect.Arg2}}});
    return values;
  }
  bool CombatState::receive(uint16_t opcode, uint32_t source, const Bytes& data)
  {
    constexpr auto off = sizeof(Wire::FFXIVARR_IPC_HEADER);
    if(opcode == WS::FFXIVIpcActionResult1::_ServerIpcType)
    {
      const auto p = readObject<WS::FFXIVIpcActionResult1>(data, off);
      append(m_state["effects"], {{"source", source}, {"target", p.Target}, {"action", p.ActionKey},
        {"kind", p.ActionKind}, {"request", p.RequestId}, {"result", p.ResultId}, {"effects", effects(p.CalcResult)}});
    }
    else if(opcode == WS::FFXIVIpcActionResult::_ServerIpcType)
    {
      const auto p = readObject<WS::FFXIVIpcActionResult>(data, off);
      if(p.TargetCount > 16) throw ProtocolError("action result target count exceeds profile");
      for(size_t i = 0; i < p.TargetCount; ++i)
        append(m_state["effects"], {{"source", source}, {"target", p.Target[i]}, {"action", p.ActionKey},
          {"kind", p.ActionKind}, {"request", p.RequestId}, {"result", p.ResultId}, {"effects", effects(p.CalcResult[i])}});
    }
    else if(opcode == WS::FFXIVIpcActorControlSelf::_ServerIpcType)
    {
      const auto p = readObject<WS::FFXIVIpcActorControlSelf>(data, off);
      if(p.category != Network::ActorControl::ActionStart) return false;
      append(m_state["starts"], {{"source", source}, {"group", p.param1}, {"action", p.param2}, {"recast_centiseconds", p.param3}});
    }
    else if(opcode == WS::FFXIVIpcActionIntegrity::_ServerIpcType)
    {
      const auto p = readObject<WS::FFXIVIpcActionIntegrity>(data, off);
      if(p.Hp > p.HpMax) throw ProtocolError("invalid received combat HP");
      append(m_state["integrities"], {{"target", p.Target}, {"result", p.ResultId}, {"hp", p.Hp}, {"hp_max", p.HpMax}, {"mp", p.Mp}, {"tp", p.Tp}});
    }
    else return false;
    return true;
  }
  void CombatState::annotateLatestIntegrity(uint32_t previousHp)
  {
    if(m_state["integrities"].empty()) throw ProtocolError("no combat integrity to annotate");
    m_state["integrities"].back()["previous_hp"] = previousHp;
  }
  uint32_t fastBladeGuardRemainingMs(std::chrono::steady_clock::time_point ready,
                                    std::chrono::steady_clock::time_point now)
  {
    if(ready <= now) return 0;
    // Round UP: truncating a positive fractional millisecond could expose zero
    // while the command-side steady-clock guard still correctly rejects a request.
    return static_cast<uint32_t>(std::chrono::ceil<std::chrono::milliseconds>(ready - now).count());
  }
  static Bytes startingMeleeRequest(uint32_t action, uint32_t classJob, const char* name,
                                    uint32_t entity, uint32_t request, uint32_t target,
                                    const std::array<float, 3>& position, const Json& actors,
                                    const Json& rewards)
  {
    const auto key = std::to_string(target), self = std::to_string(entity);
    if(!request || request > 65535 || target == entity || rewards.at("class_job") != classJob ||
       !actors.contains(self) || actors.at(self).at("hp") == 0 ||
       !actors.contains(key) || actors.at(key).at("kind") != 2 || actors.at(key).at("hp") == 0)
      throw ProtocolError(std::string(name) + " requires the matching living starter class and observed battle NPC");
    if(actors.at(self).at("tp").get<uint16_t>() < 60)
      throw ProtocolError(std::string(name) + " requires at least 60 received TP");
    auto destination = actors.at(key).at("position").get<std::array<float, 3>>();
    float squared = 0;
    for(size_t i = 0; i < 3; ++i)
    {
      if(!std::isfinite(position[i]) || !std::isfinite(destination[i])) throw ProtocolError("invalid combat position");
      squared += std::pow(position[i] - destination[i], 2);
    }
    if(squared > 9) throw ProtocolError("combat target outside three-unit range");
    Wire::WorldPackets::Client::FFXIVIpcActionRequest p{};
    std::memset(&p, 0, sizeof(p));
    p.ActionKind = Common::ACTION_KIND_NORMAL; p.ActionKey = action; p.RequestId = request; p.Target = target;
    const auto angle = std::atan2(destination[0] - position[0], destination[2] - position[2]);
    p.Dir = p.DirTarget = static_cast<uint16_t>(static_cast<uint32_t>(std::lround(
      (angle + 3.14159265358979323846) * (32768.0 / 3.14159265358979323846))) & 0xffffu);
    return objectBytes(p);
  }
  Bytes fastBladeRequest(uint32_t entity, uint32_t request, uint32_t target,
                         const std::array<float, 3>& position, const Json& actors, const Json& rewards)
  {
    return startingMeleeRequest(9, 1, "Fast Blade", entity, request, target, position, actors, rewards);
  }
  Bytes bootshineRequest(uint32_t entity, uint32_t request, uint32_t target,
                         const std::array<float, 3>& position, const Json& actors, const Json& rewards)
  {
    return startingMeleeRequest(53, 2, "Bootshine", entity, request, target, position, actors, rewards);
  }
}

#include "CombatState.h"
#include <Network/PacketDef/Zone/ServerZoneDef.h>
#include <iostream>
#include <limits>
using namespace Sapphire::Testing;
namespace WS = Wire::WorldPackets::Server;
using Json = nlohmann::json;
#define require(ok) do { if(!(ok)) throw std::runtime_error("combat assertion failed at line " + std::to_string(__LINE__)); } while(false)
template<class F> void rejects(F f)
{
  bool rejected = false;
  try { f(); } catch(const ProtocolError&) { rejected = true; }
  require(rejected);
}
template<class T> Bytes packet(const T& value)
{
  return ipc(T::_ServerIpcType, objectBytes(value));
}
int main()
{
  try
  {
    Json actors{{"7", {{"hp", 100}, {"tp", 1000}}}, {"8", {{"hp", 20}, {"kind", 2}, {"level", 1}, {"position", {0, 0, 2}}}}};
    Json rewards{{"class_job", 1}};
    auto body = fastBladeRequest(7, 1, 8, {0,0,0}, actors, rewards);
    // Independently authored request offsets, not round-tripped through a shared struct.
    require(body.size() == 32 && body[0] == 0 && body[1] == 1 && body[4] == 9 && body[8] == 1);
    require(body[12] == 0 && body[13] == 0x80 && body[14] == 0 && body[15] == 0x80);
    require(body[16] == 8 && body[20] == 0 && body[24] == 0);
    Bytes expected(32, 0);
    expected[1] = 1; expected[4] = 9; expected[8] = 1; expected[13] = expected[15] = 0x80; expected[16] = 8;
    require(body == expected);
    rejects([&] { fastBladeRequest(7, 1, 8, {0,0,-2}, actors, rewards); });
    rejects([&] { fastBladeRequest(7, 1, 9, {0,0,0}, actors, rewards); });
    rejects([&] { fastBladeRequest(7, 65536, 8, {0,0,0}, actors, rewards); });
    rejects([&] { fastBladeRequest(7, 1, 8, {std::numeric_limits<float>::quiet_NaN(),0,0}, actors, rewards); });
    for(const auto& patch : {Json{{"hp", 0}}, Json{{"kind", 1}}, Json{{"level", 2}}})
    {
      auto invalid = actors; invalid["8"].update(patch);
      rejects([&] { fastBladeRequest(7, 1, 8, {0,0,0}, invalid, rewards); });
    }
    rejects([&] { fastBladeRequest(7, 1, 8, {0,0,0}, actors, {{"class_job", 2}}); });
    auto exhausted = actors; exhausted["7"]["tp"] = 59;
    rejects([&] { fastBladeRequest(7, 1, 8, {0,0,0}, exhausted, rewards); });
    CombatState state;
    WS::FFXIVIpcActionResult1 result{};
    result.Target = 8; result.ActionKey = 9; result.ActionKind = 1; result.RequestId = 1; result.ResultId = 42;
    result.CalcResult.CalcResultTg[0].Type = 3; result.CalcResult.CalcResultTg[0].Value = 7;
    require(state.receive(result._ServerIpcType, 7, packet(result)));
    require(state.state()["effects"].back()["effects"][0]["value"] == 7);
    require(state.state()["effects"].back()["source"] == 7);
    require(state.state()["integrities"].empty()); // Effect alone must not invent HP.
    WS::FFXIVIpcActionIntegrity integrity{};
    integrity.Target = 8; integrity.ResultId = 42; integrity.Hp = 13; integrity.HpMax = 20; integrity.Tp = 40;
    require(state.receive(integrity._ServerIpcType, 8, packet(integrity)));
    require(state.state()["integrities"].back()["hp"] == 13);
    require(state.state()["integrities"].back()["tp"] == 40);
    integrity.Hp = 21;
    rejects([&] { state.receive(integrity._ServerIpcType, 8, packet(integrity)); });
    auto shortPacket = packet(result); shortPacket.pop_back();
    rejects([&] { state.receive(result._ServerIpcType, 7, shortPacket); });
    WS::FFXIVIpcActionResult multiple{};
    multiple.TargetCount = 17;
    rejects([&] { state.receive(multiple._ServerIpcType, 7, packet(multiple)); });
    multiple.TargetCount = 1; multiple.Target[0] = 8; multiple.ResultId = 43;
    state.receive(multiple._ServerIpcType, 7, packet(multiple));
    require(state.state()["effects"].back()["result"] == 43);
    for(int i = 0; i < 200; ++i) state.receive(result._ServerIpcType, 7, packet(result));
    require(state.state()["effects"].size() == 128);
    integrity.Hp = 13;
    for(int i = 0; i < 200; ++i) state.receive(integrity._ServerIpcType, 8, packet(integrity));
    require(state.state()["integrities"].size() == 128);
    WS::FFXIVIpcActorControlSelf start{};
    start.category = 0x11; start.param1 = 58; start.param2 = 9; start.param3 = 250;
    require(state.receive(start._ServerIpcType, 7, packet(start)));
    require(state.state()["starts"].back()["recast_centiseconds"] == 250);
    state = CombatState{};
    require(state.state()["effects"].empty() && state.state()["integrities"].empty());
    std::cout << "combat tests passed\n";
  }
  catch(const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}

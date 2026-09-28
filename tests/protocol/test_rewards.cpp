#include "RewardsState.h"
#include <Network/PacketDef/Zone/ServerZoneDef.h>
#include <Network/CommonActorControl.h>
#include <iostream>

using namespace Sapphire::Testing;
namespace WS = Wire::WorldPackets::Server;
void check(bool ok, const char* reason) { if(!ok) throw std::runtime_error(reason); }
template<class T> void receive(RewardsState& state, const T& p)
{ check(state.receive(T::_ServerIpcType, ipc(T::_ServerIpcType, objectBytes(p))), "packet not recognized"); }
int main()
{
  try
  {
    RewardsState state;
    check(!state.state()["inventory_ready"], "no optimistic initial inventory");
    WS::FFXIVIpcNormalItem initial{};
    initial.contextId = 10; initial.item.storageId = 0; initial.item.catalogId = 4551; initial.item.stack = 2;
    receive(state, initial);
    check(state.state()["inventory"].empty(), "snapshot requires end/count");
    WS::FFXIVIpcItemSize size{};
    size.contextId = 10; size.storageId = 0; size.size = 1;
    receive(state, size);
    check(state.state()["inventory"]["0:0"]["count"] == 2, "observed initial item");
    for(auto storage : {1, 2, 3, 2000})
    { size.contextId++; size.storageId = storage; size.size = 0; receive(state, size); }
    check(state.state()["inventory_ready"], "all required initial containers received");

    WS::FFXIVIpcUpdateItem update{};
    update.contextId = 50; update.item.storageId = 0; update.item.catalogId = 4551; update.item.stack = 4;
    receive(state, update);
    check(state.state()["inventory"]["0:0"]["count"] == 2, "update waits for batch acknowledgement");
    WS::FFXIVIpcItemOperationBatch batch{};
    batch.contextId = 50; receive(state, batch);
    check(state.state()["inventory"]["0:0"]["count"] == 4, "committed item delta");
    receive(state, batch);
    check(state.state()["inventory"]["0:0"]["count"] == 4, "duplicate acknowledgement does not duplicate reward");
    update.contextId = 51; update.item.stack = 7; receive(state, update);
    batch.contextId = 51; batch.errorType = 1;
    bool rejected = false;
    try { receive(state, batch); } catch(const ProtocolError&) { rejected = true; }
    check(rejected && state.state()["inventory"]["0:0"]["count"] == 4, "failed transaction cannot grant observed items");
    size.contextId = 52; size.storageId = 0; size.size = 0; receive(state, size);
    check(state.state()["inventory"].empty(), "new empty snapshot clears old slots");
    size.contextId = 53; size.size = 1; rejected = false;
    try { receive(state, size); } catch(const ProtocolError&) { rejected = true; }
    check(rejected, "missing item does not complete snapshot");

    WS::FFXIVIpcItemOperation created{};
    created.contextId = 60; created.operationType = Sapphire::Common::ITEM_OPERATION_TYPE_CREATEITEM;
    created.dstStorageId = 1; created.dstContainerIndex = 2; created.dstCatalogId = 4551; created.dstStack = 2;
    receive(state, created);
    check(!state.state()["inventory"].contains("1:2"), "create waits for commit");
    batch.contextId = 60; batch.errorType = 0; receive(state, batch);
    check(state.state()["inventory"]["1:2"]["count"] == 2, "created reward uses destination fields");

    WS::FFXIVIpcPlayerStatus player{};
    player.ClassJob = 1; player.Exp[0] = 12; player.Lv[0] = 1; receive(state, player);
    check(state.state()["exp_by_index"][0] == 12, "initial XP from server");
    WS::FFXIVIpcActorControlSelf xp{};
    xp.category = Sapphire::Network::ActorControl::UpdateUiExp; xp.param1 = 1; xp.param2 = 62; receive(state, xp);
    check(state.state()["exp_by_class"]["1"] == 62, "XP update uses class identity");
    receive(state, player);
    check(state.state()["exp_by_class"].empty(), "full state supersedes old incremental XP");
    std::cout << "Observed inventory transactions and XP tests passed\n";
    return 0;
  }
  catch(const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}

#include "RewardsState.h"
#include "InventoryActions.h"
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

    auto discard = discardItemRequest(state.state(), 0x12345678, 0x01020304, 1, 2, 4551);
    check(discard.size() == 48 && discard[0] == 4 && discard[3] == 1 && discard[4] == 7,
          "discard context/type wire fixture");
    check(discard[8] == 0x78 && discard[11] == 0x12 && discard[12] == 1 && discard[16] == 2 &&
          discard[20] == 2 && discard[24] == 0xc7 && discard[25] == 0x11 && discard[28] == 0,
          "discard uses observed identity, bag, slot and full stack");
    check(state.state()["inventory"].contains("1:2"), "sending discard is not an observation");
    for(auto bad : {std::array<uint32_t, 3>{2000, 0, 4551}, {1, 25, 4551}, {1, 2, 4555}, {0, 0, 4551}})
    {
      rejected = false;
      try { discardItemRequest(state.state(), 1, 1, bad[0], bad[1], bad[2]); }
      catch(const ProtocolError&) { rejected = true; }
      check(rejected, "discard must reject unobserved/mismatched/non-bag items");
    }
    batch.contextId = 0x40000001; receive(state, batch);
    check(state.state()["inventory"].contains("1:2"), "request acknowledgement does not prove deletion");
    WS::FFXIVIpcItemOperation removed{};
    removed.contextId = 61; removed.operationType = Sapphire::Common::ITEM_OPERATION_TYPE_DELETEITEM;
    removed.srcStorageId = 1; removed.srcContainerIndex = 2; removed.srcCatalogId = 4551; removed.srcStack = 2;
    receive(state, removed);
    check(state.state()["inventory"].contains("1:2"), "delete waits for transaction commit");
    batch.contextId = 61; batch.errorType = 1; rejected = false;
    try { receive(state, batch); } catch(const ProtocolError&) { rejected = true; }
    check(rejected && state.state()["inventory"].contains("1:2"), "rejected delete retains inventory");
    removed.contextId = 62; receive(state, removed);
    batch.contextId = 62; batch.errorType = 0; receive(state, batch);
    check(!state.state()["inventory"].contains("1:2"), "delete removes the stack despite nonzero source count");

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

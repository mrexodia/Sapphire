#include "RewardsState.h"
#include "InventoryActions.h"
#include <Network/PacketDef/Zone/ServerZoneDef.h>
#include <Network/CommonActorControl.h>
#include <array>
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

    // Independently authored wire offsets: whole stack to an EMPTY ordinary bag
    // slot, not a shared-struct round trip or a move prediction.
    auto move = moveItemRequest(state.state(), 0x12345678, 0x01020304, 1, 2, 4551, 3, 24);
    Bytes moveExpected(48, 0);
    moveExpected[0] = 4; moveExpected[1] = 3; moveExpected[2] = 2; moveExpected[3] = 1;
    moveExpected[4] = 8;
    for(auto offset : {8, 28})
    { moveExpected[offset] = 0x78; moveExpected[offset+1] = 0x56; moveExpected[offset+2] = 0x34; moveExpected[offset+3] = 0x12; }
    moveExpected[12] = 1; moveExpected[16] = 2; moveExpected[20] = 2;
    moveExpected[24] = 0xc7; moveExpected[25] = 0x11;
    moveExpected[32] = 3; moveExpected[36] = 24;
    check(move == moveExpected, "move request must match exact bounded empty-destination wire fixture");
    check(state.state()["inventory"].contains("1:2") && !state.state()["inventory"].contains("3:24"),
          "request serialization never moves inventory");
    auto gearState = state.state();
    gearState["class_job"] = 1;
    gearState["containers"]["1000"] = true;
    gearState["inventory"]["1000:0"] = {{"storage", 1000}, {"slot", 0}, {"id", 1601}, {"count", 1}};
    auto unequip = unequipItemRequest(gearState, 0x12345678, 0x01020308, 0, 1601, 3, 24);
    Bytes unequipExpected = moveExpected;
    unequipExpected[0] = 8;
    unequipExpected[12] = 0xe8; unequipExpected[13] = 0x03;
    unequipExpected[16] = 0; unequipExpected[20] = 1;
    unequipExpected[24] = 0x41; unequipExpected[25] = 0x06;
    check(unequip == unequipExpected, "unequip request must match exact gear-to-bag wire fixture");
    for(int fault = 0; fault < 7; ++fault)
    {
      auto invalid = gearState;
      if(fault == 0) invalid["inventory_ready"] = false;
      if(fault == 1) invalid["containers"].erase("1000");
      if(fault == 2) invalid["inventory"].erase("1000:0");
      if(fault == 3) invalid["inventory"]["1000:0"]["id"] = 1602;
      if(fault == 4) invalid["inventory"]["3:24"] = invalid["inventory"]["1000:0"];
      rejected = false;
      try { unequipItemRequest(invalid, 1, 1, fault == 5 ? 14 : 0, 1601,
                               fault == 6 ? 4 : 3, 24); }
      catch(const ProtocolError&) { rejected = true; }
      check(rejected, "invalid/unobserved/mismatched unequip rejected");
    }
    auto reequipState = gearState;
    auto starter = reequipState["inventory"]["1000:0"];
    reequipState["inventory"].erase("1000:0");
    starter["storage"] = 3; starter["slot"] = 24;
    reequipState["inventory"]["3:24"] = starter;
    auto reequip = reequipStarterItemRequest(reequipState, 0x12345678, 0x01020309, 3, 24, 1601, 0);
    Bytes reequipExpected = moveExpected;
    reequipExpected[0] = 9;
    reequipExpected[12] = 3; reequipExpected[16] = 24; reequipExpected[20] = 1;
    reequipExpected[24] = 0x41; reequipExpected[25] = 0x06;
    reequipExpected[32] = 0xe8; reequipExpected[33] = 0x03;
    reequipExpected[36] = 0;
    check(reequip == reequipExpected, "starter re-equip must match exact bag-to-main-hand wire fixture");
    auto shopEquipState = reequipState;
    shopEquipState["inventory"]["3:24"]["id"] = 3286;
    auto shopEquip = equipShopItemRequest(shopEquipState, 0x12345678, 0x0102030a,
                                          3, 24, 3286, Sapphire::Common::GearSetSlot::Legs);
    auto shopEquipExpected = reequipExpected;
    shopEquipExpected[0] = 0x0a; shopEquipExpected[24] = 0xd6; shopEquipExpected[25] = 0x0c;
    shopEquipExpected[36] = Sapphire::Common::GearSetSlot::Legs;
    check(shopEquip == shopEquipExpected, "shop leg equip must match exact bag-to-gear wire fixture");
    auto shopFeetState = shopEquipState;
    shopFeetState["inventory"]["3:24"]["id"] = 3748;
    auto shopFeet = equipShopItemRequest(shopFeetState, 0x12345678, 0x0102030a,
                                         3, 24, 3748, Sapphire::Common::GearSetSlot::Feet);
    auto shopFeetExpected = shopEquipExpected;
    shopFeetExpected[24] = 0xa4; shopFeetExpected[25] = 0x0e;
    shopFeetExpected[36] = Sapphire::Common::GearSetSlot::Feet;
    check(shopFeet == shopFeetExpected, "shop foot equip must match exact bag-to-gear wire fixture");
    rejected = false;
    try { equipShopItemRequest(shopFeetState, 1, 1, 3, 24, 3748,
                               Sapphire::Common::GearSetSlot::Legs); }
    catch(const ProtocolError&) { rejected = true; }
    check(rejected, "shop foot item rejects mismatched leg destination");
    auto shopBodyState = shopEquipState;
    shopBodyState["inventory"]["3:24"]["id"] = 2967;
    auto shopBody = equipShopItemRequest(shopBodyState, 0x12345678, 0x0102030a,
                                         3, 24, 2967, Sapphire::Common::GearSetSlot::Body);
    auto shopBodyExpected = shopEquipExpected;
    shopBodyExpected[24] = 0x97; shopBodyExpected[25] = 0x0b;
    shopBodyExpected[36] = Sapphire::Common::GearSetSlot::Body;
    check(shopBody == shopBodyExpected, "shop body equip must match exact bag-to-gear wire fixture");
    rejected = false;
    try { equipShopItemRequest(shopBodyState, 1, 1, 3, 24, 2967,
                               Sapphire::Common::GearSetSlot::Feet); }
    catch(const ProtocolError&) { rejected = true; }
    check(rejected, "shop body item rejects mismatched foot destination");
    for(int fault = 0; fault < 5; ++fault)
    {
      auto invalid = shopEquipState;
      if(fault == 0) invalid["class_job"] = 2;
      if(fault == 1) invalid["inventory"]["3:24"]["id"] = 3287;
      if(fault == 2) invalid["inventory"]["3:24"]["count"] = 2;
      if(fault == 3) invalid["inventory"]["1000:6"] = {{"id", 3296}, {"count", 1}};
      rejected = false;
      try { equipShopItemRequest(invalid, 1, 1, 3, 24, 3286,
                                 fault == 4 ? Sapphire::Common::GearSetSlot::Feet : Sapphire::Common::GearSetSlot::Legs); }
      catch(const ProtocolError&) { rejected = true; }
      check(rejected, "invalid/mismatched shop equipment request rejected");
    }
    for(const auto& supported : {std::pair<uint32_t, uint32_t>{2, 1680}, {7, 2055}})
    {
      auto other = reequipState;
      other["class_job"] = supported.first;
      other["inventory"]["3:24"]["id"] = supported.second;
      auto request = reequipStarterItemRequest(other, 0x12345678, 0x01020309, 3, 24, supported.second, 0);
      reequipExpected[24] = static_cast<uint8_t>(supported.second);
      reequipExpected[25] = static_cast<uint8_t>(supported.second >> 8);
      check(request == reequipExpected, "each Ul'dah starter main hand has an exact wire fixture");
    }
    for(const auto& armor : {std::pair<uint32_t, uint32_t>{3, 2983}, {4, 3520}, {6, 3296}, {7, 3750}})
    {
      auto other = reequipState;
      other["inventory"]["3:24"]["id"] = armor.second;
      auto request = reequipStarterItemRequest(other, 0x12345678, 0x01020309, 3, 24,
                                               armor.second, armor.first);
      reequipExpected[24] = static_cast<uint8_t>(armor.second);
      reequipExpected[25] = static_cast<uint8_t>(armor.second >> 8);
      reequipExpected[36] = static_cast<uint8_t>(armor.first);
      check(request == reequipExpected, "each shared Ul'dah starter armor slot has an exact wire fixture");
    }
    for(uint32_t ring : {4423u, 4424u, 4425u, 4426u})
      for(uint32_t ringSlot : {Sapphire::Common::GearSetSlot::Ring1, Sapphire::Common::GearSetSlot::Ring2})
      {
        auto other = reequipState;
        other["inventory"]["3:24"]["id"] = ring;
        auto request = reequipStarterItemRequest(other, 0x12345678, 0x01020309, 3, 24, ring, ringSlot);
        reequipExpected[24] = static_cast<uint8_t>(ring);
        reequipExpected[25] = static_cast<uint8_t>(ring >> 8);
        reequipExpected[36] = static_cast<uint8_t>(ringSlot);
        check(request == reequipExpected, "each source-defined Ul'dah ring has exact Ring1/Ring2 fixtures");
      }
    {
      auto invalidRing = reequipState;
      invalidRing["inventory"]["3:24"]["id"] = 4423;
      rejected = false;
      try { reequipStarterItemRequest(invalidRing, 1, 1, 3, 24, 4423, Sapphire::Common::GearSetSlot::Neck); }
      catch(const ProtocolError&) { rejected = true; }
      check(rejected, "starter accessory rejects a non-ring slot");
    }
    for(int fault = 0; fault < 9; ++fault)
    {
      auto invalid = reequipState;
      if(fault == 0) invalid["inventory_ready"] = false;
      if(fault == 1) invalid["containers"].erase("1000");
      if(fault == 2) invalid["inventory"].erase("3:24");
      if(fault == 3) invalid["inventory"]["3:24"]["count"] = 2;
      if(fault == 4) invalid["inventory"]["1000:0"] = starter;
      if(fault == 7) invalid["class_job"] = 2;
      rejected = false;
      try { reequipStarterItemRequest(invalid, 1, 1, fault == 5 ? 4 : 3, 24,
                                      fault == 6 ? 1602 : 1601, fault == 8 ? 13 : 0); }
      catch(const ProtocolError&) { rejected = true; }
      check(rejected, "invalid/unobserved/mismatched starter re-equip rejected");
    }
    for(auto bad : {std::array<uint32_t, 5>{4, 2, 4551, 3, 24}, {1, 25, 4551, 3, 24},
                   {1, 2, 4551, 4, 24}, {1, 2, 4551, 3, 25}, {1, 2, 4551, 1, 2},
                   {1, 2, 0, 3, 24}, {1, 2, 4555, 3, 24}, {0, 0, 4551, 3, 24},
                   {1, 2, 4551, 2000, 0}})
    {
      rejected = false;
      try { moveItemRequest(state.state(), 1, 1, bad[0], bad[1], bad[2], bad[3], bad[4]); }
      catch(const ProtocolError&) { rejected = true; }
      check(rejected, "invalid/non-bag/mismatched/self move rejected");
    }
    for(int fault = 0; fault < 4; ++fault)
    {
      auto invalid = state.state();
      if(fault == 0) invalid["inventory_ready"] = false;
      if(fault == 1) invalid["inventory"]["3:24"] = invalid["inventory"]["1:2"];
      if(fault == 2) invalid["containers"].erase("3");
      if(fault == 3) invalid["inventory"]["1:2"]["count"] = 0;
      rejected = false;
      try { moveItemRequest(invalid, 1, 1, 1, 2, 4551, 3, 24); }
      catch(const ProtocolError&) { rejected = true; }
      check(rejected, "unready/occupied/unobserved/empty move rejected");
    }
    auto swapState = state.state();
    swapState["inventory"]["3:24"] = {{"storage", 3}, {"slot", 24}, {"id", 4555}, {"count", 3}};
    auto swap = swapItemRequest(swapState, 0x12345678, 0x01020305, 1, 2, 4551, 3, 24, 4555);
    Bytes swapExpected = moveExpected;
    swapExpected[0] = 5; swapExpected[4] = 9;
    swapExpected[40] = 3; swapExpected[44] = 0xcb; swapExpected[45] = 0x11;
    check(swap == swapExpected, "swap request must match exact bounded occupied-destination wire fixture");
    check(swapState["inventory"]["1:2"]["id"] == 4551 && swapState["inventory"]["3:24"]["id"] == 4555,
          "swap serialization never changes inventory");
    for(int fault = 0; fault < 8; ++fault)
    {
      auto invalid = swapState;
      if(fault == 0) invalid["inventory_ready"] = false;
      if(fault == 1) invalid["inventory"].erase("3:24");
      if(fault == 2) invalid["inventory"]["3:24"]["id"] = 999;
      if(fault == 3) invalid["inventory"]["3:24"]["count"] = 0;
      if(fault == 4) invalid["containers"].erase("3");
      rejected = false;
      try
      {
        if(fault == 5) swapItemRequest(invalid, 1, 1, 1, 2, 4551, 1, 2, 4555);
        else if(fault == 6) swapItemRequest(invalid, 1, 1, 1, 2, 4551, 3, 24, 4551);
        else if(fault == 7) swapItemRequest(invalid, 1, 1, 1, 2, 4551, 4, 24, 4555);
        else swapItemRequest(invalid, 1, 1, 1, 2, 4551, 3, 24, 4555);
      }
      catch(const ProtocolError&) { rejected = true; }
      check(rejected, "invalid/unready/unobserved/mismatched swap rejected");
    }
    auto split = splitItemRequest(state.state(), 0x12345678, 0x01020306,
                                  1, 2, 4551, 2, 1, 3, 24);
    Bytes splitExpected = moveExpected;
    splitExpected[0] = 6; splitExpected[4] = 10;
    splitExpected[40] = 1; splitExpected[44] = 0xc7; splitExpected[45] = 0x11;
    check(split == splitExpected, "split request must match exact bounded partial-stack wire fixture");
    rejected = false;
    try { splitItemRequest(state.state(), 1, 1, 1, 2, 4551, 2, 2, 3, 24); }
    catch(const ProtocolError&) { rejected = true; }
    check(rejected, "whole-stack split rejected");
    auto splitState = state.state();
    splitState["inventory"]["3:24"] = {{"storage", 3}, {"slot", 24}, {"id", 4551}, {"count", 1}};
    auto merge = mergeItemRequest(splitState, 0x12345678, 0x01020307,
                                  3, 24, 4551, 1, 1, 2, 2);
    Bytes mergeExpected = splitExpected;
    mergeExpected[0] = 7; mergeExpected[4] = 12;
    mergeExpected[12] = 3; mergeExpected[16] = 24; mergeExpected[20] = 1;
    mergeExpected[32] = 1; mergeExpected[36] = 2; mergeExpected[40] = 2;
    check(merge == mergeExpected, "merge request must match exact bounded matching-stack wire fixture");
    rejected = false;
    try { mergeItemRequest(swapState, 1, 1, 3, 24, 4555, 3, 1, 2, 2); }
    catch(const ProtocolError&) { rejected = true; }
    check(rejected, "mismatched merge rejected");

    batch.contextId = 0x01020305; batch.operationType = 9; batch.errorType = 0;
    auto swapInventoryBeforeAck = state.state()["inventory"];
    receive(state, batch);
    check(state.state()["inventory"] == swapInventoryBeforeAck, "swap acknowledgement is NOT mutation proof");
    check(state.state()["operation_batches"].back() == nlohmann::json{{"context", 0x01020305}, {"operation", 9}, {"error", 0}},
          "swap acknowledgement retains exact context/type/error");

    auto inventoryBeforeAck = state.state()["inventory"];
    batch.contextId = 0x01020304; batch.operationType = 8; batch.errorType = 0; receive(state, batch);
    check(state.state()["inventory"] == inventoryBeforeAck, "move acknowledgement is NOT mutation proof");
    check(state.state()["operation_batches"].back() == nlohmann::json{{"context", 0x01020304}, {"operation", 8}, {"error", 0}},
          "move acknowledgement retains exact context/type/error");
    batch.contextId++; batch.errorType = 1; rejected = false;
    try { receive(state, batch); } catch(const ProtocolError&) { rejected = true; }
    check(rejected && state.state()["inventory"] == inventoryBeforeAck, "failed move cannot change observed state");
    check(state.state()["operation_batches"].back()["error"] == 1, "failed acknowledgement remains diagnostic evidence");
    batch.errorType = 0; batch.operationType = 0;
    for(int i = 0; i < 200; ++i) { batch.contextId++; receive(state, batch); }
    check(state.state()["operation_batches"].size() == 128, "batch history is bounded");

    // Only complete fresh server snapshots establish the moved placement.
    RewardsState fresh;
    initial.contextId = 70; initial.item.storageId = 3; initial.item.containerIndex = 24;
    initial.item.catalogId = 4551; initial.item.stack = 2; receive(fresh, initial);
    check(fresh.state()["inventory"].empty(), "destination needs snapshot completion");
    size.contextId = 70; size.storageId = 3; size.size = 1; receive(fresh, size);
    check(!fresh.state()["inventory_ready"], "one bag does not establish all inventory");
    for(auto storage : {0, 1, 2, 2000})
    { size.contextId++; size.storageId = storage; size.size = 0; receive(fresh, size); }
    check(fresh.state()["inventory_ready"] && fresh.state()["inventory"].size() == 1 &&
          fresh.state()["inventory"]["3:24"]["count"] == 2 && !fresh.state()["inventory"].contains("1:2"),
          "received fresh snapshots establish source absence and exact destination stack");

    auto vfxRewards = state.state();
    vfxRewards["inventory"]["3:24"] = {{"storage", 3}, {"slot", 24}, {"id", 5890}, {"count", 3}};
    auto vfx = shopVfxItemRequest(vfxRewards, 0x12345678, 5, 3, 24, 3);
    Bytes expectedVfx(32, 0); expectedVfx[1] = 2; expectedVfx[4] = 0x02; expectedVfx[5] = 0x17;
    expectedVfx[8] = 5; expectedVfx[16] = 0x78; expectedVfx[17] = 0x56;
    expectedVfx[18] = 0x34; expectedVfx[19] = 0x12;
    expectedVfx[24] = 24; expectedVfx[26] = 3;
    check(vfx == expectedVfx, "shop VFX item exact action request fixture");
    for(auto invalid : {std::array<uint32_t,3>{4,24,3}, {3,25,3}, {3,24,2}})
    {
      bool rejected = false;
      try { shopVfxItemRequest(vfxRewards, 1, 1, invalid[0], invalid[1], invalid[2]); }
      catch(const ProtocolError&) { rejected = true; }
      check(rejected, "invalid shop VFX item source/count must fail");
    }
    auto wrongVfx = vfxRewards; wrongVfx["inventory"]["3:24"]["id"] = 5891;
    bool wrongVfxRejected = false;
    try { shopVfxItemRequest(wrongVfx, 1, 1, 3, 24, 3); }
    catch(const ProtocolError&) { wrongVfxRejected = true; }
    check(wrongVfxRejected, "wrong shop VFX item identity must fail");

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

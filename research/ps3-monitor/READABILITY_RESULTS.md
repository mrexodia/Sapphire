# Windows IDB readability pass

## Outcome

The saved Windows 3.35 IDB now uses the confirmed Sapphire/PS3 packet work as
semantic anchors rather than only as function names. The pass is reproducible
through `build_readability_plan.py`, `ida_apply_readability.py`, and the
source-controlled plan/type files.

Applied and verified:

| Improvement | Count |
| --- | ---: |
| Concrete local types | 42 |
| Typed functions | 67 |
| Typed globals | 4 |
| Additional named globals | 1 |
| Dispatcher case-address comments | 309 |
| PS3-linked Windows names/comments | 240 |
| Windows-semantic/supporting names/comments without PS3 links | 17 |

The 309 comments cover all explicit Windows dispatcher cases that have distinct
ctree case addresses; fall-through cases sharing an address are grouped in one
comment.

## Dispatcher improvements

The zone and chat dispatchers now receive typed IPC views:

```cpp
void OnReceivePacket_Zone(
    Win335_PacketDispatcher *self,
    uint32_t targetActorId,
    const Win335_ZoneIpcPacket *packet);
```

Consequences in Hex-Rays include:

- `switch (packet->opcode)` instead of `switch (*(_WORD *)(a3 + 2))`;
- symbolic `Win335_ZoneDownOpcode_*` and `Win335_ChatDownOpcode_*` cases;
- `packet->payload` instead of repeated `a3 + 16` expressions;
- explicitly unknown names for cases whose semantics are not proven;
- grouped comments distinguishing PS3-linked, Windows-semantic, inline, and
  unproven numeric cases.

The generated IPC payload array is an inspection window, not an exact wire-size
claim.

## Packet types

`windows_readability_types.h` contains 31 `Win335_*_KnownFields` structures.
They include only the 83 independently Windows-confirmed field observations
recorded in `packet_structures.json`. Unknown gaps remain byte arrays, and no
PS3-only trailing size is asserted.

Twenty-five handlers that demonstrably receive the complete payload pointer now
use these types. For example, `InviteResult` decompiles using
`packet->AuthType` and `packet->Result`, while `PlayerStatusUpdate` uses
`packet->ClassJob`, `packet->Lv`, `packet->LvSync`, `packet->Exp`, and
`packet->RestPoint` at the proven Windows offsets.

Handlers whose dispatchers extract individual fields, such as the quest and
daily-quest SyncTag family, were intentionally not assigned a whole-packet
pointer type.

## Framework, information-proxy, and treasure semantic islands

Four high-leverage accessors/lookups are linked directly to PS3 DWARF identities:

- Windows `0x140013960` ↔ PS3 `0x00017A78`:
  `Client::System::Framework::Framework::GetUIModule`
- Windows `0x1406044E0` ↔ PS3 `0x00A516F4`:
  `Client::Game::Event::EventFramework::GetInstance`
- Windows `0x140032C30` ↔ PS3 `0x0024059C`:
  `Client::UI::Info::InfoModule::GetProxy`
- Windows `0x1405428B0` ↔ PS3 `0x0098829C`:
  `Client::Game::Object::TreasureManager::GetTreasureFromEntityId`

`InfoModule::GetProxy` is confirmed by the same indexed proxy-array access and
by eight matched retainer/market handlers using the same proxy IDs. Its partial
receiver type turns the body into `self->proxies[proxyId]`. Nine downstream
InfoModule/InfoProxyItemSearch methods are also linked and typed: request
result, retainer-list and singular-retainer updates, market-buy result, market
callback, item and retainer sales history, and both error-printer overloads.
Their matched callers now decompile as a coherent proxy-ID-9 path instead of
untyped calls.

The TreasureManager match is anchored by both object-table loops, entity-ID
comparison, object-kind 4 check, and the same matched treasure callers. Its
global receiver is named without asserting an unproven complete class layout.

The Framework accessor remains especially high leverage: it has roughly 1,500
callers and returns `Win335_UIModule *` rather than an untyped integer. Its
Framework global and the EventFramework singleton global are also named and
typed.

## Quest and leve notifications

Fifteen downstream SyncTag/EventFramework boundaries are now PS3-linked and
typed, including:

- quest-array initialization and `OnSyncQuest`;
- quest-completion initialization and incremental synchronization;
- bulk and singular daily-quest synchronization;
- repeat-flag initialization, bulk synchronization, and singular updates;
- guildleve initialization and `OnSyncGuildleve`;
- leve-completion initialization and incremental synchronization.

The three Windows leve initialization/completion notifications at
`0x140604600`–`0x140604620` are dedicated no-ops in 3.x. They are still mapped
because their unique matched callers preserve the source-level method
boundaries. `Win335_QuestWork_KnownFields` and
`Win335_LeveWork_KnownFields` expose only the Windows-confirmed IDs and quest
sequence byte.

## Inventory fragment assembler

The retainer, market-price, item-operation, and item-storage wrappers and their
four downstream implementations now use:

- `Win335_ZoneIpcPacket *` and symbolic packet opcodes;
- `targetActorId` argument names;
- typed `Win335_ItemPacketAssembler`, `Win335_ItemAssemblyContext`, and
  `Win335_ItemAssemblyFragment` links;
- named acquire, append, and release helpers;
- named fields for the free/active lists, fragment links, target actor ID,
  received count, and expected count;
- a typed/named StorageManager singleton.

The three assembler-helper names remain explicitly Windows-supporting labels
and do not claim PS3 equivalence. Their structures are based on complete Windows
access evidence through offsets `+0x40` (assembler), `+0x38` (context), and
`+0x60` (fragment); unknown fields remain byte arrays.

## Subsystem expansion queue

`subsystem_callgraph.json` records one-hop callees from two packet-rooted
semantic islands:

| Cluster | Root functions | Direct callees | Still auto-named |
| --- | ---: | ---: | ---: |
| Quest/leve | 14 | 34 | 17 |
| Retainer/inventory | 28 | 72 | 55 |

The priority score is triage only. The strongest next review targets are now:

1. Resolve the remaining virtual InfoProxyItemSearch method at vtable slot
   `+0x50` used by `GetItemSearchListResult`, and recover a conservative concrete
   receiver layout for the proxy.
2. Identify the static/stand object manager accessors and Treasure methods used
   after `TreasureManager::GetTreasureFromEntityId`.
3. Recover the shared EventFramework initialization implementation at
   `0x1406604E0`, quest-update helper at `0x14065FF10`, and event-handler
   container rooted at EventFramework `+0x58`.
4. Type the packet-family-specific 0x50-byte fragment payload variants and the
   StorageManager commit methods reached by the four assembler implementations.

## Reproduction

Generate/check host artifacts:

```text
python research/ps3-monitor/build_readability_plan.py
python research/ps3-monitor/build_readability_plan.py --check
python research/ps3-monitor/validate_research.py
```

With the Windows IDB open through IDA Nexus, load `ida_apply_matches.py` and
`ida_apply_readability.py`, then call their apply or verification functions.
`ida_subsystem_export.py` regenerates the subsystem call graph read-only.

No PS3 IDB mutation is required. The PS3 database was used only for read-only
identity and disassembly confirmation.

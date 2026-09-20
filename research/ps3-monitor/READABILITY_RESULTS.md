# Windows IDB readability pass

## Outcome

The saved Windows 3.35 IDB now uses the confirmed Sapphire/PS3 packet work as
semantic anchors rather than only as function names. The pass is reproducible
through `build_readability_plan.py`, `ida_apply_readability.py`, and the
source-controlled plan/type files.

Applied and verified:

| Improvement | Count |
| --- | ---: |
| Concrete local types | 37 |
| Typed functions | 38 |
| Typed/named globals | 4 |
| Dispatcher case-address comments | 309 |
| PS3-linked Windows names/comments | 214 |
| Windows-semantic/supporting names/comments without PS3 links | 14 |

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

## Framework and inventory semantic islands

Two supporting functions were linked directly to PS3 DWARF identities:

- Windows `0x140013960` ↔ PS3 `0x00017A78`:
  `Client::System::Framework::Framework::GetUIModule`
- Windows `0x1406044E0` ↔ PS3 `0x00A516F4`:
  `Client::Game::Event::EventFramework::GetInstance`

The first is especially high leverage: it has roughly 1,500 callers and now
returns `Win335_UIModule *` rather than an untyped integer. Its Framework global
and the EventFramework singleton global are also named and typed.

The retainer, market-price, item-operation, and item-storage wrappers and their
four downstream implementations now use:

- `Win335_ZoneIpcPacket *`;
- symbolic packet opcodes;
- `targetActorId` argument names;
- a partial `Win335_ItemPacketAssembler` with its proven context-list member;
- a typed/named StorageManager singleton.

These implementation names remain explicitly Windows-supporting labels and do
not claim PS3 function equivalence.

## Subsystem expansion queue

`subsystem_callgraph.json` records one-hop callees from two packet-rooted
semantic islands:

| Cluster | Root functions | Direct callees | Still auto-named |
| --- | ---: | ---: | ---: |
| Quest/leve | 14 | 34 | 28 |
| Retainer/inventory | 28 | 72 | 66 |

The priority score is triage only. The strongest next review targets are:

1. `0x140032C30`, used by eight retainer/market information handlers, likely an
   indexed information-proxy accessor; its receiver class must be established
   before naming it.
2. `0x1405428B0`, shared by four treasure handlers and behaving as an actor/game
   object lookup; the exact GameObjectManager role needs a stronger cross-build
   anchor.
3. Quest/EventFramework notification functions around `0x140657ED0`,
   `0x140657FD0`, and `0x14066B1C0`–`0x14066B2A0`; their side effects are clear,
   but exact source-level method identities remain unproven.
4. The item packet-assembler context records reached through offset `+0x38`;
   recovering that node type would improve all four inventory-family
   implementations simultaneously.

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

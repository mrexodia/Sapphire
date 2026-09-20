# PS3 Monitor to 3.x client matching

This directory records cross-architecture function matches between the FFXIV
2.3 PS3 Monitor development build and the Windows 3.x client used by Sapphire.
Addresses are tied to the exact binaries and hashes in `packet_matches.json`.

## Initial result

The zone-down and chat-down packet dispatchers were matched with high confidence:

| Build | Zone address | Chat address |
| --- | ---: | ---: |
| PS3 Monitor | `0x002F8710` | `0x002FA984` |
| Windows 3.x | `0x140DD9430` | `0x140DD9300` |

The Windows zone function reads the opcode from the IPC packet, invokes the
receive-preparation hook, and directly dispatches to packet-specific handlers.
Its cases agree with the PS3 DWARF-labelled dispatcher and Sapphire's
`ThreePointThree` opcode definitions. The chat functions independently agree on
opcodes 100 through 106 and their ordered handler roles.

The class identity is additionally anchored by its constructors: PS3
`0x002F85C8` and Windows `0x140DD93E0` both store the `NetworkModuleProxy`
pointer and install adjacent Zone and Chat callback-interface vtables.

`0x1411B95B0`, previously labelled `flawed_unshuffle_opcodes` in the local IDB,
is a different generated virtual dispatcher. It maps zone opcodes to callback
vtable slots. It is useful for recovering the complete opcode/vtable ordering,
but it is not the direct equivalent of the PS3 `PacketDispatcher` function.

## Validation method

A match is accepted only when the dispatcher case and packet semantics agree.
Useful independent evidence includes:

- packet opcode and neighbouring cases;
- field offsets matching `ServerZoneDef.h`;
- the same secondary switch values;
- equivalent manager/proxy calls and state updates;
- distinctive constants or control-flow decisions.

Raw function size and CFG similarity are not sufficient across PPC64 and x64.

## Current coverage

The exhaustive pass records 285 PS3 and 355 Windows zone-down opcodes plus both
chat-down dispatchers. It confirms 209 packet-handler function pairs covering
253 opcode cases and leaves no probable or unreviewed candidate in the generated
ranking. Eleven exact shared-handler mappings preserve 55 many-opcode/one-function
relationships without inventing separate functions. Twenty-one relationships
remain unresolved across builds; the Windows side is nevertheless identified for
19 of them through ten semantic function mappings and three inline dispatcher cases.

Start with the combined [`PACKET_CATALOG.md`](PACKET_CATALOG.md), or open the
searchable [`packet_catalog.html`](packet_catalog.html) for field layouts,
evidence, and status filters. The underlying machine-readable ledgers are
`packet_matches.json`, `dispatcher_cases.json`, `packet_structures.json`, and
`case_reviews.json`. Regenerate and verify both catalog views with:

```bash
python research/ps3-monitor/build_packet_catalog.py
python research/ps3-monitor/build_packet_catalog.py --check
```

See [`OVERNIGHT_RESULTS.md`](OVERNIGHT_RESULTS.md) for the full results and
[`COMPLETION_AUDIT.md`](COMPLETION_AUDIT.md) for the requirement-to-evidence
checklist. Approved names and repeatable comments have been applied to the
local Windows IDB.
Confirmed Windows functions link back to PS3 counterparts with comments such as
`PS3 Monitor: idb://ffxivgame.ppu.elf.i64:002F85C8`.

The detailed execution plan and pasteable persistent goal remain in
[`OVERNIGHT_GOAL.md`](OVERNIGHT_GOAL.md).

## Windows IDB readability

The first semantic-island readability pass is documented in
[`READABILITY_RESULTS.md`](READABILITY_RESULTS.md). It adds generated opcode and
IPC types, 31 conservative Windows-known-field packet views, types 38 functions
and four globals, comments 309 dispatcher case addresses, and exports quest/leve
and retainer/inventory call-graph queues. `build_readability_plan.py` generates
the auditable plan/header, while `ida_apply_readability.py` applies or verifies
the changes in the Windows IDB.

## Next iteration

1. Resolve the receiver class behind `0x140032C30`, the indexed proxy accessor
   shared by eight retainer/market information handlers.
2. Identify the exact GameObjectManager role of `0x1405428B0` and recover the
   quest/EventFramework notification family around `0x140657ED0`–`0x14066B2A0`.
3. Recover the item packet-assembler context-node type used by all four typed
   retainer/market/item implementations.
4. Normalize and export outbound Zone/Chat DWARF packet types.
5. Fully validate Windows layouts before promoting any of the 99 missing
   Sapphire declarations, and retain the `0x030C`/`0x0338` conflicts until
   runtime or packet-capture evidence distinguishes them.

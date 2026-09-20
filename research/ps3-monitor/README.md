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
local Windows IDB. The downstream readability pass extends this to 267
PS3-linked functions and 19 Windows-semantic/supporting functions.
Confirmed Windows functions link back to PS3 counterparts with comments such as
`PS3 Monitor: idb://ffxivgame.ppu.elf.i64:002F85C8`.

The detailed execution plan and pasteable persistent goal remain in
[`OVERNIGHT_GOAL.md`](OVERNIGHT_GOAL.md).

## Windows IDB readability

The semantic-island readability work is documented in
[`READABILITY_RESULTS.md`](READABILITY_RESULTS.md). It adds generated opcode and
IPC types, 36 conservative Windows-known-field packet views, 59 concrete local
types, 101 typed functions, four typed globals, four additional named globals,
and comments on 309 dispatcher case addresses. It also resolves
`InfoModule::GetProxy`, `TreasureManager::GetTreasureFromEntityId`, the typed
InfoProxyItemSearch page lifecycle and records, the Treasure/GameObject creation
and packet family, the quest/leve EventFramework handler tree and notification
family, and the shared item-fragment assembler layouts. `build_readability_plan.py` generates the auditable
plan/header, while `ida_apply_readability.py` applies or verifies the changes in
the Windows IDB.

## Sapphire packet declaration cleanup

The production header now uses evidence-backed semantic names for quest
completion, tracking entries, condition/configuration flags, and actor movement
state. The `FFFXIVIpcItemSearchResult` typo is corrected. No PS3 layout is
copied wholesale: `FFXIVIpcActorMove` gains four trailing padding bytes only
because both PS3 DWARF size and the Windows fixed 16-byte queue copy prove the
wire size. Structure inventory generation discovers actual
`FFXIVIpcBasePacket<Role>` specializations, reducing false missing declarations
from 99 to 80 while preserving descriptive Sapphire type names. See
[`SAPPHIRE_PACKET_CLEANUP.md`](SAPPHIRE_PACKET_CLEANUP.md) for the per-field
evidence classification and deliberately retained unknowns.

## Next iteration

1. Recover remaining InfoProxyItemSearch formatter/agent methods downstream of
   the typed page and history paths.
2. Resolve the new 3.x `CreateTreasure` byte at payload `+0x15` and prove exact
   wire sizes before promoting treasure packet declarations.
3. Extend EventFramework update/range boundaries and type packet-family-specific
   item-assembly fragment payloads.
4. Normalize and export outbound Zone/Chat DWARF packet types.
5. Fully validate Windows layouts before promoting any of the 80 genuinely
   missing Sapphire declarations, and retain the `0x030C`/`0x0338` conflicts until
   runtime or packet-capture evidence distinguishes them.

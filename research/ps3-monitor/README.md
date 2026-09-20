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
chat-down dispatchers. It confirms 203 packet-handler function pairs covering
246 opcode cases, reviews 28 additional same-opcode relationships, and leaves
no unreviewed candidate in the generated ranking. Eleven exact shared-handler
mappings preserve 54 many-opcode/one-function relationships without inventing
separate functions. The remaining 4 probable relationships are retained
without authoritative names.

See `packet_matches.json` for confirmed addresses and evidence,
`dispatcher_cases.json` for complete case coverage, `packet_structures.json` for
246 PS3 DWARF layouts and Windows/Sapphire comparisons, and
[`OVERNIGHT_RESULTS.md`](OVERNIGHT_RESULTS.md) for the results, and
[`COMPLETION_AUDIT.md`](COMPLETION_AUDIT.md) for the requirement-to-evidence
checklist. Approved names and repeatable comments have been applied to the
local Windows IDB.
Confirmed Windows functions link back to PS3 counterparts with comments such as
`PS3 Monitor: idb://ffxivgame.ppu.elf.i64:002F85C8`.

The detailed execution plan and pasteable persistent goal remain in
[`OVERNIGHT_GOAL.md`](OVERNIGHT_GOAL.md).

## Next iteration

1. Export every direct case/callee from both zone-down dispatchers.
2. Seed matches using opcodes that remain stable between 2.3 and 3.x.
3. Verify each seed using packet layouts and callee semantics.
4. Use verified handlers to propagate names into manager/UI functions.
5. Record renamed, removed, and newly introduced packets rather than forcing a
   one-to-one match.
6. Add a re-runnable IDAPython importer after the mapping schema stabilizes.

# PS3 Monitor to 3.x client matching

This directory records cross-architecture function matches between the FFXIV
2.3 PS3 Monitor development build and the Windows 3.x client used by Sapphire.
Addresses are tied to the exact binaries and hashes in `packet_matches.json`.

## Initial result

The zone-down packet dispatcher was matched with high confidence:

| Build | Address | Function |
| --- | ---: | --- |
| PS3 Monitor | `0x002F8710` | `Client::Network::PacketDispatcher::OnReceivePacket(uint32_t, ZoneProtoDown const&)` |
| Windows 3.x | `0x140DD9430` | `Client__Network__PacketDispatcher__OnReceivePacket_Zone` |

The Windows function reads the zone opcode from the IPC packet, invokes the
receive-preparation hook, and directly dispatches to packet-specific handlers.
Its cases agree with the PS3 DWARF-labelled dispatcher and Sapphire's
`ThreePointThree` opcode definitions.

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

The first pass identifies ten packet-specific handlers:

- `InviteResult` (`0x00C9`)
- `InviteReplyResult` (`0x00CA`)
- `InviteUpdate` (`0x00CB`)
- `GetCommonlistResult` (`0x00CC`)
- `GetCommonlistDetailResult` (`0x00CD`)
- `SetProfileResult` (`0x00CE`)
- `Create` (`0x0190`)
- `InitZone` (`0x019A`)
- `PlayerStatusUpdate` (`0x019F`)
- `PlayerStatus` (`0x01A0`)

See `packet_matches.json` for addresses and evidence. The approved names and
repeatable comments have also been applied to the local Windows IDB.

## Next iteration

1. Export every direct case/callee from both zone-down dispatchers.
2. Seed matches using opcodes that remain stable between 2.3 and 3.x.
3. Verify each seed using packet layouts and callee semantics.
4. Use verified handlers to propagate names into manager/UI functions.
5. Record renamed, removed, and newly introduced packets rather than forcing a
   one-to-one match.
6. Add a re-runnable IDAPython importer after the mapping schema stabilizes.

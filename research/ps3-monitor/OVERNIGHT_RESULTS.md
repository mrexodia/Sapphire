# Packet-matching run results

## Outcome

The core zone-down and chat-down dispatchers were exhaustively inventoried and
triaged for the PS3 Monitor 2.3 build and the Windows 3.x client. The direct
one-to-one mapping pass produced 179 confirmed packet-handler matches and 179
corresponding PS3 DWARF structure records. No unreviewed candidate remains in
the generated ranking.

No production packet header was changed. The structure ledger identifies gaps,
but incomplete Windows size/layout evidence makes adding those declarations
premature.

## Dispatcher coverage

| Build/channel | Explicit opcodes | Confirmed | Probable | Build-only case presence | Unresolved |
| --- | ---: | ---: | ---: | ---: | ---: |
| PS3 zone-down | 285 | 172 | 74 | 18 PS3-only | 22 |
| Windows zone-down | 355 | 172 | 74 | 88 Windows-only | 22 |
| PS3 chat-down | 8 | 7 | 0 | 1 PS3-only | 1 |
| Windows chat-down | 7 | 7 | 0 | 0 | 1 |

The unresolved counts include each dispatcher's default case. Twenty-one
same-opcode zone relationships remain unresolved after review. The 74 probable
relationships are primarily shared, merged, or variant handlers for which an
authoritative one-to-one function link would be misleading.

`ps3-only` and `windows-only` mean that the numeric dispatcher case occurs in
only that build. They do not prove that the semantic feature lacks a
changed-opcode counterpart.

## Confirmed mappings

- 179 packet-handler pairs:
  - 172 zone-down handlers
  - 7 chat-down handlers
- Three supporting `PacketDispatcher` functions:
  - constructor
  - zone-down dispatcher
  - chat-down dispatcher
- 182 Windows functions in total have verified names and repeatable PS3 links.

Every confirmed Windows function comment starts with:

```text
PS3 Monitor: idb://ffxivgame.ppu.elf.i64:XXXXXXXX
```

The mapping ledger is `packet_matches.json`. `ida_apply_matches.py` can apply or
verify the names and comments. A verification pass checked all 182 entries with
zero failures after saving `E:/Sapphire/game/ffxiv_dx11.exe.i64`.

Three obviously unrelated pre-existing names were replaced after the dispatcher
and semantic evidence proved the packet roles:

- Windows `0x140CBE8B0`: `ReceiveFatePcWork`
- Windows `0x140CBE8F0`: `ReceiveFateAccessCollectionEventObject`
- Windows `0x140CC1330`: `OnMIPMemberList`

## Structure results

`packet_structures.json` contains 179 PS3 DWARF packet structures, their member
offsets and sizes, current and immutable ThreePointThree Sapphire declaration
locations, and per-field Windows validation where available.

The strongest confirmed layout delta is:

| Packet | Field | PS3 2.3 | Windows 3.x |
| --- | --- | ---: | ---: |
| `PlayerStatusUpdate` | `LvSync` | `+0x04` | `+0x06` |

The current Sapphire declaration already reflects the 3.x layout by placing
`Lv1` at `+0x04` and `LvSync` at `+0x06`, so no correction was needed.

Sixty-six confirmed packet roles currently lack a correspondingly named
Sapphire declaration. They are recorded as research gaps rather than production
changes because many complete 3.x sizes and unaccessed fields remain unproven.
The complete list is in `packet_structures.json` under
`summary.missingCurrentDeclarations`.

## Reproducibility artifacts

- `dispatcher_cases.json`: every explicit case, default, target, data offset,
  dispatch kind, and status.
- `packet_matches.json`: confirmed one-to-one function mappings and evidence.
- `packet_structures.json`: PS3 layouts and Windows/Sapphire comparisons.
- `case_reviews.json`: all non-promoted same-opcode candidates and reasons.
- `candidate_rankings.json`: now empty because every candidate was either
  promoted or explicitly reviewed.
- `ida_dispatcher_export.py`: read-only IDA ctree exporter.
- `ida_type_export.py`: read-only PS3 DWARF type exporter.
- `ida_apply_matches.py`: Windows IDB annotation applier/verifier.
- `build_dispatcher_inventory.py`, `build_structure_inventory.py`,
  `promote_exact_opcode_matches.py`, `review_remaining_candidates.py`, and
  `validate_research.py`: host-side generation and validation tools.

## Verification

The following checks completed successfully:

```text
python research/ps3-monitor/validate_research.py
validated: 179 confirmed packet matches and structures, 659 dispatcher cases, 0 ranked candidates

cmake --build build --target common world
[124/124] Linking CXX static library src\world\world.lib

git diff --check
```

No production source file was modified. The `common` and `world` build therefore
also serves as a clean baseline rather than validation of a packet-header edit.

## Remaining work

1. Separate the 74 probable shared/merged relationships, especially event-scene,
   map-marker, log-message, battle-talk, and SyncTag opcode families. Use
   overload-aware names or shared-function comments instead of false one-to-one
   links.
2. Review the 21 unresolved same-opcode cases whose handlers are inline,
   indirect, ignored, or absent in one ctree representation.
3. Triage the 18 PS3-only and 88 Windows-only zone cases for changed-opcode or
   newly introduced semantics.
4. Fully validate Windows sizes and every member of the 66 missing Sapphire
   declarations before adding production definitions.
5. Apply confirmed packet types to the Windows IDB and propagate packet-derived
   names into directly related managers only when call semantics support them.

# Packet-matching run results

## Outcome

The core zone-down and chat-down dispatchers were exhaustively inventoried and
triaged for the PS3 Monitor 2.3 build and the Windows 3.x client. The mapping
passes produced 192 one-to-one and 11 shared packet-handler function matches,
covering 246 opcode cases and corresponding PS3 DWARF structure records. No
unreviewed candidate remains in the generated ranking.

No production packet header was changed. The structure ledger identifies gaps,
but incomplete Windows size/layout evidence makes adding those declarations
premature.

## Dispatcher coverage

| Build/channel | Explicit opcodes | Confirmed | Probable | Build-only case presence | Unresolved |
| --- | ---: | ---: | ---: | ---: | ---: |
| PS3 zone-down | 285 | 239 | 7 | 18 PS3-only | 22 |
| Windows zone-down | 355 | 239 | 7 | 88 Windows-only | 22 |
| PS3 chat-down | 8 | 7 | 0 | 1 PS3-only | 1 |
| Windows chat-down | 7 | 7 | 0 | 0 | 1 |

The unresolved counts include each dispatcher's default case. Twenty-one
same-opcode zone relationships remain unresolved after review. Eleven exact
shared-handler mappings confirm 54 additional opcode cases while preserving
their many-opcode/one-function relationship. Thirteen additional unique
matches were confirmed by packet-field, loop-bound, constant, and
downstream-call behavior. The remaining 7 probable relationships lack enough evidence for an
authoritative function link.

`ps3-only` and `windows-only` mean that the numeric dispatcher case occurs in
only that build. They do not prove that the semantic feature lacks a
changed-opcode counterpart.

## Confirmed mappings

- 203 packet-handler function pairs:
  - 192 one-to-one functions
  - 11 shared functions covering 54 opcode variants
- 246 confirmed packet cases:
  - 239 zone-down cases
  - 7 chat-down cases
- Three supporting `PacketDispatcher` functions:
  - constructor
  - zone-down dispatcher
  - chat-down dispatcher
- 206 Windows functions in total have verified names and repeatable PS3 links.

Every confirmed Windows function comment starts with:

```text
PS3 Monitor: idb://ffxivgame.ppu.elf.i64:XXXXXXXX
```

The mapping ledger is `packet_matches.json`. `ida_apply_matches.py` can apply or
verify the names and comments. A verification pass checked all 206 entries with
zero failures after saving `E:/Sapphire/game/ffxiv_dx11.exe.i64`.

Five obviously unrelated pre-existing names were replaced after the dispatcher
and semantic evidence proved the packet roles:

- Windows `0x140CBE880`: `ReceiveMapMarker`
- Windows `0x140CBE8B0`: `ReceiveFatePcWork`
- Windows `0x140CBE8F0`: `ReceiveFateAccessCollectionEventObject`
- Windows `0x140CC1330`: `OnMIPMemberList`
- Windows `0x140CC9600`: `Order`

## Structure results

`packet_structures.json` contains 246 PS3 DWARF packet structures, their member
offsets and sizes, current and immutable ThreePointThree Sapphire declaration
locations, and per-field Windows validation where available.

The strongest confirmed layout delta is:

| Packet | Field | PS3 2.3 | Windows 3.x |
| --- | --- | ---: | ---: |
| `PlayerStatusUpdate` | `LvSync` | `+0x04` | `+0x06` |

The current Sapphire declaration already reflects the 3.x layout by placing
`Lv1` at `+0x04` and `LvSync` at `+0x06`, so no correction was needed.

Ninety-seven confirmed packet roles currently lack a correspondingly named
Sapphire declaration. They are recorded as research gaps rather than production
changes because many complete 3.x sizes and unaccessed fields remain unproven.
The complete list is in `packet_structures.json` under
`summary.missingCurrentDeclarations`.

## Reproducibility artifacts

- `dispatcher_cases.json`: every explicit case, default, target, data offset,
  dispatch kind, and status.
- `packet_matches.json`: confirmed one-to-one and shared function mappings and evidence.
- `packet_structures.json`: PS3 layouts and Windows/Sapphire comparisons.
- `case_reviews.json`: all non-promoted same-opcode candidates and reasons.
- `candidate_rankings.json`: now empty because every candidate was either
  promoted or explicitly reviewed.
- `ida_dispatcher_export.py`: read-only IDA ctree exporter.
- `ida_type_export.py`: read-only PS3 DWARF type exporter.
- `ida_apply_matches.py`: Windows IDB annotation applier/verifier.
- `build_dispatcher_inventory.py`, `build_structure_inventory.py`,
  `promote_exact_opcode_matches.py`, `promote_shared_handler_matches.py`,
  `promote_validated_semantic_matches.py`, `review_remaining_candidates.py`,
  and `validate_research.py`: host-side
  generation and validation tools.

## Verification

The following checks completed successfully:

```text
python research/ps3-monitor/validate_research.py
validated: 246 confirmed packet cases and structures, 659 dispatcher cases, 0 ranked candidates

cmake --build build --target common world
[124/124] Linking CXX static library src\world\world.lib

git diff --check
```

No production source file was modified. The `common` and `world` build therefore
also serves as a clean baseline rather than validation of a packet-header edit.

## Remaining work

1. Deepen the 7 probable direct relationships whose semantic names differ or
   whose PS3 path includes indirect/inlined calls; do not promote opcode-only
   agreement.
2. Review the 21 unresolved same-opcode cases whose handlers are inline,
   indirect, ignored, or absent in one ctree representation.
3. Triage the 18 PS3-only and 88 Windows-only zone cases for changed-opcode or
   newly introduced semantics.
4. Fully validate Windows sizes and every member of the 97 missing Sapphire
   declarations before adding production definitions.
5. Apply confirmed packet types to the Windows IDB and propagate packet-derived
   names into directly related managers only when call semantics support them.

## Residual blockers

The seven probable cases are `0x030C`, `0x0336`, `0x0337`, `0x0338`, `0x01E3`,
`0x01E7`, and `0x0321`. `0x030C` has materially different visible behavior
between builds. The three `0x033x` Windows targets enter unidentified or
mislabelled manager/thunk paths. The three SyncTag cases include indirect or
inlined PS3 calls whose Windows manager identities have not been independently
established. Dispatcher and opcode evidence alone is therefore insufficient.

The 21 unresolved same-opcode cases are `0x0142`, `0x0320`, `0x0322`, `0x01AA`,
`0x01AB`, `0x01AC`, `0x01AD`, `0x01AF`, `0x01B0`, `0x01B1`, `0x01B2`, `0x01B3`,
`0x01B7`, `0x01C0`, `0x029E`, `0x029F`, `0x02A0`, `0x02A1`, `0x02D6`, `0x02D7`,
and `0x02E7`. At least one dispatcher side is ignored, inline, indirect, or has
no extractable packet target. The next useful input would be type-applied
Windows pseudocode/call graphs for the unidentified managers, or packet captures
that distinguish changed-opcode semantics; without that, promotion would be
speculative.

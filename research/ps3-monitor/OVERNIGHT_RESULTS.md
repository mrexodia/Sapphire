# Packet-matching run results

## Outcome

The core zone-down and chat-down dispatchers were exhaustively inventoried and
triaged for the PS3 Monitor 2.3 build and the Windows 3.x client. The mapping
passes produced 193 one-to-one and 11 shared packet-handler function matches,
covering 247 opcode cases and corresponding PS3 DWARF structure records. No
unreviewed candidate remains in the generated ranking.

One production packet header was corrected without changing its wire size:
`FFXIVIpcQuestFinish` now exposes the Windows-read byte at `+0x04` separately
from three trailing padding bytes. Other incomplete layouts remain research-only.

## Dispatcher coverage

| Build/channel | Explicit opcodes | Confirmed | Probable | Build-only case presence | Unresolved |
| --- | ---: | ---: | ---: | ---: | ---: |
| PS3 zone-down | 285 | 240 | 3 | 18 PS3-only | 25 |
| Windows zone-down | 355 | 240 | 3 | 88 Windows-only | 25 |
| PS3 chat-down | 8 | 7 | 0 | 1 PS3-only | 1 |
| Windows chat-down | 7 | 7 | 0 | 0 | 1 |

The unresolved counts include each dispatcher's default case. Twenty-four
same-opcode zone relationships remain unresolved after review. Eleven exact
shared-handler mappings confirm 54 additional opcode cases while preserving
their many-opcode/one-function relationship. Fourteen additional unique
matches were confirmed by packet-field, loop-bound, constant, and
downstream-call behavior. The remaining 3 probable relationships lack enough evidence for an
authoritative function link.

`ps3-only` and `windows-only` mean that the numeric dispatcher case occurs in
only that build. They do not prove that the semantic feature lacks a
changed-opcode counterpart.

## Confirmed mappings

- 204 packet-handler function pairs:
  - 193 one-to-one functions
  - 11 shared functions covering 54 opcode variants
- 247 confirmed packet cases:
  - 240 zone-down cases
  - 7 chat-down cases
- Three supporting `PacketDispatcher` functions:
  - constructor
  - zone-down dispatcher
  - chat-down dispatcher
- 207 Windows functions in total have verified names and repeatable PS3 links.

A manual follow-up confirmed `QuestCompleteFlag` (`0x01E3`): both builds use
`bitIndex >> 3` with `0x80 >> (bitIndex & 7)`, set or clear the same completion
bit, and notify EventFramework with the same three semantic arguments. Windows
uses the first byte of the existing four-byte tail at `+0x04` for later 3.x-only
state/UI work.

Every confirmed Windows function comment starts with:

```text
PS3 Monitor: idb://ffxivgame.ppu.elf.i64:XXXXXXXX
```

The mapping ledger is `packet_matches.json`. `ida_apply_matches.py` can apply or
verify the names and comments. A verification pass checked all 207 entries with
zero failures after saving `E:/Sapphire/game/ffxiv_dx11.exe.i64`.

Six obviously unrelated pre-existing names were replaced after the dispatcher
and semantic evidence proved the packet roles:

- Windows `0x140CBE880`: `ReceiveMapMarker`
- Windows `0x140CBE8B0`: `ReceiveFatePcWork`
- Windows `0x140CBE8F0`: `ReceiveFateAccessCollectionEventObject`
- Windows `0x140CBE920`: `ReceiveSyncFateLimitTime`
- Windows `0x140CC1330`: `OnMIPMemberList`
- Windows `0x140CC9600`: `Order`

## Structure results

`packet_structures.json` contains 247 PS3 DWARF packet structures, their member
offsets and sizes, current and immutable ThreePointThree Sapphire declaration
locations, and per-field Windows validation where available.

The strongest confirmed layout delta is:

| Packet | Field | PS3 2.3 | Windows 3.x |
| --- | --- | ---: | ---: |
| `PlayerStatusUpdate` | `LvSync` | `+0x04` | `+0x06` |

The current Sapphire declaration already reflects the 3.x layout by placing
`Lv1` at `+0x04` and `LvSync` at `+0x06`, so no correction was needed. For
`QuestCompleteFlag`, both Sapphire and PS3 establish an eight-byte payload;
Windows proves that byte `+0x04`, previously grouped into a `uint32_t padding`
field, is consumed. Sapphire now represents it as `unknown4` plus three padding
bytes while preserving `sizeof(FFXIVIpcQuestFinish) == 8`.

Ninety-five confirmed packet roles currently lack a correspondingly named
Sapphire declaration. They are recorded as research gaps rather than production
changes because many complete 3.x sizes and unaccessed fields remain unproven.
The complete list is in `packet_structures.json` under
`summary.missingCurrentDeclarations`.

## Reproducibility artifacts

- `PACKET_CATALOG.md` and `packet_catalog.html`: generated combined views of
  Sapphire names, PS3 types/handlers, Windows handlers, fields, and review status.
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
- `build_packet_catalog.py`: deterministic Markdown/HTML catalog generator and
  stale-output checker.
- `build_dispatcher_inventory.py`, `build_structure_inventory.py`,
  `promote_exact_opcode_matches.py`, `promote_shared_handler_matches.py`,
  `promote_validated_semantic_matches.py`, `review_remaining_candidates.py`,
  and `validate_research.py`: host-side
  generation and validation tools.

## Verification

The following checks completed successfully:

```text
python research/ps3-monitor/validate_research.py
validated: 247 confirmed packet cases and structures, 659 dispatcher cases, 0 ranked candidates

cmake --build build --target common world
common and world targets completed successfully

git diff --check
```

The successful build validates the wire-size-preserving
`FFXIVIpcQuestFinish` packet-header correction.

## Remaining work

1. Deepen the 3 probable direct relationships whose semantic names differ or
   whose PS3 path includes indirect/inlined calls; do not promote opcode-only
   agreement.
2. Review the 24 unresolved same-opcode cases whose handlers are inline,
   indirect, ignored, or absent in one ctree representation.
3. Triage the 18 PS3-only and 88 Windows-only zone cases for changed-opcode or
   newly introduced semantics.
4. Fully validate Windows sizes and every member of the 95 missing Sapphire
   declarations before adding production definitions.
5. Apply confirmed packet types to the Windows IDB and propagate packet-derived
   names into directly related managers only when call semantics support them.

## Residual blockers

The three probable cases are `0x0337`, `0x01E7`, and `0x0321`. `0x0337` has
matching EventFramework/instance-director wrapper behavior but an unidentified
Windows downstream method. The two remaining SyncTag cases include indirect or
inlined PS3 calls whose Windows manager identities have not been independently
established. Dispatcher and opcode evidence alone is therefore insufficient.

The 24 unresolved same-opcode cases are `0x030C`, `0x0336`, `0x0338`, `0x0142`,
`0x0320`, `0x0322`, `0x01AA`,
`0x01AB`, `0x01AC`, `0x01AD`, `0x01AF`, `0x01B0`, `0x01B1`, `0x01B2`, `0x01B3`,
`0x01B7`, `0x01C0`, `0x029E`, `0x029F`, `0x02A0`, `0x02A1`, `0x02D6`, `0x02D7`,
and `0x02E7`. At least one dispatcher side is ignored, inline, indirect, has
no extractable packet target, or exhibits materially divergent behavior. The
next useful input would be type-applied
Windows pseudocode/call graphs for the unidentified managers, or packet captures
that distinguish changed-opcode semantics; without that, promotion would be
speculative.

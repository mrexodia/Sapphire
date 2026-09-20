# Packet-matching run results

## Outcome

The core zone-down and chat-down dispatchers were exhaustively inventoried and
triaged for the PS3 Monitor 2.3 build and the Windows 3.x client. The mapping
passes produced 198 one-to-one and 11 shared packet-handler function matches,
covering 253 opcode cases and corresponding PS3 DWARF structure records. No
probable or unreviewed candidate remains in the generated ranking.

One production packet header was corrected without changing its wire size:
`FFXIVIpcQuestFinish` now exposes the Windows-read byte at `+0x04` separately
from three trailing padding bytes. Other incomplete layouts remain research-only.

## Dispatcher coverage

| Build/channel | Explicit opcodes | Confirmed | Probable | Build-only case presence | Unresolved |
| --- | ---: | ---: | ---: | ---: | ---: |
| PS3 zone-down | 285 | 246 | 0 | 18 PS3-only | 22 |
| Windows zone-down | 355 | 246 | 0 | 88 Windows-only | 22 |
| PS3 chat-down | 8 | 7 | 0 | 1 PS3-only | 1 |
| Windows chat-down | 7 | 7 | 0 | 0 | 1 |

The unresolved counts include each dispatcher's default case. Twenty-one
same-opcode zone relationships remain unresolved across builds after review.
Eleven exact shared-handler mappings confirm 55 opcode cases while preserving
their many-opcode/one-function relationship. Nineteen additional unique matches
were confirmed by packet-field, loop-bound, constant, and downstream-call
behavior. No probable case remains.

`ps3-only` and `windows-only` mean that the numeric dispatcher case occurs in
only that build. They do not prove that the semantic feature lacks a
changed-opcode counterpart.

## Confirmed mappings

- 209 packet-handler function pairs:
  - 198 one-to-one functions
  - 11 shared functions covering 55 opcode variants
- 253 confirmed packet cases:
  - 246 zone-down cases
  - 7 chat-down cases
- Three `PacketDispatcher` functions:
  - constructor
  - zone-down dispatcher
  - chat-down dispatcher
- Two additional PS3-linked framework accessors: `Framework::GetUIModule` and
  `EventFramework::GetInstance`.
- 214 Windows functions in total have verified names and repeatable PS3 links.

A manual follow-up confirmed `QuestCompleteFlag` (`0x01E3`): both builds use
`bitIndex >> 3` with `0x80 >> (bitIndex & 7)`, set or clear the same completion
bit, and notify EventFramework with the same three semantic arguments. Windows
uses the first byte of the existing four-byte tail at `+0x04` for later 3.x-only
state/UI work. This singular eight-byte packet is distinct from plural
`QuestCompleteFlags` (`0x01E2`): Windows forwards a 310-byte completion mask and
then a second 32-byte region, exactly matching Sapphire's 342-byte
`FFXIVIpcQuestCompleteList`. PS3 2.3 only forwards a 200-byte completion mask.

Every confirmed Windows function comment starts with:

```text
PS3 Monitor: idb://ffxivgame.ppu.elf.i64:XXXXXXXX
```

The mapping ledger is `packet_matches.json`. `ida_apply_matches.py` can apply or
verify the names and comments. A verification pass checked all 214 entries with
zero failures after saving `E:/Sapphire/game/ffxiv_dx11.exe.i64`.

Six obviously unrelated pre-existing names were replaced after the dispatcher
and semantic evidence proved the packet roles:

- Windows `0x140CBE880`: `ReceiveMapMarker`
- Windows `0x140CBE8B0`: `ReceiveFatePcWork`
- Windows `0x140CBE8F0`: `ReceiveFateAccessCollectionEventObject`
- Windows `0x140CBE920`: `ReceiveSyncFateLimitTime`
- Windows `0x140CC1330`: `OnMIPMemberList`
- Windows `0x140CC9600`: `Order`

Six further reviewed mappings were promoted: `Order` (`0x0142`) joins its exact
shared handler; `LeveCompleteFlag` (`0x01E7`), `DailyQuests` (`0x0320`),
`DailyQuest` (`0x0321`), `QuestRepeatFlags` (`0x0322`), and
`Frontline01BaseInfo` (`0x0337`) have independent Windows field, loop, manager,
or wrapper evidence.

## Windows semantic mappings without PS3 links

Ten additional Windows functions covering 16 opcode cases have stable semantic
names based on Sapphire enums/structures and Windows behavior. They cover the
retainer/market/item families (`0x01AA`–`0x01B7`), `TreasureFadeOut`, four
inspect packets, and `Frontline01Result`. Three more cases—`EnableLogout`,
`LogMessage`, and `CancelLogoutCountdown`—are proven inline dispatcher paths.
These 19 cases deliberately remain separate from PS3-linked matches and receive
no `PS3 Monitor:` backlink. Four downstream retainer/market/item implementation
functions also have separately verified Windows-supporting names. The saved
Windows IDB contains and verifies all fourteen Windows-only names/comments.

## Windows IDB readability

The semantic-island pass adds 37 concrete local types, types 38 functions and
four globals, and comments 309 distinct dispatcher case addresses. The typed
zone/chat IPC views produce symbolic opcode switches and `packet->payload`
expressions; 31 `Win335_*_KnownFields` structures expose only Windows-confirmed
fields, and 25 complete-payload handlers use them. `subsystem_callgraph.json`
exports one-hop quest/leve and retainer/inventory expansion queues. Full details
and safety boundaries are in `READABILITY_RESULTS.md`.

## Structure results

`packet_structures.json` contains 253 PS3 DWARF packet structures, their member
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

Ninety-nine confirmed packet roles currently lack a correspondingly named
Sapphire declaration. They are recorded as research gaps rather than production
changes because many complete 3.x sizes and unaccessed fields remain unproven.
The complete list is in `packet_structures.json` under
`summary.missingCurrentDeclarations`.

## Reproducibility artifacts

- `PACKET_CATALOG.md` and `packet_catalog.html`: generated combined views of
  Sapphire names, PS3 types/handlers, Windows handlers, fields, and review status.
- `dispatcher_cases.json`: every explicit case, default, target, data offset,
  dispatch kind, and status.
- `packet_matches.json`: confirmed PS3-linked, Windows-semantic, inline, and shared mappings and evidence.
- `packet_structures.json`: PS3 layouts and Windows/Sapphire comparisons.
- `case_reviews.json`: all non-promoted same-opcode candidates and reasons.
- `candidate_rankings.json`: now empty because every candidate was either
  promoted or explicitly reviewed.
- `ida_dispatcher_export.py`: read-only IDA ctree exporter.
- `ida_type_export.py`: read-only PS3 DWARF type exporter.
- `ida_apply_matches.py`: Windows IDB annotation applier/verifier.
- `windows_readability_types.h` and `readability_plan.json`: generated,
  conservative Windows type/comment plan.
- `ida_apply_readability.py`: Windows type/global/case-comment applier/verifier.
- `ida_subsystem_export.py` and `subsystem_callgraph.json`: packet-rooted
  subsystem call-graph exporter and result.
- `build_packet_catalog.py`: deterministic Markdown/HTML catalog generator and
  stale-output checker.
- `build_dispatcher_inventory.py`, `build_structure_inventory.py`,
  `promote_exact_opcode_matches.py`, `promote_shared_handler_matches.py`,
  `promote_validated_semantic_matches.py`, `promote_windows_handler_mappings.py`,
  `review_remaining_candidates.py`,
  and `validate_research.py`: host-side
  generation and validation tools.

## Verification

The following checks completed successfully:

```text
python research/ps3-monitor/validate_research.py
validated: 253 confirmed packet cases and structures, 659 dispatcher cases, 0 ranked candidates, 10 Windows-only semantic functions, 4 Windows supporting functions, 3 Windows inline cases, 31 readability types, 38 typed functions, 4 typed globals, 309 case comments

cmake --build build --target common world
common and world targets completed successfully

git diff --check
```

The successful build validates the wire-size-preserving
`FFXIVIpcQuestFinish` packet-header correction.

## Remaining work

1. Recover defensible PS3↔Windows links for the 19 unresolved relationships
   whose Windows behavior is now independently identified.
2. Resolve the `0x030C` and `0x0338` semantic conflicts with runtime traces,
   packet captures, or stronger downstream type recovery.
3. Triage the 18 PS3-only and 88 Windows-only zone cases for changed-opcode or
   newly introduced semantics.
4. Fully validate Windows sizes and every member of the 99 missing Sapphire
   declarations before adding production definitions.
5. Apply confirmed packet types to the Windows IDB and propagate packet-derived
   names into directly related managers only when call semantics support them.

## Residual blockers

The 21 unresolved cross-build cases are `0x030C`, `0x0336`, `0x0338`,
`0x01AA`, `0x01AB`, `0x01AC`, `0x01AD`, `0x01AF`, `0x01B0`, `0x01B1`,
`0x01B2`, `0x01B3`, `0x01B7`, `0x01C0`, `0x029E`, `0x029F`, `0x02A0`,
`0x02A1`, `0x02D6`, `0x02D7`, and `0x02E7`. Nineteen have independently
identified Windows semantics but no defensible PS3 leaf-function counterpart:
the PS3 side is ignored, inline, indirect, or structurally divergent.
`0x030C` lacks a stable Sapphire semantic name and has incompatible build
behavior; `0x0338` is called `FinishContentMatchToClient` by Sapphire while the
Windows case instead performs instance-director initialization. The next useful
input is stronger PS3 call recovery or packet captures that distinguish
changed-opcode semantics; manufacturing cross-build links would be speculative.

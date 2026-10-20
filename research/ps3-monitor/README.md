# PS3 Monitor to 3.x client matching

This directory records cross-architecture function matches between the FFXIV
2.3 PS3 Monitor development build and the Windows 3.x client used by Sapphire.
Addresses are tied to the exact binaries and hashes in `packet_matches.json`.

## Event-object and data-format research

See [`EOBJ_EXD_RESULTS.md`](EOBJ_EXD_RESULTS.md) for the Sastasha grate's
asset-confirmed timeline masks, packet argument distinctions, EXD coverage,
archive addressing fixes, and remaining format/decryption boundaries. The new
headless [`Ps3DataInspector`](../../src/tools/Ps3DataInspector/README.md) scans
all root-listed sheets, inventories every PS3 index, extracts by path or hash,
and reports SGB general-purpose timeline mappings. `ida_asset_export.py`
exports all imported IDB types/symbols and candidate debug/resource paths.
[`WINDOWS_EOBJ_MAPPING.md`](WINDOWS_EOBJ_MAPPING.md) records the verified Windows
setter (`0x1409EC750`), its `+0x1A2` state field, supporting functions and saved
IDB annotations.

For a guided explanation, open
[`eobj-flow-explainer.html`](eobj-flow-explainer.html) directly in a browser.
It is self-contained and works offline, with file/ID flow diagrams, the
Sastasha slot mapping, packet-path distinctions, and an interactive mask
simulator. The mechanism is general; slot meanings belong to each SGB asset,
not a global dungeon animation enum.

Validate local links and browser behavior with:

```bash
python research/ps3-monitor/validate_eobj_explainer.py --static-only
python research/ps3-monitor/validate_eobj_explainer.py
```

The full check requires Python Playwright and Edge (auto-detected on Windows)
or Playwright Chromium; `--browser PATH` selects another Chromium executable.
It checks example transitions, all 24,576 modeled low-four-bit transitions,
input validation, offline operation and mobile overflow. Screenshots stay in
`build/`. This explainer does not change production timeline behavior.

## Toolkit integration, path names and Excel semantics

ToolkitPs3 now shares the inspector's decoder and adds **Tools > Excel** plus
**Tools > Data Graph** for exact symbols, SQLite FTS/ID search, all 1,933
recovered/authentic Lua source files plus their 1,932 backing bytecode resources,
confidence-qualified EXD links, source hits, hierarchical assets, placements
and SGB timelines. Recovered Lua is shown as the primary readable source while
preserving bytecode provenance. Excel and graph rows now pivot in both
directions; the Excel view overlays semantic names without replacing its live
PS3 SqPack values.
See [its feature matrix](../../src/tools/ToolkitPs3/README.md) and
[`TOOLKIT_DATA_STATUS.md`](TOOLKIT_DATA_STATUS.md) for tests and boundaries.
The full library-path scan independently exercises the API used by Toolkit:
2,131 sheets, 10,295 pages/languages, 1,021,511 row/subrow instances, zero errors.

The measured recovery pass finds candidate names matching 16,191 of 745,952
indexed entries, exact name/size row-struct matches for 303 sheets and 10,182
single-name debug column candidates. These are lower bounds / metadata
candidates, not complete path recovery or a verified foreign-key graph.
Regenerate [`monitor_recovery.json`](monitor_recovery.json) with
`python research/ps3-monitor/build_monitor_recovery_report.py`; full ledgers
remain under `build/`.

[`DATA_GRAPH_RESULTS.md`](DATA_GRAPH_RESULTS.md) documents the new SQLite/FTS
semantic graph and the reproduced “satasha dungeon what is involved?” and
`2000182` magic-ID investigations. The graph joins selected-language EXD rows,
evidence-qualified fields and links, Sapphire source references, all 273
referenced LVB files, 1,711 LVB-to-LGB links, 370,647 unique LGB placements,
2,817 unique LGB-to-SGB links, and bounded timeline details for 1,752 SGB files.
Build and query it with
`build_excel_semantic_schema.py` and `ps3_data_graph.py`; uncertain numeric
coincidences remain searchable but are not promoted to graph edges.

## Lua and timeline runtime starting points

[`LUA_TIMELINE_START.md`](LUA_TIMELINE_START.md) corrects the earlier SDAT
encryption claim: both local SDATs are debug/plain, and all 1,934 script / 283
shader records validate after keyless deframing. The standard-library-only
`inspect_monitor_scripts.py` parses all 1,932 Lua 5.1 chunks, inventories scene
and static API operands, and optionally extracts hash-named scripts without
executing them. It documents Lua loader/binding/resume and timeline scheduler
symbol anchors, retained debug information and a practical vertical-slice plan.
General SDAT support and integration into the C++ backend remain separate work.

## Original Lua filename recovery

[`LUA_FILENAME_RECOVERY.md`](LUA_FILENAME_RECOVERY.md) records direct PathList
matching against both CRCs in the raw PS3 script index: all 1,932 compiled
chunks and the one source-text record have unique dictionary paths. Named,
byte-identical payloads are under `build/ps3-lua-named/game_script/`, with a
full hash/path manifest. Only the non-Lua placeholder remains unnamed.
All compiled basenames also agree with embedded `.cli.lua` / `.cmn.lua` debug
sources. `recover_lua_paths.py` reproduces the mapping and copies;
`test_recover_lua_paths.py` verifies the matching rules. The supplied decompiler
was tested on five named samples; outputs stay under `build/`.

## Full Lua decompilation

[`LUA_DECOMPILATION.md`](LUA_DECOMPILATION.md) compares the included 2015 unluac,
a newer official jar and cLuaDecompiler across all 1,932 compiled resources.
Browse `build/ps3-lua-decompiled/recommended/game_script/`: all 1,932 syntax-valid
reconstructed resources plus the authentic Gld10000 source. The
[manual ChocoboTaxiStand repair](CHOCOBO_TAXI_RECONSTRUCTION.md) closes the final
exception and recompiles to the same seven ordered instruction/constant trees. The original jars/payloads
are untouched; compilation checks do not execute game scripts.

### Binding-annotated Lua

[`LUA_BINDING_ANNOTATIONS.md`](LUA_BINDING_ANNOTATIONS.md) documents the separate
`research/ps3-monitor/game_script/` corpus (generated copy under
`build/ps3-lua-annotated/game_script/`): handler Name/Value pairs and referenced
shared-table candidates appear near reads. Native constants live in 13
`defines/*.lua` reference modules; script comments link to them. Redundant
Lua-literal comments and unused shared/native header inventories are omitted. All 1,933 files preserve their input's code tokens and pass Lua 5.1
syntax checks. Stored numbers are concrete dataset facts, not a claim of
immutable runtime fields or proven scope/override precedence.

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

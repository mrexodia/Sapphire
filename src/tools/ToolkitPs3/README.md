# ToolkitPs3

ToolkitPs3 is an ImGui/OpenGL **territory, placement and navigation research
viewer**, not a complete game editor or universal asset workbench.

## Current capabilities

| Area | Implemented | Boundaries |
| --- | --- | --- |
| Settings | PS3 SqPack location, MySQL settings, navigation location, reload, persisted settings and OS-window placement/state | The initial PS3 path comes from `[General] DataPathPs3`; `editor_config_ps3.txt` persists ToolkitPs3 selections, while `window_state_ps3.txt` preserves normal position/size and maximized state. Startup still attempts a database connection; Excel inspection itself does not need MySQL. |
| Territories | Search/filter, named metadata, linked place-name lookups, geographic/visual/gameplay fields | Compiled typed views cover selected sheets, not the entire semantic schema. |
| Maps | Map texture loading, zoom/pan, overlays and coordinate inspection | Not a complete PS3 texture/material rendering pipeline. |
| BNPCs | Database-backed territory list, filtering, name resolution and detailed spawn/combat/linking fields | Database-dependent. “Show on Map” still has a TODO; no general database-edit/save implementation is claimed. |
| LGB placements | Groups/categories, entry lists, IDs/transforms, detailed BNPC/shared-group/EObj/path/exit/pop-range views | Selected entry types, not every serialized format. “Export Group Info” remains a placeholder. |
| Navigation / geometry | Navmesh visualization, camera controls, markers/raycasting and optional external OBJ geometry | External OBJ geometry is not native textured MDL model support. |
| Excel browser | Tools > Excel; live PS3 SqPack rows, languages, IDs/subrows, exact EXH type/offset/value plus graph-derived semantic names, confidence/evidence tooltips, and clickable evidence-qualified references. Script-local `Symbol` values are searchable; every row pivots to graph relations. | Semantic names and references require the configured graph; unresolved fields deliberately remain `ColumnN`/`physical_only` rather than receiving guessed meanings. |
| Semantic data graph (**new**) | Tools > Data Graph; exact symbol, FTS and numeric-ID search across PS3 EXD, 1,933 recovered/authentic Lua source files, all 1,932 backing bytecode resources, and Sapphire source; confidence-qualified links, source previews, live-Excel pivots, breadcrumbs, and Territory → LVB → LGB → SGB navigation | Recovered Lua is presented first and retains its backing bytecode identity. Unknown or ambiguous relationships remain candidates; equal numeric IDs remain separate search results. One observed SGB profile remains explicitly unsupported. |
| Archives | Shared PS3 index/DAT backend; path-based retrieval, 64-bit offsets including >4-GiB BG DAT entries, and transparent support for the two known plaintext retail SDAT archives | No GUI-wide hash inventory/extract-by-hash panel; use Ps3DataInspector for those commands. Other SDAT profiles are rejected; no decryption or licensing support is provided. |

Source inventory: `ServerState.cpp`, `ZoneEditor.cpp`, `LgbViewer.cpp`,
`ExcelBrowser.cpp`. Listed UI features were assessed from code; not all
rendering/database workflows have been exercised against a running game.

## Inspector fixes now used by ToolkitPs3

Both tools now use `deps/datReaderPs3/ExcelBinary.h`. The inspector's `Excel.h`
is just a JSON presentation adapter; the library's `Exh`/`Exd` use the same
byte-oriented decoder. There are no longer two independent EXD parsers to fix.

- EXH v3 magic/version/bounds checks and the full key count.
- Column order is preserved even when physical offsets are repeated or unsorted.
- Byte-sized language descriptors, with language-neutral fallback only when
  that language is explicitly declared; pages load lazily per language.
- Big-endian signed/unsigned integers, including signed 64-bit cells, float32,
  one-byte packed booleans, strings and raw F16 bits.
- Full 16-bit subrow counts and up to three stored subkeys.
- Strings resolved from the pool after **all** fixed subrecords.
- Correct typed-row subrow selection, bounded reads and string replacement.
- Repeated `get_rows()`/`get_row()` calls no longer append duplicate fields.
- Main-ID enumeration does not eagerly decode every row.
- Toolkit's wrapper no longer copies the entire sheet on every row request,
  ignores its subrow parameter, or retains stale typed-sheet copies on reload.
- Initialization errors are reported rather than escaping as ordinary decoder
  exceptions; one GameData instance is shared with the placement reader.

### Typed C++ bitfields need special treatment

The legacy `Excel::Ps3` structs declare packed boolean fields in PS3 allocation
order. On the current little-endian host compiler, that declaration order is
reversed relative to the on-disk bit positions. The typed adapter reverses the
original byte at each packed-column offset, once in effect even when the offset
is repeated. It does **not** overwrite a packed byte with a single decoded bool.

The generic column API and Excel browser retain the original EXH bit semantics.
Both Excel and graph field views can switch between declared EXH column order
and fixed-byte offset order. These are not always the same: `GimmickAccessor`
declares `Type, Param0, Param1, Param2`, while its row bytes are laid out
`Param0@0x00, Param1@0x04, Param2@0x08, Type@0x0C`.

ToolkitPs3 defaults each newly opened live EXD sheet and graph-to-Excel pivot
to English when that sheet declares it, then neutral or the first declared
language when English is unavailable. Japanese and Simplified Chinese remain
selectable, with matching Windows fallback fonts merged into the ImGui atlas.
The graph build is likewise selected-language snapshot data (English by default).
Typed row views assume the declaration convention in `Exd/Structs.h`; they are
not an arbitrary host-ABI struct deserializer. Size equality alone does not
prove every handwritten layout. Synthetic bitfield tests and monitor EObj /
TerritoryType tests validate the important affected views.

`get_row(id, ordinal)` and `getRow<T>(id, ordinal)` take a **physical ordinal**.
Use `get_subrow_keys()` to read the actual key IDs. `get_rows()` remains a
compatibility view of the first subrow for each main ID, not every subrow.
`Exh::get_members()` remains a lossy legacy offset lookup; use
`get_exh_members()` / `get_binary_header().columns` for column count and order.

## Build and verification

Generate the semantic graph before opening **Tools > Data Graph**:

```sh
python research/ps3-monitor/build_excel_semantic_schema.py
python research/ps3-monitor/ps3_data_graph.py build build/ps3-data-graph.sqlite \
  --sqpack E:/FFXIV-Monitor-PS3/game/sqpack --source-root src \
  --lua-source-root research/ps3-monitor/game_script
```

Configure its path under **File > Settings > Data Graph**. The default source-tree build path is `build/ps3-data-graph.sqlite`. Rebuild when the viewer reports an older schema version.

For example, searching `TEXT_EXITRANGE_EXITCONTENT_Q_PARTY` resolves the Lua table-member operand in `@System/ExitRange.cli.lua` to `system/ExitRange:6`, whose `Symbol` and `Text` fields hold the identifier and localized prompt. The graph row opens directly in the live Excel browser, and the symbol links back to its Lua references.

The Relations tab separates resolved incoming edges from speculative discovery. It also shows sheet-wide runtime lookup paths, unresolved exact numeric coincidences, low-16-bit encoding hypotheses, and nearby keys from fields already known to target that sheet. Nearby and transformed candidates display their formula and remain explicitly non-authoritative. For example, `LogMessage:2041` has a content-workflow candidate from Sastasha's four unnatural-ripple accessors and disassembly-confirmed packet/Lua lookup paths, while unrelated equal numeric values remain `exact_value_candidate` rather than foreign keys.

Numeric graph searches accept decimal or hexadecimal with or without `id:`; for example, `0xF001A` and `id:0xF001A` both find the EObj whose `EventHandler` contains that value. Game-data integers of 10 or greater are displayed as decimal plus uppercase hexadecimal, such as `983066 (0xF001A)`, in both the Data Graph and live Excel browser.

```sh
cmake --build build -j 6
ctest --test-dir build -R ps3_data_inspector_tests --output-on-failure

# Optional checks requiring the local monitor corpus; no OpenGL or MySQL needed.
bin/tools/ps3_toolkit_data_smoke.exe E:/FFXIV-Monitor-PS3/game/sqpack
bin/tools/ps3_data_inspector.exe exd-library-scan E:/FFXIV-Monitor-PS3/game/sqpack build/ps3-exd-library-scan.json
```

The actual library path decoded **2,131 sheets, 10,295 pages/languages and
1,021,511 row/subrow instances with zero errors**, matching the inspector's
original scan. The Toolkit wrapper smoke test passed names, numerics, packed
flags, a differing Resident subrow, repeated ID listing and reload.

At integration time, a pre-existing ToolkitPs3 process locked
`bin/tools/ToolkitPs3.exe`. All affected sources compiled and the same generated
link command succeeded with alternate outputs
`build/ToolkitPs3-verified.exe` / `.pdb`. The running process was not terminated.
Close ToolkitPs3 and rerun the normal build to replace the installed executable.
The new browser has compiled/linked successfully; interactive GUI testing is
still separate from the headless decoder and wrapper checks.

## Paths, metadata and IDs

See [monitor recovery status](../../../research/ps3-monitor/TOOLKIT_DATA_STATUS.md)
for measured path-name coverage, debug-field candidates and the distinction
between storage types, semantic ID spaces and proven sheet relationships.

# PS3 Data Inspector

Headless inspection of the FFXIV PS3 Monitor corpus using `xivdatps3`, without
starting the game, a server, or an OpenGL GUI. Use trusted local game files;
this is research tooling, not a hardened parser for hostile archives.

## Build and test

```sh
cmake --build build --target ps3_data_inspector ps3_data_inspector_tests
ctest --test-dir build -R ps3_data_inspector_tests --output-on-failure
```

The test target is available when `BUILD_TESTING` is enabled. The configured
Windows build places executables under `bin/tools/`.

## Semantic data graph

The graph prototype combines every selected-language EXD row, physical EXH
columns, evidence-qualified semantic labels/links, asset paths and searchable
references from Sapphire source code. Generate the schema and SQLite graph:

```sh
# Run ida_excel_getter_export.py in the open PS3 Monitor IDB first when the
# build/ps3-excel-getters.json evidence export needs to be refreshed.
python research/ps3-monitor/build_excel_semantic_schema.py
python research/ps3-monitor/ps3_data_graph.py build build/ps3-data-graph.sqlite \
  --sqpack E:/FFXIV-Monitor-PS3/game/sqpack --source-root src

python research/ps3-monitor/ps3_data_graph.py search build/ps3-data-graph.sqlite id:2000182
python research/ps3-monitor/ps3_data_graph.py row build/ps3-data-graph.sqlite InstanceContent 4
python research/ps3-monitor/ps3_data_graph.py asset build/ps3-data-graph.sqlite \
  bg/ffxiv/sea_s1/dun/s1d1/level/planmap.lgb
python research/ps3-monitor/ps3_data_graph.py explain build/ps3-data-graph.sqlite \
  "satasha dungeon what is involved?" --depth 2
```

Text uses SQLite FTS5. Misspelled terms are corrected against the corpus
vocabulary. Numeric search reports row keys, same-valued cells, and source
literals; only declared field resolvers become edges. Confidence and evidence
remain attached so coincidental integers do not become authoritative foreign
keys. `exd-stream` is the internal line-oriented decoder used while building
the graph; normal users should invoke `ps3_data_graph.py`. The build also
parses every referenced LVB and LGB into layer sets, groups, placements and
LGB-to-SGB asset edges. It also applies the bounded timeline profile to every
unique referenced SGB, indexing accepted timelines and slots in the graph.
Use `sgb-timelines` for focused inspection after pivoting to an SGB path.

## Commands

All outputs are explicit filenames; parent directories must already exist.
Successful commands return 0, failures 1, usage errors 2. Scans retain their
error records in JSON and return nonzero if anything could not be decoded.

```sh
# All hashed entries, including unnamed categories and SDAT-wrapped payloads.
bin/tools/ps3_data_inspector.exe inventory E:/FFXIV-Monitor-PS3/game/sqpack build/ps3-inventory.json

# Also inventory loose configuration, executable, movie and debug/IDB files.
bin/tools/ps3_data_inspector.exe inventory E:/FFXIV-Monitor-PS3/game build/ps3-game-inventory.json

# Every root.exl sheet, every declared page and language: schemas + decode counts/errors.
bin/tools/ps3_data_inspector.exe exd-scan E:/FFXIV-Monitor-PS3/game/sqpack build/ps3-exd-scan.json

# Every page through the actual Exh/Exd library path used by ToolkitPs3.
bin/tools/ps3_data_inspector.exe exd-library-scan E:/FFXIV-Monitor-PS3/game/sqpack build/ps3-exd-library-scan.json

# Toolkit's typed wrapper, without an OpenGL window or database connection.
bin/tools/ps3_toolkit_data_smoke.exe E:/FFXIV-Monitor-PS3/game/sqpack

# Schema only; columns stay in original order (including repeated offsets).
bin/tools/ps3_data_inspector.exe schema E:/FFXIV-Monitor-PS3/game/sqpack EObj build/eobj-schema.json

# Entire sheet as indexed fields. Language IDs: 0 none, 1 Japanese, 2 English,
# 3 German, 4 French, 5 Simplified Chinese, 6 Traditional Chinese, 7 Korean.
bin/tools/ps3_data_inspector.exe dump E:/FFXIV-Monitor-PS3/game/sqpack EObj build/ps3-eobj.json 2

# Corpus-wide text or numeric-ID/value search. The optional semantic schema gives
# fields evidence-qualified names instead of only column numbers.
python research/ps3-monitor/build_excel_semantic_schema.py
bin/tools/ps3_data_inspector.exe exd-search E:/FFXIV-Monitor-PS3/game/sqpack Sastasha build/search-sastasha.json 2 100 build/ps3-exd-semantic-schema.json
bin/tools/ps3_data_inspector.exe exd-search E:/FFXIV-Monitor-PS3/game/sqpack id:2000182 build/search-eobj.json 2 100 build/ps3-exd-semantic-schema.json

# Standard payload extraction by game path.
bin/tools/ps3_data_inspector.exe extract E:/FFXIV-Monitor-PS3/game/sqpack bg/ffxiv/sea_s1/shared/for_bg/sgbg_s1d1_m1_bos1.sgb build/grate.sgb

# Slot -> mask -> MemberID -> asset timeline name, without decoding animation clips.
bin/tools/ps3_data_inspector.exe sgb-timelines E:/FFXIV-Monitor-PS3/game/sqpack bg/ffxiv/sea_s1/shared/for_bg/sgbg_s1d1_m1_bos1.sgb build/grate-timelines.json

# Raw hash lookup works for unnamed categories too. Hash args are hexadecimal;
# use inventory directory_hash/filename_hash values, converted from decimal.
bin/tools/ps3_data_inspector.exe extract-hash E:/FFXIV-Monitor-PS3/game/sqpack/120000.ps3.d.index DIRECTORY_HEX FILENAME_HEX build/asset.bin
```

Extraction concatenates the data sections produced by the existing PS3 DAT
reader. For standard assets this is the decompressed payload. Model/texture
reconstruction correctness is not claimed by this tool. Matching the game, the
shared reader prefers `.datN.sdat` over `.datN` when both exist and deframes the
verified plaintext `0x8100003C` / `0x4000` profile used by both local retail
archives. Other SDAT profiles are rejected; decryption and
metadata authentication are intentionally out of scope. The inventory's
legacy `encrypted_sdat_present` key only reports filename presence. Index names
cannot in general be recovered from CRC hashes.

## EXD representation and scope

The new decoder reads bytes rather than copying native ABI structs. It handles
EXH v3, BE fixed values, signed/unsigned integers, float32, packed bools, strings,
and up to four total row keys. Subkeys are actual IDs, not ordinal indices.
Strings are output as `{text, bytes_hex}`: bytes preserve SeString payloads and
non-UTF-8 data even if readable JSON text needs replacement characters.
Nonfinite floats are retained as raw bit patterns. F16 is currently raw bits.
Binary type 12, unknown types, and older EXH versions fail explicitly.

Decoding now lives in `deps/datReaderPs3/ExcelBinary.h`, shared by the
`Exh`/`Exd` library classes, ToolkitPs3 and this tool. `Excel.h` only adapts the
shared values to JSON. ToolkitPs3 has a generic **Tools > Excel** browser;
see its [feature matrix](../ToolkitPs3/README.md).

Scanning validates values against the implemented layout; it does not prove
semantic column names, foreign keys or units. `exd-search` is an immediate
full-corpus scan, not yet a persistent FTS index. An `id:NUMBER` query reports
matching main keys, subkeys and integral cells as candidates; equal integers do
not by themselves establish a relationship.

EXH schemas and PS3 DWARF types can be joined to recover candidate names, with
ABI/version checks and separate consumer tracing to prove relationships.
`ida_excel_getter_export.py` records the typed DataManager lookup surface and
`build_excel_semantic_schema.py` combines that evidence with physical columns,
monitor labels and explicitly weak newer-EXDSchema hints. The reproducible
lower-bound path and metadata report is
[here](../../../research/ps3-monitor/TOOLKIT_DATA_STATUS.md).

Research results, address-level evidence, the read-only IDB metadata exporter,
and the compact reproducible coverage report are in
[`research/ps3-monitor/EOBJ_EXD_RESULTS.md`](../../../research/ps3-monitor/EOBJ_EXD_RESULTS.md).

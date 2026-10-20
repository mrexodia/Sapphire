# PS3 semantic data graph prototype

## Generated corpus

The graph was built from the retail PS3 SqPack, the selected English/neutral
EXD views, PS3 Monitor DWARF metadata/getters, explicit evidence-qualified
field overrides, all referenced LVB/LGB files, and Sapphire `src/` text.

Generated database: `build/ps3-data-graph.sqlite` (about 387 MiB).

| Record | Count |
| --- | ---: |
| Sheets / physical columns | 2,131 / 16,930 |
| EXD rows/subrows | 262,763 |
| Searchable nonzero integer cells | 1,291,721 |
| Searchable text cells | 357,170 |
| Evidence-qualified row/asset edges | 53,756 |
| LVB files decoded without error | 273 |
| Unique LVB-to-LGB edges | 1,711 |
| Unique LGB placements | 370,647 |
| Unique LGB-to-SGB edges | 2,817 |
| Bounded timeline-profile SGB files / other profiles | 1,752 / 1 |
| Indexed SGB timelines / general-purpose slots | 1,720 / 28,032 |
| Indexed recovered/authentic Lua source files / mapped bytecode assets | 1,933 / 1,932 |
| Indexed Lua member references in recovered source | 147,481 |
| Indexed Lua bytecode files / unique per-script symbols | 1,932 / 149,279 |
| Evidence-qualified Lua-to-EXD symbol links | 46,330 |
| Indexed Sapphire source files / numeric literals | 1,468 / 241,730 |

All 2,131 EXD sheets, 262,763 selected-language rows, 1,932 Lua bytecode resources and 273 referenced LVB
files streamed with zero decode errors. Every LGB named by those LVB files was
also parsed while producing the placement graph.

## Simulated question: “satasha dungeon what is involved?”

The query deliberately misspells Sastasha. The vocabulary resolver corrects
`satasha` to `sastasha`; FTS returns both game rows and Sapphire source.

The useful confirmed path is:

```text
InstanceContent 4 "Sastasha"
  TerritoryType = 157
    Name/LVB token = s1d1 / ffxiv/sea_s1/dun/s1d1/level/s1d1
    Area = PlaceName 35 "Sastasha"
    Region = PlaceName 22 "La Noscea"
    SubRegion = PlaceName 502 "La Noscea"
    Map = Map 31 "s1d1/00"
    Aetheryte = Aetheryte 13
    IntendedUse = TerritoryIntendedUse 3
    LVB = bg/ffxiv/sea_s1/dun/s1d1/level/s1d1.lvb
```

The LVB contributes layer set `79213` (`ls001`), territory `157`, the server
navmesh path, and these six LGB children:

```text
bg.lgb
vfx.lgb
planmap.lgb
planevent.lgb
planlive.lgb
sound.lgb
```

`bg.lgb` has 6,962 placements (6,561 background parts, 69 shared groups and
332 other entries) and 15 unique SGB targets. `planmap.lgb` has 307 placements
and 10 unique SGB targets. One Sastasha boss shared group,
`sgbg_s1d1_m1_bos1.sgb`, decodes to four timelines (`open`, `close`, `vfx_on`,
`vfx_off`) and sixteen general-purpose slots.

FTS also finds `src/scripts/instances/dungeons/Sastasha.cpp`, where
`InstanceContentScript(4)` is labeled as an InstanceContent key and `addEObj`
arguments are labeled as EObj keys. This lets a user pivot from content row 4
to the implemented encounter objects, doors, coral formations, keys, boss
walls and shared-group IDs without treating every integer on those lines as
the same ID domain.

Reproduce:

```sh
python research/ps3-monitor/ps3_data_graph.py explain build/ps3-data-graph.sqlite \
  "satasha dungeon what is involved?" --depth 2
python research/ps3-monitor/ps3_data_graph.py row build/ps3-data-graph.sqlite TerritoryType 157
python research/ps3-monitor/ps3_data_graph.py asset build/ps3-data-graph.sqlite \
  bg/ffxiv/sea_s1/dun/s1d1/level/planmap.lgb
bin/tools/ps3_data_inspector.exe sgb-timelines E:/FFXIV-Monitor-PS3/game/sqpack \
  bg/ffxiv/sea_s1/shared/for_bg/sgbg_s1d1_m1_bos1.sgb build/sastasha-bos1.json
```

## Simulated magic-ID question: `2000182`

Numeric search reports two physical row-key matches: `EObj:2000182` and
`EventItem:2000182`. It does **not** infer an edge from that coincidence.

Source indexing identifies uses in `addEObj` calls semantically as `EObj main
key (Entrance)` across dungeon scripts, including Sastasha. The EObj row itself
has `PopType = 1` and `EyeCollision = true`. This demonstrates the intended
fog-of-war behavior: physical matches are visible, typed source usage resolves
the relevant domain, and unsupported relationships remain candidates rather
than silently becoming foreign keys.

## Speculative lookup example: LogMessage 2041

`LogMessage:2041` (“The evil presence has gone.”) has no exact serialized
foreign key in the decoded EXD/Lua/source corpus. It is nevertheless reachable
through two separately displayed evidence classes:

- disassembly-confirmed generic consumers accept a server packet `messageId` or
  Lua numeric argument and pass it unchanged to `RaptureLogModule::PushLog`;
- a `content_workflow_candidate` connects Sastasha GimmickAccessor rows 67–70,
  the four unnatural ripples, to the contiguous 2039–2042 message sequence.

The candidate records `Param0 + 2` for discovery but explicitly does not claim
that the client computes that offset. The browser also lists unresolved exact,
low-16-bit, and nearby-key candidates separately from graph edges.

## Lua symbol example

`TEXT_EXITRANGE_EXITCONTENT_Q_PARTY` appears at
`game_script/system/ExitRange.lua:9`, backed by the table-member operand in
`@System/ExitRange.cli.lua`. Exact symbol search resolves it to
`system/ExitRange:6`: `Symbol` contains the identifier and `Text` contains
"Leaving the area will result in the abandonment of your current duty and your
removal from the party. Do you wish to proceed?" The link is marked
`structural_candidate`: the Lua debug source path names the same script-local
sheet and the token is an exact match, but this does not claim a universal
foreign-key rule.

## Remaining boundary

The graph build now applies the bounded timeline parser to every unique SGB
referenced by an LGB. It accepted 1,752 SGB files, indexing 1,720 named
timelines and 28,032 general-purpose slots; one target has a different profile
and remains an explicit unsupported boundary. Additional SGB profiles should be
added as bounded parsers rather than forcing all files through the known layout.
ToolkitPs3 exposes the indexed timelines and slots under **Tools > Data Graph**.

# ToolkitPs3 integration and monitor recovery status

## What was applied

The inspector's byte decoding has moved to the shared
`deps/datReaderPs3/ExcelBinary.h`. `Exh`/`Exd`, ToolkitPs3's typed wrapper and
Ps3DataInspector now share it. ToolkitPs3 additionally has a generic
**Tools > Excel** browser. The complete feature matrix and adapter details are
in [`src/tools/ToolkitPs3/README.md`](../../src/tools/ToolkitPs3/README.md).

The previous 64-bit DAT/index fixes were already in the shared backend, so
ToolkitPs3 inherits them too. Extraction/inventory and SGB timeline-report
commands remain inspector CLI capabilities; this does not claim those all
have new GUI panels.

Verification:

- Synthetic decoder/index/library/typed-row tests passed.
- Actual Toolkit `Data::ExdData` smoke test passed typed territory/EObj names,
  numerics and flags, nondefault Resident subrow selection, ID lists and reload.
- Full library-path scan: **2,131 sheets, 10,295 pages/languages,
  1,021,511 row/subrow instances, zero errors**.
- All affected sources compiled. Normal executable replacement was blocked by
  a pre-existing running ToolkitPs3 instance. An alternate executable,
  `build/ToolkitPs3-verified.exe`, linked successfully with the generated command.
  No user process was terminated; close ToolkitPs3 and rebuild to install it.
- New GUI rendering/interaction has not been smoke-tested in the live session.

## Do we have every hashed asset path? No.

We have a complete inventory of the supplied **14 indices / 745,952 entries**.
That gives archive identity, directory hash, filename hash, DAT number and
64-bit offset. It does not give the original text of every path.

The new reproducible recovery pass finds candidate path strings whose **two
CRC hashes match 16,191 archive entries**, about **2.17%** of the inventory.
That is a conservative lower bound from deliberately limited sources—not an
estimate of how much can ultimately be recovered:

- All root-listed EXH names and validated EXD page/language paths.
- Fixed asset-like literals from the monitor's exported candidate strings.
- Already-decoded EObj, TerritoryType and ExportedSG sheet strings.
- Territory LVB path construction and the verified Sastasha SGB path.

EXD names are much more complete than general assets: **12,427 / 12,443**
entries in the EXD index are named by these sources. The remaining 16 have not
been named by this pass. They are not automatically missing sheets.

Important limitations:

- 8,707 exported “candidate path strings” include source paths, debug paths,
  printf templates, directories and false positives; they are not 8,707
  confirmed game assets.
- A hash-pair match supports a candidate name; CRC collisions and case folding
  mean it is not a unique recovery of original spelling.
- Many names are generated from IDs using formatting templates, rather than
  being stored as full literal paths in the executable.
- Other paths occur in level groups, shared groups, materials, models, VFX,
  sound resources and sheet strings. We have not recursively traversed all
  those dependencies or exhaustively expanded generated-name templates.
- SDAT is not synonymous with encryption. Both local shader/game-script
  containers were later validated as debug/plain and deframed without keys.
  The separate [script helper](LUA_TIMELINE_START.md) validates every record;
  C++ backend integration and general SDAT integrity/decryption remain absent.
  A matched name still does not imply complete semantic payload decoding.

The natural next path-recovery step is a provenance-bearing dictionary:
`candidate path → source/recipe → category + hashes → matched archive entry`.
Expand only justified templates and recursively traverse supported asset
references; keep unnamed entries addressable by hash. Do not pretend CRCs are
an invertible pathname database.

## What the monitor build gives us for Excel relationships

It gives significantly more than a retail executable, but not a ready-made
SQL schema with declared foreign keys.

### 1. Named row structs, fields, arrays and bit positions

The exported IDB metadata contains **26,223 imported type records**. Matching
exact `SheetNameStruct` names and fixed row size finds **303 / 2,131 sheets**.
Flattening their nested structs/one-dimensional arrays and joining by byte
width, offset and packed bit produces **10,182 single-name column candidates
out of 16,930 total EXH columns**.

These are **metadata-derived candidates**, not 10,182 verified relationships.
Some imported types are alternate views, gap-only records or runtime structures.
The pass deliberately does not claim the 303 direct matches are the only
recoverable sheet types.

For EObj, the candidates line up particularly well:

| EXH column | Fixed offset | Debug field candidate |
| ---: | ---: | --- |
| 0 | 0 | Text.SGL |
| 2 | 4 | Text.PLR |
| 8 | 26 | PopType |
| 9 | 20 | EventHandler |
| 11 | 24 | SharedGroup |
| 12 | 28, bit 0 | Target |
| 13 | 28, bit 1 | DirectorControl |
| 14 | 28, bit 2 | EyeCollision |
| 15 | 16 | EventHighAddition |

**Column order is not memory-offset order.** Sorting by offset loses the
logical column order; mapping by offset alone collapses packed booleans.
Arrays and nested text structures must be flattened, and strings must be
recognized as four-byte stored offsets rather than live runtime pointers.

### 2. Named getters and their callers

The monitor has named DataManager functions such as `GetEObjData`,
`GetItemData` and `GetTerritoryTypeData`, along with named setup routines.
Their callers let us distinguish “this integer is consumed as a row key for
sheet X” from “this integer merely happens to equal a row ID in sheet X.”

The established EObj setup path demonstrates a real relationship:

```text
EObj.BaseId → GetEObjData(BaseId)
EObj.SharedGroup → ExportedSG lookup → shared-group asset path
```

The bound Sastasha objects take the alternative existing-placement path via
BindLayoutId. Their `SharedGroup = 0` therefore must not be blindly treated as
an invalid foreign key. See [`EOBJ_EXD_RESULTS.md`](EOBJ_EXD_RESULTS.md).

The territory path also demonstrates that a reference may be a **string
recipe** rather than another sheet row: the LVB string leads to level assets,
which lead to LGB placements and SGB references.

### 3. Excel key/debug machinery

The imported `Common::Component::Excel::ExcelEntryKey` record is 12 bytes:
main key at +0 (uint32), hash at +4 (uint16), and three uint16 subkey-info values
at +6. Excel getters and row-reading disassembly prove the physical key-count
and shared-subrow-string rules used by the decoder.

The symbol/type export also includes ExdTrace-related debug templates and
named sheet/cache machinery. These are useful search leads and potential
runtime instrumentation surfaces; their presence does not prove a complete
foreign-key log or a usable monitor console command is already available.

### Recommended relationship-recovery standard

For each proposed edge, record:

1. Source sheet, logical column, physical offset and bit/array index.
2. Debug field name/type and exact monitor build identity.
3. A consuming function and callsite that loads this field and invokes the
   target-sheet lookup, or an independently documented asset-path recipe.
4. Sentinel values, signedness, key/subkey rules and conditional lookup paths.
5. Corpus validation: target-row existence for applicable source values.
6. Confidence: metadata candidate, data-correlated, disassembly-confirmed or
   runtime-confirmed. Keep these levels distinct.

Names and row-existence correlations are useful for prioritization, not proof.
Likewise, matching a PS3 schema does not authorize copying a PS3 runtime class
layout into the Windows client.

## Do we know every ID type? No.

There are three different questions:

| Question | Current answer |
| --- | --- |
| Physical EXH cell types / widths | All types encountered in this corpus decode. Older EXH versions and binary type 12 remain unsupported; F16 stays raw bits. |
| Named debug typedefs / enums / key structures | A substantial imported catalog exists. It has **3,186 enum records** and **463 type names containing `Id` or `ID`**, but those counts include unrelated enums, alternate views and names that are not ID aliases. |
| Semantic ID domains, encodings and every field's target | Incomplete. Many references use ordinary uint8/uint16/uint32/uint64 fields, so the C++ type alone does not identify a target sheet or resource namespace. |

Known distinctions include EObj BaseId/sheet row key, live EntityId, layout
InstanceID/BindLayoutId, per-SGB timeline MemberID, slot index and stored mask.
They can all involve integers without being interchangeable. An Item ModelId
is also not automatically an Item row ID simply because it is numeric.

Encoded IDs, selector-dependent columns, zero/negative sentinels, multi-key
lookups and asset-local member IDs need their consumers traced separately.
There is no established complete “ID enum” that assigns every EXD integer a
universal semantic meaning.

## Reproduce the recovery report

```sh
python research/ps3-monitor/build_monitor_recovery_report.py
```

Inputs are the existing `build/ps3-exd-scan.json`, `ps3-inventory.json` and
`ps3-monitor-metadata.json`, plus the optional decoded sheets listed above.
Outputs:

- [`monitor_recovery.json`](monitor_recovery.json): compact counts, limits and
  EObj/Item/TerritoryType column candidates.
- `build/ps3-known-paths.json`: matched candidate paths and their source labels.
- `build/ps3-excel-column-candidates.json`: complete candidate-column ledger for
  the 303 directly matched row structs.

These ledgers are a starting point for a provenance-aware asset/relationship
browser, not a declaration that semantic recovery is complete.

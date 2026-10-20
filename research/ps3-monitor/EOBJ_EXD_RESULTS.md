# PS3 Monitor: event-object masks and data coverage

## Sastasha result: confirmed in code AND assets

The four grate bindings in Sapphire (`3992454`, `3992452`, `3992449`,
`3992453`) all point to:

`bg/ffxiv/sea_s1/shared/for_bg/sgbg_s1d1_m1_bos1.sgb`

The bindings were located in `bg/ffxiv/sea_s1/dun/s1d1/level/bg.lgb`.
The SGB's general-purpose slots are:

| Slot | Mask | MemberID | Asset timeline name |
| ---: | ---: | ---: | --- |
| 0 | `0x0001` | 12 | `open` |
| 1 | `0x0002` | 14 | `close` |
| 2 | `0x0004` | 15 | `vfx_on` |
| 3 | `0x0008` | 16 | `vfx_off` |

Slots 4–15 are disabled (MemberID zero). These names are **asset-specific**,
not a global `ANIMFLAG_OPEN_GRATE` enum. The user's four constants agree with
this asset; `CLOSE_GRATE | STOP_BUBBLE` is `0x000A`.

The named PS3 `SharedGroupTimelineState` is two bytes. EventObject stores it
at `+0x17A`. The important code addresses are:

- `0x97A850`, `EventObject::SetSharedGroupTimelineState`: `sth` to `+0x17A`,
  then tests `(1 << index) & state` across 16 slots when no event handler owns
  the object. Starts enabled set-bit timelines and stops cleared-bit timelines.
- `0x98D228`, `EventHandler::OnSetSharedGroupTimelineState`: PPC `xor`, `and`,
  `andc` prove the rising/falling masks, respectively `(old ^ new) & new`
  and `(old ^ new) & ~new`.
- `0x9E27BC`, quest override: plays rising bits. Overrides can differ from the
  base handler; there is not one universal replay policy.
- `0x48AF94`, `SharedGroupLayoutInstance::CreateChildNodeInstance`: copies 16
  bytes starting at SGSettings `+5` to `m_generalTimelineId` (`this+0xE4`).
- `0x489160`, `CreateTimeLineInstance`: timelines are contiguous 44-byte
  records, relative to the folder, identified by MemberID.
- `0x4545AC`, `IsEnableGeneralTimeline`: checks slot `<16` and a nonzero ID.
- `0x4543E0`, `PlayGeneralTimeline_Local`: resolves that slot's MemberID.

See [`sastasha_grate_timelines.json`](sastasha_grate_timelines.json),
[`asset_types.json`](asset_types.json), and
[`eobj_excel_disassembly.txt`](eobj_excel_disassembly.txt).

## Packet distinction relevant to Sapphire

Do not confuse the stored timeline state, the playback mask, and the object
spawn `Flag`/Sapphire `getState()` byte:

- ActorControl `0x199` (`SetSharedGroupTimelineState`): arg0 becomes the stored
  16-bit state through the setter. `Packet::Order` calls it at `0xAF2E9C`.
- ActorControl `0x19A`: arg0 is a **single timeline index**, arg1 is its time.
- ActorControl `0x19D` (`PlaySharedGroupTimeline`): arg1 is the **playback mask**;
  after synchronizing all 16 timeline slots, arg0 is stored at EventObject
  `+0x17A`. See disassembly `0xAF2FFC`–`0xAF3078`. The arguments can differ.
- `Packet::CreateObject` (`0xAE3438`) initializes the stored state from Args2.

The present `EventObject::playSharedGroupTimeline(flag, animationFlag)` sends
`0x19D`; its first argument is therefore not the playback selector. A future
`setAnimation()` must deliberately maintain the stored mask as well as send
an appropriate packet, and initialize spawn Args2 for late-arriving players.
These packet statements were first confirmed for the **PS3 monitor**, not an
automatic proof that every later Windows build has identical layouts/semantics.
The subsequent [`Windows 3.3 mapping`](WINDOWS_EOBJ_MAPPING.md) independently
confirms the mask behavior and argument distinction there, with a different
EventObject field offset (`+0x1A2`).

For conditions on a stored mask:

```cpp
const bool hasAny = (animation & mask) != 0;
const bool hasAll = (animation & mask) == mask;
const bool hasNone = (animation & mask) == 0;
```

Keep exact equality available when desired. `hasAll` is vacuously true for a
zero mask; use an explicit zero/equality condition for the initial state.
`vfx_on` and `vfx_off` are separate timeline selections, not a generic
persistent boolean. OR-ing `0x08` onto `0x04` does not clear the `0x04` bit.
The stored mask also does not prove that a one-shot timeline is still running.

**No production timeline behavior was changed.** This checkout lacks the
user's `getAnimation()/setAnimation()` implementation and an EObj condition;
`SetEObjState` currently operates on the separate state byte. Replacing those
comparisons globally would conflate two different fields.

## EXD and file coverage delivered

The new headless tool is [`src/tools/Ps3DataInspector`](../../src/tools/Ps3DataInspector).
It initially used an independent byte-oriented EXH/EXD decoder to avoid the
legacy reader's offset-map column collapse, 64-bit packed-bool reads,
unimplemented subrow strings and low-byte row counts. That decoder now lives
in shared `ExcelBinary.h`; the library's Exh/Exd and ToolkitPs3 use it too.
ToolkitPs3 also has a generic Excel browser. The library-path full-corpus scan
matches the counts below with zero errors; typed flags/subrow forwarding were
checked separately. See [integration and recovery status](TOOLKIT_DATA_STATUS.md).

Run on this monitor corpus:

- **2,131 root-listed sheets**, all EXH v3.
- **10,295 successfully decoded pages/languages**.
- **1,021,511 decoded row/subrow instances**, including language duplicates.
- Four multi-key sheets: Behavior, GatheringItemPoint, Resident, TreasureSpot.
- All encountered cell types decoded, including strings, signed integers,
  uint64, float32 and eight packed boolean types. Zero scan errors.
- **14 indices**, **745,952 archive entries**. All hashes and 64-bit offsets
  independently cross-checked against the raw on-disk PS3 index records.
- Shader (`0x05`) and game_script (`0x0B`) use SDAT-wrapped DAT payloads.
  Later verification found both local containers are debug/plain: keyless
  deframing and SqPack decompression validate all 283 / 1,934 records.
  The C++ backend still lacks a logical SDAT reader; a separate Python helper
  now inspects/extracts these. See [Lua/timeline starting points](LUA_TIMELINE_START.md). Categories `0x12` (3 entries) and `0x13`
  (361 entries) are retained without inventing category names.
- IDB metadata export: **26,223 types**, **229,766 symbols**, **8,707 candidate
  path strings**. Candidate/source/debug strings do not prove file existence.
  Alternate/gap-only imported types remain unverified metadata, not generated
  host-ABI C++ structures.

EXD layout evidence: `EXHeader` getters at `0xE9C4B4` onward read BE header
values; `GetSubkeyCount` at `0xE9C584` reads total keys, from which ExcelSheet
subtracts one. `ExcelSubSheet::OnReadAll` (`0xE9B2B8`) places the common string
pool after all fixed subrecords. Column offsets may repeat for packed booleans.
Language descriptors are a language byte plus padding (`02 00` = English),
not a BE language uint16. PS3 fixed-row values and string offsets are BE.

### Reader fixes needed for full archive addressing

The PS3 bg DAT is **4,795,943,168 bytes**; **14,880** bg entries lie above 4 GiB.
`datReaderPs3` previously multiplied index offsets in uint32 and carried
uint32 absolute offsets through Dat extraction. Those offsets are now uint64,
including model/texture block cursors. Index entries now populate their hash
fields too, so enumeration returns usable metadata.

A real standard entry at **4,639,310,720** was successfully extracted (1,564
bytes) with `extract-hash`, in addition to the synthetic >4-GiB index test.

### Verification and boundaries

- `cmake --build build -j 6`: passed, including ToolkitPs3.
- `ctest --test-dir build -R ps3_data_inspector_tests --output-on-failure`: passed.
- Tests cover BE signed/unsigned numerics, repeated packed-bool offsets,
  shared subrow strings, nonordinal subkeys, counts above 255, malformed
  offsets/strings, unsupported versions/types, and >4-GiB index offsets.
- Large scan/inventory/metadata artifacts remain under `build/`; compact
  results and source/index SHA-256 fingerprints are in
  [`data_coverage.json`](data_coverage.json). Regenerate with
  `build_data_coverage.py` after running the tool commands in its README.

**This is corpus-complete root-listed EXD decoding and an archive inventory,
not complete semantic decoding of every game format.** Older EXH v2, binary
cell type 12, general SDAT support/integrity/decryption, and full model/texture/audio/shader/timeline
binary parsers remain outside the implemented decoder. F16 is preserved as
raw bits; it is not used in this corpus. SGB support here reports timeline
metadata, not all animation clips. No PS3 layouts have been copied into
Windows/server wire types without validation.

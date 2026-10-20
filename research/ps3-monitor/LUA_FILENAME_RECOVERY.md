# Lua filenames recovered from PathList.txt

## Result

`PathList.txt` contains 2,411,241 lines, including 6,992 `game_script/` paths.
Comparing case-folded **directory AND filename CRC32 hashes** against the actual
PS3 script index recovers unique dictionary names for:

- **All 1,932 compiled Lua chunks.**
- **The one Lua source-text record:** `game_script/leve/Gld10000.luab`.
- **1,933 / 1,934 archive records total.**

Only the non-Lua placeholder at hash pair `10e2eace / e4951b06` remains unnamed.
There are no ambiguous hash-pair matches in this dictionary. Unmatched candidate
paths mostly belong to other game versions; they are not missing monitor files.

This is direct dictionary matching, **not inference from Lua class/global names**.
For all 1,932 compiled chunks, the recovered basename additionally agrees with
both embedded debug-source basenames. Hashes cannot prove original capitalization;
output spelling is preserved from the supplied PathList.

## Files written

The original payload bytes are copied—not converted or decompiled—under their
recovered archive names:

```text
build/ps3-lua-named/
  manifest.json
  game_script/
    custom/000/CmnDefRetainerCall_00010.luab
    custom/001/CmnDefMateriaSlot_00174.luab
    custom/001/CmnDefBeautySalon_00148.luab
    transport/Aetheryte.luab
    leve/Gld10000.luab
    ...
```

All 1,933 named copies were verified against recorded sizes and SHA-256 hashes.
The original `build/ps3-lua/` hash-named extraction remains untouched.
`manifest.json` retains every record, hashes, logical offset, dictionary line
numbers, match/ambiguity status, payload kind and embedded debug-source names.
The compact research summary is [`lua_path_recovery.json`](lua_path_recovery.json).

`.luab` is the archive filename extension. It does not force a binary payload:
`Gld10000.luab` contains source text. Keep that distinction when invoking a
bytecode decompiler.

## Hash mapping examples

| Directory hash | Filename hash | Recovered archive path |
| --- | --- | --- |
| `06bc4074` | `c151e0b5` | `game_script/custom/000/CmnDefRetainerCall_00010.luab` |
| `5e9a31c1` | `79eaa126` | `game_script/transport/Aetheryte.luab` |
| `71bb70e2` | `0472d814` | `game_script/custom/001/CmnDefMateriaSlot_00174.luab` |
| `71bb70e2` | `26544b7f` | `game_script/custom/001/CmnDefBeautySalon_00148.luab` |

Matching filename hash alone is insufficient: the dictionary also names a
separate `game_script/system/aetheryte.luab`. Directory hashes distinguish it
from the transport script.

## Original source names are preserved too

The outer compiled chunk uses `=(luac)`, but child prototypes preserve **3,864
actual non-wrapper source names**, two per chunk. For example:

```text
archive: game_script/transport/Aetheryte.luab
  source: @Transport/Aetheryte.cli.lua
  source: @Transport/Aetheryte.cmn.lua
```

These are embedded debug strings, not guesses. A compiled archive record bundles
multiple input source files, so a `.luab` resource name and its original `.lua`
source names are different layers. Decompilation does not reproduce authentic
source bytes, comments or formatting merely because these names survive.

## Reproduce

```sh
# Requires the previous hash-named extraction and runtime ledger.
python research/ps3-monitor/recover_lua_paths.py
python research/ps3-monitor/test_recover_lua_paths.py
```

Use `--path-list`, `--index`, `--runtime`, `--extracted`, `--output-dir` and
`--summary` to override defaults. The script checks the ledger against the raw
index and verifies copied payload hashes. It refuses to assign ambiguous names
or overwrite differing output bytes. Eight synthetic tests cover aliases,
directory discrimination, ambiguity, stale offsets, payload tampering and
output preservation.

## Supplied decompiler

`build/cLuaDecompiler.exe` directly reads the big-endian monitor chunks.
Explicit `--dis` and `--dec --annotate` runs returned success for five samples
(the four timeline-related resources above and the system Aetheryte stub).
Disassembled prototype counts agree with the independent parser.

Outputs are under `build/ps3-lua-decompiler-samples/game_script/`, using suffixes
`.luab.dis.txt` and `.luab.decompiled.lua`. For example:

```sh
build/cLuaDecompiler.exe --dis build/ps3-lua-named/game_script/transport/Aetheryte.luab
build/cLuaDecompiler.exe --dec --annotate build/ps3-lua-named/game_script/transport/Aetheryte.luab
```

Treat the decompiled text as a navigation aid, not verified original source.
Successful exit codes/prototype counts do not prove reconstructed control flow.
For example, the Aetheryte scene disassembly contains an unconditional jump out
of the home-point-already-registered branch which is not retained as an early
exit in the sample pseudo-Lua. Use the disassembly for behavioral conclusions.
No scripts were executed. These were only samples during the filename-recovery
pass; the subsequent [full decompilation pass](LUA_DECOMPILATION.md) processed
all 1,932 chunks and compared both unluac versions with cLuaDecompiler.

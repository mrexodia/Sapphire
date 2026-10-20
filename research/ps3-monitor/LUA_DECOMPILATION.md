# Full monitor Lua decompilation

All **1,932 compiled resources** were processed with three decompilers and
cLuaDecompiler's disassembler. Original resource filenames and payloads remain
unchanged. Generated sources, bytecode recompilations, logs and diagnostics are
under `build/ps3-lua-decompiled/`; no game scripts were executed.

## Where to browse

Start at:

```text
build/ps3-lua-decompiled/recommended/game_script/
```

This now contains **all 1,932 syntax-valid reconstructed resources plus the
authentic Gld10000 source-text payload**. Automatic selections use complete
tool outputs; one explicitly marked manual reconstruction closes the remaining
exception. The full manifest records each choice and its verification results.

The manually recovered exception was:

```text
game_script/transport/ChocoboTaxiStand.luab
```

Both unluac versions mishandle its nested menu loops. Their raw output and the
complete disassembly are retained. Do not mistake the malformed output for
original Lua. A `--nodebug` retry emitted Lua-5.1-incompatible goto syntax.
Adding explicit statement separators to cLuaDecompiler's output made that
sample compile, but only four of seven prototype bodies matched; that retry
was **not** promoted into recommended output. The subsequent manual repair
restored the original nested loops and gil/buddy `elseif` chain. Its recompiled
ordered instruction/constant/arity tree matches **all seven original prototypes,
234 code words**. Scene/helper execution headers also match; reviewed differences
are limited to unused wrapper vararg capability and synthetic-root stack sizing.
See [manual recovery details](CHOCOBO_TAXI_RECONSTRUCTION.md).

Other output trees:

- `unluac-2015/game_script/`: the jar already included in the repository.
- `unluac/game_script/`: newer official SourceForge jar, version 1.2.3.569,
  filename `unluac_2025_12_23.jar` (published in **Unstable**).
- `cLuaDecompiler/game_script/`: untouched annotated pseudo-Lua.
- `disassembly/game_script/`: cLuaDecompiler disassembly for every resource.
- `manual/game_script/transport/ChocoboTaxiStand.lua`: verified manual reconstruction.
- `original-source/game_script/leve/Gld10000.lua`: byte-identical source payload.
- `diagnostics/`, `recompiled/`, `manifest.json`: errors and verification evidence.

## Comparison

| Tool | Returned success | Passes Lua 5.1 syntax | Exact ordered instruction/constant tree matches |
| --- | ---: | ---: | ---: |
| Included unluac (2015-06-13) | 1,932 | **1,897** | **1,877** |
| Newer unluac (2025-12-23) | 1,932 | **1,930** | 0 |
| cLuaDecompiler, untouched `--dec --annotate` | 1,932 | 0 | not compiled |

The newer jar generally names the synthetic outer wrapper `L0_1` and introduces
local-function/call register changes, preventing whole-tree equality. This is
**not evidence that its output is semantically worse**. Its valid outputs
retain 31,796 exact prototype bodies out of 37,138 original prototypes in those
files. The old jar retains 36,965 / 36,989 bodies in its syntax-valid files.

The recommended set uses **1,897 old-unluac outputs and 34 newer-unluac outputs**:
syntax validity first, then exact tree agreement, then matching body count;
ties favor the newer version. A **single manual reconstruction** completes the
set. All selections are explicit in the manifest; automatic-tool measurements
in the comparison table remain unchanged.

cLuaDecompiler's raw output commonly lacks separators between immediately
invoked outer wrappers; some files additionally have malformed branch/loop
structure. Its universal syntax failure here does not imply every individual
function is wrong. Its disassembly remains useful: all **37,185 prototype
counts** agree with the independent parser.

## Verification limits

- Syntax checking uses **Lua 5.1.5's reference compiler**, compiled locally from
  the official source archive. Compilation does not run the game code.
- The cross-endian fingerprint compares arity, instruction words, exact constant
  bytes (including numeric bit patterns), and ordered child prototypes.
- It excludes source/debug metadata, stack sizes and vararg flags. Thus even an
  exact match is corroboration, **not complete behavior/ABI proof**.
- Matching-body counts are unordered multiset comparisons, not function-identity
  proofs. Nonmatching trees can still be equivalent.
- Output SHA-256 hashes and all recommended copies were checked. Decompiler exit
  code zero alone is not treated as validity.

The compact measured summary is [`lua_decompilation.json`](lua_decompilation.json).
Tool SHA-256 identities are recorded there and in the full generated manifest.

## Reproduce

```sh
python research/ps3-monitor/decompile_monitor_scripts.py
python research/ps3-monitor/reconstruct_chocobo_taxi.py
python research/ps3-monitor/test_decompile_monitor_scripts.py
python research/ps3-monitor/test_reconstruct_chocobo_taxi.py
```

Defaults require the named extraction, the included jar, `build/cLuaDecompiler.exe`,
`build/unluac-current.jar` and `build/lua51-reference/luac51.exe`. Java is found
through PATH, JAVA_HOME or standard installation directories. Override paths
with `--java`, `--unluac`, `--legacy-unluac`, `--clua`, `--luac`, `--named` and
`--output`. `--jobs`, `--timeout` and `--limit` support bounded smoke tests.
Use a new output directory to preserve edits to an earlier generated corpus.

Newer jar source (original included jars were not replaced):
<https://sourceforge.net/projects/unluac/files/Unstable/unluac_2025_12_23.jar>

Reference compiler source:
<https://www.lua.org/ftp/lua-5.1.5.tar.gz>, SHA-256
`2640fc56a795f29d28ef15e13c34a47e223960b0240e8cb0a82d9b0738695333`.
Built with LLVM clang from every `src/*.c` except `lua.c`, using `-O2
-DLUA_USE_WINDOWS -D_CRT_SECURE_NO_WARNINGS -o luac51.exe`.

Seven synthetic tests cover endian/size_t normalization, raw string preservation,
debug exclusion, instruction and signed-zero differences, truncation and
unsupported profiles. The full batch completed in approximately four minutes.

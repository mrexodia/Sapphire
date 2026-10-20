# ChocoboTaxiStand manual reconstruction

Recovered resource: `game_script/transport/ChocoboTaxiStand.luab`.
Original payload SHA-256:
`011d0a510845a9bc9f1bd6df83af0ba95ce59b003d046e922f8e513dadc5b66f`.

## Result

The reconstructed source is available at:

```text
build/ps3-lua-decompiled/manual/game_script/transport/ChocoboTaxiStand.lua
build/ps3-lua-decompiled/recommended/game_script/transport/ChocoboTaxiStand.lua
```

Compilation with reference Lua 5.1.5 reproduces the **same ordered arity,
instruction and constant trees for all seven prototypes: 234 instruction words**.
The tree SHA-256 is identical before and after recompilation:
`9f539a2f94e4f4d295923590fa871ebf6d4634f0a48b4aecda0041bd20d0584f`.
This includes the original jump offsets and unreachable tail jumps, not merely
similar method calls or matching unordered body counts.

Scene/helper execution headers also match exactly. Reviewed wrapper differences:

| Prototype (preorder index) | Original | Recompiled |
| --- | --- | --- |
| Synthetic root (0) | vararg flags 0, stack 1 | flags 2, stack 2 |
| CLI wrapper (1) | vararg flags 2 | flags 0 |
| Common wrapper (3) | vararg flags 2 | flags 0 |

These wrappers contain no VARARG instructions, no implicit legacy arg-table
flags, and zero parameters/upvalues. Their unused vararg capability differs;
the root's extra stack slot does not alter the identical instructions. Source
names, line numbers and other debug metadata differ as expected. This is **not
byte-for-byte recovery of the original source text** or a live-client test.

## Why the decompilers failed

The outer menu and inner taxi-selector loop have different cancellation targets.
The scene also uses a gil/buddy `elseif` chain whose compiler emits jumps after
returns. Both unluac versions misplaced loop boundaries; simply fixing syntax
would not necessarily retain those control-flow edges.

Scene program counters below are **1-based**, from
`build/ps3-lua-decompiled/disassembly/game_script/transport/ChocoboTaxiStand.dis.txt`:

| PCs | Behavior / target |
| --- | --- |
| 1–17 | Level check; low level talks/system-talks and returns 0. |
| 18–49 | Stand ID and first vararg; unlock/how-to/introduction handling. |
| 50–57 | Main menu and choice-1 test; other choices branch to 126. |
| 58–77 | Explicit `IsChocoboTaxiPossible == false`: messages, then retry **main menu at 50**. |
| 78–82 | Taxi selector returns four values; taxi ID not greater than zero returns to **50**. |
| 83–96 | Format confirmation; confirmation not exactly true retries **taxi selector at 78**. |
| 97–110 | Explicit failed gil check: talk, return 0. |
| 111–120 | Explicit buddy-present check: log, return 0. |
| 121 | Otherwise return the selected taxi ID. |
| 122–125 | Compiler-emitted loop/branch tail jumps retained by the reconstruction. |
| 126–174 | Choice 2 displays nine help talks, then retries main menu at 50. |
| 175–179 | Other choices leave the loop and return 0; final empty return is unreachable. |

The repair preserves `== true` and `== false` rather than converting them to Lua
truthiness checks. It preserves call argument counts, the four taxi-selector
results, the first-vararg unlock check, and all three common helper functions.

## Reproduce and test

```sh
python research/ps3-monitor/reconstruct_chocobo_taxi.py
python research/ps3-monitor/test_reconstruct_chocobo_taxi.py
```

`--no-promote` verifies without changing the recommendation or corpus manifest.
The generator verifies original/raw-output identities, replaces only the damaged
loop region, compiles the result, and refuses promotion unless the entire ordered
tree matches. It checks the remaining execution-header differences separately.

Five tests cover unknown/duplicate repair layouts, all seven matching prototypes,
scene/helper header equality, and negative cases which invert confirmation or
send declined confirmation to the wrong menu. These mutations compile but fail
the tree comparison. Tests **compile only; no game scripts are executed**.

Evidence: `build/ps3-lua-decompiled/manual/ChocoboTaxiStand-verification.json`.
Original archive payloads and raw decompiler outputs remain untouched. The corpus
now has recommendations for all 1,932 compiled resources, plus the original
Gld10000 source payload; original automatic-tool statistics are retained.

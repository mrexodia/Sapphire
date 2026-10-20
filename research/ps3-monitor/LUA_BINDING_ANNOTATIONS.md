# Lua binding comments

Browse **`research/ps3-monitor/game_script/`** for the updated comment-only
corpus and its `defines/` reference modules. Generated copies/reports also live
under `build/ps3-lua-annotated/`; staging from the user's copied corpus is under
`build/ps3-lua-reannotated/`. The verified recommendations and raw outputs under
`build/ps3-lua-decompiled/` are unchanged.

## What is included

- Handler `Define[n].Name/Value` pairs joined by the exact `Script` basename
  in the decoded EXD graph: Quest, CustomTalk, Opening, Story and WarpLogic.
- `EventSystemDefine`, family-specific/matching-stem shared tables, and shared
  tables containing directly referenced names. These are **scope candidates**,
  not a proven class hierarchy or binding-precedence model.
- Lua literal assignments are **not annotated**: they are already readable in
  the code. Shared-table entries appear in scripts only when directly referenced.
- Native `DefineLuaClass` integer registrations with PPC assembly witnesses.
  The native export examines 21 handler/director definitions and accepts 245
  registrations, including the reviewed `SHARED_GROUP_TIMELINE_0..5` loop.
  Decompiler candidates lacking witnesses are retained in the native export
  but are not used as recovered values.
- Script-local text-symbol row keys, explicitly labeled **not stored
  DefineValue**. A text-row key is not automatically its runtime binding value.

The header groups referenced and **not directly referenced** handler/text facts.
Unused shared/native inventories do not appear in script headers. Comments
immediately before direct `self.NAME`/class-member reads show stored EXD numbers,
source sheet/row/field, source writes and conflicting values. Native names link
to the relevant `defines/*.lua` module rather than repeating their values. Quoted identifier bracket keys are also
recognized. Dynamic keys, other receivers, and bare identifiers are not given
guessed bindings. Unknown direct members are listed; some are methods/state,
not missing constants. This is lexical cross-referencing, not reachability
analysis or a full Lua name-resolution/type checker.

For example, `transport/Aetheryte.lua` now includes:

```lua
-- @ps3-bind DEFAULT_NO <- defines/EventSystem.lua native.LuaEventHandler [scope candidate]
-- @ps3-bind SHARED_GROUP_TIMELINE_2 <- defines/EventSystem.lua native.LuaEventHandler [scope candidate]
```

Its native menu constants and `MAX_FAVORITE_POINT = 4` are recorded in
`defines/AetheryteSystem.lua`. The 13 definition modules contain complete accepted
shared/native inventories, separated into `exd` and `native.<Class>` tables to
avoid silently overwriting colliding names. They are static reference modules,
not an assertion that the game automatically loads files from `defines/`.
An index named `SHARED_GROUP_TIMELINE_2` is not by itself an asset MemberID or
proof of a universal authored animation meaning.

## Are the values always concrete?

**The stored numeric Name/Value entries are concrete for this dataset.**
Accepted native literals are concrete numbers registered by this binary.
Lua assignments remain in the code without redundant definition comments.

**That does not mean every runtime expression has one immutable value.** Lua
fields can be assigned later, handler/class/shared definitions can collide,
and lookup scope or initialization order matters. The annotator preserves
all matching facts rather than choosing a winner. It does not convert aliases,
dynamic lookups, absent constants, or text keys into invented numeric values.
Shared/native candidates are not guaranteed to belong to each selected script.
The PS3 monitor numbers are not asserted to be identical in another client build.

Examples with visible multiple-source values include `EMOTE_BOW`/`EMOTE_YES`
in RetainerCall and `ACTION_TIMELINE_EVENT_TALK_BIG` in GaiUse207. “Not directly
referenced” only means no supported lexical read was found; it does not prove
that a definition is unused at runtime.

## Script-associated text sheets

These are localized EXD dialogue/message resources, not additional Lua source
files or general constant tables. Examples in the decoded dataset:

- `transport/ChocoboTaxiStand`: two string columns labeled `Symbol` and `Text`;
  row 1 is `TEXT_CHOCOBOTAXISTAND_00000_SYSTEM_000_1` with English text
  “Chocobo porters are available for hire upon attaining level 10.”
- `custom/000/CmnDefRetainerCall_00010`: retainer greetings, menu labels and
  other messages; some strings contain embedded formatting/control payloads.

The two-column labels are marked `format_inferred_candidate` in the graph,
not imported-debug-struct proof. Association is by the matching script-relative
path. The annotation maps the symbol to the stored EXD main row ID; it does not
prove the runtime loader binds that exact number to `self.TEXT_...`. Text fields
with formatting payloads must not be treated as simple plain UTF-8; the graph's
string view is not a full rich-text decoder. The separate `ChocoboTaxiStand`
sheet without the `transport/` prefix holds taxi/destination data, not dialogue.

## Coverage and validation

Latest generated corpus:

| Measure | Count |
| --- | ---: |
| Annotated Lua files | 1,933 |
| Files with mapped handler bindings | 1,607 |
| Handler Name/Value facts | 18,036 |
| Inline comments | 134,393 |
| Script fact occurrences (referenced shared/native plus handler/text facts) | 151,999 |
| Shared/native definition modules | 13 |

Every file passes **Lua 5.1 compilation-only syntax checking** and comparison
of its exact non-comment lexical tokens against the input. These checks show
that the annotation preserved code; they do not establish the correctness of
all earlier decompilation or infer runtime binding precedence. No game script
is executed. Ten synthetic tests cover conflicts, unused definitions,
quoted/dynamic keys, multiline-string safety, expression rejection, text-key
separation and refusal of unconfirmed native candidates.

`QuestBattle` binding rows lacking a direct `Script` field remain unmapped.
The unmatched binding stem `tstplntest_00036` is reported. Basename collisions
are not silently resolved.

## Reproduction and evidence

```bash
python research/ps3-monitor/annotate_lua_bindings.py
python research/ps3-monitor/test_annotate_lua_bindings.py
```

Inputs default to `build/ps3-data-graph.sqlite`, the recommended Lua corpus,
and optional `build/ps3-native-lua-defines.json`. Generate the last input with
`ida_export_lua_defines.py` through IDA-domain against the PS3 monitor IDB.
It preserves pseudocode, disassembly, unconfirmed candidates and accepted
literal witnesses. Native export is read-only; the hard-coded reviewed loop
belongs specifically to this monitor function at `0x009942DC`.

`build/ps3-lua-annotated/summary.json` records graph metadata, native input hash,
coverage and unmapped cases. `manifest.json` schema 3 additionally records
input/output hashes, validations, selected scopes and conflicts per script.
Each record's zero-based `fact_ids` indexes the shared `fact_registry`, avoiding
repeating all provenance objects for every file. The full generated ledger
and annotated sources remain under `build/`.

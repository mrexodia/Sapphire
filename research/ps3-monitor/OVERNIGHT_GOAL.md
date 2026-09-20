# Overnight packet-matching plan

## Objective

Use the FFXIV 2.3 PS3 Monitor build's DWARF names and types to identify as many
packet dispatchers, handlers, and wire structures as can be defensibly matched
in the Windows 3.x client. Preserve the results in reproducible research
artifacts, annotate the Windows IDB, and make only Windows-validated corrections
to Sapphire's packet definitions.

The finite core of the work is exhaustive triage of the zone-down and chat-down
dispatchers. Outbound and lobby work are stretch goals. A case recorded as
unresolved is preferable to an unsupported match.

## Inputs and existing anchors

- Branch: `research/ps3-33-packet-matching`
- Existing commits: `9efcdaec8`, `fcd8a4dfb`
- Mapping ledger: `research/ps3-monitor/packet_matches.json`
- PS3 ELF/IDB: `E:/FFXIV-Monitor-PS3/game/ffxivgame.ppu.elf`
  - Version: `2014.06.13.0000.0000`
  - SHA-256: `99ed4e57ea8d7a05c691c843e996ab85a9df51c239b2adc9d10ffe1acaa01537`
- Windows executable/IDB: `E:/Sapphire/game/ffxiv_dx11.exe` and
  `E:/Sapphire/game/ffxiv_dx11.exe.i64`
  - Version: `2016.07.05.0000.0001`
  - SHA-256: `d818584c782bbe3cacbc2b306391e6f3246bc3065c517a3324784e49d572ba12`
- Historical packet definitions: `upstream/ThreePointThree` at commit
  `fe26d3ba840deb1eaca6db6d8a486c8e068482f9`

Confirmed class anchors:

| Role | PS3 | Windows |
| --- | ---: | ---: |
| `PacketDispatcher` constructor | `0x002F85C8` | `0x140DD93E0` |
| Zone receive dispatcher | `0x002F8710` | `0x140DD9430` |
| Chat receive dispatcher | `0x002FA984` | `0x140DD9300` |

Windows `0x1411B95B0`, currently labelled `flawed_unshuffle_opcodes`, is a
separate generated opcode-to-vtable dispatcher. It is not the direct equivalent
of the PS3 zone dispatcher.

## Windows IDB annotation convention

Every confirmed Windows function match must have a repeatable function comment
whose first line links to the corresponding PS3 function:

```text
PS3 Monitor: idb://ffxivgame.ppu.elf.i64:002F85C8
```

Use the exact database name `ffxivgame.ppu.elf.i64` and an eight-digit,
uppercase, zero-padded PS3 function address without `0x`. Put concise evidence
on following lines. The link must target the PS3 function entry, not an OPD
record or an interior instruction.

Only confirmed matches receive the authoritative `PS3 Monitor:` link. A
probable or candidate relationship may be recorded in the mapping ledger, but
must not receive the link or a definitive Windows name. If one Windows function
incorporates multiple PS3 functions, document each relationship explicitly and
do not imply a one-to-one match.

## Phase 1: Preserve and inventory

1. Verify the current branch and clean working tree. Do not switch branches,
   rewrite history, or push.
2. Treat the PS3 database as the named reference baseline; avoid modifying it.
3. Export every explicit case from the PS3 and Windows zone-down and chat-down
   dispatchers.
4. Record opcode, direct target, handler address/name, packet-data offset, and
   whether the behavior is direct, shared, inline, ignored, or default.
5. Include cases with no immediate match so dispatcher coverage is auditable.

## Phase 2: Match functions

Prioritize candidates in this order:

1. Same opcode with a named PS3 handler.
2. Same secondary switch, field accesses, or distinctive constants.
3. Equivalent manager, UI, game-state, or event-framework effects.
4. Equivalent vtable role and call-graph neighborhood.
5. Semantic matches whose opcodes changed between releases.

Assign every dispatcher case exactly one status:

- `confirmed`
- `probable`
- `candidate`
- `ps3-only`
- `windows-only`
- `unresolved`

A confirmed match requires at least two independent semantic anchors. Opcode
equality, function size, or superficial CFG similarity is not sufficient.
Record additions, removals, splits, merges, and inlining rather than forcing a
one-to-one correspondence.

For each confirmed match:

1. Add or update the entry in `packet_matches.json`.
2. Add `ps3IdbUrl` using the required `idb://` format.
3. Apply a stable `Client__...` name to the Windows function.
4. Add the repeatable function comment with the PS3 IDB link and evidence.
5. Save the Windows IDB after each coherent batch.

## Phase 3: Recover packet structures

Inventory PS3 DWARF types related to:

- `ZoneProtoDown*` and `ZoneProtoUp*`
- `ChatProtoDown*` and `ChatProtoUp*`
- packet enums and common headers
- nested records used by confirmed handlers

For each useful structure and field, record:

- PS3 type and field name
- PS3 offset and width
- corresponding Windows access and inferred width
- current and historical Sapphire declaration
- confidence and evidence
- whether it is unchanged, moved, added, removed, or unresolved

The PS3 type proves a 2.3 layout only. Do not modify a 3.x Sapphire structure
unless the Windows executable independently confirms the field's existence,
offset, and width. Do not guess padding, signedness, pointer-sized fields, or
field names from alignment alone.

## Phase 4: Apply safe Sapphire discoveries

Where Windows evidence conclusively identifies a missing or incorrect Sapphire
packet definition:

1. Make the smallest correction in the current branch.
2. Add size or offset assertions when safe and useful.
3. Document the PS3 clue and the independent Windows validation.
4. Build `common` and `world` before committing.

Do not change gameplay behavior, database code, parsers, protocol runtime logic,
or unrelated architecture as part of this effort. If a correction remains
probable rather than confirmed, preserve it in the research ledger instead of
changing production headers.

## Phase 5: Validation and commits

After each coherent batch:

1. Validate every JSON artifact.
2. Run or extend a mapping validator that checks required fields, address
   formatting, duplicate addresses, conflicting names, and IDB URL consistency.
3. Query the Windows IDB and verify every confirmed entry's name, repeatable
   comment, and `idb://` target against the ledger.
4. Run `git diff --check`.
5. If production packet headers changed, run:

   ```bash
   cmake --build build --target common world
   ```

6. Commit a small, descriptive milestone. Do not push.

Do not commit executables, IDBs, packet captures, decrypted assets, bulk
pseudocode, or disassembly dumps. Commit derived addresses, names, concise
evidence, scripts, and structure metadata only.

## Completion criteria

The core overnight pass is complete when:

1. Every explicit PS3 and Windows zone-down/chat-down dispatcher case appears in
   the inventory and has one status.
2. Every obvious same-opcode or named-PS3-handler candidate has been reviewed
   semantically.
3. Relevant inbound structures used by confirmed matches have been compared
   with Sapphire and recorded.
4. No unreviewed high-likelihood candidate remains in the candidate ranking.
5. Every confirmed Windows function has a saved name, repeatable evidence
   comment, and correct `idb://ffxivgame.ppu.elf.i64:XXXXXXXX` link.
6. The mapping ledger can reproduce or verify the IDB annotations.
7. Research artifacts validate, production changes build, and all repository
   work is committed locally with a clean working tree.

## Stretch work

Only after the core criteria are met:

1. Match chat leaf handlers.
2. Investigate outbound Zone/Chat packet construction and send sites.
3. Inventory lobby packet types and handlers.
4. Propagate confirmed names into directly related managers and UI proxies.
5. Record version-specific functionality without forcing false equivalence.

## Pasteable Pi goal

```text
/goal Exhaustively triage and match as many defensible packet dispatchers, packet handlers, and packet structures as possible between the FFXIV 2.3 PS3 Monitor development build and the Windows 3.x client, then use independently confirmed Windows-side evidence to fill safe gaps in Sapphire.

Resume from the clean branch `research/ps3-33-packet-matching`, existing commits `9efcdaec8` and `fcd8a4dfb`, and `research/ps3-monitor/OVERNIGHT_GOAL.md`. Do not switch branches, rewrite history, or push. Use `research/ps3-monitor/packet_matches.json` as the source-controlled mapping ledger.

Use these exact inputs: PS3 `E:/FFXIV-Monitor-PS3/game/ffxivgame.ppu.elf`, version `2014.06.13.0000.0000`, SHA-256 `99ed4e57ea8d7a05c691c843e996ab85a9df51c239b2adc9d10ffe1acaa01537`; Windows `E:/Sapphire/game/ffxiv_dx11.exe` and `E:/Sapphire/game/ffxiv_dx11.exe.i64`, version `2016.07.05.0000.0001`, SHA-256 `d818584c782bbe3cacbc2b306391e6f3246bc3065c517a3324784e49d572ba12`; historical packet definitions from `upstream/ThreePointThree` commit `fe26d3ba840deb1eaca6db6d8a486c8e068482f9`. Confirmed anchors are PS3 constructor `0x002F85C8` to Windows `0x140DD93E0`, PS3 zone dispatcher `0x002F8710` to Windows `0x140DD9430`, and PS3 chat dispatcher `0x002FA984` to Windows `0x140DD9300`. Treat Windows `0x1411B95B0` (`flawed_unshuffle_opcodes`) as a separate generated opcode-to-vtable dispatcher, not the direct PS3 dispatcher equivalent.

First create a complete machine-readable inventory of every explicit case in the PS3 and Windows zone-down and chat-down dispatchers, including opcode, direct target, inline/shared-handler status, address, packet-data offset, and current name. Account for ignored/default/unmatched cases as well as successful matches. Add reusable export, validation, and IDB-application scripts where practical, but do not commit binaries, IDBs, packet captures, decrypted assets, bulk disassembly, or decompiler output.

Assign every case exactly one status: `confirmed`, `probable`, `candidate`, `ps3-only`, `windows-only`, or `unresolved`. A confirmed function match requires at least two independent semantic anchors, such as equivalent packet-field offsets and widths, the same secondary switch, equivalent manager/UI/game effects, distinctive constants, matching vtable role, or a matching call-graph neighborhood. Opcode equality, function size, or superficial CFG similarity alone is never sufficient. Record concise evidence and version differences. Do not force one-to-one matches when functionality was added, removed, split, merged, or inlined.

For every confirmed Windows function, apply a stable `Client__...` name and a repeatable function comment whose first line is exactly `PS3 Monitor: idb://ffxivgame.ppu.elf.i64:XXXXXXXX`, where `XXXXXXXX` is the corresponding PS3 function entry as eight uppercase zero-padded hexadecimal digits without `0x`; place concise evidence on following lines. The link must target the PS3 function entry rather than an OPD record or interior instruction. Add the same URI as `ps3IdbUrl` in the mapping ledger. Do not add an authoritative link or definitive name for probable/candidate matches. Preserve intentional existing labels unless replacement is strongly proven. Save the Windows IDB after coherent batches and verify the saved names and comments against the ledger.

Inventory relevant PS3 DWARF packet types, prioritizing `ZoneProtoDown*`, `ZoneProtoUp*`, `ChatProtoDown*`, `ChatProtoUp*`, common headers, enums, and records used by confirmed handlers. Compare sizes, fields, offsets, widths, and names against Windows accesses, the exact `ThreePointThree` headers, and current Sapphire headers. Record per-field confidence and evidence. PS3 layout alone proves only 2.3; do not modify a 3.x Sapphire structure unless Windows independently confirms the field's existence, offset, and width. Do not guess padding, signedness, field names, or pointer-sized fields.

Where Windows evidence conclusively identifies a Sapphire gap, make the smallest packet-definition correction, add safe size/offset assertions where useful, and document the evidence. Avoid unrelated gameplay, database, parser, runtime-protocol, or architecture changes. Leave merely probable corrections in the research ledger.

Work in batches, prioritizing same-opcode named PS3 handlers, packet families surrounding existing matches, game-object/player/event packets with distinctive semantics, and finally changed-opcode semantic candidates. After each batch update coverage counts and artifacts, validate JSON, audit duplicate/conflicting addresses and names, verify Windows IDB annotations and URI targets, run `git diff --check`, and commit a coherent milestone without pushing. If production packet headers change, run `cmake --build build --target common world` and do not commit broken production changes.

The core completion condition is: every explicit PS3 and Windows zone-down/chat-down case is inventoried and assigned a status; every obvious same-opcode/named-handler candidate has been semantically reviewed; inbound structures used by confirmed matches have been compared and recorded; no unreviewed high-likelihood candidate remains; every confirmed Windows function has a saved name, repeatable evidence comment, and correct PS3 IDB URI; the ledger can reproduce or verify the annotations; artifacts validate; production changes build; and repository work is committed locally with a clean tree.

If the core condition is reached with time remaining, continue with chat leaf handlers, outbound Zone/Chat construction sites, lobby packets, and directly related manager/UI name propagation under the same evidence rules. Do not sacrifice confidence to increase counts.

Finish with an auditable report containing case totals per dispatcher, counts by status, confirmed function and structure matches, exact Sapphire header changes, IDB annotations applied, validation/build commands and results, commits created, unresolved high-value candidates, version-specific functionality, and the next best batch. If IDA access, decompilation, damaged analysis, missing types, build failures, or lack of independent Windows evidence blocks further defensible progress, stop with the exact blocker, evidence gathered, attempted paths, and the specific input or manual decision needed.
```

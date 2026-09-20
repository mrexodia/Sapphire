# Completion audit

This checklist maps the persistent goal and `OVERNIGHT_GOAL.md` requirements to
current artifacts and direct verification evidence.

## Outcome and scope

| Requirement | Evidence | Result |
| --- | --- | --- |
| Remain on `research/ps3-33-packet-matching` | `git branch --show-current` | Satisfied |
| Do not push or rewrite history | Local milestone commits begin at `9efcdaec8`; remote `origin/build-cleanup` remains at `a4724c627` | Satisfied |
| Do not modify the PS3 reference IDB | All PS3 scripts are read-only exporters; no PS3 save or mutation operation was performed | Satisfied |
| Avoid unrelated production changes | Branch changes are research artifacts plus the independently Windows-validated `FFXIVIpcQuestFinish` byte/padding split | Satisfied |
| Do not commit binaries, IDBs, captures, decrypted assets, or bulk decompiler output | Branch diff contains Markdown, Python, and derived JSON only | Satisfied |

## Dispatcher inventory

| Requirement | Evidence | Result |
| --- | --- | --- |
| Inventory every PS3 zone-down case | `dispatcher_cases.json`: 285 explicit opcodes plus default | Satisfied |
| Inventory every Windows zone-down case | `dispatcher_cases.json`: 355 explicit opcodes plus default | Satisfied |
| Inventory every PS3 chat-down case | `dispatcher_cases.json`: 8 explicit opcodes plus default | Satisfied |
| Inventory every Windows chat-down case | `dispatcher_cases.json`: 7 explicit opcodes plus default | Satisfied |
| Record opcode, case/target addresses, packet offset, direct calls, and dispatch kind | Required fields are present per case and checked by `validate_research.py` | Satisfied |
| Include ignored, inline, shared, unmatched, and default behavior | `dispatchKind` summaries cover direct/shared/inline/ignored/default | Satisfied |
| Assign every case a permitted status | Validator checks every record; no `candidate` status remains | Satisfied |

## Matching and review

| Requirement | Evidence | Result |
| --- | --- | --- |
| Use multiple anchors rather than opcode alone | Confirmed mappings require ThreePointThree semantic name, PS3 DWARF handler identity, confirmed dispatcher/payload routing, and a unique Windows direct target; manually established mappings include field/callee/constant evidence | Satisfied |
| Preserve splits, merges, and shared handlers | `packet_matches.json` explicitly records 11 shared functions covering 55 opcode cases; no false separate functions were invented | Satisfied |
| Review every obvious same-opcode/named-handler candidate | `case_reviews.json`: 21 retained unresolved reviews and no probable cases | Satisfied |
| Leave no unreviewed high-likelihood candidate | `candidate_rankings.json` has zero entries; validator enforces this | Satisfied |
| Record one-sided case presence without overclaiming semantics | 18 PS3-only and 88 Windows-only zone cases plus one PS3-only chat case; inventory limitation defines status scope | Satisfied |
| Confirm as many defensible direct matches as possible | `packet_matches.json`: 209 packet-handler function pairs covering 253 cases (246 zone, 7 chat), plus 53 PS3-linked subsystem functions beyond the initial framework accessors, 10 Windows semantic functions, 9 Windows supporting functions, and 3 inline Windows cases without PS3 links | Satisfied |

## Windows IDB annotations

| Requirement | Evidence | Result |
| --- | --- | --- |
| Give confirmed Windows functions stable names | 209 PS3-linked handler names plus constructor, two dispatchers, 55 subsystem/accessor names, 10 Windows-semantic handlers, and 9 supporting functions in the saved Windows IDB | Satisfied |
| First repeatable-comment line uses the required PS3 URI | `ida_apply_matches.py` and `packet_matches.json`; IDA verification checked all 267 PS3-linked entries with zero failures | Satisfied |
| Use eight uppercase PS3 address digits and the exact database name | `validate_research.py` validates every `ps3IdbUrl` | Satisfied |
| Do not authoritatively link unresolved cross-build matches | Windows-only semantic names are explicitly separated from PS3-linked matches; unresolved relationships retain no PS3 backlink | Satisfied |
| Type dispatchers and proven complete-payload handlers conservatively | `readability_plan.json`: 101 typed functions; 36 packet views contain only Windows-confirmed fields | Satisfied |
| Make opcode dispatch readable without overclaiming | Generated enums label confirmed semantics and explicitly name all other values `Unknown`; 309 grouped case comments record evidence status | Satisfied |
| Recover high-leverage framework/inventory anchors | PS3-linked Framework, typed InfoModule/InfoProxyItemSearch lifecycle and records, Treasure/GameObject creation methods and packet views, and the quest/leve EventFramework handler tree; typed item assembly context/fragment lists; four typed globals and four named subsystem globals are saved and verified | Satisfied |
| Save the Windows database | `ida_save_database` succeeded for `E:/Sapphire/game/ffxiv_dx11.exe.i64` after the final annotation batch | Satisfied |
| Make annotations reproducible/verifiable | `ida_apply_matches.py` separately applies or verifies PS3-linked and Windows-only high-confidence mapping entries; `ida_apply_readability.py` does the same for types, globals, and case comments | Satisfied |

## Structures and Sapphire gaps

| Requirement | Evidence | Result |
| --- | --- | --- |
| Inventory PS3 DWARF structures used by confirmed handlers | `packet_structures.json`: 253 structures; exported by `ida_type_export.py` | Satisfied |
| Record PS3 size, members, offsets, widths/types | Every exported structure contains `ps3Size` and member metadata | Satisfied |
| Compare with current and ThreePointThree Sapphire declarations | Each structure records current and immutable historical path/line presence | Satisfied |
| Record independent Windows field evidence | `windowsValidation` records confirmed same-offset fields and version deltas; unreviewed fields are explicitly labelled | Satisfied |
| Do not promote PS3-only layout assumptions | Production decisions explicitly withhold 99 missing declarations pending complete Windows validation | Satisfied |
| Record confirmed version differences | `PlayerStatusUpdate.LvSync` moves `+0x04`→`+0x06`; TreasureHuntReward gains a leading event-handler ID; CreateTreasure shifts timers/content/catalogue data by four bytes | Satisfied |
| Make only conclusively supported production corrections | `FFXIVIpcQuestFinish` retains its proven 8-byte size while splitting the Windows-read byte at `+0x04` from three trailing padding bytes | Satisfied |

## Validation, build, and reporting

| Requirement | Evidence | Result |
| --- | --- | --- |
| Validate JSON and cross-artifact consistency | `python research/ps3-monitor/validate_research.py` reports 253 confirmed cases/structures, 659 cases, zero candidates, 10 Windows semantic functions, 9 supporting functions, 3 inline cases, 36 known-field types, 101 typed functions, 4 typed globals, and 309 case comments | Satisfied |
| Check whitespace/diff integrity | `git diff --check` succeeds | Satisfied |
| Build `common` and `world` if production headers change | After the `FFXIVIpcQuestFinish` correction, `cmake --build build --target common world` completed successfully | Satisfied |
| Commit coherent local milestones | Multiple coherent research commits are present after `origin/build-cleanup` | Satisfied |
| Finish with an auditable report | `OVERNIGHT_RESULTS.md` records coverage, annotations, structure gaps, verification, and remaining work | Satisfied |
| Leave a clean working tree | Verified after the final audit commit | Pending final commit at the time this file was written; rechecked immediately afterward |

## Completion judgment

All finite core criteria are covered by direct artifacts and validators. The
remaining 21 unresolved same-opcode relationships are not unreviewed work: each
has an explicit evidence-backed review and reason no PS3↔Windows link was
promoted. Nineteen now have a separately proven Windows semantic implementation;
`0x030C` and `0x0338` retain genuine semantic conflicts. The 99 missing Sapphire
declarations are documented gaps, not safe production edits, because complete
Windows layouts remain unproven.

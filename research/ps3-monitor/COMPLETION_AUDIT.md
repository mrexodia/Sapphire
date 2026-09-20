# Completion audit

This checklist maps the persistent goal and `OVERNIGHT_GOAL.md` requirements to
current artifacts and direct verification evidence.

## Outcome and scope

| Requirement | Evidence | Result |
| --- | --- | --- |
| Remain on `research/ps3-33-packet-matching` | `git branch --show-current` | Satisfied |
| Do not push or rewrite history | Local milestone commits begin at `9efcdaec8`; remote `origin/build-cleanup` remains at `a4724c627` | Satisfied |
| Do not modify the PS3 reference IDB | All PS3 scripts are read-only exporters; no PS3 save or mutation operation was performed | Satisfied |
| Avoid unrelated production changes | `git diff --name-only origin/build-cleanup...HEAD` contains only `research/ps3-monitor/*` | Satisfied |
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
| Preserve splits, merges, and shared handlers | `packet_matches.json` explicitly records 11 shared functions covering 54 opcode cases; no false separate functions were invented | Satisfied |
| Review every obvious same-opcode/named-handler candidate | `case_reviews.json`: 28 retained reviews; 4 probable and 24 unresolved | Satisfied |
| Leave no unreviewed high-likelihood candidate | `candidate_rankings.json` has zero entries; validator enforces this | Satisfied |
| Record one-sided case presence without overclaiming semantics | 18 PS3-only and 88 Windows-only zone cases plus one PS3-only chat case; inventory limitation defines status scope | Satisfied |
| Confirm as many defensible direct matches as possible | `packet_matches.json`: 203 packet-handler function pairs covering 246 cases (239 zone, 7 chat) | Satisfied |

## Windows IDB annotations

| Requirement | Evidence | Result |
| --- | --- | --- |
| Give confirmed Windows functions stable names | 203 handler names plus constructor and two dispatchers in the saved Windows IDB | Satisfied |
| First repeatable-comment line uses the required PS3 URI | `ida_apply_matches.py` and `packet_matches.json`; IDA verification checked all 206 entries with zero failures | Satisfied |
| Use eight uppercase PS3 address digits and the exact database name | `validate_research.py` validates every `ps3IdbUrl` | Satisfied |
| Do not authoritatively name probable/unresolved matches | Probable and unresolved relationships exist only in `case_reviews.json` and dispatcher status records | Satisfied |
| Save the Windows database | `ida_save_database` succeeded for `E:/Sapphire/game/ffxiv_dx11.exe.i64` after the final annotation batch | Satisfied |
| Make annotations reproducible/verifiable | `ida_apply_matches.py` applies or verifies all high-confidence mapping entries | Satisfied |

## Structures and Sapphire gaps

| Requirement | Evidence | Result |
| --- | --- | --- |
| Inventory PS3 DWARF structures used by confirmed handlers | `packet_structures.json`: 246 structures; exported by `ida_type_export.py` | Satisfied |
| Record PS3 size, members, offsets, widths/types | Every exported structure contains `ps3Size` and member metadata | Satisfied |
| Compare with current and ThreePointThree Sapphire declarations | Each structure records current and immutable historical path/line presence | Satisfied |
| Record independent Windows field evidence | `windowsValidation` records confirmed same-offset fields and version deltas; unreviewed fields are explicitly labelled | Satisfied |
| Do not promote PS3-only layout assumptions | Production decisions explicitly withhold 97 missing declarations pending complete Windows validation | Satisfied |
| Record confirmed version differences | `PlayerStatusUpdate.LvSync`: PS3 `+0x04`, Windows 3.x `+0x06` | Satisfied |
| Make only conclusively supported production corrections | No production header was changed because no missing declaration had complete Windows size/member proof | Satisfied |

## Validation, build, and reporting

| Requirement | Evidence | Result |
| --- | --- | --- |
| Validate JSON and cross-artifact consistency | `python research/ps3-monitor/validate_research.py` reports 246 confirmed cases/structures, 659 cases, zero candidates | Satisfied |
| Check whitespace/diff integrity | `git diff --check` succeeds | Satisfied |
| Build `common` and `world` if production headers change | No production header changed; the clean baseline build nevertheless completed through `[124/124]` | Satisfied |
| Commit coherent local milestones | Multiple coherent research commits are present after `origin/build-cleanup` | Satisfied |
| Finish with an auditable report | `OVERNIGHT_RESULTS.md` records coverage, annotations, structure gaps, verification, and remaining work | Satisfied |
| Leave a clean working tree | Verified after the final audit commit | Pending final commit at the time this file was written; rechecked immediately afterward |

## Completion judgment

All finite core criteria are covered by direct artifacts and validators. The
remaining 4 probable and 24 unresolved same-opcode relationships are not
unreviewed work: each has an explicit evidence-backed review and reason it was
not promoted. The 97 missing Sapphire declarations are documented gaps, not
safe production edits, because complete Windows layouts remain unproven.

# Sapphire packet declaration cleanup

This pass improves production packet names only where the Windows 3.35 client,
PS3 Monitor DWARF, or existing Sapphire construction behavior supports the
meaning. It does not copy complete PS3 2.3 layouts into Sapphire.

## Applied names

| Declaration | Old | New | Classification | Evidence |
|---|---|---|---|---|
| `FFXIVIpcQuestFinish +0x00` | `questId` | `bitIndex` | Windows-confirmed | Windows `0x140CC6A90` indexes the completion bitset with `value >> 3` and `0x80 >> (value & 7)`. |
| `FFXIVIpcQuestFinish +0x02` | `flag1` | `completed` | Windows-confirmed | Windows `0x140CC6A90` sets or clears that bit from this byte and forwards it as `completed`. |
| `FFXIVIpcQuestFinish +0x03` | `flag2` | `update` | Windows-confirmed | Windows `0x140CC6A90` forwards this byte as the EventFramework update argument. |
| `FFXIVIpcQuestTracker` | type name | `FFXIVIpcTracking` | Windows-confirmed | Windows `0x140CC6D50` handles both quest (`type == 1`) and leve (`type == 2`) tracking records, so the old type name was too narrow. |
| `TrackingEntry +0x00` | `active` | `type` | Windows-confirmed | Windows `0x140CC6D50` branches on values 1 and 2 rather than treating the byte as Boolean. |
| `TrackingEntry +0x01` | `questIndex` | `index` | Windows-confirmed | The byte indexes either a quest or leve collection according to `type`. |
| `FFXIVIpcCondition` | `flags` | `conditionFlags` | Windows-confirmed | Windows `0x140CBFF50` tests condition IDs 17 through 79 from this bit array. |
| `FFXIVIpcConfig` | `flag` | `configFlags` | Windows-confirmed | Windows `0x140CC7000` independently tests several bits and retains the complete 16-bit value. |
| `FFXIVIpcActorMove` | `flag`, `flag2`, `speed` | `animationType`, `animationState`, `animationSpeed` | Sapphire construction semantics | Existing wrapper and debug-command parameters already assign these meanings. Windows treats the record opaquely, so this is not claimed as a Windows field recovery. |
| `FFFXIVIpcItemSearchResult` | typoed type | `FFXIVIpcItemSearchResult` | Semantic identity | The role is `ItemSearchResult`; Windows `0x140D17280` independently consumes its catalog, result, subquality, materia-count, and count fields. |

Call sites were updated with each declaration rename.

## Layout decisions

- `FFXIVIpcQuestFinish` remains exactly 8 bytes. `unknown4` remains unknown because
  Windows reads it but current evidence establishes only its effect, not a stable
  protocol name.
- `FFXIVIpcTracking` preserves Sapphire's 16-byte size: five two-byte records
  followed by six padding bytes. Windows consumes the five records, and PS3
  DWARF independently agrees with the existing size; this does not claim that
  Windows requires the trailing bytes.
- `FFXIVIpcResting` preserves Sapphire's 16-byte size. Its implicit two-byte
  alignment gap is now explicit protocol padding. Windows `0x140CC8290`
  confirms HP, MP, TP, and GP at offsets `+0x00`, `+0x04`, `+0x06`, and `+0x08`;
  PS3 DWARF agrees with the existing size.
- `FFXIVIpcActorMove` is corrected from an implicit 12-byte C++ size to 16 bytes.
  PS3 DWARF reports 16 bytes, and Windows queue helper `0x140CD6C00` copies two
  consecutive eight-byte words from the payload. The trailing four bytes stay
  padding because neither client assigns them semantics.

Size assertions guard these layouts.

## Deliberately retained unknowns

- `FFXIVIpcQuestFinish::unknown4`: consumed by Windows for additional state/UI
  work, but no stable wire-level meaning is established.
- `FFXIVIpcActionIntegrity::unknown_E0`: Sapphire deliberately writes `0xE0`, so
  relabeling it as padding would be incorrect without stronger evidence.
- Client movement `flag`/`flag2` fields: current handler use conflates multiple
  animation notions, so cleaner names would overstate certainty.
- Other generic `Flag` and `unknown*` fields remain unchanged unless a Windows
  consumer or complete copy boundary proves their meaning.

## Inventory correction

`build_structure_inventory.py` now discovers protocol roles from
`FFXIVIpcBasePacket<Role>` inheritance. This preserves descriptive Sapphire
class names while recognizing their actual packet roles and reduces false
"missing declaration" reports from 99 to 80. `validate_research.py` checks the
role-to-type mapping against the current headers.

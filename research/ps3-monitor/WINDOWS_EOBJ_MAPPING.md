# EventObject timeline mapping: Windows 3.3 IDB

Mapped and annotated in `E:/Sapphire/game/ffxiv_dx11.exe.i64`.

| Role | PS3 Monitor | Windows 3.3 |
| --- | ---: | ---: |
| EventObject::SetSharedGroupTimelineState | `0x0097A850` | **`0x1409EC750`** |
| EventHandler::OnSetSharedGroupTimelineState | `0x0098D228` | `0x140652F30` |
| SharedGroupLayoutInstance::IsEnableGeneralTimeline | `0x004545AC` | `0x1402C0D00` |
| SharedGroupLayoutInstance::PlayGeneralTimeline | `0x00454580` | `0x1402EDF40` |
| SharedGroupLayoutInstance::PlayGeneralTimeline_Local | `0x004543E0` | `0x1402EA9D0` |

## Windows field locations (not copied from PS3)

- EventObject `+0x1A2`: **uint16 timelineState**. Setter disassembly:
  `movzx r13d, word ptr [rcx+1A2h]` followed by `mov [rcx+1A2h],dx`.
  PS3 stores the corresponding field at `+0x17A`.
- GameObject/EventObject `+0x108`: shared-group pointer.
- SharedGroupLayoutInstance `+0x168`: sixteen byte-sized general-purpose
  timeline MemberIDs. `IsEnableGeneralTimeline` checks `index < 16`, a nonempty
  child vector, and a nonzero byte at `this+0x168+index`. PS3 uses `+0xE4`.

The setter fallback has `shl ax,cl`, `test si,ax`, and a loop limit of `0x10`.
Set bits start enabled timelines not already playing; cleared bits stop playing
ones. With an owning event handler it calls vtable `+0x200`, passing the saved
old state and the new state. The base callback's `xor`, `not`, and `and` sequence
proves the same rising/falling masks as the PS3 callback. The rollback cleanup
also matches independently.

Windows has an additional fourth setter argument, forwarded to the virtual
handler as its fifth argument. Its complete contract remains unverified, so
it is named `unknownHandlerArg`. One Windows override at `0x140655120` handles
additional low-12-bit masks and delegates to the base callback; no subclass
identity was assigned. The original inferred return type is preserved rather
than assuming the PS3 void return proves the Windows source declaration.

## Independent packet anchors

- Previously matched CreateObject handler: `0x140CC5D20` (PS3 `0xAE3438`).
  Callsite `0x140CC5EE9` loads the low 16 bits of Args2 at payload `+0x28`,
  sets `checkLayoutReady=true`, clears the fourth argument and calls the setter.
- Previously matched Packet::Order: `0x140CC9600` (PS3 `0xAE9C48`).
  ActorControl `0x199` calls the setter at `0x140CD1B30` with arg0,
  `checkLayoutReady=false` and fourth argument zero.
- The same Order function's `0x19D` path synchronizes the 16 playback slots
  using **arg1**, then at `0x140CD1C2A` stores **arg0** in EventObject `+0x1A2`.
  Thus the PS3 playback-mask/stored-state distinction is confirmed for this
  Windows client too. ActorControl IDs are not outer IPC packet opcodes.

## IDB changes

Ten functions received semantic names and evidence comments. Besides the
five linked above, Windows-supported names were added for:

- `0x1402CD550`: SharedGroupLayoutInstance::IsPlayingGeneralTimeline
- `0x1402CD4A0`: SharedGroupLayoutInstance::StopGeneralTimeline
- `0x1409DE910`: GameObject::PlaySharedGroupTimeline
- `0x1409DE980`: GameObject::StopSharedGroupTimeline
- `0x1409DEA00`: GameObject::IsPlaySharedGroupTimeline

Two partial types, `Win335_EventObject_TimelineStateView` and
`Win335_SharedGroup_TimelineView`, make the field names readable without
asserting either complete class size. The setter has a typed self argument,
16-bit state argument and named readiness argument. Existing GameObject views,
packet types, executable bytes, and unrelated names were not changed.

Reapply with [`ida_apply_eobj_mapping.py`](ida_apply_eobj_mapping.py)'s
`apply(db)`. Address-bearing disassembly captured before renaming is in
[`windows_eobj_disassembly.txt`](windows_eobj_disassembly.txt).

# PS3 Gimmick handlers: client behavior and Sastasha examples

## Scope and conclusion

Inspected `E:/FFXIV-Monitor-PS3/game/ffxivgame.ppu.elf.i64` read-only in IDA,
including the PowerPC instructions, imported types, symbols and vtables.
Fresh sheet dumps came from `E:/FFXIV-Monitor-PS3/game/sqpack` using
`bin/tools/ps3_data_inspector.exe`. Placement IDs were joined against the existing
PS3 data graph, which was built from the same archive directory.

**Gimmick is an umbrella for authored interactive mechanisms, not one animation,
object class, or cutscene system.** The relevant `Client::Game::Gimmick` classes
are small event-handler implementations. They mainly provide standard client UI
for server-controlled interactions. A handler, an EObj, an LGB placement, a
shared-group timeline, and a cutscene are different things with different IDs.

**The GimmickAccessor `Type` column is real.** The imported row type calls it
`Type`, the actual EXH declares an i32 column at byte offset 12, and instructions
at `0xB45508–0xB45548` load and branch on it. What remains unknown is the original
complete enum naming and server-side semantics of every value, not the existence
of this discriminator.

Evidence export: `build/ps3-gimmick-code.json` contains pseudocode and addressed
instruction listings for 33 functions. Fresh sheet dumps are
`build/ps3-Gimmick{Accessor,Rect,Bill,YesNo}.json` and
`build/gimmick-{EObj,InstanceContent,LogMessage,Cutscene}.json`.
The follow-up range/cinematic investigation is exported with addressed
instructions in `build/ps3-gimmick-trigger-code.json` (9 functions).

## Handler IDs and dispatch

| Class | Handler type/high 16 bits | Handler ID | Sheet/root ID |
| --- | ---: | --- | ---: |
| GimmickAccessor | 15 / 0x000F | `0x000F0000 | rowId` | GimmickAccessor / 120 |
| GimmickBill | 16 / 0x0010 | `0x00100000 | rowId` | GimmickBill / 116 |
| GimmickRect | 17 / 0x0011 | `0x00110000 | rowId` | GimmickRect / 128 |

Creators: `0x149A30C`, `0x149A38C`, `0x149A424`. Accessor and Rect initialize
from the low 16 bits of the handler ID (`0xB45440`, `0xB45B50`). Bill loads
its text on interaction (`0xB459A4`), rather than preloading it at initialization.
These are not EObj row IDs; EObj has a separate EventHandler field.

`GimmickEventHandler::OnPlayEventScene`, `0xB44D74`, dispatches:

- scene 1: `OnGimmickTalk(args, count)`;
- scene 2: `OnGimmickRectIn()`;
- scene 3: `OnGimmickRectOut()`;
- other scenes: ordinary EventHandler fallback, which returns an empty result.

These numbers are **event scene IDs**, not cutscene IDs. Confirmed constants are
at `0x183A024`, `0x183A026`, `0x183A028` and virtual-call offsets are
`0x2CC`, `0x2D0`, `0x2D4`.

Ordinary object interaction enters `OnTalkEvent` (`0xB44C74`), which sets rollback
policy and calls the base handler. It only starts scene 1 locally if the event
state has the client-event bit (`flags & 2`). The normal inherited
`IsClientEvent` returns false (`0x98E3C8`), so do not assume clicking one of these
objects unconditionally runs scene 1 locally. The server can request the scene.

## GimmickAccessor row and Type behavior

Physical EXH column order is **Type, Param0, Param1, Param2**, but fixed-byte
layout is:

```cpp
// Row data, not the C++ handler object's layout.
struct GimmickAccessorRow {
    uint32_t Param0; // +0x00
    uint32_t Param1; // +0x04
    uint32_t Param2; // +0x08
    int32_t  Type;   // +0x0C
};
```

`OnSheetDataReady`, `0xB45364`, copies these words into handler offsets
`+0xF8`, `+0xFC`, `+0x100`, `+0x104`, then marks the handler initialized.

The exact client implementation of scene 1 (`0xB454EC`) is:

| Type | Client action when OnGimmickTalk is called |
| ---: | --- |
| 2, 3, 5, 6 | Load `GimmickYesNo[Param0]`, open the yes/no dialog |
| 8 | Ask the current InstanceContentDirector to construct a selection menu using the accessor row ID; open SelectString |
| 0, 1, 4, 7, other values | Debug trap, followed by empty ReturnEventScene if execution continues past the trap |

**The trap cases do not mean those rows are invalid.** The data contains many
Type 1 and Type 4 rows used by real dungeon objects. It means they do not have a
supported client *talk scene* in this class. The client executable alone cannot
recover the corresponding server callback logic.

Types 2/3/5/6 share the same UI code; their differences are not implemented here.
Only Param0 is consumed by this client's talk function. Param1/Param2 must remain
conditional parameters, not universal foreign keys. Sastasha data strongly
supports LogMessage IDs in Type 3 Param1 and Type 4 Param0, but those lookups are
not executed by this function.

### Practical interpretations of individual Type values

These are descriptive categories, **not recovered official enum names**.
Client branches are proven; categories beyond those branches are inferred from
sheet parameters, object assignments and dialog/message text. Counts cover the
389 rows in this PS3 dump, not every game version.

| Type | Rows | Evidence-qualified meaning |
| ---: | ---: | --- |
| 0 | 5 | Empty/unused-looking rows: all parameters zero. No supported local talk scene. |
| 1 | 218 | Direct server-handled interaction, with no supported local talk scene; includes Sastasha's collectible keys. Not exclusively a key type. |
| 2 | 84 | Yes/no interaction: Param0 selects GimmickYesNo; includes the coral switches. |
| 3 | 33 | Gated yes/no interaction in observed objects, notably locked doors; Param0 is the confirmation and Param1 matches refusal LogMessage IDs. The gate is not implemented in this client's dialog code. |
| 4 | 12 | Server-handled interaction with a message parameter in observed rows; includes the inactive switch and ripples. This does not imply that displaying text is its only effect. |
| 5 | 26 | Shortcut/teleporter-style confirmation in observed objects. Locally identical to Types 2/3/6. |
| 6 | 4 | Exit/area-transition confirmation in observed objects. Locally identical to Types 2/3/5. |
| 7 | 1 | Engraving-related message interaction: row 191 has Param0 2076, whose LogMessage says the engraving is too worn to decipher. No supported local talk scene. |
| 8 | 6 | Director-generated selection menu, directly proven; rows 196–201 use Qarn's override. |

In particular, the client cannot distinguish the full server semantics of
Types 2/3/5/6: it only draws their common confirmation and returns the answer.

The shared yes/no loader (`0xB44AB0`) reads three strings from GimmickYesNo
(sheet 129): message, yes label, no label. It opens SelectYesNo with the default
set to yes. Closing the dialog returns the selected integer as one scene result
(`0xB44E98`). SelectString does the same (`0xB44EE4`). The resulting scene task
enters the ordinary ReturnEventScene machinery (`0x98B94C`). This is the client
answer to the interaction, not the implementation of unlocking/teleporting/etc.

Type 8's virtual call at `0xB45610–0xB45628`, director vtable `+0x300`, resolves
to `OnCreateAccessorMenu`. Qarn overrides it at `0xB20AAC`, building choices from
its synchronized variables. Accessor IDs 196–201 have Type 8; 200/201 receive
special filtering in that Qarn override. This is a concrete nontrivial gimmick:
a dungeon-specific menu built by the content director, not a generic model type.

## GimmickBill

`OnGimmickTalk`, `0xB459A4`, loads `GimmickBill[handlerId & 0xFFFF]`.
`OnSheetDataReady`, `0xB45760`, reads its message string and opens a Talk window
with no talker, shape 4, log kind 61. Closing it returns an empty scene result
(`0xB44E64`). This is a readable sign/note/message handler, not necessarily a
physical billboard.

## GimmickRect

Its row has five meaningful columns and a 16-byte fixed layout:

```cpp
struct GimmickRectRow {
    uint32_t LayoutId;  // +0x00
    uint32_t Param0;    // +0x04: conditional entry parameter
    uint32_t Param1;    // +0x08: conditional exit parameter
    uint8_t TriggerIn;  // +0x0C
    uint8_t TriggerOut; // +0x0D
    uint8_t padding[2];
};
```

Physical column order is **LayoutId, TriggerIn, TriggerOut, Param0, Param1**.
Loading at `0xB45A44` copies the row, then sends
`EventHandlerCommand(0x80000000, 0, 0)`. Unlike Accessor, it does not immediately
mark itself initialized: it waits for the server initialization order.

`EventHandlerCommand`, `0x98EE0C`, sends game command `0x328` with arguments
`handlerId, command, arg1, arg2`. Do not confuse that command ID with an IPC
opcode.

Server orders dispatch at `0xB44F30`:

| Order arg0 | Callback |
| --- | --- |
| `0x80000000` | OnRecieveInitParameter(arg1, arg2) |
| `0x80000001` | OnRecieveEnabled, only if initialized |
| `0x80000002` | OnRecieveDisabled, only if initialized |
| below `0x80000000` | OnRecieveServerCommand; base implementation is empty |

The original symbol spells **Recieve** this way.

Rect starts with `m_enable=false`. Init enables it if its first argument equals
1 and then marks it initialized (`0xB45D64`). Enable/disable update the flag and
invalidate holder visibility (`0xB45DC4`, `0xB45E08`). `IsEventVisible`
(`0xB45F4C`) returns that flag. This is proven visibility behavior; it is not
proof that the same flag itself registers or removes collision geometry.

For scene 2, `OnGimmickRectIn` (`0xB45BFC`) only acts on TriggerIn 2 or 3,
loading GimmickYesNo[Param0]. For scene 3, `OnGimmickRectOut` (`0xB45CB0`) only
acts on TriggerOut 2 or 3, loading GimmickYesNo[Param1]. Byte loads at
`0xB45C18` and `0xB45CCC` prove these are separate trigger bytes, not one
32-bit Type field. Other trigger values have **no local UI action here**;
there is no direct cutscene call in either method.

Type 3 has a special two-stage close callback (`0xB45E4C`): result 0 opens
GimmickYesNo row 6 and changes the active type to 2; a nonzero result returns
an empty result. Type 2 returns the selected result normally. The archive text
identifies row 6 as the named-content leave confirmation.

## Concrete Sastasha data

| EObj / object | Handler ID | Row Type/parameters or text |
| --- | --- | --- |
| 2000213/214/215: blue/red/green coral | `0xF0017/18/19` | Accessor 23/24/25: Type 2, Param0 12: “You find a switch. Press it?” |
| 2000216: inconspicuous switch | `0xF001A` | Accessor 26: Type 4, Param0 2033; LogMessage 2033 says it does not function at this time |
| 2000227: captain's quarters | `0xF001C` | Accessor 28: Type 3, Param0 44: unlock confirmation; Param1 2068: “The door is locked tight.” |
| 2000231: Waverider Gate | `0xF0020` | Accessor 32: Type 3, Param0 45, Param1 2068 |
| 2000232: the Hole | `0xF0021` | Accessor 33: Type 3, Param0 46, Param1 2068 |
| 2000250/255/256: dungeon keys | `0xF0022/27/28` | Accessor 34/39/40: Type 1, parameters zero |
| 2000405–408: unnatural ripples | `0xF0043–46` | Accessor 67–70: Type 4, Param0 2039: “There is nothing out of the ordinary.” |
| 2000700: shortcut | `0xF004A` | Accessor 74: Type 5, Param0 36: “Utilize the shortcut?” |
| 2000139: exit | `0xF0005` | Accessor 5: Type 6, Param0 8: “Leave duty?” |
| 2000212/1548/1549: bloody memos | `0x100009/A/B` | Bill 9/10/11: blue/red/green clues |

LogMessage rows 2039–2042 form a contiguous Sastasha interaction sequence: “nothing out of the ordinary,” bubbles forming, “The evil presence has gone,” and an enemy appearing. Accessors 67–70 identify 2039 directly and are the four unnatural ripples. The graph therefore exposes a `content_workflow_candidate` from those accessors to LogMessage 2041 using the observed `Param0 + 2` position in that sequence. This is a navigation hypothesis, **not** proof that the client performs addition. Disassembly shows that the retail server can supply a LogMessage ID directly, unchanged, through `EventPacket::ReceiveLogMessage` (`0xADC8D0`) and `EventFramework::OnLogMessage` (`0xA59D98`).

### Sastasha ranges and candidate cinematic trigger

The extracted `bg/ffxiv/sea_s1/dun/s1d1/level/planmap.lgb`
(`build/gimmick-sastasha-planmap.lgb`) supplies these placements. Positions and
scales below are decoded directly from the big-endian InstanceObject headers;
scale is the authored transform, not a claim about final collision dimensions.

| Source | Handler | EventRange LayoutId | Position (x, y, z) | Scale (x, y, z) |
| --- | --- | ---: | --- | --- |
| InstanceContent 4 EntranceRect | Shared Rect `0x110001` is created when this field is nonzero | 3283219 | (373.248, 46.729, -225.020) | (4, 3, 1) |
| GimmickRect 27 | `0x11001B` | 4069552 | (-301.878, 12.405, 280.974) | (10, 10, 2) |
| GimmickRect 28 | `0x11001C` | 4138412 | (-39.113, 28.156, 125.326) | (2.106, 9.727, 6.083) |

All three placements are **EventRange assets, type 49**, not GimmickRange.
Rows 27/28 both have TriggerIn 1, TriggerOut 0 and zero parameters. TriggerIn 1
has no local confirmation action (`0xB45C18–0xB45C28`); neither row contains a
cutscene ID.

Rect 27 is a **plausible final-boss approach trigger**: its range sits near
EObj 2001508/2001509, the final boss wall/line placements 4036045/4036046 at
approximately (-304, 5.6, 276) and (-305, 5.5, 276). Their identities and
positions agree with `src/scripts/instances/dungeons/Sastasha.cpp`.
Rect 28 is elsewhere, in layer `LVD_gimmick_02`, which also contains the Hole
placement 3281161. These spatial observations do **not** prove a cutscene
mapping or an official trigger purpose. The Sapphire script is a reconstruction,
not authoritative retail server logic.

### Entrance/exit confirmation is not the opening cinematic

Sastasha InstanceContent row 4 has EntranceRect **3283219** and StartCutscene
**174**. The director creates shared **GimmickRect handler `0x110001`** when
EntranceRect is nonzero: instructions `0xB1C218–0xB1C234` test the field and build
the handler ID. This proves the creation condition, not a cinematic callback
from that handler.

Rect row 1 has LayoutId 0, TriggerIn 3, TriggerOut 0, Param0 8 and Param1 0.
Its client behavior is an **exit confirmation**: GimmickYesNo 8 asks whether to
leave duty; the Type-3 close path can then open the named-content leave
confirmation in row 6. It should not be labeled an opening-cutscene trigger.
The content-specific entrance placement is supplied by InstanceContent, rather
than by this shared row's zero LayoutId; the precise runtime range binding is
not established by the handler-creation call alone.

### Proven cinematic dispatch and the missing server edge

The PS3 client has distinct range-event and cinematic-dispatch paths:

- Generic registered EventRange entry/exit is processed by
  `EventFramework::OnWithinRange`/`OnOutsideRange` (`0xA55460`/`0xA55D70`). After
  listener/permission checks, the non-client-event path sends packet types
  `0x1C4`/`0x1C5` containing the placement ID, selected handler ID and player
  position (`0xA55BE0–0xA55C20`, `0xA56434–0xA56474`). This is conditional on
  registration and event state, **not proof that these specific Rects are
  registered through this path**.
- `EventPacket::ReceivePlayEventScene` (`0xADC454`) forwards the server-provided
  handler ID, event scene ID, flags and arguments to EventFramework.
- `EventFramework::playEventScene` (`0xA586D0`) chooses a director when handler
  bit `0x80000000` is set; otherwise it looks up an ordinary event handler
  (`0xA5873C–0xA5876C`). It does not translate a Rect row into a cutscene.
- `InstanceContentDirector::OnPlayEventScene` (`0xB1CEC4`) handles scene 1 by
  loading StartCutscene and passing it as one Lua argument
  (`0xB1CFA4–0xB1CFC4`). Scene 3 forwards the supplied cinematic arguments and
  updates skip/music bookkeeping.
- `LuaEventHandler::OnPlayEventScene` (`0x9BF7F0`) selects `OnScene%05u`.
  The recovered `game_script/system/InstanceContentDirector.lua` implements
  OnScene00001 and OnScene00003 using PlayCutscene and the cutscene API.

Consequently, the defensible candidate sequence is:

```text
GimmickRect 27 -> EventRange placement 4069552
  ... server-side range/progression decision (unrecovered) ...
server PlayEventScene addressed to InstanceContentDirector
  -> director scene 3 -> Lua PlayCutscene(supplied cutsceneId)
```

The first association is sheet/placement evidence, and the final dispatch is
client-code evidence. **The middle edge and selected cutscene ID are not proven.**
In particular, Rect scene 3 means range exit in GimmickEventHandler, whereas
director scene 3 means a cinematic: the handler ID determines the meaning.

The Cutscene sheet contains the following Sastasha resources, all extracted
successfully as `build/gimmick-dunsea1d{110,120,130}.cutb`:

| Cutscene | Sheet path | Evidence |
| ---: | --- | --- |
| 174 | `ffxiv/dunsea/dunsea1d110/dunsea1d110` | Explicit InstanceContent 4 StartCutscene; opening cinematic. |
| 175 | `ffxiv/dunsea/dunsea1d120/dunsea1d120` | Resource strings include demihuman d1007 animation and menace assets. |
| 176 | `ffxiv/dunsea/dunsea1d130/dunsea1d130` | Resource strings include demihuman d1007 animation and ouch assets. |

None of these three raw CUTB files contains the three range placement IDs as
literal 32-bit big- or little-endian words. This negative scan is not proof
against an indirect association; resource strings also cannot establish the
server trigger. No recovered table or client branch assigns Rect 27/28 to
Cutscene 175/176. A retail server script or trace showing range notification,
handler IDs and the subsequent director scene arguments is needed to prove it.

## Related uses of the word, not interchangeable systems

- `GimmickRangeLayoutInstance`: an authored layout range. Imported
  `GimmickRangeInstanceObject_t::eGimmickType` values are Fishing=1, Content=2,
  Room=3, with GimmickKey, RoomUseAttribute, GroupId, EnabledInDead fields.
  These are **not** the Accessor Type values. Layout shape handling supports
  box/sphere/cylinder/board (`0x4AFD5C`).
- `GimmickJump`: scripted movement/jump data, used by Character and
  MoveController; not the accessor dialog discriminator.
- Graphics `GimmickParameter`: equipment/helmet movement parameter data;
  unrelated to these event handlers.
- Quest `GetGimmickState`/PlayQuestGimmickReaction: quest/object state and
  reaction APIs; do not equate their state numbers with Accessor Type.

## Practical Sapphire implications and remaining limits

Use handler-ID decoding and conditional parameter interpretation. For supported
Accessor UI interactions, the server can request scene 1 and consume the returned
choice. Implement the dungeon effect (keys, doors, shortcut destinations,
progression and cinematics) separately. Use Bill for readable text; model Rect
initialization and enable orders rather than treating every Rect as an always-on
cutscene.

Confirmed locally: class/type identity, row layouts, supported client branches,
UI/results, Rect command/visibility behavior, Qarn menu ownership, and Sastasha
sheet/placement examples. Not recovered: official Accessor/Trigger enum names,
complete server meanings of all parameters, exact server range policy, or the
full Sastasha boss-trigger/cutscene mapping. No production code or IDB was modified.

# Technical starting point: monitor Lua and timeline runtime

## SDAT correction, independently verified

The earlier description of this corpus's SDAT payloads as encrypted was wrong.
SDAT is a container; encryption/integrity capabilities are not proof that a
particular payload is encrypted.

Both local files use flags **0x8100003C**, a **0x4000** block size and an
interleaved **0x20-byte metadata / data-block** layout. Removing the framing
without keys yielded valid SqPack streams and successfully decoded every
indexed standard record:

| File under `sqpack/ffxiv` | Physical bytes | Logical bytes | Validated records |
| --- | ---: | ---: | ---: |
| `0b0000.ps3.d.dat0.sdat` | `0x65C9F0` | `0x659600` | 1,934 |
| `050000.ps3.d.dat0.sdat` | `0x14D290` | `0x14C700` | 283 |

The script archive contains 1,932 Lua 5.1 chunks, one Lua source-text record
and one `placeholder` record. The shader records include `ShPk` / `ShCd`
payloads, placeholders and other records; they were decompressed, not fully
semantically decoded.

For this exact framing profile, logical byte offset `x` maps to:

```text
physical = 0x120 + (x / 0x4000) * 0x4020 + (x % 0x4000)
```

Division is integer division. Reads crossing logical blocks must skip metadata;
index/DAT offsets refer to the **logical** SqPack stream, not the physical SDAT.
Stop at the declared logical length and ignore trailing physical padding.
This formula is not a general EDAT/SDAT reader. Metadata authentication was
not verified; no decryption is implemented or needed for these local payloads.

The C++ inspector/Toolkit DAT backend does **not yet** use an SDAT logical
reader. The Python helper below handles only this observed plaintext profile.
Historical inventory JSON's `encrypted_sdat_present` key means only “the
`.sdat` filename exists”; it must not be used as an encryption classification.

## First target: Lua chunks and the event API, not rendering

All 1,932 bytecode records parsed completely using the stock Lua 5.1 prototype
serialization grammar. Their common header is:

```text
1B 4C 75 61  51 00 00 04 04 04 08 00
magic        │  │  │  │  │  │  │  └─ nonintegral lua_Number
             │  │  │  │  │  │  └──── 8-byte numbers
             │  │  │  │  │  └─────── 4-byte instruction words
             │  │  │  │  └────────── 4-byte size_t
             │  │  │  └───────────── 4-byte int
             │  │  └──────────────── big-endian
             │  └─────────────────── format 0
             └────────────────────── Lua 5.1
```

A native Windows `luac` commonly expects a different byte order and size_t;
its rejecting these chunks is not evidence of encryption or a custom opcode
format. Prefer an endian-aware parser/disassembler. Consider decompilation
only after validating the prototype/constant/instruction representation.

The observed corpus has:

- **37,185 prototypes**, including nested functions.
- **1,309,978 32-bit code words** (not a runtime execution count).
- **35,253 prototypes with line information**.
- **156,886 local-variable entries**.
- Zero serialized upvalue-name entries.

Top-level source-name fields are all `=(luac)`, but the child prototypes retain
3,864 original source names, two per chunk, such as
`@Transport/Aetheryte.cli.lua` and `@Transport/Aetheryte.cmn.lua`.
The supplied PathList now names every compiled Lua resource by matching both
index hashes; see [Lua filename recovery](LUA_FILENAME_RECOVERY.md).
Local-variable/debug tables and method/scene constants also make this much
more informative than fully stripped bytecode. The source-text record
provides an especially approachable sample: class `Gld10000`,
`OnScene00100(player, target)`, `target:Talk(...)`, and quest-offer calls.

### Format references

Use the actual [Lua 5.1 source](https://www.lua.org/source/5.1/):

- `lundump.c`: reading headers, prototypes, constants and debug tables.
- `ldump.c`: serialization rules, especially string lengths/NULs.
- `lobject.h`: Proto, constants, locals and upvalues.
- `lopcodes.h` / `lopcodes.c`: ABC, ABx, AsBx and opcode names.
- `lvm.c`: execution semantics; `ldo.c`: calls, yielding and resumption.

For the outer wrapper, consult an EDAT/SDAT implementation such as RPCS3's
`rpcs3/Crypto/unedat.cpp`, but keep full container support separate from the
small observed-profile reader used here.

## Most informative runtime anchors

These addresses are exported **PS3 Monitor symbol anchors**, not a claim that
all listed functions already form a disassembly-verified call chain:

| Anchor | Address | Investigate |
| --- | --- | --- |
| LuaScriptLoader<LuaEventHandler>::LoadLuaScript | `0x0147532C` | Script naming/path construction, resource requests and load completion. |
| Common::Lua::LuaState::LoadBuffer | `0x00221AB8` | Boundary between a loaded resource and the Lua VM. |
| LuaEventHandler::DefineLuaClass | `0x009942DC` | Lua-visible class methods and native bindings. |
| LuaEventHandler::OnPlayEventScene | `0x009BF7F0` | Scene entry selection and arguments. |
| LuaEventHandler::ResumeLuaThread | `0x009C0620` | Suspended Lua execution and completion callbacks. |
| LuaEventHandler::OnResumeEventScene (numeric args) | `0x009C2E18` | Network-driven resumption. |
| EventSceneModule::PlayActionTimeline(lua_State*) | `0x009D4B30` | Lua-to-native action-timeline entry point. |
| EventSceneModule::WaitForActionTimeline(lua_State*) | `0x009D4BE8` | Waiting/completion contract. |
| EventSceneModule::PlaySharedGroupTimeline(lua_State*) | `0x009D4A1C` | Lua arguments and shared-group dispatch. |
| EventSceneModuleImplBase::PlaySharedGroupTimelineImpl | `0x009A7FE0` | Native implementation behind the Lua wrapper. |

Static Lua 5.1 `OP_SELF` interpretation finds many references to `Talk`,
`PlayActionTimeline`, `Wait`, `LookAt` and `WaitForActionTimeline`. These are
static operands, not execution frequencies or complete reachable-call proofs.

There are only **seven** `PlaySharedGroupTimeline` operands in **four chunks**:

| Directory hash | Filename hash | Likely class identity from globals | Operands |
| --- | --- | --- | ---: |
| `06bc4074` | `c151e0b5` | CmnDefRetainerCall | 2 |
| `5e9a31c1` | `79eaa126` | Aetheryte | 1 |
| `71bb70e2` | `0472d814` | CmnDefMateriaSlot | 3 |
| `71bb70e2` | `26544b7f` | CmnDefBeautySalon | 1 |

Global names were identity leads at this stage. The later
[PathList pass](LUA_FILENAME_RECOVERY.md) recovered the actual archive resource
names for all compiled chunks, independently of those globals. These four
chunks are still not proof that the Sastasha grates themselves use Lua for
their timeline transitions.

**Important:** a Lua API named `PlaySharedGroupTimeline` need not have the
same argument contract as ActorControl 0x19D. The native GameObject wrapper
uses a slot index/time; the packet path we already mapped uses masks. Trace
the binding before treating Lua numbers as mask flags or MemberIDs.

## Second target: timeline execution, not art formats

Keep three systems distinct:

1. Event Lua/coroutines: scene control, interactions, waits and callbacks.
2. Client scheduler timelines: action or shared-group clips/tracks and their
   native side effects, loading, timing and cancellation.
3. Sapphire encounter timelines: server gameplay orchestration; not the same
   serialization format or runtime as either client system.

The monitor's useful types include:

- `Common::DevEnv::Generated::TimelineBinaryTrack`
- `TimelineBinaryClipBase`, `ClipMotionTimelineBinary`, `ClipSGTimelineBinary`
- `Client::System::Scheduler::Resource::TimelineClipBinaryTable`
- `Client::System::Scheduler::Base::SchedulerTimeline`
- `Client::System::Scheduler::Base::TimelineControler` (original spelling)
- `Client::Game::Control::ActionTimelineSequencer`

Start with one known timeline, enumerate track/clip types, and trace the native
clip factory/dispatch switch. Recover timing units, start/stop/loop rules,
completion notification and rollback behavior before trying to decode every
format. Use SGB settings only as the entry mapping; rendering models/textures
is not necessary to understand these scheduling contracts.

## A practical first milestone

Build a small technical catalog with:

```text
script hash pair → prototype/PC → scene/method operand
Lua-visible API name → C++ binding → argument/return/yield contract
one scene start → wait condition → completion event → coroutine resume
one timeline selection → native clip dispatch → completion/stop behavior
```

Then verify one vertical slice end to end. This will explain substantially
more of how the client works than a complete list of asset filenames.

## Reproduce and extract without executing scripts

```sh
python research/ps3-monitor/inspect_monitor_scripts.py E:/FFXIV-Monitor-PS3/game/sqpack --output build/ps3-script-runtime.json

# Optional: write raw chunks/source using hash-pair filenames.
python research/ps3-monitor/inspect_monitor_scripts.py E:/FFXIV-Monitor-PS3/game/sqpack --output build/ps3-script-runtime.json --extract build/ps3-lua
```

The full ledger stays in `build/` and records archive hashes, logical record
offsets, per-script hashes, prototype/debug counts, scene-name constants and
static global/method operands. It does not execute Lua or decompile scripts,
authenticate SDAT metadata, or expose universal ID/argument meanings.

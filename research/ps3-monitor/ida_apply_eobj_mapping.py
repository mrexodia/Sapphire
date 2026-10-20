"""Apply the disassembly-verified EventObject timeline mapping to the 3.3 Windows IDB.

Run apply(db) in ida_execute_python. Types are partial Windows-known-field views,
not PS3 structure copies. No packet definitions, object sizes or bytes are changed.
"""

DECLARATIONS = r"""
#pragma pack(push, 1)
struct Win335_SharedGroup_TimelineView {
  unsigned char _unknown_0000[0x168];
  unsigned char generalPurposeTimelineIds[16];
};
struct Win335_EventObject_TimelineStateView {
  unsigned char _unknown_0000[0x108];
  Win335_SharedGroup_TimelineView *sharedGroup;
  unsigned char _unknown_0110[0x92];
  unsigned short timelineState;
};
#pragma pack(pop)
"""

FUNCTIONS = [
    (0x1409EC750, "Client__Game__Object__EventObject__SetSharedGroupTimelineState", 0x97A850,
     "mov [rcx+1A2h],dx stores a 16-bit mask; sharedGroup is read at +108h. "
     "Loops over 16 slots using shl ax,cl/test si,ax; starts/stops general timelines. "
     "Invokes an owning handler at vtable +200h with old/new state. "
     "Windows has a fourth handler argument forwarded unchanged; its complete contract and return value are unverified."),
    (0x140652F30, "Client__Game__Event__EventHandler__OnSetSharedGroupTimelineState", 0x98D228,
     "xor r8w,r9w plus and/not proves rising=(old^new)&new and falling=(old^new)&~new. "
     "16-slot general timeline loop and scene rollback-flag cleanup independently match PS3. "
     "The Windows override at 0x140655120 adds mask handling; no subclass identity is asserted."),
    (0x1402C0D00, "Client__LayoutEngine__Group__SharedGroupLayoutInstance__IsEnableGeneralTimeline", 0x4545AC,
     "index <16; child vector nonempty; byte [this+168h+index] nonzero. "
     "Windows general-purpose timeline MemberID array is +168h, NOT PS3 +E4h."),
    (0x1402EDF40, "Client__LayoutEngine__Group__SharedGroupLayoutInstance__PlayGeneralTimeline", 0x454580,
     "Wrapper into PlayGeneralTimeline_Local with the extra control argument cleared."),
    (0x1402EA9D0, "Client__LayoutEngine__Group__SharedGroupLayoutInstance__PlayGeneralTimeline_Local", 0x4543E0,
     "Checks index <16; selects MemberID from +168h array, resolves hierarchical ID, "
     "then plays a timeline. Defers index/time in the play-call stack while child nodes are absent. "
     "Windows also checks a MemberID predicate before playback; not claimed byte-for-byte identical to PS3."),
    (0x1402CD550, "Client__LayoutEngine__Group__SharedGroupLayoutInstance__IsPlayingGeneralTimeline", None,
     "Checks a general-purpose slot, resolves its hierarchical MemberID, and queries scheduler playback state."),
    (0x1402CD4A0, "Client__LayoutEngine__Group__SharedGroupLayoutInstance__StopGeneralTimeline", None,
     "Checks a general-purpose slot, resolves its hierarchical MemberID, and stops the scheduler timeline."),
    (0x1409DE910, "Client__Game__Object__GameObject__PlaySharedGroupTimeline", None,
     "GameObject wrapper: sharedGroup +108h, enabled slot check, then PlayGeneralTimeline(index,time). "
     "ActorControl 19Ah uses this single-index API; 19Dh calls it for each set mask bit."),
    (0x1409DE980, "Client__Game__Object__GameObject__StopSharedGroupTimeline", None,
     "GameObject wrapper: sharedGroup +108h, enabled/playing checks, then StopGeneralTimeline."),
    (0x1409DEA00, "Client__Game__Object__GameObject__IsPlaySharedGroupTimeline", None,
     "GameObject wrapper: sharedGroup +108h, enabled slot check, then IsPlayingGeneralTimeline."),
]


def apply(db):
    import ida_typeinf
    from ida_domain.types import TypeFormattingFlags
    errors = db.types.parse_declarations(ida_typeinf.get_idati(), DECLARATIONS,
                                         TypeFormattingFlags.HTI_DCL | TypeFormattingFlags.HTI_PAKDEF)
    if errors:
        raise RuntimeError(f"Type parse errors: {errors}")
    event = db.types.get_by_name("Win335_EventObject_TimelineStateView")
    group = db.types.get_by_name("Win335_SharedGroup_TimelineView")
    event_members = {m.name: (m.offset, m.size) for m in db.types.get_udt_members(event)}
    group_members = {m.name: (m.offset, m.size) for m in db.types.get_udt_members(group)}
    assert event_members["sharedGroup"] == (0x108, 8)
    assert event_members["timelineState"] == (0x1A2, 2)
    assert group_members["generalPurposeTimelineIds"] == (0x168, 16)
    db.types.set_comment(event, "Partial 3.3 Windows view only. +108h pointer / +1A2h uint16 confirmed in setter and packet paths. Not a complete object size.")
    db.types.set_comment(group, "Partial 3.3 Windows view only. +168h 16-byte general-purpose timeline MemberID array, proven by enabled/play/stop/query routines. Not a complete object size.")
    for ea, name, ps3, evidence in FUNCTIONS:
        f = db.functions.get_at(ea)
        if f is None or f.start_ea != ea:
            raise RuntimeError(f"No function at {ea:X}")
        old_name = db.functions.get_name(f)
        if old_name != name and not old_name.startswith(("sub_", "j_sub_")):
            raise RuntimeError(f"Refusing to replace existing semantic name {old_name}")
        if not db.names.set_name(ea, name):
            raise RuntimeError(f"Rename failed at {ea:X}")
        prefix = f"PS3 Monitor: idb://ffxivgame.ppu.elf.i64:{ps3:08X}\n" if ps3 else "Windows timeline helper verified through the PS3-linked EventObject setter / packet paths.\n"
        if not db.functions.set_comment(f, prefix + evidence):
            raise RuntimeError(f"Comment failed at {ea:X}")
    # Preserve the pre-existing inferred return type and fourth argument width:
    # a decompiler return value is not proof of the original C++ return contract.
    prototype = "__int64 __fastcall f(Win335_EventObject_TimelineStateView *self, unsigned short state, bool checkLayoutReady, unsigned __int64 unknownHandlerArg);"
    if not db.functions.apply_declaration(db.functions.get_at(0x1409EC750), prototype):
        raise RuntimeError("Setter prototype application failed")
    db.comments.set_at(0x140CC5EE9, "EventObject initial timeline state from CreateObject Args2 (payload +28h, low 16 bits). Windows +1A2h; PS3 +17Ah.")
    db.comments.set_at(0x140CD1B30, "ActorControl 0199h: arg0 -> EventObject::SetSharedGroupTimelineState; checkLayoutReady=false, extra handler arg=0.")
    db.comments.set_at(0x140CD1C2A, "ActorControl 019Dh: store arg0's low 16 bits at EventObject +1A2h after synchronizing playback with arg1's mask. The two arguments need not be equal.")
    return {"renamed_functions": len(FUNCTIONS), "event_timeline_state_offset": "0x1A2", "shared_group_slot_array_offset": "0x168"}

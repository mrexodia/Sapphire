"""Read-only asset/schema metadata export from the PS3 Monitor IDB.

Run in IDA/ida_execute_python with the ida-domain `db` already available:
    export(db, 'C:/CodeBlocks/Sapphire/build/ps3-monitor-metadata.json')

This exports imported IDB types, NOT ABI-portable C++ declarations or verified
file layouts. Stub/gap-only types and alternate DWARF views are kept as-is.
"""
from pathlib import Path
import json
import re


def type_record(db, t):
    size = t.get_size()
    out = {"name": t.get_type_name(), "size": size if size < 0xFFFFFFFF else None,
           "declaration": str(t),
           "kind": "enum" if t.is_enum() else "udt" if t.is_udt() else "other"}
    if t.is_enum():
        out["members"] = [{"name": m.name, "value": m.value} for m in db.types.get_enum_members(t)]
    elif t.is_udt():
        out["members"] = [
            {"name": m.name, "offset": m.offset, "size": m.size, "type": str(m.type),
             "bitfield": m.is_bitfield, "bit_offset": m.bit_offset, "bit_size": m.bit_size}
            for m in db.types.get_udt_members(t)
        ]
    return out


def export(db, output):
    import idautils
    import ida_funcs
    records = [type_record(db, t) for t in db.types.get_all()]
    symbols = [{"address": f"0x{ea:X}", "name": name, "is_function": bool(ida_funcs.get_func(ea))}
               for ea, name in idautils.Names()]
    # Keep candidate paths separately, including source/debug paths. The text is
    # evidence of a compiled-in string, not proof that the corresponding file exists.
    paths = [{"address": f"0x{s.ea:X}", "text": str(s)} for s in idautils.Strings()
             if re.search(r"(?:[/\\]|\.(?:exh|exd|sgb|lgb|lvb|lua|cpp|h)\b)", str(s), re.I)]
    result = {"schema_version": 1, "source": "PS3 Monitor imported IDB metadata",
              "warning": "PS3 pointer/bitfield ABI; gap-only and alternate type views are unverified",
              "types": sorted(records, key=lambda r: r["name"] or ""),
              "symbols": symbols, "candidate_paths": paths}
    Path(output).write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return {"types": len(records), "symbols": len(symbols), "candidate_paths": len(paths)}


def export_relevant(db, output):
    needles = ("Excel", "EObj", "EventObject", "SGTimeline", "SGSettings", "eGeneralTimeline", "Scene_t",
               "SharedGroupTimelineState", "ExportedSG", "Layer_t", "LayerGroup_t", "InstanceObject_t")
    records = [type_record(db, t) for t in db.types.get_all()
               if any(n in (t.get_type_name() or "") for n in needles)]
    Path(output).write_text(json.dumps({"source": "PS3 Monitor imported IDB metadata (not Windows ABI)",
                                      "types": records}, indent=2) + "\n", encoding="utf-8")
    return len(records)

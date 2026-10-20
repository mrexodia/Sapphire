"""Export PS3 Monitor Excel getter wrappers and their consumer callsites.

Run read-only in IDA/ida_execute_python with an ida-domain ``db`` available:
    export(db, 'C:/CodeBlocks/Sapphire/build/ps3-excel-getters.json')

The export identifies wrappers that directly call ExdModule::GetEntry or
GetEntryByIndex with a constant root.exl sheet index. It records evidence; it
does not infer that every integer passed to a getter is a foreign key.
"""
from pathlib import Path
import json
import re


ENTRY_EAS = {
    0x30531C: "key",
    0x305568: "index",
}


def _pseudocode(db, ea):
    function = db.functions.get_at(ea)
    if function is None:
        raise RuntimeError(f"No function at 0x{ea:X}")
    return "\n".join(db.functions.get_pseudocode(function).to_text())


def _return_type(text):
    first = text.splitlines()[0] if text else ""
    return first.split("__fastcall", 1)[0].strip() if "__fastcall" in first else None


def _argument_expression(text, lookup):
    label = "mainkey" if lookup == "key" else "index"
    match = re.search(rf"\b{label}:\s*([^,\n\)]+)", text)
    return match.group(1).strip() if match else None


def export(db, output):
    wrappers = {}
    for target, lookup in ENTRY_EAS.items():
        for caller in db.xrefs.get_callers(target):
            # Keep the stable, typed DataManager surface. Other direct users are
            # useful consumers, not declarations of a sheet getter.
            if "Client4Game11DataManager" not in caller.name:
                continue
            ea = caller.function_ea
            text = _pseudocode(db, ea)
            sheet = re.search(r"sheet_index:\s*(0x[0-9A-Fa-f]+|\d+)u?", text)
            if not sheet:
                continue
            consumers = [
                {"xref_address": f"0x{item.ea:X}",
                 "function_address": f"0x{item.function_ea:X}",
                 "function": item.name}
                for item in db.xrefs.get_callers(ea)
            ]
            record = {
                "address": f"0x{ea:X}",
                "function": caller.name,
                "return_type": _return_type(text),
                "sheet_index": int(sheet.group(1), 0),
                "lookup": lookup,
                "argument_expression": _argument_expression(text, lookup),
                "consumers": consumers,
                "pseudocode": text,
            }
            # Some helper methods call both APIs. Preserve both observations.
            existing = wrappers.get(ea)
            if existing:
                existing.setdefault("alternate_lookups", []).append(record)
            else:
                wrappers[ea] = record

    result = {
        "schema_version": 1,
        "source": "PS3 Monitor IDB DataManager wrappers",
        "warning": (
            "A typed getter and constant sheet index identify a lookup surface. "
            "Foreign-key edges still require tracing the value supplied by each consumer."
        ),
        "entry_functions": {f"0x{ea:X}": mode for ea, mode in ENTRY_EAS.items()},
        "getters": sorted(wrappers.values(), key=lambda item: (item["sheet_index"], item["address"])),
    }
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return {
        "getters": len(result["getters"]),
        "sheet_indices": len({item["sheet_index"] for item in result["getters"]}),
        "consumer_callsites": sum(len(item["consumers"]) for item in result["getters"]),
    }

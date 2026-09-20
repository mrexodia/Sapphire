"""Export packet-rooted Windows subsystem call graphs without modifying the IDB."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

CLUSTERS = {
    "quest-leve": re.compile(r"Quest|Leve|Tracking|ContentClear|ContentAttain"),
    "retainer-inventory": re.compile(
        r"Retainer|Market|Item|Trade|Loot|Treasure|Salvage|Cabinet"
    ),
}


def _mapping_functions(mapping: dict[str, Any]) -> list[dict[str, Any]]:
    output = list(mapping.get("matches", []))
    for entry in mapping.get("sharedMatches", []):
        for opcode, packet in zip(entry["opcodes"], entry["packets"]):
            output.append({**entry, "opcode": opcode, "packet": packet})
    for entry in mapping.get("windowsMappings", []):
        for opcode, packet in zip(entry["opcodes"], entry["packets"]):
            output.append(
                {
                    **entry,
                    "opcode": opcode,
                    "packet": packet,
                    "ps3Address": None,
                    "ps3IdbUrl": None,
                }
            )
    return output


def export_subsystem_callgraph(
    db: Any, mapping_path: str | Path, output_path: str | Path | None = None
) -> dict[str, Any]:
    mapping = json.loads(Path(mapping_path).read_text(encoding="utf-8"))
    mapped = _mapping_functions(mapping)
    clusters = []
    for cluster_name, pattern in CLUSTERS.items():
        roots_by_address: dict[int, dict[str, Any]] = {}
        for entry in mapped:
            if not pattern.search(entry["packet"]):
                continue
            address = int(entry["windowsAddress"], 16)
            record = roots_by_address.setdefault(
                address,
                {
                    "windowsAddress": f"0x{address:016X}",
                    "windowsName": entry["windowsName"],
                    "packets": [],
                    "opcodes": [],
                    "ps3Links": [],
                },
            )
            record["packets"].append(entry["packet"])
            record["opcodes"].append(entry["opcode"])
            if entry.get("ps3IdbUrl"):
                record["ps3Links"].append(entry["ps3IdbUrl"])

        callees: dict[int, dict[str, Any]] = {}
        root_addresses = set(roots_by_address)
        for address, root in roots_by_address.items():
            function = db.functions.get_at(address)
            if function is None:
                continue
            for callee in db.functions.get_callees(function):
                callee_address = callee.start_ea
                if callee_address in root_addresses:
                    continue
                record = callees.setdefault(
                    callee_address,
                    {
                        "windowsAddress": f"0x{callee_address:016X}",
                        "windowsName": db.functions.get_name(callee),
                        "rootReferences": [],
                        "totalCallers": len(db.functions.get_callers(callee)),
                    },
                )
                record["rootReferences"].append(root["windowsName"])

        callee_records = []
        for record in callees.values():
            record["rootReferences"] = sorted(set(record["rootReferences"]))
            name = record["windowsName"]
            record["autoNamed"] = name.startswith(("sub_", "nullsub_", "j_sub_"))
            record["priority"] = (
                len(record["rootReferences"]) * 100
                + (25 if record["autoNamed"] else 0)
                + (10 if record["totalCallers"] <= 5 else 0)
            )
            callee_records.append(record)
        callee_records.sort(
            key=lambda item: (-item["priority"], item["windowsAddress"])
        )
        roots = sorted(roots_by_address.values(), key=lambda item: item["windowsAddress"])
        for root in roots:
            root["packets"] = sorted(set(root["packets"]))
            root["opcodes"] = sorted(set(root["opcodes"]))
            root["ps3Links"] = sorted(set(root["ps3Links"]))
        clusters.append(
            {
                "name": cluster_name,
                "rootFunctions": roots,
                "directCallees": callee_records,
                "summary": {
                    "roots": len(roots),
                    "directCallees": len(callee_records),
                    "autoNamedCallees": sum(item["autoNamed"] for item in callee_records),
                },
            }
        )

    result = {
        "schemaVersion": 1,
        "binary": "ffxiv_dx11.exe 2016.07.05.0000.0001",
        "method": "One-hop direct callees from confirmed packet-handler semantic islands. Priority is triage only and is not semantic proof.",
        "clusters": clusters,
    }
    if output_path is not None:
        path = Path(output_path)
        with path.open("w", encoding="utf-8", newline="\n") as output:
            json.dump(result, output, indent=2)
            output.write("\n")
    return result

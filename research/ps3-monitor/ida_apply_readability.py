"""Apply or verify conservative packet readability improvements in the Windows IDB."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

MARKER = "Sapphire packet cases (Windows 2016.07.05):"
BASE_TYPE_NAMES = [
    "Win335_ZoneDownOpcode",
    "Win335_ChatDownOpcode",
    "Win335_ZoneIpcPacket",
    "Win335_ChatIpcPacket",
    "Win335_PacketDispatcher",
    "Win335_InfoModule",
    "Win335_QuestWork_KnownFields",
    "Win335_LeveWork_KnownFields",
    "Win335_ItemAssemblyFragment",
    "Win335_ItemAssemblyContext",
    "Win335_ItemPacketAssembler",
]


def _load(root: str | Path) -> tuple[str, dict[str, Any]]:
    root = Path(root)
    return (
        (root / "windows_readability_types.h").read_text(encoding="utf-8"),
        json.loads((root / "readability_plan.json").read_text(encoding="utf-8")),
    )


def _comment_text(info: Any) -> str:
    if info is None:
        return ""
    return getattr(info, "comment", str(info))


def _merge_case_comment(existing: str, generated: str) -> str:
    marker_at = existing.find(MARKER)
    if marker_at >= 0:
        existing = existing[:marker_at].rstrip()
    return generated if not existing else existing + "\n" + generated


def _payload_declaration(db: Any, entry: dict[str, Any]) -> str:
    address = int(entry["windowsAddress"], 16)
    function = db.functions.get_at(address)
    signature = str(db.functions.get_signature(function) or "")
    match = re.match(r"^(.*?)\s*__fastcall\(", signature)
    if match is None:
        raise RuntimeError(f"cannot preserve return type for {entry['windowsAddress']}: {signature}")
    return_type = match.group(1).strip()
    return (
        f"{return_type} __fastcall {entry['windowsName']}("
        f"unsigned __int32 targetActorId, const {entry['typeName']} *packet)"
    )


def apply_readability(db: Any, root: str | Path) -> dict[str, Any]:
    declarations, plan = _load(root)
    failures: list[dict[str, Any]] = []
    applied = {"types": 0, "functionTypes": 0, "caseComments": 0}

    parse_errors = db.types.parse_declarations(None, declarations)
    if parse_errors:
        failures.append({"kind": "type declarations", "parseErrors": parse_errors})
    else:
        applied["types"] = len(BASE_TYPE_NAMES) + len(plan["knownFieldTypes"])

    definite = ida_domain.types.TypeApplyFlags.DEFINITE
    fixed_function_types = (
        plan["dispatcherTypes"]
        + [plan["eventFrameworkType"], plan["frameworkUiModuleType"]]
        + plan.get("ipcWrapperTypes", [])
        + plan.get("supportingFunctionTypes", [])
        + plan.get("subsystemFunctionTypes", [])
        + plan.get("internalFunctionTypes", [])
    )
    for entry in fixed_function_types:
        address = int(entry["address"], 16)
        try:
            ok = db.types.apply_declaration_at(address, entry["declaration"], flags=definite)
        except Exception as exc:
            ok = False
            failures.append(
                {"kind": "function type", "address": entry["address"], "error": str(exc)}
            )
        if ok:
            applied["functionTypes"] += 1
        elif not any(item.get("address") == entry["address"] for item in failures):
            failures.append(
                {"kind": "function type", "address": entry["address"], "error": "rejected"}
            )

    for entry in plan["payloadHandlerTypes"]:
        address = int(entry["windowsAddress"], 16)
        try:
            declaration = _payload_declaration(db, entry)
            ok = db.types.apply_declaration_at(address, declaration, flags=definite)
        except Exception as exc:
            ok = False
            failures.append(
                {
                    "kind": "payload handler type",
                    "address": entry["windowsAddress"],
                    "packet": entry["packet"],
                    "error": str(exc),
                }
            )
        if ok:
            applied["functionTypes"] += 1
        elif not any(item.get("address") == entry["windowsAddress"] for item in failures):
            failures.append(
                {
                    "kind": "payload handler type",
                    "address": entry["windowsAddress"],
                    "packet": entry["packet"],
                    "error": "rejected",
                }
            )

    for entry in plan.get("globalNames", []):
        address = int(entry["address"], 16)
        if not db.names.set_name(address, entry["name"]):
            failures.append(
                {"kind": "global name", "address": entry["address"], "error": "rejected"}
            )

    for entry in plan.get("globalTypes", []):
        address = int(entry["address"], 16)
        name_ok = db.names.set_name(address, entry["name"])
        try:
            type_ok = db.types.apply_declaration_at(address, entry["declaration"], flags=definite)
        except Exception as exc:
            type_ok = False
            failures.append(
                {"kind": "global type", "address": entry["address"], "error": str(exc)}
            )
        if not name_ok or not type_ok:
            failures.append(
                {
                    "kind": "global type",
                    "address": entry["address"],
                    "nameOk": name_ok,
                    "typeOk": type_ok,
                }
            )

    for entry in plan["caseComments"]:
        address = int(entry["address"], 16)
        existing = _comment_text(db.comments.get_at(address))
        wanted = _merge_case_comment(existing, entry["comment"])
        if db.comments.set_at(address, wanted):
            applied["caseComments"] += 1
        else:
            failures.append(
                {"kind": "case comment", "address": entry["address"], "error": "rejected"}
            )

    # Type changes do not reliably invalidate already cached caller pseudocode.
    # Flush the typed functions and their direct callers so new names, argument
    # types, and recovered member accesses are visible on the next decompilation.
    try:
        import ida_hexrays

        dirty: set[int] = set()
        typed_entries = list(fixed_function_types) + list(plan["payloadHandlerTypes"])
        for entry in typed_entries:
            address = int(entry.get("address", entry.get("windowsAddress")), 16)
            dirty.add(address)
            function = db.functions.get_at(address)
            if function is not None:
                dirty.update(caller.start_ea for caller in db.functions.get_callers(function))
        applied["cacheInvalidations"] = sum(
            bool(ida_hexrays.mark_cfunc_dirty(address, False)) for address in dirty
        )
    except (ImportError, AttributeError):
        # Host-side inspection can import this module without an IDA GUI.
        applied["cacheInvalidations"] = 0

    return {"applied": applied, "failures": failures, "ok": not failures}


def verify_readability(db: Any, root: str | Path) -> dict[str, Any]:
    _, plan = _load(root)
    failures: list[dict[str, Any]] = []

    type_names = BASE_TYPE_NAMES + [entry["typeName"] for entry in plan["knownFieldTypes"]]
    for name in type_names:
        if db.types.get_by_name(name) is None:
            failures.append({"kind": "missing type", "name": name})
    for record in plan["knownFieldTypes"]:
        type_info = db.types.get_by_name(record["typeName"])
        if type_info is None:
            continue
        actual_size = ida_domain.types.TypeDetails.from_tinfo_t(type_info).size
        if actual_size != record["knownSize"]:
            failures.append(
                {
                    "kind": "known-field type size mismatch",
                    "name": record["typeName"],
                    "expected": record["knownSize"],
                    "actual": actual_size,
                }
            )

    for entry in plan["dispatcherTypes"]:
        function = db.functions.get_at(int(entry["address"], 16))
        signature = str(db.functions.get_signature(function) or "")
        required = (
            "Win335_ZoneIpcPacket"
            if "Zone" in entry["declaration"]
            else "Win335_ChatIpcPacket"
            if "Chat" in entry["declaration"]
            else "Win335_PacketDispatcher"
        )
        if required not in signature:
            failures.append(
                {
                    "kind": "dispatcher type mismatch",
                    "address": entry["address"],
                    "signature": signature,
                }
            )

    for entry in plan.get("ipcWrapperTypes", []) + plan.get("supportingFunctionTypes", []):
        function = db.functions.get_at(int(entry["address"], 16))
        signature = str(db.functions.get_signature(function) or "")
        if "Win335_ZoneIpcPacket" not in signature:
            failures.append(
                {
                    "kind": "IPC/supporting type mismatch",
                    "address": entry["address"],
                    "signature": signature,
                }
            )

    for entry in plan.get("subsystemFunctionTypes", []) + plan.get("internalFunctionTypes", []):
        function = db.functions.get_at(int(entry["address"], 16))
        signature = str(db.functions.get_signature(function) or "")
        required = [name for name in type_names if name in entry["declaration"]]
        if not signature or any(name not in signature for name in required):
            failures.append(
                {
                    "kind": "subsystem/internal type mismatch",
                    "address": entry["address"],
                    "requiredTypes": required,
                    "signature": signature,
                }
            )

    framework_ui = plan["frameworkUiModuleType"]
    framework_ui_function = db.functions.get_at(int(framework_ui["address"], 16))
    framework_ui_signature = str(db.functions.get_signature(framework_ui_function) or "")
    if "Win335_UIModule" not in framework_ui_signature or "Win335_Framework" not in framework_ui_signature:
        failures.append(
            {
                "kind": "Framework UI-module type mismatch",
                "address": framework_ui["address"],
                "signature": framework_ui_signature,
            }
        )

    event = plan["eventFrameworkType"]
    event_function = db.functions.get_at(int(event["address"], 16))
    event_signature = str(db.functions.get_signature(event_function) or "")
    if "Win335_EventFramework" not in event_signature:
        failures.append(
            {
                "kind": "EventFramework type mismatch",
                "address": event["address"],
                "signature": event_signature,
            }
        )

    for entry in plan["payloadHandlerTypes"]:
        function = db.functions.get_at(int(entry["windowsAddress"], 16))
        signature = str(db.functions.get_signature(function) or "")
        if entry["typeName"] not in signature or "targetActorId" not in signature:
            failures.append(
                {
                    "kind": "payload handler type mismatch",
                    "address": entry["windowsAddress"],
                    "packet": entry["packet"],
                    "signature": signature,
                }
            )

    for entry in plan.get("globalNames", []):
        address = int(entry["address"], 16)
        actual_name = db.names.get_at(address)
        if actual_name != entry["name"]:
            failures.append(
                {
                    "kind": "global name mismatch",
                    "address": entry["address"],
                    "expectedName": entry["name"],
                    "actualName": actual_name,
                }
            )

    for entry in plan.get("globalTypes", []):
        address = int(entry["address"], 16)
        actual_name = db.names.get_at(address)
        actual_type = str(db.types.get_at(address) or "")
        expected_type = entry["declaration"].split(" ", 1)[0]
        if actual_name != entry["name"] or expected_type not in actual_type:
            failures.append(
                {
                    "kind": "global type mismatch",
                    "address": entry["address"],
                    "expectedName": entry["name"],
                    "actualName": actual_name,
                    "actualType": actual_type,
                }
            )

    for entry in plan["caseComments"]:
        actual = _comment_text(db.comments.get_at(int(entry["address"], 16)))
        if entry["comment"] not in actual:
            failures.append(
                {"kind": "case comment mismatch", "address": entry["address"]}
            )

    return {
        "checked": {
            "types": len(type_names),
            "functionTypes": len(plan["dispatcherTypes"])
            + 2
            + len(plan.get("ipcWrapperTypes", []))
            + len(plan.get("supportingFunctionTypes", []))
            + len(plan.get("subsystemFunctionTypes", []))
            + len(plan.get("internalFunctionTypes", []))
            + len(plan["payloadHandlerTypes"]),
            "globalTypes": len(plan.get("globalTypes", [])),
            "globalNames": len(plan.get("globalNames", [])),
            "caseComments": len(plan["caseComments"]),
        },
        "failures": failures,
        "ok": not failures,
    }

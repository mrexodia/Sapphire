"""Helpers for exporting FFXIV packet-dispatcher cases through IDA Nexus.

This module is intentionally read-only. Load it in an ida_execute_python session
with exec(Path(...).read_text()) and call the export_* functions with the active
ida-domain Database.
"""

from __future__ import annotations

import re
from typing import Any


_HEADER_COMPARE_RE = re.compile(
    r"commonHeader\s*(<=|>=|==|!=|<|>)\s*(0x[0-9A-Fa-f]+|\d+)"
)


def _address(value: int | None, width: int) -> str | None:
    return None if value is None else f"0x{value:0{width}X}"


def _short_name(db: Any, address: int) -> str | None:
    function = db.functions.get_at(address)
    if function is None:
        return db.names.get_at(address)
    raw_name = db.functions.get_name(function)
    demangled = db.names.demangle_name(raw_name)
    if demangled and demangled != raw_name:
        return demangled.split("(", 1)[0]
    return raw_name


def _calls(db: Any, instruction: Any, address_width: int) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for expression in instruction.walk_expressions():
        if not expression.is_call:
            continue
        callee = expression.x
        target = callee.obj_ea if callee is not None else None
        calls.append(
            {
                "callsite": _address(expression.ea, address_width),
                "address": _address(target, address_width),
                "name": _short_name(db, target) if target is not None else None,
                "_text": str(expression),
            }
        )
    return calls


def _deduplicate_calls(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str | None, str | None, str]] = set()
    for call in calls:
        key = (call["callsite"], call["address"], call["_text"])
        if key not in seen:
            seen.add(key)
            result.append(call)
    return result


def _evaluate_header_condition(text: str, opcode: int) -> bool | None:
    if "commonHeader" not in text:
        return None
    parts = re.split(r"\s*&&\s*", text)
    results: list[bool] = []
    for part in parts:
        match = _HEADER_COMPARE_RE.search(part)
        if match is None:
            return None
        operator, literal = match.groups()
        value = int(literal, 0)
        results.append(
            {
                "<=": opcode <= value,
                ">=": opcode >= value,
                "==": opcode == value,
                "!=": opcode != value,
                "<": opcode < value,
                ">": opcode > value,
            }[operator]
        )
    return all(results)


def _execute_for_opcode(
    db: Any,
    instruction: Any,
    opcode: int,
    address_width: int,
    depth: int = 0,
) -> tuple[list[dict[str, Any]], bool]:
    """Walk structured ctree for one concrete opcode.

    Non-opcode runtime conditions are conservatively explored in both
    directions. The returned boolean means all explored paths terminate the
    current sequence.
    """
    if depth > 256:
        raise RuntimeError("ctree nesting exceeded safety limit")

    operation = getattr(instruction.op, "name", str(instruction.op))
    if operation == "BLOCK":
        calls: list[dict[str, Any]] = []
        for child in instruction.block:
            child_calls, stops = _execute_for_opcode(
                db, child, opcode, address_width, depth + 1
            )
            calls.extend(child_calls)
            if stops:
                return calls, True
        return calls, False

    if operation == "IF":
        details = instruction.if_details
        condition = _evaluate_header_condition(str(details.condition), opcode)
        if condition is True:
            return _execute_for_opcode(
                db, details.then_branch, opcode, address_width, depth + 1
            )
        if condition is False:
            if details.has_else:
                return _execute_for_opcode(
                    db, details.else_branch, opcode, address_width, depth + 1
                )
            return [], False

        then_calls, then_stops = _execute_for_opcode(
            db, details.then_branch, opcode, address_width, depth + 1
        )
        if details.has_else:
            else_calls, else_stops = _execute_for_opcode(
                db, details.else_branch, opcode, address_width, depth + 1
            )
        else:
            else_calls, else_stops = [], False
        return then_calls + else_calls, then_stops and else_stops

    if operation == "SWITCH":
        details = instruction.switch_details
        if "commonHeader" in str(details.expression):
            selected = None
            default = None
            for case in details.cases:
                if case.is_default:
                    default = case
                elif opcode in case.values:
                    selected = case
                    break
            selected = selected or default
            if selected is None:
                return [], False
            return _execute_for_opcode(
                db, selected.body, opcode, address_width, depth + 1
            )

        calls: list[dict[str, Any]] = []
        stops: list[bool] = []
        for case in details.cases:
            case_calls, case_stops = _execute_for_opcode(
                db, case.body, opcode, address_width, depth + 1
            )
            calls.extend(case_calls)
            stops.append(case_stops)
        return calls, bool(stops) and all(stops)

    calls = _calls(db, instruction, address_width)
    return calls, operation in {"RETURN", "GOTO", "BREAK", "CONTINUE"}


def _public_calls(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: value for key, value in call.items() if key != "_text"} for call in calls]


def _case_record(
    opcode: int | None,
    case_ea: int | None,
    calls: list[dict[str, Any]],
    packet_calls: list[dict[str, Any]],
    address_width: int,
    packet_data_offset: str | None,
) -> dict[str, Any]:
    calls = _deduplicate_calls(calls)
    packet_calls = _deduplicate_calls(packet_calls)
    if packet_calls:
        kind = "direct" if len(packet_calls) == 1 else "shared"
    elif calls:
        kind = "inline"
    else:
        kind = "ignored" if opcode is not None else "default"
    return {
        "opcode": None if opcode is None else f"0x{opcode:04X}",
        "caseEa": _address(case_ea, address_width),
        "dispatchKind": kind,
        "packetDataOffset": packet_data_offset if packet_calls else None,
        "packetCalls": _public_calls(packet_calls),
        "directCalls": _public_calls(calls),
        "status": "unresolved",
    }


def export_ps3_zone(db: Any, dispatcher_ea: int = 0x002F8710) -> dict[str, Any]:
    """Export the optimized PS3 zone dispatcher by concrete ctree evaluation."""
    pseudocode = db.pseudocode.decompile(dispatcher_ea)
    explicit_switch_values: set[int] = set()
    ignored_case_eas: dict[int, int] = {}
    for instruction in pseudocode.walk_instructions():
        if not instruction.is_switch:
            continue
        details = instruction.switch_details
        if "commonHeader" not in str(details.expression):
            continue
        for case in details.cases:
            for value in case.values:
                explicit_switch_values.add(value)
                ignored_case_eas.setdefault(value, case.body.ea)

    common_prepare = 0x00AE6F20
    cases: list[dict[str, Any]] = []
    for opcode in range(0x10000):
        calls, _ = _execute_for_opcode(db, pseudocode.body, opcode, 8)
        calls = [call for call in calls if call["address"] != _address(common_prepare, 8)]
        calls = _deduplicate_calls(calls)
        packet_calls = [
            call
            for call in calls
            if ".data" in call["_text"] or "->data" in call["_text"]
        ]
        if not calls and opcode not in explicit_switch_values:
            continue
        case_ea = None
        if packet_calls:
            case_ea = int(packet_calls[0]["callsite"], 16)
        elif calls:
            case_ea = int(calls[0]["callsite"], 16)
        else:
            case_ea = ignored_case_eas.get(opcode)
        cases.append(
            _case_record(opcode, case_ea, calls, packet_calls, 8, "0x10")
        )

    # The optimized decision tree has an implicit fallthrough for all other
    # 16-bit values rather than a recoverable ctree case node.
    cases.append(_case_record(None, None, [], [], 8, None))

    return {
        "build": "ps3-monitor-2.3",
        "channel": "zone-down",
        "dispatcherAddress": _address(dispatcher_ea, 8),
        "extraction": "concrete ctree evaluation of optimized comparison tree",
        "cases": cases,
    }


def export_switch_dispatcher(
    db: Any,
    dispatcher_ea: int,
    build: str,
    channel: str,
    address_width: int,
    packet_markers: tuple[str, ...],
    packet_data_offset: str,
) -> dict[str, Any]:
    """Export a dispatcher represented as one top-level decompiler switch."""
    pseudocode = db.pseudocode.decompile(dispatcher_ea)
    switches = [instruction for instruction in pseudocode.walk_instructions() if instruction.is_switch]
    if not switches:
        raise RuntimeError(f"no switch found at {dispatcher_ea:#x}")
    switch = max(switches, key=lambda item: len(item.switch_details.cases)).switch_details

    cases: list[dict[str, Any]] = []
    for case in switch.cases:
        calls = _deduplicate_calls(_calls(db, case.body, address_width))
        packet_calls = [
            call for call in calls if any(marker in call["_text"] for marker in packet_markers)
        ]
        values = case.values or [None]
        for opcode in values:
            cases.append(
                _case_record(
                    opcode,
                    None if opcode is None else case.body.ea,
                    calls,
                    packet_calls,
                    address_width,
                    packet_data_offset,
                )
            )

    cases.sort(key=lambda item: (item["opcode"] is None, item["opcode"] or ""))
    return {
        "build": build,
        "channel": channel,
        "dispatcherAddress": _address(dispatcher_ea, address_width),
        "extraction": "top-level decompiler switch",
        "cases": cases,
    }


def export_ps3_chat(db: Any, dispatcher_ea: int = 0x002FA984) -> dict[str, Any]:
    return export_switch_dispatcher(
        db,
        dispatcher_ea,
        "ps3-monitor-2.3",
        "chat-down",
        8,
        ("p_data", ".data", "->data"),
        "0x10",
    )


def export_windows_zone(db: Any, dispatcher_ea: int = 0x140DD9430) -> dict[str, Any]:
    return export_switch_dispatcher(
        db,
        dispatcher_ea,
        "windows-3.x",
        "zone-down",
        16,
        ("a3 + 16", "a3+16"),
        "0x10",
    )


def export_windows_chat(db: Any, dispatcher_ea: int = 0x140DD9300) -> dict[str, Any]:
    return export_switch_dispatcher(
        db,
        dispatcher_ea,
        "windows-3.x",
        "chat-down",
        16,
        ("a3 + 16", "a3+16"),
        "0x10",
    )

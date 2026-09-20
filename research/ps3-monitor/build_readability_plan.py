#!/usr/bin/env python3
"""Build conservative IDA types/comments for the Windows 3.35 packet semantic islands."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent

# These handlers receive the complete payload pointer as their second argument.
# Other handlers often receive fields extracted by the dispatcher and must not be
# assigned a whole-packet pointer type.
DIRECT_PAYLOAD_PACKETS = {
    "InviteResult",
    "InviteReplyResult",
    "InviteUpdate",
    "GetCommonlistResult",
    "SetProfileResult",
    "Create",
    "PlayerStatusUpdate",
    "PlayerStatus",
    "ChatFrom",
    "Chat",
    "TellNotFound",
    "RecvBusyStatus",
    "RecvFinderStatus",
    "GetProfileResult",
    "GetSearchCommentResult",
    "ChatChannelResult",
    "SendSystemMessage",
    "SendLoginMessage",
    "UpdateOnlineStatus",
    "PartyRecruitResult",
    "RequestItmeResult",
    "AllianceReadyCheckResult",
    "PcPartyResult",
    "PcPartyUpdate",
    "InviteCancelResult",
}


def load(name: str) -> dict[str, Any]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as output:
        json.dump(value, output, indent=2)
        output.write("\n")


def identifier(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_]", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    if not value or value[0].isdigit():
        value = "_" + value
    return value


def flatten_matches(mapping: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    output: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in mapping["matches"]:
        output[(entry.get("channel", "zone-down"), entry["opcode"])] = entry
    for entry in mapping.get("sharedMatches", []):
        channel = entry.get("channel", "zone-down")
        for opcode, packet in zip(entry["opcodes"], entry["packets"]):
            output[(channel, opcode)] = {**entry, "opcode": opcode, "packet": packet}
    return output


def semantic_labels(mapping: dict[str, Any]) -> dict[tuple[str, str], tuple[str, str]]:
    labels: dict[tuple[str, str], tuple[str, str]] = {}
    for key, entry in flatten_matches(mapping).items():
        labels[key] = (entry["packet"], "PS3-linked")
    for entry in mapping.get("windowsMappings", []):
        for opcode, packet in zip(entry["opcodes"], entry["packets"]):
            labels[(entry["channel"], opcode)] = (packet, "Windows-semantic")
    for entry in mapping.get("windowsInlineMappings", []):
        labels[(entry["channel"], entry["opcode"])] = (
            entry["packet"],
            "Windows-inline",
        )
    return labels


def enum_declaration(
    name: str,
    channel: str,
    cases: list[dict[str, Any]],
    labels: dict[tuple[str, str], tuple[str, str]],
) -> str:
    members = []
    used: set[str] = set()
    for case in cases:
        opcode = case["opcode"]
        if opcode is None:
            continue
        packet = labels.get((channel, opcode), (f"Unknown_{opcode[2:]}", ""))[0]
        member = f"{name}_{identifier(packet)}"
        if member in used:
            member += f"_{opcode[2:]}"
        used.add(member)
        members.append(f"  {member} = {opcode}")
    return f"enum {name} : unsigned __int16\n{{\n" + ",\n".join(members) + "\n};\n"


def primitive_decl(type_name: str, size: int) -> str | None:
    normalized = type_name.replace("const ", "").strip()
    exact = {
        "uint8_t": "unsigned __int8",
        "int8_t": "signed __int8",
        "char": "char",
        "bool": "unsigned __int8",
        "uint16_t": "unsigned __int16",
        "int16_t": "signed __int16",
        "uint32_t": "unsigned __int32",
        "int32_t": "signed __int32",
        "float": "float",
        "uint64_t": "unsigned __int64",
        "int64_t": "signed __int64",
        "double": "double",
    }
    declaration = exact.get(normalized)
    expected = {
        "unsigned __int8": 1,
        "signed __int8": 1,
        "char": 1,
        "unsigned __int16": 2,
        "signed __int16": 2,
        "unsigned __int32": 4,
        "signed __int32": 4,
        "float": 4,
        "unsigned __int64": 8,
        "signed __int64": 8,
        "double": 8,
    }
    return declaration if declaration and expected[declaration] == size else None


def known_fields(structure: dict[str, Any]) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for member in structure["members"]:
        validation = member["windowsValidation"]
        if not validation["status"].startswith("confirmed-"):
            continue
        fields.append(
            {
                "name": identifier(member["name"]),
                "offset": int(validation["offset"], 16),
                "size": member["size"],
                "sourceType": member["type"],
                "evidence": validation["evidence"],
            }
        )
    for field in structure.get("windowsExtraFields", []):
        fields.append(
            {
                "name": identifier(field["name"]),
                "offset": int(field["offset"], 16),
                "size": field["width"],
                "sourceType": "Windows-only",
                "evidence": field["evidence"],
            }
        )
    fields.sort(key=lambda item: (item["offset"], item["name"]))
    return fields


def struct_declaration(structure: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    type_name = f"Win335_{identifier(structure['packet'])}_KnownFields"
    fields = known_fields(structure)
    lines = [f"struct {type_name}", "{"]
    cursor = 0
    emitted: list[dict[str, Any]] = []
    names: set[str] = set()
    for field in fields:
        offset = field["offset"]
        size = field["size"]
        if offset < cursor:
            continue
        if offset > cursor:
            lines.append(f"  unsigned __int8 _unknown_{cursor:04X}[0x{offset - cursor:X}];")
        name = field["name"]
        if name in names:
            name += f"_{offset:04X}"
        names.add(name)
        primitive = primitive_decl(field["sourceType"], size)
        if primitive:
            lines.append(f"  {primitive} {name}; // +0x{offset:X}: {field['evidence']}")
        else:
            lines.append(
                f"  unsigned __int8 {name}[0x{size:X}]; // +0x{offset:X}: {field['evidence']}"
            )
        cursor = offset + size
        emitted.append({**field, "name": name})
    lines.extend(["};", ""])
    return "\n".join(lines), {
        "packet": structure["packet"],
        "channel": structure["channel"],
        "typeName": type_name,
        "knownSize": cursor,
        "fields": emitted,
    }


def build() -> tuple[str, dict[str, Any]]:
    mapping = load("packet_matches.json")
    structures = load("packet_structures.json")["structures"]
    inventory = load("dispatcher_cases.json")
    labels = semantic_labels(mapping)
    windows_dispatchers = {
        item["channel"]: item
        for item in inventory["dispatchers"]
        if item["build"] == "windows-3.x"
    }

    declarations = [
        "// Generated by build_readability_plan.py. Windows 2016.07.05 only.",
        "// KnownFields structures intentionally contain only Windows-confirmed fields.",
        "#pragma pack(push, 1)",
        enum_declaration(
            "Win335_ZoneDownOpcode",
            "zone-down",
            windows_dispatchers["zone-down"]["cases"],
            labels,
        ),
        enum_declaration(
            "Win335_ChatDownOpcode",
            "chat-down",
            windows_dispatchers["chat-down"]["cases"],
            labels,
        ),
        "struct Win335_ZoneIpcPacket\n{\n"
        "  unsigned __int16 reserved;\n"
        "  Win335_ZoneDownOpcode opcode;\n"
        "  unsigned __int16 padding;\n"
        "  unsigned __int16 serverId;\n"
        "  unsigned __int32 timestamp;\n"
        "  unsigned __int32 padding1;\n"
        "  unsigned __int8 payload[0x1000]; // inspection window; not an exact wire size\n"
        "};\n",
        "struct Win335_ChatIpcPacket\n{\n"
        "  unsigned __int16 reserved;\n"
        "  Win335_ChatDownOpcode opcode;\n"
        "  unsigned __int16 padding;\n"
        "  unsigned __int16 serverId;\n"
        "  unsigned __int32 timestamp;\n"
        "  unsigned __int32 padding1;\n"
        "  unsigned __int8 payload[0x1000]; // inspection window; not an exact wire size\n"
        "};\n",
        "struct Win335_PacketDispatcher\n{\n"
        "  void *zoneVftable;\n"
        "  void *chatVftable;\n"
        "  void *networkModuleProxy;\n"
        "};\n",
        "struct Win335_EventFramework;\n",
        "struct Win335_Framework;\n",
        "struct Win335_UIModule;\n",
        "struct Win335_StorageManager;\n",
        "struct Win335_ItemPacketAssembler\n{\n"
        "  unsigned __int8 _unknown_0000[0x38];\n"
        "  void *contextList;\n"
        "};\n",
    ]

    type_records: list[dict[str, Any]] = []
    type_by_packet: dict[tuple[str, str], str] = {}
    for structure in structures:
        if structure["comparisonStatus"] != "partially-windows-validated":
            continue
        declaration, record = struct_declaration(structure)
        if not record["fields"]:
            continue
        declarations.append(declaration)
        type_records.append(record)
        type_by_packet[(structure["channel"], structure["packet"])] = record["typeName"]
    declarations.append("#pragma pack(pop)\n")

    entries = flatten_matches(mapping)
    payload_handlers = []
    for entry in entries.values():
        packet = entry["packet"]
        key = (entry.get("channel", "zone-down"), packet)
        if packet not in DIRECT_PAYLOAD_PACKETS or key not in type_by_packet:
            continue
        payload_handlers.append(
            {
                "channel": key[0],
                "packet": packet,
                "opcode": entry["opcode"],
                "windowsAddress": entry["windowsAddress"],
                "windowsName": entry["windowsName"],
                "typeName": type_by_packet[key],
                "argumentIndex": 1,
            }
        )
    payload_handlers.sort(key=lambda item: int(item["windowsAddress"], 16))

    comments: dict[int, list[str]] = defaultdict(list)
    for channel, dispatcher in windows_dispatchers.items():
        for case in dispatcher["cases"]:
            if case["opcode"] is None or case["caseEa"] is None:
                continue
            opcode = case["opcode"]
            semantic = labels.get((channel, opcode))
            if semantic:
                packet, status = semantic
                line = f"{opcode} {packet} [{status}]"
            elif case["status"] == "windows-only":
                line = f"{opcode} unknown [Windows-only numeric case; semantics unproven]"
            else:
                line = f"{opcode} unknown [{case['status']}]"
            comments[int(case["caseEa"], 16)].append(line)
    case_comments = [
        {
            "address": f"0x{address:016X}",
            "comment": "Sapphire packet cases (Windows 2016.07.05):\n" + "\n".join(sorted(set(lines))),
        }
        for address, lines in sorted(comments.items())
    ]

    dispatcher_names = {
        entry["direction"]: entry for entry in mapping["dispatchers"]
    }
    ctor = next(
        item
        for item in mapping["supportingFunctions"]
        if item["role"] == "PacketDispatcher constructor"
    )
    inventory_families = [
        {
            "wrapperAddress": "0x140CC8730",
            "wrapperName": "Client__Game__Network__Packet__ReceiveRetainerPackets",
            "implementationAddress": "0x140CC7090",
            "implementationName": "Client__Game__Network__Packet__ReceiveRetainerPackets_Impl",
        },
        {
            "wrapperAddress": "0x140CC8710",
            "wrapperName": "Client__Game__Network__Packet__ReceiveMarketPricePackets",
            "implementationAddress": "0x140CC7200",
            "implementationName": "Client__Game__Network__Packet__ReceiveMarketPricePackets_Impl",
        },
        {
            "wrapperAddress": "0x140CC86F0",
            "wrapperName": "Client__Game__Network__Packet__ReceiveItemOperationPackets",
            "implementationAddress": "0x140CC7330",
            "implementationName": "Client__Game__Network__Packet__ReceiveItemOperationPackets_Impl",
        },
        {
            "wrapperAddress": "0x140CC8FE0",
            "wrapperName": "Client__Game__Network__Packet__ReceiveItemStoragePackets",
            "implementationAddress": "0x140CC8870",
            "implementationName": "Client__Game__Network__Packet__ReceiveItemStoragePackets_Impl",
        },
    ]
    ipc_wrapper_types = []
    supporting_types = []
    for family in inventory_families:
        ipc_wrapper_types.append(
            {
                "address": family["wrapperAddress"],
                "declaration": (
                    f"void __fastcall {family['wrapperName']}(unsigned __int32 targetActorId, "
                    "const Win335_ZoneIpcPacket *packet)"
                ),
            }
        )
        supporting_types.append(
            {
                "address": family["implementationAddress"],
                "declaration": (
                    f"void __fastcall {family['implementationName']}("
                    "Win335_ItemPacketAssembler *assembler, unsigned __int32 targetActorId, "
                    "const Win335_ZoneIpcPacket *packet)"
                ),
            }
        )

    plan = {
        "schemaVersion": 1,
        "policy": "Only Windows-confirmed fields are emitted. Unknown gaps remain byte arrays; no PS3-only trailing size is asserted.",
        "summary": {
            "opcodeTypes": 2,
            "knownFieldTypes": len(type_records),
            "typedPayloadHandlers": len(payload_handlers),
            "typedIpcWrappers": len(ipc_wrapper_types),
            "typedSupportingFunctions": len(supporting_types),
            "typedGlobals": 4,
            "dispatcherCaseComments": len(case_comments),
        },
        "dispatcherTypes": [
            {
                "address": dispatcher_names["zone-down"]["windowsAddress"],
                "declaration": "void __fastcall Client__Network__PacketDispatcher__OnReceivePacket_Zone(Win335_PacketDispatcher *self, unsigned __int32 targetActorId, const Win335_ZoneIpcPacket *packet)",
            },
            {
                "address": dispatcher_names["chat-down"]["windowsAddress"],
                "declaration": "__int64 __fastcall Client__Network__PacketDispatcher__OnReceivePacket_Chat(Win335_PacketDispatcher *self, unsigned __int32 targetActorId, const Win335_ChatIpcPacket *packet)",
            },
            {
                "address": ctor["windowsAddress"],
                "declaration": "Win335_PacketDispatcher *__fastcall Client__Network__PacketDispatcher__ctor(Win335_PacketDispatcher *self, void *networkModuleProxy)",
                "role": "constructor",
            },
        ],
        "eventFrameworkType": {
            "address": "0x1406044E0",
            "declaration": "Win335_EventFramework *__fastcall Client__Game__Event__EventFramework__GetInstance(void)",
        },
        "frameworkUiModuleType": {
            "address": "0x140013960",
            "declaration": "Win335_UIModule *__fastcall Client__System__Framework__Framework__GetUIModule(Win335_Framework *self)",
        },
        "payloadHandlerTypes": payload_handlers,
        "ipcWrapperTypes": ipc_wrapper_types,
        "supportingFunctionTypes": supporting_types,
        "globalTypes": [
            {
                "address": "0x1415E9400",
                "name": "Client__System__Framework__Framework__s_instance",
                "declaration": "Win335_Framework *Client__System__Framework__Framework__s_instance",
                "evidence": "The Framework::GetUIModule receiver used throughout packet and UI paths.",
            },
            {
                "address": "0x1417C39D0",
                "name": "Client__Game__Event__EventFramework__s_instance",
                "declaration": "Win335_EventFramework *Client__Game__Event__EventFramework__s_instance",
                "evidence": "Returned directly by the PS3-linked EventFramework::GetInstance function.",
            },
            {
                "address": "0x1415BEFF0",
                "name": "g_Win335_ItemPacketAssembler",
                "declaration": "Win335_ItemPacketAssembler g_Win335_ItemPacketAssembler",
                "evidence": "Static assembler object passed by all four typed retainer/market/item wrappers.",
            },
            {
                "address": "0x14179EEF0",
                "name": "Client__Game__Item__StorageManager__s_instance",
                "declaration": "Win335_StorageManager *Client__Game__Item__StorageManager__s_instance",
                "evidence": "Receiver passed to independently named StorageManager packet handlers and item commits.",
            },
        ],
        "knownFieldTypes": type_records,
        "caseComments": case_comments,
    }
    return "\n".join(declarations), plan


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    header, plan = build()
    outputs: dict[Path, str] = {
        ROOT / "windows_readability_types.h": header,
        ROOT / "readability_plan.json": json.dumps(plan, indent=2) + "\n",
    }
    if args.check:
        stale = [
            str(path)
            for path, content in outputs.items()
            if not path.exists() or path.read_text(encoding="utf-8") != content
        ]
        if stale:
            raise SystemExit("stale readability outputs: " + ", ".join(stale))
        print("readability plan is current")
        return
    for path, content in outputs.items():
        path.write_text(content, encoding="utf-8", newline="\n")
    print(
        f"wrote {len(outputs)} readability artifacts: "
        f"{plan['summary']['knownFieldTypes']} known-field types, "
        f"{plan['summary']['typedPayloadHandlers']} typed handlers, "
        f"{plan['summary']['dispatcherCaseComments']} case comments"
    )


if __name__ == "__main__":
    main()

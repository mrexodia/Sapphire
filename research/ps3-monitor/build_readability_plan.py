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
    "CreateTreasure",
    "OpenTreasure",
    "TreasureOpenRight",
    "LootItems",
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
                "sourceType": field.get("type", "Windows-only"),
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
        array_match = re.fullmatch(r"(.+?)\[(\d+)\]", field["sourceType"].strip())
        array_primitive = None
        array_count = 0
        if array_match:
            array_count = int(array_match.group(2))
            if array_count and size % array_count == 0:
                array_primitive = primitive_decl(array_match.group(1), size // array_count)
        if primitive:
            lines.append(f"  {primitive} {name}; // +0x{offset:X}: {field['evidence']}")
        elif array_primitive:
            lines.append(
                f"  {array_primitive} {name}[{array_count}]; // +0x{offset:X}: {field['evidence']}"
            )
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
        "struct Win335_EventHandler\n{\n"
        "  void *vftable;\n"
        "  unsigned __int8 _unknown_0008[0x2A];\n"
        "  unsigned __int16 handlerType;\n"
        "};\n",
        "struct Win335_EventHandlerTreeNode\n{\n"
        "  Win335_EventHandlerTreeNode *left;\n"
        "  Win335_EventHandlerTreeNode *parent;\n"
        "  Win335_EventHandlerTreeNode *right;\n"
        "  unsigned __int32 handlerId;\n"
        "  unsigned __int8 _unknown_001C[0x4];\n"
        "  Win335_EventHandler *handler;\n"
        "  unsigned __int8 color;\n"
        "  unsigned __int8 isNil;\n"
        "};\n",
        "struct Win335_EventFramework\n{\n"
        "  unsigned __int8 _unknown_0000[0x58];\n"
        "  Win335_EventHandlerTreeNode *eventHandlers;\n"
        "  unsigned __int8 _unknown_0060[0x30];\n"
        "  Win335_EventHandler *specialHandler_A0001;\n"
        "  Win335_EventHandler *specialHandler_E0000;\n"
        "  Win335_EventHandler *specialHandler_150001;\n"
        "  Win335_EventHandler *specialHandler_140001;\n"
        "  Win335_EventHandler *specialHandler_230001;\n"
        "  Win335_EventHandler *specialHandler_B0129;\n"
        "  Win335_EventHandler *specialHandler_B0130;\n"
        "};\n",
        "struct Win335_Framework;\n",
        "struct Win335_UIModule;\n",
        "struct Win335_StorageManager;\n",
        "struct Win335_InfoProxyItemSearch;\n",
        "struct Win335_InfoProxyInterface\n{\n"
        "  void *vftable;\n"
        "  Win335_UIModule *ui;\n"
        "  unsigned __int32 count;\n"
        "};\n",
        "struct Win335_InfoProxyItemSearchResult_KnownFields\n{\n"
        "  unsigned __int64 itemId;\n"
        "  unsigned __int64 sellRetainerId;\n"
        "  unsigned __int64 signatureId;\n"
        "  unsigned __int32 sellPrice;\n"
        "  unsigned __int32 buyTax;\n"
        "  unsigned __int32 stack;\n"
        "  unsigned __int32 catalogId;\n"
        "  unsigned __int16 containerIndex;\n"
        "  unsigned __int16 durability;\n"
        "  unsigned __int16 refine;\n"
        "  unsigned __int16 materia[5];\n"
        "  unsigned __int8 subQuality;\n"
        "  unsigned __int8 materiaCount;\n"
        "  unsigned __int8 registerMarket;\n"
        "  unsigned __int8 unknown3B;\n"
        "  unsigned __int8 _unknown_003C[0x4];\n"
        "};\n",
        "struct Win335_InfoProxyItemSearchRetainer_KnownFields\n{\n"
        "  unsigned __int64 retainerId;\n"
        "  unsigned __int8 registerMarket;\n"
        "  unsigned __int8 isMarket;\n"
        "  unsigned __int8 sellTaxRate;\n"
        "  unsigned __int8 _unknown_000B;\n"
        "  unsigned __int32 expirationSellTaxRateDate;\n"
        "  unsigned __int8 retainerNameStorage[0x68];\n"
        "};\n",
        "struct Win335_InfoProxyItemSearchVTable\n{\n"
        "  void *deletingDestructor;\n"
        "  void (__fastcall *Add)(Win335_InfoProxyItemSearch *self, const void *records, unsigned __int32 count);\n"
        "  void (__fastcall *Sub)(Win335_InfoProxyItemSearch *self, const void *records, unsigned __int32 count);\n"
        "  void (__fastcall *Clear)(Win335_InfoProxyItemSearch *self);\n"
        "  void *unknown20;\n"
        "  unsigned __int8 (__fastcall *Request)(Win335_InfoProxyItemSearch *self);\n"
        "  void (__fastcall *Finish)(Win335_InfoProxyItemSearch *self);\n"
        "  unsigned __int32 (__fastcall *Count)(const Win335_InfoProxyItemSearch *self);\n"
        "  void *unknown40;\n"
        "  void *unknown48;\n"
        "  void (__fastcall *AddPage)(Win335_InfoProxyItemSearch *self, const void *packet);\n"
        "};\n",
        "struct Win335_InfoProxyItemSearch\n{\n"
        "  Win335_InfoProxyItemSearchVTable *vftable;\n"
        "  Win335_UIModule *ui;\n"
        "  unsigned __int32 count;\n"
        "  unsigned __int8 _unknown_0014[0x5];\n"
        "  unsigned __int8 requestKey;\n"
        "  unsigned __int8 _unknown_001A[0x6];\n"
        "  unsigned __int32 requestCatalogId;\n"
        "  unsigned __int8 requestSubQuality;\n"
        "  unsigned __int8 requestMateriaCount;\n"
        "  unsigned __int8 _unknown_0026[0x2];\n"
        "  Win335_InfoProxyItemSearchResult_KnownFields results[100];\n"
        "  unsigned __int32 total;\n"
        "  unsigned __int8 _unknown_192C[0x534];\n"
        "  Win335_InfoProxyItemSearchRetainer_KnownFields retainers[8];\n"
        "  unsigned __int32 retainerCount;\n"
        "  unsigned __int8 _unknown_2224[0x3A];\n"
        "  unsigned __int8 setData;\n"
        "};\n",
        "struct Win335_GameObject_KnownFields\n{\n"
        "  void *vftable;\n"
        "  unsigned __int8 _unknown_0008[0x68];\n"
        "  unsigned __int8 permissionInvisibility;\n"
        "  unsigned __int8 _unknown_0071[0x3];\n"
        "  unsigned __int32 entityId;\n"
        "  unsigned __int32 layoutId;\n"
        "  unsigned __int8 _unknown_007C[0x78];\n"
        "  unsigned __int32 contentId;\n"
        "};\n",
        "struct Win335_TreasureItemSlot\n{\n"
        "  unsigned __int32 itemCatalogueId;\n"
        "};\n",
        "struct Win335_Treasure\n{\n"
        "  void *vftable;\n"
        "  unsigned __int8 _unknown_0008[0x68];\n"
        "  unsigned __int8 permissionInvisibility;\n"
        "  unsigned __int8 _unknown_0071[0x3];\n"
        "  unsigned __int32 entityId;\n"
        "  unsigned __int32 layoutId;\n"
        "  unsigned __int8 _unknown_007C[0x4];\n"
        "  unsigned __int32 baseId;\n"
        "  unsigned __int8 _unknown_0084[0x6];\n"
        "  unsigned __int8 objectKind;\n"
        "  unsigned __int8 _unknown_008B[0x9];\n"
        "  unsigned __int8 stateFlags;\n"
        "  unsigned __int8 _unknown_0095[0x5F];\n"
        "  unsigned __int32 contentId;\n"
        "  unsigned __int8 _unknown_00F8[0x10];\n"
        "  void *sharedGroup;\n"
        "  unsigned __int8 _unknown_0110[0x80];\n"
        "  unsigned __int32 graphicalState;\n"
        "  float timer;\n"
        "  float maxTimer;\n"
        "  float maxLootTimer;\n"
        "  Win335_TreasureItemSlot items[16];\n"
        "  unsigned __int32 itemCount;\n"
        "  unsigned __int8 _unknown_01E4[0x4];\n"
        "  unsigned __int8 isOpened;\n"
        "  unsigned __int8 _unknown_01E9[0x7];\n"
        "  unsigned __int8 isFadeOut;\n"
        "  unsigned __int8 isLoot;\n"
        "  unsigned __int8 lootMode;\n"
        "  unsigned __int8 _unknown_01F3;\n"
        "  unsigned __int32 dropperNameId;\n"
        "  unsigned __int16 layerId;\n"
        "  unsigned __int8 _unknown_01FA[0x2];\n"
        "  unsigned __int32 treasureType;\n"
        "  unsigned __int16 sharedGroupId;\n"
        "};\n",
        "struct Win335_StaticObjectManager\n{\n"
        "  unsigned __int8 _unknown_0000[0x10];\n"
        "  Win335_GameObject_KnownFields *objects[40];\n"
        "};\n",
        "struct Win335_StandObjectManager;\n",
        "struct Win335_TreasureManager;\n",
        "struct Win335_InfoModule\n{\n"
        "  void *vftable;\n"
        "  Win335_InfoProxyInterface *proxies[1]; // indexed array; one-element declaration does not assert the trailing class size\n"
        "};\n",
        "struct Win335_QuestWork_KnownFields\n{\n"
        "  unsigned __int8 _unknown_0000[0x8];\n"
        "  unsigned __int16 questId;\n"
        "  unsigned __int8 sequence;\n"
        "};\n",
        "struct Win335_LeveWork_KnownFields\n{\n"
        "  unsigned __int8 _unknown_0000[0x8];\n"
        "  unsigned __int16 leveId;\n"
        "};\n",
        "struct Win335_ItemAssemblyFragment\n{\n"
        "  unsigned __int8 _unknown_0000[0x8];\n"
        "  unsigned __int8 payload[0x50];\n"
        "  Win335_ItemAssemblyFragment *previous;\n"
        "  Win335_ItemAssemblyFragment *next;\n"
        "};\n",
        "struct Win335_ItemAssemblyContext\n{\n"
        "  unsigned __int8 _unknown_0000[0x10];\n"
        "  unsigned __int32 targetActorId;\n"
        "  unsigned __int8 _unknown_0014[0x4];\n"
        "  Win335_ItemAssemblyFragment *firstFragment;\n"
        "  Win335_ItemAssemblyFragment *lastFragment;\n"
        "  unsigned __int32 receivedFragmentCount;\n"
        "  signed __int32 expectedFragmentCount;\n"
        "  Win335_ItemAssemblyContext *previous;\n"
        "  Win335_ItemAssemblyContext *next;\n"
        "};\n",
        "struct Win335_ItemPacketAssembler\n{\n"
        "  unsigned __int8 _unknown_0000[0x10];\n"
        "  Win335_ItemAssemblyFragment *freeFragmentHead;\n"
        "  Win335_ItemAssemblyFragment *freeFragmentTail;\n"
        "  unsigned __int8 _unknown_0020[0x8];\n"
        "  Win335_ItemAssemblyContext *freeContextHead;\n"
        "  Win335_ItemAssemblyContext *freeContextTail;\n"
        "  Win335_ItemAssemblyContext *activeContextHead;\n"
        "  Win335_ItemAssemblyContext *activeContextTail;\n"
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

    subsystem_function_types = [
        {
            "address": "0x140032C30",
            "declaration": "Win335_InfoProxyInterface *__fastcall Client__UI__Info__InfoModule__GetProxy(Win335_InfoModule *self, unsigned __int32 proxyId)",
        },
        {
            "address": "0x1405428B0",
            "declaration": "Win335_Treasure *__fastcall Client__Game__Object__TreasureManager__GetTreasureFromEntityId(const Win335_TreasureManager *self, unsigned __int32 entityId)",
        },
        {
            "address": "0x14066B1C0",
            "declaration": "void __fastcall Client__Game__Event__EventFramework__OnQuestsInitialized(Win335_EventFramework *self)",
        },
        {
            "address": "0x1406A8970",
            "declaration": "void __fastcall Client__Game__Event__EventFramework__OnSyncQuest(Win335_EventFramework *self, const Win335_QuestWork_KnownFields *newWork, const Win335_QuestWork_KnownFields *oldWork, unsigned __int16 workIndex)",
        },
        {
            "address": "0x14066B230",
            "declaration": "void __fastcall Client__Game__Event__EventFramework__OnQuestCompleteFlagsInitialized(Win335_EventFramework *self)",
        },
        {
            "address": "0x14066B240",
            "declaration": "void __fastcall Client__Game__Event__EventFramework__OnSyncQuestComplete(Win335_EventFramework *self, unsigned __int16 questId, unsigned __int8 completed, unsigned __int8 update)",
        },
        {
            "address": "0x14066B280",
            "declaration": "void __fastcall Client__Game__Event__EventFramework__OnDailyQuestsInitialized(Win335_EventFramework *self)",
        },
        {
            "address": "0x140657ED0",
            "declaration": "void __fastcall Client__Game__Event__EventFramework__OnSyncDailyQuests(Win335_EventFramework *self, unsigned __int8 update)",
        },
        {
            "address": "0x140657FD0",
            "declaration": "void __fastcall Client__Game__Event__EventFramework__OnSyncDailyQuest(Win335_EventFramework *self, unsigned __int8 update)",
        },
        {
            "address": "0x14066B290",
            "declaration": "void __fastcall Client__Game__Event__EventFramework__OnQuestRepeatFlagsInitialized(Win335_EventFramework *self)",
        },
        {
            "address": "0x14066B2A0",
            "declaration": "void __fastcall Client__Game__Event__EventFramework__OnSyncQuestRepeatFlags(Win335_EventFramework *self, unsigned __int8 update)",
        },
        {
            "address": "0x14065FD10",
            "declaration": "void __fastcall Client__Game__Event__EventFramework__OnSyncQuestRepeatFlag(Win335_EventFramework *self, unsigned __int8 flagId, unsigned __int8 value, unsigned __int8 update)",
        },
        {
            "address": "0x140CC2630",
            "declaration": "void __fastcall Client__Game__Network__SyncTagPacket__ReceiveQuestRepeatFlag(unsigned __int8 flagId, unsigned __int8 value, unsigned __int8 update)",
        },
        {
            "address": "0x140604600",
            "declaration": "void __fastcall Client__Game__Event__EventFramework__OnGuildlevesInitialized(Win335_EventFramework *self)",
        },
        {
            "address": "0x1406B4400",
            "declaration": "void __fastcall Client__Game__Event__EventFramework__OnSyncGuildleve(Win335_EventFramework *self, const Win335_LeveWork_KnownFields *newWork, const Win335_LeveWork_KnownFields *oldWork, unsigned __int16 workIndex)",
        },
        {
            "address": "0x140604610",
            "declaration": "void __fastcall Client__Game__Event__EventFramework__OnLeveCompleteFlagsInitialized(Win335_EventFramework *self)",
        },
        {
            "address": "0x140604620",
            "declaration": "void __fastcall Client__Game__Event__EventFramework__OnSyncLeveComplete(Win335_EventFramework *self, unsigned __int16 leveId)",
        },
        {
            "address": "0x14004C3F0",
            "declaration": "void __fastcall Client__UI__Info__InfoProxyItemSearch__RequestResult(Win335_InfoProxyItemSearch *self, unsigned __int32 catalogId, unsigned __int8 subQuality, unsigned __int8 materiaCount, unsigned __int8 count, unsigned __int32 result)",
        },
        {
            "address": "0x140037CA0",
            "declaration": "void __fastcall Client__UI__Info__InfoProxyItemSearch__SetRetainerDataList(Win335_InfoProxyItemSearch *self, const void *records, unsigned __int32 count)",
        },
        {
            "address": "0x14004C710",
            "declaration": "void __fastcall Client__UI__Info__InfoProxyItemSearch__MarketBuyResult(Win335_InfoProxyItemSearch *self, unsigned __int32 catalogId, unsigned __int32 result)",
        },
        {
            "address": "0x140037B00",
            "declaration": "void __fastcall Client__UI__Info__InfoProxyItemSearch__MarketCallback(Win335_InfoProxyItemSearch *self, unsigned __int8 type)",
        },
        {
            "address": "0x14004C6C0",
            "declaration": "void __fastcall Client__UI__Info__InfoProxyItemSearch__SetItemHistory(Win335_InfoProxyItemSearch *self, const void *records, unsigned __int32 count)",
        },
        {
            "address": "0x140037A80",
            "declaration": "void __fastcall Client__UI__Info__InfoProxyItemSearch__SetRetainerSalesHistory(Win335_InfoProxyItemSearch *self, const void *records, unsigned __int32 count)",
        },
        {
            "address": "0x140037DB0",
            "declaration": "void __fastcall Client__UI__Info__InfoProxyItemSearch__SetRetainerData(Win335_InfoProxyItemSearch *self, unsigned __int64 retainerId, unsigned __int8 registerMarket, unsigned __int8 isMarket)",
        },
        {
            "address": "0x140046470",
            "declaration": "void __fastcall Client__UI__Info__InfoModule__PrintError(Win335_InfoModule *self, unsigned __int32 infoCode)",
        },
        {
            "address": "0x1400464C0",
            "declaration": "void __fastcall Client__UI__Info__InfoModule__PrintErrorWithParam(Win335_InfoModule *self, unsigned __int32 infoCode, unsigned __int32 parameter)",
        },
        {
            "address": "0x14004C090",
            "declaration": "void __fastcall Client__UI__Info__InfoProxyItemSearch__Add(Win335_InfoProxyItemSearch *self, const void *records, unsigned __int32 count)",
        },
        {
            "address": "0x140037740",
            "declaration": "void __fastcall Client__UI__Info__InfoProxyItemSearch__Sub(Win335_InfoProxyItemSearch *self, const void *records, unsigned __int32 count)",
        },
        {
            "address": "0x140037750",
            "declaration": "void __fastcall Client__UI__Info__InfoProxyItemSearch__Clear(Win335_InfoProxyItemSearch *self)",
        },
        {
            "address": "0x14004C210",
            "declaration": "unsigned __int8 __fastcall Client__UI__Info__InfoProxyItemSearch__Request(Win335_InfoProxyItemSearch *self)",
        },
        {
            "address": "0x140037760",
            "declaration": "void __fastcall Client__UI__Info__InfoProxyItemSearch__Finish(Win335_InfoProxyItemSearch *self)",
        },
        {
            "address": "0x14004C2B0",
            "declaration": "void __fastcall Client__UI__Info__InfoProxyItemSearch__AddPage(Win335_InfoProxyItemSearch *self, const void *packet)",
        },
        {
            "address": "0x140037870",
            "declaration": "void __fastcall Client__UI__Info__InfoProxyItemSearch__SetItemHistory_Impl(Win335_InfoProxyItemSearch *self, const void *records, unsigned __int32 count, unsigned __int8 itemHistoryMode)",
        },
        {
            "address": "0x14007C740",
            "declaration": "unsigned __int32 __fastcall Client__UI__Info__InfoProxyInterface__Count(const Win335_InfoProxyInterface *self)",
        },
        {
            "address": "0x1409EC240",
            "declaration": "void __fastcall Client__Game__Object__Treasure__FadeOut(Win335_Treasure *self)",
        },
        {
            "address": "0x1409ED5D0",
            "declaration": "void __fastcall Client__Game__Object__Treasure__SetMaxTimer(Win335_Treasure *self, float maxTimer)",
        },
        {
            "address": "0x1409EBEF0",
            "declaration": "Win335_TreasureItemSlot *__fastcall Client__Game__Object__Treasure__GetItemSlot(Win335_Treasure *self, unsigned __int32 index)",
        },
        {
            "address": "0x1409EC030",
            "declaration": "void __fastcall Client__Game__Object__Treasure__Open(Win335_Treasure *self)",
        },
        {
            "address": "0x1409EC080",
            "declaration": "void __fastcall Client__Game__Object__Treasure__OpenWithTimers(Win335_Treasure *self, float timer, float maxTimer, float maxLootTimer)",
        },
        {
            "address": "0x1409EBA30",
            "declaration": "Win335_GameObject_KnownFields *__fastcall Client__Game__Object__StaticObjectManager__GetObject(Win335_StaticObjectManager *self, unsigned __int32 index)",
        },
        {
            "address": "0x140DC6040",
            "declaration": "Win335_GameObject_KnownFields *__fastcall Client__Game__Object__StandObjectManager__GetObject(Win335_StandObjectManager *self, unsigned __int32 index)",
        },
        {
            "address": "0x14065F1E0",
            "declaration": "void __fastcall Client__Game__Event__EventHandlerModule__InitializeEventHandlers(Win335_EventFramework *self, unsigned __int16 handlerType)",
        },
        {
            "address": "0x14065FF10",
            "declaration": "void __fastcall Client__Game__Event__EventFramework__onQuestUpdate(Win335_EventFramework *self, signed __int32 updateType, unsigned __int16 questId, unsigned __int16 workIndex, Win335_EventHandler *handler)",
        },
        {
            "address": "0x1406604E0",
            "declaration": "void __fastcall Win335_EventFramework__InitializeQuestHandlersIfReady(Win335_EventFramework *self)",
        },
        {
            "address": "0x140656ED0",
            "declaration": "Win335_EventHandler *__fastcall Client__Game__Event__EventHandlerModule__GetEventHandler(const Win335_EventFramework *self, unsigned __int32 handlerId)",
        },
        {
            "address": "0x14065EA80",
            "declaration": "void __fastcall Client__Game__Event__EventHandlerModule__UpdateEventVisibility(Win335_EventFramework *self, unsigned __int16 handlerType)",
        },
        {
            "address": "0x1409EC2B0",
            "declaration": "void __fastcall Win335_Treasure__ApplyLootItems(Win335_Treasure *self, const Win335_LootItems_KnownFields *packet)",
        },
        {
            "address": "0x140CC03D0",
            "declaration": "void __fastcall Client__Game__Network__Packet__OnTreasureHuntReward(const Win335_TreasureHuntReward_KnownFields *packet)",
        },
        {
            "address": "0x14054FE20",
            "declaration": "void __fastcall Client__Game__Object__TreasureManager__OnTreasureHuntReward(Win335_TreasureManager *self, unsigned __int32 eventHandlerId, unsigned __int32 rank, signed __int32 experience, signed __int32 money, unsigned __int32 itemCatalogueId, unsigned __int32 itemStack)",
        },
        {
            "address": "0x1409DE380",
            "declaration": "void __fastcall Client__Game__Object__GameObject__SetEntityId(Win335_GameObject_KnownFields *self, unsigned __int32 entityId)",
        },
        {
            "address": "0x1409DE350",
            "declaration": "void __fastcall Client__Game__Object__GameObject__SetLayoutId(Win335_GameObject_KnownFields *self, unsigned __int32 layoutId)",
        },
        {
            "address": "0x1409DE4B0",
            "declaration": "void __fastcall Client__Game__Object__GameObject__SetContentId(Win335_GameObject_KnownFields *self, unsigned __int32 contentId)",
        },
        {
            "address": "0x1409DE4F0",
            "declaration": "void __fastcall Client__Game__Object__GameObject__SetPermissionInvisibility(Win335_GameObject_KnownFields *self, unsigned __int8 permissionInvisibility)",
        },
        {
            "address": "0x1409EE530",
            "declaration": "signed __int32 __fastcall Client__Game__Object__StaticObjectManager__CreateTreasure(Win335_StaticObjectManager *self, unsigned __int32 entityId, unsigned __int32 baseId, unsigned __int16 layerId, unsigned __int32 layoutId, signed __int32 index)",
        },
        {
            "address": "0x1409EBE30",
            "declaration": "void __fastcall Client__Game__Object__Treasure__Setup(Win335_Treasure *self, unsigned __int32 baseId, unsigned __int16 layerId, unsigned __int32 layoutId)",
        },
        {
            "address": "0x1409EC260",
            "declaration": "void __fastcall Client__Game__Object__Treasure__OnCreated(Win335_Treasure *self)",
        },
    ]
    internal_function_types = [
        {
            "address": "0x140CC67D0",
            "declaration": "Win335_ItemAssemblyContext *__fastcall Win335_ItemPacketAssembler__AcquireContext(Win335_ItemPacketAssembler *self, unsigned __int32 targetActorId)",
        },
        {
            "address": "0x140CC2070",
            "declaration": "Win335_ItemAssemblyFragment *__fastcall Win335_ItemPacketAssembler__AppendFragment(Win335_ItemPacketAssembler *self, Win335_ItemAssemblyContext *context, const void *payload)",
        },
        {
            "address": "0x140CC6860",
            "declaration": "void __fastcall Win335_ItemPacketAssembler__ReleaseContext(Win335_ItemPacketAssembler *self, Win335_ItemAssemblyContext *context)",
        },
    ]

    plan = {
        "schemaVersion": 1,
        "policy": "Only Windows-confirmed fields are emitted. Unknown gaps remain byte arrays; no PS3-only trailing size is asserted.",
        "summary": {
            "opcodeTypes": 2,
            "knownFieldTypes": len(type_records),
            "typedPayloadHandlers": len(payload_handlers),
            "typedIpcWrappers": len(ipc_wrapper_types),
            "typedSupportingFunctions": len(supporting_types),
            "typedSubsystemFunctions": len(subsystem_function_types),
            "typedInternalFunctions": len(internal_function_types),
            "typedGlobals": 4,
            "namedGlobals": 4,
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
        "subsystemFunctionTypes": subsystem_function_types,
        "internalFunctionTypes": internal_function_types,
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
        "globalNames": [
            {
                "address": "0x1411EA990",
                "name": "Client__UI__Info__InfoProxyItemSearch__vftable",
                "evidence": "Recovered vtable whose Add/Sub/Clear/Request/Finish/Count/AddPage slots match the PS3 DWARF class vtable and Windows method behavior.",
            },
            {
                "address": "0x1417A4AA8",
                "name": "Client__Game__Object__gTreasureManager",
                "evidence": "Receiver passed to the PS3-linked TreasureManager entity-ID lookup by treasure packet handlers.",
            },
            {
                "address": "0x14180C360",
                "name": "Client__Game__Object__gStaticObjectManager",
                "evidence": "Receiver used by the PS3-linked StaticObjectManager indexed accessor and treasure creation/lookup paths.",
            },
            {
                "address": "0x14181BC90",
                "name": "Client__Game__Object__gStandObjectManager",
                "evidence": "Receiver used by the PS3-linked StandObjectManager indexed accessor and TreasureManager's second scan.",
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

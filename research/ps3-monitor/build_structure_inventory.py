#!/usr/bin/env python3
"""Build a packet-structure comparison ledger from the PS3 DWARF export."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ZONE_HEADER = Path("src/common/Network/PacketDef/Zone/ServerZoneDef.h")
CHAT_HEADER = Path("src/common/Network/PacketDef/Chat/ServerChatDef.h")
HISTORICAL_REF = "fe26d3ba840deb1eaca6db6d8a486c8e068482f9"

SAPPHIRE_TYPES = {
    "Create": "FFXIVIpcPlayerSpawn",
    "UpdateOnlineStatus": "FFXIVIpcSetOnlineStatus",
    "ChatFrom": "FFXIVChatFrom",
    "Chat": "FFXIVChatToChannel",
    "TellNotFound": "FFXIVIpcTellNotFound",
    "RecvBusyStatus": "FFXIVRecvBusyStatus",
    "RecvFinderStatus": "FFXIVRecvFinderStatus",
    "QuestCompleteFlags": "FFXIVIpcQuestCompleteList",
    "QuestCompleteFlag": "FFXIVIpcQuestFinish",
    "LegacyQuestCompleteFlags": "FFXIVIpcLegacyQuestCompleteList",
    "DailyQuest": "FFXIVIpcDailyQuest",
}

# Fields independently observed in the Windows handler. An offset differing
# from PS3 is an intentional version delta, not a validation failure.
WINDOWS_FIELDS: dict[str, dict[str, tuple[int, str]]] = {
    "InviteResult": {"Result": (0x0, "32-bit result load"), "AuthType": (0x4, "AuthType switch")},
    "InviteReplyResult": {"AuthType": (0x4, "AuthType switch 1/2/4/5/6")},
    "InviteUpdate": {"AuthType": (0xC, "AuthType switch")},
    "GetCommonlistResult": {"ListType": (0xC, "proxy-selection switch")},
    "SetProfileResult": {
        "Result": (0x10, "result branch"),
        "CurrentSelectClassID": (0x14, "detail-proxy update"),
        "Region": (0x15, "language/region update"),
        "SearchComment": (0x16, "comment pointer"),
    },
    "PlayerStatusUpdate": {
        "ClassJob": (0x0, "class/job update"),
        "Lv": (0x2, "level update"),
        "LvSync": (0x6, "3.x synchronized-level load"),
        "Exp": (0x8, "experience update"),
        "RestPoint": (0xC, "rested experience update"),
    },
    "PlayerStatus": {"Crest": (0x8, "crest update")},
    "LeveCompleteFlag": {
        "bitIndex": (0x0, "leve-completion bit index"),
        "completed": (0x2, "set/clear boolean"),
    },
    "QuestCompleteFlags": {
        "completeFlagArray": (0x0, "Windows copies 0x136 bytes; PS3 copies 0xC8 bytes"),
    },
    "QuestCompleteFlag": {
        "bitIndex": (0x0, "quest-completion bit index"),
        "completed": (0x2, "set/clear boolean"),
        "update": (0x3, "EventFramework update boolean"),
    },
    "DailyQuests": {
        "update": (0x0, "daily-quest synchronization update boolean"),
        "dailyQuestArray": (0x4, "12 DailyQuest records in Windows versus 6 in PS3"),
    },
    "DailyQuest": {
        "index": (0x0, "daily-quest slot index"),
        "update": (0x1, "daily-quest synchronization update boolean"),
        "dailyQuest": (0x4, "quest ID and flags record"),
    },
    "QuestRepeatFlags": {
        "update": (0x0, "repeat-flag synchronization update boolean"),
        "repeatFlagArray": (0x1, "one-byte repeat-quest mask"),
    },
    "ChatFrom": {
        "fromCharacterID": (0x0, "sender ID use"),
        "type": (0x8, "chat-type branch"),
        "fromName": (0x9, "UTF-8 sender name"),
        "message": (0x29, "UTF-8 message"),
    },
    "Chat": {
        "channelID": (0x0, "channel proxy lookup"),
        "speakerCharacterID": (0x8, "speaker log ID"),
        "speakerEntityID": (0x10, "character lookup"),
        "type": (0x14, "chat-type branch"),
        "speakerName": (0x15, "UTF-8 speaker name"),
        "message": (0x35, "UTF-8 message"),
    },
    "TellNotFound": {"toName": (0x0, "payload converted to UTF-8 string")},
    "RecvBusyStatus": {"toName": (0x0, "payload converted to UTF-8 string")},
    "RecvFinderStatus": {"toName": (0x0, "payload converted to UTF-8 string")},
    "GetProfileResult": {
        "OnlineStatus": (0x0, "status update"),
        "SelectClassID": (0x8, "selected-class update"),
        "CurrentSelectClassID": (0x10, "current-class update"),
        "Region": (0x11, "language/region update"),
        "SearchComment": (0x12, "comment pointer"),
    },
    "GetSearchCommentResult": {
        "TargetEntityID": (0x0, "entity ID argument"),
        "SearchComment": (0x4, "comment pointer"),
    },
    "ChatChannelResult": {
        "ChannelID": (0x0, "channel-state update"),
        "CommunityID": (0x8, "community comparison"),
        "TargetCharacterID": (0x10, "target comparison"),
        "UpPacketNo": (0x18, "209/210 branch"),
        "Result": (0x1C, "result branch"),
    },
    "SendSystemMessage": {"MessageParam": (0x0, "bit 1/4 tests"), "Message": (0x1, "UTF-8 message")},
    "SendLoginMessage": {"MessageParam": (0x0, "bit 1/4 tests"), "Message": (0x1, "UTF-8 message")},
    "UpdateOnlineStatus": {"OnlineStatus": (0x0, "64-bit status forwarding")},
    "PartyRecruitResult": {"Type": (0x10, "recruitment-mode switch"), "Result": (0x14, "result/error branch")},
    "RequestItmeResult": {"Param": (0x8, "wishlist parameter"), "Type": (0x10, "wishlist-mode switch"), "Result": (0x14, "result/error branch")},
    "AllianceReadyCheckResult": {
        "EntityID": (0x0, "entity-ID array"),
        "Ready": (0x20, "ready-state array"),
        "Count": (0x28, "entry count"),
    },
    "PcPartyResult": {"UpPacketNo": (0x0, "party operation"), "Result": (0x4, "error/result branch")},
    "PcPartyUpdate": {
        "ExecuteCharacterID": (0x0, "executor ID"),
        "TargetCharacterID": (0x8, "target ID"),
        "ExecuteIdentity": (0x10, "executor identity"),
        "TargetIdentity": (0x11, "target identity"),
        "UpdateStatus": (0x12, "party-update switch"),
        "Count": (0x13, "party count"),
        "ExecuteCharacterName": (0x14, "executor name"),
        "TargetCharacterName": (0x34, "target name"),
    },
    "InviteCancelResult": {"Result": (0x0, "result field layout"), "AuthType": (0x4, "party AuthType test")},
    "CreateTreasure": {
        "BaseId": (0x0, "static-object creation and final base-ID store"),
        "EntityId": (0x4, "static-object creation and GameObject::SetEntityId"),
        "LayoutId": (0x8, "GameObject::SetLayoutId argument"),
        "Index": (0xE, "static-object slot creation and lookup index"),
        "IsOpened": (0xF, "conditional Treasure::Open branch"),
        "DropperNameId": (0x10, "Treasure dropper-name field store"),
        "itemNumber": (0x11, "catalogue-ID loop bound and Treasure item count"),
        "PermissionInvisibility": (0x12, "GameObject::SetPermissionInvisibility argument"),
        "Loot": (0x13, "Treasure loot-mode field store"),
        "TreasureType": (0x14, "Treasure type store and OnCreated state test"),
        "Timer": (0x18, "Treasure current-timer store"),
        "MaxTimer": (0x1C, "Treasure::SetMaxTimer argument"),
        "MaxLootTimer": (0x20, "Treasure maximum-loot-timer store"),
        "ContentId": (0x24, "GameObject::SetContentId argument"),
        "SharedGroup": (0x28, "Treasure shared-group identifier store"),
        "catalogueIds": (0x34, "catalogue-ID copy into indexed Treasure item slots"),
    },
    "OpenTreasure": {
        "timer": (0x0, "timer passed to Treasure::OpenWithTimers"),
        "maxTimer": (0x4, "maximum timer passed to Treasure::OpenWithTimers"),
        "maxLootTimer": (0x8, "maximum loot timer passed to Treasure::OpenWithTimers"),
        "entityId": (0x10, "TreasureManager entity-ID lookup"),
    },
    "TreasureOpenRight": {
        "treasureEntityId": (0x0, "TreasureManager entity-ID lookup"),
        "openRight": (0x4, "open-right result switch"),
        "argument": (0x8, "result-specific log/message argument"),
        "timer": (0xC, "Treasure current-timer store"),
        "maxTimer": (0x10, "Treasure::SetMaxTimer argument"),
        "maxLootTimer": (0x14, "Treasure maximum-loot-timer store"),
    },
    "LootItems": {
        "entityId": (0x0, "TreasureManager entity-ID lookup"),
        "itemNumber": (0x4, "item-copy loop bound and Treasure item count"),
        "timer": (0x8, "Treasure current-timer store"),
        "maxTimer": (0xC, "Treasure maximum-timer store"),
        "maxLootTimer": (0x10, "Treasure maximum-loot-timer store"),
        "catalogueIds": (0x14, "catalogue-ID copy into indexed Treasure item slots"),
    },
    "TreasureHuntReward": {
        "Rank": (0x4, "rank argument passed to TreasureManager reward handling"),
        "Exp": (0x8, "experience reward argument"),
        "Money": (0xC, "currency reward argument"),
        "ItemCatalogId": (0x10, "item catalogue reward argument"),
        "ItemStack": (0x14, "item stack reward argument"),
    },
}

WINDOWS_EXTRA_FIELDS = {
    "Create": [
        {"name": "OwnerId", "offset": "0x14", "width": 4, "evidence": "local-owner comparison"},
        {"name": "ObjType", "offset": "0x33", "width": 1, "evidence": "ObjType == 2 test"},
    ],
    "QuestCompleteFlags": [
        {
            "name": "unknownCompleteMask",
            "offset": "0x136",
            "width": 32,
            "evidence": "Windows dispatcher forwards a second 32-byte region at payload +0x136",
        }
    ],
    "DailyQuests": [
        {
            "name": "dailyQuestArray[6..11]",
            "offset": "0x1C",
            "width": 24,
            "evidence": "Windows processes 12 four-byte records; PS3 processes 6",
        }
    ],
    "QuestCompleteFlag": [
        {
            "name": "unknown4",
            "offset": "0x4",
            "width": 1,
            "evidence": "optional 3.x bitset/UI update index",
        }
    ],
    "CreateTreasure": [
        {
            "name": "unknown15",
            "offset": "0x15",
            "width": 1,
            "type": "uint8_t",
            "evidence": "3.x-only byte forwarded to the object state/visibility helper at 0x1409DFF20",
        }
    ],
    "TreasureHuntReward": [
        {
            "name": "eventHandlerId",
            "offset": "0x0",
            "width": 4,
            "type": "uint32_t",
            "evidence": "3.x EventFramework handler lookup before displaying the reward",
        }
    ],
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def source_location(text: str, type_name: str) -> int | None:
    pattern = re.compile(rf"\bstruct\s+{re.escape(type_name)}\b")
    for number, line in enumerate(text.splitlines(), 1):
        if pattern.search(line):
            return number
    return None


def declared_packet_types(text: str) -> dict[str, str]:
    """Map protocol role names to the actual Sapphire struct names.

    Sapphire intentionally uses descriptive names such as FFXIVIpcActorControl
    for the protocol role named Order. Discovering the FFXIVIpcBasePacket
    specialization prevents those aliases from being reported as missing.
    """
    pattern = re.compile(
        r"\bstruct\s+(\w+)\s*:\s*FFXIVIpcBasePacket\s*<\s*(\w+)\s*>",
        re.MULTILINE,
    )
    return {match.group(2): match.group(1) for match in pattern.finditer(text)}


def git_show(path: Path) -> str:
    result = subprocess.run(
        ["git", "show", f"{HISTORICAL_REF}:{path.as_posix()}"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout


def sapphire_type(packet: str) -> str:
    return SAPPHIRE_TYPES.get(packet, f"FFXIVIpc{packet}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ps3", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).with_name("packet_structures.json")
    )
    args = parser.parse_args()

    ps3 = load_json(args.ps3)
    current_text = {
        "zone-down": (ROOT / ZONE_HEADER).read_text(encoding="utf-8"),
        "chat-down": (ROOT / CHAT_HEADER).read_text(encoding="utf-8"),
    }
    historical_text = {
        "zone-down": git_show(ZONE_HEADER),
        "chat-down": git_show(CHAT_HEADER),
    }
    source_paths = {"zone-down": ZONE_HEADER, "chat-down": CHAT_HEADER}
    current_types = {
        channel: declared_packet_types(text) for channel, text in current_text.items()
    }
    historical_types = {
        channel: declared_packet_types(text) for channel, text in historical_text.items()
    }

    missing: list[str] = []
    changed_offsets: list[dict[str, Any]] = []
    for structure in ps3["structures"]:
        packet = structure["packet"]
        channel = structure["channel"]
        fallback_type = sapphire_type(packet)
        current_type = current_types[channel].get(packet, fallback_type)
        historical_type = historical_types[channel].get(packet, current_type)
        current_line = source_location(current_text[channel], current_type)
        historical_line = source_location(historical_text[channel], historical_type)
        structure["sapphire"] = {
            "type": current_type,
            "path": source_paths[channel].as_posix(),
            "currentLine": current_line,
            "currentStatus": "present" if current_line else "missing",
            "threePointThreeLine": historical_line,
            "threePointThreeStatus": "present" if historical_line else "missing",
        }
        if current_line is None:
            missing.append(f"{channel}:{packet}")
        observed = WINDOWS_FIELDS.get(packet, {})
        for member in structure.get("members", []):
            validation = observed.get(member["name"])
            if validation is None:
                member["windowsValidation"] = {"status": "unreviewed"}
                continue
            offset, evidence = validation
            ps3_offset = int(member["offset"], 16)
            status = "confirmed-same-offset" if offset == ps3_offset else "confirmed-version-delta"
            member["windowsValidation"] = {
                "status": status,
                "offset": f"0x{offset:X}",
                "evidence": evidence,
            }
            if offset != ps3_offset:
                changed_offsets.append(
                    {
                        "packet": packet,
                        "field": member["name"],
                        "ps3Offset": member["offset"],
                        "windowsOffset": f"0x{offset:X}",
                    }
                )
        structure["windowsExtraFields"] = WINDOWS_EXTRA_FIELDS.get(packet, [])
        structure["comparisonStatus"] = (
            "partially-windows-validated" if observed or structure["windowsExtraFields"] else "layout-unreviewed"
        )
        structure["productionDecision"] = (
            "Existing Sapphire declaration; retain unless a complete Windows comparison proves a correction."
            if current_line
            else "Do not add yet: missing declaration recorded, but complete Windows size/layout is not proven."
        )

    output = {
        "schemaVersion": 1,
        "inputs": {
            "ps3": "PS3 Monitor DWARF imported into IDA",
            "windows": "field accesses in confirmed Windows handlers",
            "sapphireCurrent": "working tree",
            "sapphireThreePointThree": HISTORICAL_REF,
        },
        "policy": (
            "PS3 fields describe 2.3. A field is a 3.x fact only when windowsValidation is "
            "confirmed; unreviewed fields must not be promoted into production definitions."
        ),
        "summary": {
            "structures": len(ps3["structures"]),
            "missingCurrentDeclarations": sorted(missing),
            "confirmedVersionDeltas": changed_offsets,
        },
        "structures": ps3["structures"],
    }
    with args.output.open("w", encoding="utf-8", newline="\n") as output_file:
        json.dump(output, output_file, indent=2)
        output_file.write("\n")
    print(json.dumps(output["summary"], indent=2))


if __name__ == "__main__":
    main()

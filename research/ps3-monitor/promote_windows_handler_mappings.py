#!/usr/bin/env python3
"""Record high-confidence Windows handlers that lack a PS3 function counterpart."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

INLINE_MAPPINGS: list[dict[str, Any]] = [
    {
        "opcode": "0x02D6",
        "packet": "EnableLogout",
        "windowsCaseEa": "0x140DD94EA",
        "evidence": [
            "The Windows dispatcher handles this case inline by resolving the framework/UI command interface and invoking command 7 with the packet.",
        ],
    },
    {
        "opcode": "0x02D7",
        "packet": "LogMessage",
        "windowsCaseEa": "0x140DD9593",
        "evidence": [
            "The Windows dispatcher handles this case inline through the same framework/UI command interface using command 4.",
        ],
    },
    {
        "opcode": "0x02E7",
        "packet": "CancelLogoutCountdown",
        "windowsCaseEa": "0x140DD947E",
        "evidence": [
            "The Windows dispatcher handles this case inline through the same framework/UI command interface using command 8.",
        ],
    },
]

MAPPINGS: list[dict[str, Any]] = [
    {
        "opcodes": ["0x01AA", "0x01AB"],
        "packets": ["RetainerList", "RetainerData"],
        "windowsAddress": "0x140CC8730",
        "windowsName": "Client__Game__Network__Packet__ReceiveRetainerPackets",
        "evidence": [
            "The Windows dispatcher groups exactly RetainerList and RetainerData into this wrapper.",
            "Its downstream function explicitly switches on IPC opcodes 0x01AA and 0x01AB and accumulates retainer records by owner/context ID.",
        ],
    },
    {
        "opcodes": ["0x01AC", "0x01AD"],
        "packets": ["MarketPriceHeader", "MarketPrice"],
        "windowsAddress": "0x140CC8710",
        "windowsName": "Client__Game__Network__Packet__ReceiveMarketPricePackets",
        "evidence": [
            "The Windows dispatcher groups exactly MarketPriceHeader and MarketPrice into this wrapper.",
            "Its downstream function explicitly switches on 0x01AC and 0x01AD and assembles the associated market-price records.",
        ],
    },
    {
        "opcodes": ["0x01AF", "0x01B0", "0x01B3", "0x01B7"],
        "packets": ["NormalItem", "ItemSize", "GilItem", "AliasItem"],
        "windowsAddress": "0x140CC8FE0",
        "windowsName": "Client__Game__Network__Packet__ReceiveItemStoragePackets",
        "evidence": [
            "The Windows dispatcher groups these four Sapphire item-storage opcodes into this wrapper.",
            "The downstream switch handles 0x01AF/0x01B3/0x01B7 as item records and 0x01B0 as the item-count/size record before committing storage state.",
        ],
    },
    {
        "opcodes": ["0x01B1", "0x01B2"],
        "packets": ["ItemOperationBatch", "ItemOperation"],
        "windowsAddress": "0x140CC86F0",
        "windowsName": "Client__Game__Network__Packet__ReceiveItemOperationPackets",
        "evidence": [
            "The Windows dispatcher groups exactly ItemOperationBatch and ItemOperation into this wrapper.",
            "The downstream function explicitly switches on 0x01B1 and 0x01B2, copies operation records, and commits the completed batch.",
        ],
    },
    {
        "opcodes": ["0x01C0"],
        "packets": ["TreasureFadeOut"],
        "windowsAddress": "0x140CC03A0",
        "windowsName": "Client__Game__Network__Packet__TreasureFadeOut",
        "evidence": [
            "Sapphire identifies 0x01C0 as TreasureFadeOut.",
            "The Windows target resolves the dispatcher target actor through the game-object table and invokes its fade/removal path.",
        ],
    },
    {
        "opcodes": ["0x029E"],
        "packets": ["InspectQuests"],
        "windowsAddress": "0x140CC31D0",
        "windowsName": "Client__Game__Network__Packet__InspectQuests",
        "evidence": [
            "The dispatcher extracts actor ID, content ID, a payload array, and count 30 for Sapphire opcode InspectQuests.",
            "The target iterates 12-byte quest records and formats quest ID, sequence, flags, class/job, and variables using an explicit quest diagnostic string.",
        ],
    },
    {
        "opcodes": ["0x029F"],
        "packets": ["InspectGuildleves"],
        "windowsAddress": "0x140CC35A0",
        "windowsName": "Client__Game__Network__Packet__InspectGuildleves",
        "evidence": [
            "The dispatcher extracts actor ID, content ID, a payload array, and count 16 for Sapphire opcode InspectGuildleves.",
            "The target iterates leve records and formats ID, sequence, flags, seed, and class using an explicit leve diagnostic string.",
        ],
    },
    {
        "opcodes": ["0x02A0"],
        "packets": ["InspectReward"],
        "windowsAddress": "0x140CC6300",
        "windowsName": "Client__Game__Network__Packet__InspectReward",
        "evidence": [
            "The dispatcher extracts actor ID, content ID, a reward bitset, and count 64 for Sapphire opcode InspectReward.",
            "The target enumerates every reward bit and formats explicit reward diagnostics for the inspected character.",
        ],
    },
    {
        "opcodes": ["0x02A1"],
        "packets": ["InspectBeastReputation"],
        "windowsAddress": "0x140CC3910",
        "windowsName": "Client__Game__Network__Packet__InspectBeastReputation",
        "evidence": [
            "The dispatcher extracts actor ID, content ID, rank/value arrays, and count 8 for Sapphire opcode InspectBeastReputation.",
            "The target resolves beast-reputation names and formats each rank and value using an explicit brep diagnostic string.",
        ],
    },
    {
        "opcodes": ["0x0336"],
        "packets": ["Frontline01Result"],
        "windowsAddress": "0x140CBEE10",
        "windowsName": "Client__Game__Network__Packet__ReceiveFrontline01Result",
        "evidence": [
            "Current and ThreePointThree Sapphire enums identify 0x0336 as Frontline01Result.",
            "The Windows target copies fifteen consecutive result dwords into a dedicated global result block; this is a Windows semantic label only because the PS3 packet layout is materially different.",
        ],
    },
]


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as output:
        json.dump(value, output, indent=2)
        output.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--matches", type=Path, default=Path(__file__).with_name("packet_matches.json")
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    mapping = load(args.matches)
    existing = {int(item["windowsAddress"], 16) for item in mapping.get("windowsMappings", [])}
    additions = []
    for item in MAPPINGS:
        if int(item["windowsAddress"], 16) in existing:
            continue
        additions.append(
            {
                **item,
                "channel": "zone-down",
                "confidence": "high",
                "mappingKind": "windows-semantic",
            }
        )
    existing_inline = {
        item["opcode"] for item in mapping.get("windowsInlineMappings", [])
    }
    inline_additions = [
        {
            **item,
            "channel": "zone-down",
            "confidence": "high",
            "mappingKind": "windows-inline",
        }
        for item in INLINE_MAPPINGS
        if item["opcode"] not in existing_inline
    ]
    print(
        json.dumps(
            {
                "promotable": len(additions),
                "entries": additions,
                "inlinePromotable": len(inline_additions),
                "inlineEntries": inline_additions,
            },
            indent=2,
        )
    )
    if args.apply:
        mapping.setdefault("windowsMappings", []).extend(additions)
        mapping["windowsMappings"].sort(key=lambda item: int(item["opcodes"][0], 16))
        mapping.setdefault("windowsInlineMappings", []).extend(inline_additions)
        mapping["windowsInlineMappings"].sort(key=lambda item: int(item["opcode"], 16))
        write(args.matches, mapping)


if __name__ == "__main__":
    main()

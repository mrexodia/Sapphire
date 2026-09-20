#!/usr/bin/env python3
"""Record supporting functions recovered while expanding packet semantic islands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PS3_LINKED: list[dict[str, Any]] = [
    {
        "role": "Framework UI-module accessor",
        "ps3Address": "0x00017A78",
        "ps3Name": "Client::System::Framework::Framework::GetUIModule",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:00017A78",
        "windowsAddress": "0x140013960",
        "windowsName": "Client__System__Framework__Framework__GetUIModule",
        "confidence": "high",
        "evidence": [
            "The PS3 DWARF function and Windows function are one-load accessors returning the UI-module pointer from the Framework object; the member offset changes from PS3 +0x1F20 to Windows +0x2C00.",
            "Both packet dispatchers call this accessor before the same UI command-interface paths, including ChatToChannel and logout-countdown cases.",
        ],
    },
    {
        "role": "EventFramework singleton accessor",
        "ps3Address": "0x00A516F4",
        "ps3Name": "Client::Game::Event::EventFramework::GetInstance",
        "ps3IdbUrl": "idb://ffxivgame.ppu.elf.i64:00A516F4",
        "windowsAddress": "0x1406044E0",
        "windowsName": "Client__Game__Event__EventFramework__GetInstance",
        "confidence": "high",
        "evidence": [
            "The PS3 DWARF function and Windows function both return the process-wide EventFramework singleton.",
            "Confirmed quest, leve, daily-quest, repeat-flag, and instance-content packet handlers obtain their EventFramework receiver through this function.",
        ],
    }
]

WINDOWS_SUPPORTING: list[dict[str, Any]] = [
    {
        "windowsAddress": "0x140CC7090",
        "windowsName": "Client__Game__Network__Packet__ReceiveRetainerPackets_Impl",
        "roles": ["RetainerList", "RetainerData"],
        "confidence": "high",
        "mappingKind": "windows-supporting",
        "evidence": [
            "The confirmed RetainerList/RetainerData wrapper calls only this implementation.",
            "This function switches on 0x01AA/0x01AB, finds or creates the owner-context accumulator, copies retainer records, and commits the completed group.",
        ],
    },
    {
        "windowsAddress": "0x140CC7200",
        "windowsName": "Client__Game__Network__Packet__ReceiveMarketPricePackets_Impl",
        "roles": ["MarketPriceHeader", "MarketPrice"],
        "confidence": "high",
        "mappingKind": "windows-supporting",
        "evidence": [
            "The confirmed MarketPriceHeader/MarketPrice wrapper calls only this implementation.",
            "This function switches on 0x01AC/0x01AD, assembles market-price records by owner context, and commits the completed group.",
        ],
    },
    {
        "windowsAddress": "0x140CC7330",
        "windowsName": "Client__Game__Network__Packet__ReceiveItemOperationPackets_Impl",
        "roles": ["ItemOperationBatch", "ItemOperation"],
        "confidence": "high",
        "mappingKind": "windows-supporting",
        "evidence": [
            "The confirmed ItemOperationBatch/ItemOperation wrapper calls only this implementation.",
            "This function switches on 0x01B1/0x01B2, copies operation records into an owner-context accumulator, and commits the completed batch.",
        ],
    },
    {
        "windowsAddress": "0x140CC8870",
        "windowsName": "Client__Game__Network__Packet__ReceiveItemStoragePackets_Impl",
        "roles": ["NormalItem", "ItemSize", "GilItem", "AliasItem"],
        "confidence": "high",
        "mappingKind": "windows-supporting",
        "evidence": [
            "The confirmed item-storage wrapper calls only this implementation.",
            "This function switches on 0x01AF/0x01B0/0x01B3/0x01B7, processes item or size records, and commits complete storage state.",
        ],
    },
]


def write_json(path: Path, value: Any) -> None:
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

    mapping = json.loads(args.matches.read_text(encoding="utf-8"))
    existing_ps3 = {
        int(item["windowsAddress"], 16) for item in mapping.get("supportingFunctions", [])
    }
    existing_windows = {
        int(item["windowsAddress"], 16)
        for item in mapping.get("windowsSupportingFunctions", [])
    }
    ps3_additions = [
        item for item in PS3_LINKED if int(item["windowsAddress"], 16) not in existing_ps3
    ]
    windows_additions = [
        item
        for item in WINDOWS_SUPPORTING
        if int(item["windowsAddress"], 16) not in existing_windows
    ]
    print(
        json.dumps(
            {
                "ps3LinkedPromotable": len(ps3_additions),
                "windowsSupportingPromotable": len(windows_additions),
                "ps3Linked": ps3_additions,
                "windowsSupporting": windows_additions,
            },
            indent=2,
        )
    )
    if args.apply:
        mapping.setdefault("supportingFunctions", []).extend(ps3_additions)
        mapping["supportingFunctions"].sort(
            key=lambda item: int(item["windowsAddress"], 16)
        )
        mapping.setdefault("windowsSupportingFunctions", []).extend(windows_additions)
        mapping["windowsSupportingFunctions"].sort(
            key=lambda item: int(item["windowsAddress"], 16)
        )
        write_json(args.matches, mapping)


if __name__ == "__main__":
    main()

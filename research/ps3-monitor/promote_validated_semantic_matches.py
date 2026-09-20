#!/usr/bin/env python3
"""Promote manually reviewed unique matches with independent behavioral anchors."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PROMOTIONS: dict[str, list[str]] = {
    "0x0067": [
        "Both resolve the packet entity ID through CharacterManager before acting.",
        "Both call strlen on the packet message and pass its length plus the packet type to the character lip-sync path.",
    ],
    "0x0192": [
        "Both wrappers forward actor ID and the packed movement payload into the global movement packet queue.",
        "The downstream paths preserve transmission timing and enqueue/retry movement records rather than handling an unrelated packet.",
    ],
    "0x01A6": [
        "Both copy the inspect name, PSN ID, object/job/level/title data, and base parameters into inspect state.",
        "Both iterate 14 equipment records and five materia slots and update the inspect storage/UI representation.",
    ],
    "0x01A7": [
        "Both search a 200-entry name cache whose records have 72-byte stride.",
        "Both insert ID/name into a circular cache on miss and clear the inquiry flag.",
    ],
    "0x01B6": [
        "Both resolve storage ID and container index, copy the same item fields, compute change flags, and signal inventory changes.",
        "Both contain the distinctive storage 25001 and range 25003..25006 UI-dirty special cases.",
    ],
    "0x01EE": [
        "Both process exactly five two-byte tracking records and update five persistent tracking slots.",
        "Both notify the journal/event path and set the same two post-sync dirty flags.",
    ],
    "0x01F2": [
        "Both obtain the EventFramework singleton and forward handler ID, scene ID, resume ID, and one string argument.",
        "The adjacent resume-scene overload family has already been matched as a shared dispatcher target.",
    ],
    "0x01FF": [
        "Both obtain the EventFramework singleton and forward handler ID, scene ID, resume ID, string, argument array, and argument count.",
        "The distinct seven-argument downstream overload agrees across builds and with the packet variant name.",
    ],
    "0x02D5": [
        "Both obtain the EventFramework singleton and forward director ID, start time, and limit time.",
        "The three-value forwarding shape and adjacent event-packet family distinguish this from unrelated replay behavior.",
    ],
    "0x02DF": [
        "Both obtain the EventFramework singleton and forward the ColosseumResult44 packet to one dedicated overload.",
        "The adjacent Result88 case uses a separate target in both builds, preserving the overload split.",
    ],
    "0x02E0": [
        "Both obtain the EventFramework singleton and forward the ColosseumResult88 packet to one dedicated overload.",
        "The adjacent Result44 case uses a separate target in both builds, preserving the overload split.",
    ],
    "0x02EB": [
        "Both iterate four reward item/count pairs and use packet flag bits 0x08 and 0x10 for error/tutorial behavior.",
        "Both open HowTo entry 66 and emit the gil/reward log path after processing the same packet fields.",
    ],
    "0x0317": [
        "Both resolve the salvage UI agent and copy three catalog/count result pairs.",
        "Both pass the original catalog ID, result count three, and copied result array to the salvage-result UI path.",
    ],
}

WINDOWS_NAME_OVERRIDES = {
    "0x01F2": "Client__Game__Network__EventPacket__ReceiveResumeEventScene_Str32",
    "0x01FF": "Client__Game__Network__EventPacket__ReceiveResumeEventScene_2Str",
    "0x02DF": "Client__Game__Network__EventPacket__ReceiveColosseumResult_44",
    "0x02E0": "Client__Game__Network__EventPacket__ReceiveColosseumResult_88",
}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as output:
        json.dump(value, output, indent=2)
        output.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reviews", type=Path, default=Path(__file__).with_name("case_reviews.json")
    )
    parser.add_argument(
        "--matches", type=Path, default=Path(__file__).with_name("packet_matches.json")
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    review_file = load(args.reviews)
    mapping = load(args.matches)
    reviews = {review["ps3Opcode"]: review for review in review_file["reviews"]}
    existing_opcodes = {
        (entry.get("channel", "zone-down"), entry["opcode"])
        for entry in mapping["matches"]
    }
    existing_windows = {
        int(entry["windowsAddress"], 16)
        for section in ("matches", "sharedMatches")
        for entry in mapping.get(section, [])
    }
    promoted: list[dict[str, Any]] = []
    for opcode, behavioral_evidence in PROMOTIONS.items():
        review = reviews.get(opcode)
        if review is None:
            continue
        if (review["channel"], opcode) in existing_opcodes:
            continue
        ps3_calls = [call for call in review["ps3PacketCalls"] if call["address"]]
        windows_calls = [call for call in review["windowsPacketCalls"] if call["address"]]
        if len(ps3_calls) != 1 or len(windows_calls) != 1:
            raise RuntimeError(f"{opcode}: expected one direct target in each build")
        ps3_address = int(ps3_calls[0]["address"], 16)
        windows_address = int(windows_calls[0]["address"], 16)
        if windows_address in existing_windows:
            raise RuntimeError(f"{opcode}: duplicate Windows target")
        ps3_name = ps3_calls[0]["name"]
        promoted.append(
            {
                "opcode": opcode,
                "packet": review["threePointThreePacket"],
                "ps3Address": f"0x{ps3_address:08X}",
                "ps3Name": ps3_name,
                "windowsAddress": f"0x{windows_address:X}",
                "windowsName": WINDOWS_NAME_OVERRIDES.get(
                    opcode, ps3_name.replace("::", "__")
                ),
                "confidence": "high",
                "evidence": [
                    "The same unique opcode routes packet payload data at +0x10 to these functions in both dispatchers.",
                    *behavioral_evidence,
                ],
                "ps3IdbUrl": f"idb://ffxivgame.ppu.elf.i64:{ps3_address:08X}",
                "channel": review["channel"],
            }
        )
    promoted.sort(key=lambda entry: entry["opcode"])
    print(json.dumps({"promotable": len(promoted), "entries": promoted}, indent=2))
    if args.apply:
        promoted_opcodes = {entry["opcode"] for entry in promoted}
        mapping["matches"].extend(promoted)
        review_file["reviews"] = [
            review
            for review in review_file["reviews"]
            if review["ps3Opcode"] not in promoted_opcodes
        ]
        review_file["summary"] = {
            "reviewed": len(review_file["reviews"]),
            "probable": sum(
                review["status"] == "probable" for review in review_file["reviews"]
            ),
            "unresolved": sum(
                review["status"] == "unresolved" for review in review_file["reviews"]
            ),
        }
        write(args.matches, mapping)
        write(args.reviews, review_file)


if __name__ == "__main__":
    main()

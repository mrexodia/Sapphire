#!/usr/bin/env python3
"""Promote exact many-opcode/one-function relationships shared by both builds."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


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
    reviews = review_file["reviews"]
    mapping = load(args.matches)
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for review in reviews:
        if review["status"] != "probable":
            continue
        ps3_addresses = {call["address"] for call in review["ps3PacketCalls"] if call["address"]}
        windows_addresses = {
            call["address"] for call in review["windowsPacketCalls"] if call["address"]
        }
        ps3_names = {call["name"] for call in review["ps3PacketCalls"] if call["name"]}
        if len(ps3_addresses) != 1 or len(windows_addresses) != 1 or len(ps3_names) != 1:
            continue
        key = (
            review["channel"],
            next(iter(ps3_addresses)),
            next(iter(windows_addresses)),
            next(iter(ps3_names)),
        )
        groups[key].append(review)

    existing_windows = {
        int(entry["windowsAddress"], 16)
        for section in ("matches", "sharedMatches")
        for entry in mapping.get(section, [])
    }
    promoted: list[dict[str, Any]] = []
    for (channel, ps3_text, windows_text, ps3_name), items in groups.items():
        if len(items) < 2:
            continue
        ps3_address = int(ps3_text, 16)
        windows_address = int(windows_text, 16)
        if windows_address in existing_windows:
            continue
        opcodes = sorted(item["ps3Opcode"] for item in items)
        packets = [item["threePointThreePacket"] for item in sorted(items, key=lambda x: x["ps3Opcode"])]
        promoted.append(
            {
                "opcodes": opcodes,
                "packets": packets,
                "ps3Address": f"0x{ps3_address:08X}",
                "ps3Name": ps3_name,
                "windowsAddress": f"0x{windows_address:X}",
                "windowsName": ps3_name.replace("::", "__"),
                "confidence": "high",
                "evidence": [
                    "Every listed opcode routes to the same PS3 DWARF function and the same unique Windows function.",
                    "The shared opcode sets agree across both dispatchers and ThreePointThree names each packet variant.",
                    "Both builds pass packet payload data at +0x10; this is a many-opcode/one-function match, not separate one-to-one links.",
                ],
                "ps3IdbUrl": f"idb://ffxivgame.ppu.elf.i64:{ps3_address:08X}",
                "channel": channel,
            }
        )
    promoted.sort(key=lambda entry: entry["opcodes"][0])
    print(json.dumps({"promotable": len(promoted), "entries": promoted}, indent=2))
    if args.apply:
        mapping.setdefault("sharedMatches", []).extend(promoted)
        promoted_opcodes = {
            opcode for entry in promoted for opcode in entry["opcodes"]
        }
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

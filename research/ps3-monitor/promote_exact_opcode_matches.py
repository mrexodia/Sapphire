#!/usr/bin/env python3
"""Promote exact, unique ThreePointThree/PS3/Windows zone matches.

This deliberately handles only the narrow case where three independent sources
agree: the historical ServerZoneIpcType semantic name, the PS3 DWARF handler
name, and one unique Windows payload target. Other candidates remain for manual
semantic review.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
HISTORICAL_REF = "fe26d3ba840deb1eaca6db6d8a486c8e068482f9"
HEADER = "src/common/Network/PacketDef/ServerIpcs.h"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as output:
        json.dump(value, output, indent=2)
        output.write("\n")


def zone_opcodes() -> dict[str, str]:
    text = subprocess.run(
        ["git", "show", f"{HISTORICAL_REF}:{HEADER}"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    ).stdout
    match = re.search(r"enum\s+ServerZoneIpcType[^\{]*\{(?P<body>.*?)\n\s*\};", text, re.S)
    if match is None:
        raise RuntimeError("ServerZoneIpcType was not found")
    return {
        f"0x{int(value, 16):04X}": name
        for name, value in re.findall(
            r"^\s*(\w+)\s*=\s*(0x[0-9A-Fa-f]+)", match.group("body"), re.M
        )
    }


def normalized_handler_name(name: str) -> str:
    short_name = name.rsplit("::", 1)[-1]
    for prefix in ("OnReceive", "Receive", "Response", "On"):
        if short_name.startswith(prefix):
            return short_name[len(prefix) :]
    return short_name


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--candidates",
        type=Path,
        default=Path(__file__).with_name("candidate_rankings.json"),
    )
    parser.add_argument(
        "--matches", type=Path, default=Path(__file__).with_name("packet_matches.json")
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    candidates = load(args.candidates)["candidates"]
    mapping = load(args.matches)
    enum_names = zone_opcodes()
    windows_counts = Counter(
        candidate["windowsPacketCalls"][0]["address"]
        for candidate in candidates
        if len(candidate["windowsPacketCalls"]) == 1
    )
    ps3_counts = Counter(
        candidate["ps3PacketCalls"][0]["address"]
        for candidate in candidates
        if len(candidate["ps3PacketCalls"]) == 1
    )
    existing_addresses = {int(item["windowsAddress"], 16) for item in mapping["matches"]}
    existing_keys = {
        (item.get("channel", "zone-down"), item["opcode"]) for item in mapping["matches"]
    }

    promoted: list[dict[str, Any]] = []
    for candidate in candidates:
        if candidate["channel"] != "zone-down" or candidate["score"] != 4:
            continue
        if len(candidate["ps3PacketCalls"]) != 1 or len(candidate["windowsPacketCalls"]) != 1:
            continue
        ps3_call = candidate["ps3PacketCalls"][0]
        windows_call = candidate["windowsPacketCalls"][0]
        if ps3_counts[ps3_call["address"]] != 1 or windows_counts[windows_call["address"]] != 1:
            continue
        opcode = candidate["ps3Opcode"]
        packet = enum_names.get(opcode)
        if packet is None:
            continue
        ps3_name = ps3_call["name"]
        if not ps3_name or normalized_handler_name(ps3_name) != packet:
            continue
        windows_address = int(windows_call["address"], 16)
        if windows_address in existing_addresses or ("zone-down", opcode) in existing_keys:
            continue
        ps3_address = int(ps3_call["address"], 16)
        promoted.append(
            {
                "opcode": opcode,
                "packet": packet,
                "ps3Address": f"0x{ps3_address:08X}",
                "ps3Name": ps3_name,
                "windowsAddress": f"0x{windows_address:X}",
                "windowsName": ps3_name.replace("::", "__"),
                "confidence": "high",
                "evidence": [
                    f"ThreePointThree ServerZoneIpcType independently identifies {opcode} as {packet}.",
                    f"The PS3 DWARF dispatcher routes the same opcode and +0x10 payload to {ps3_name}; its conventional On/Receive/Response prefix normalizes to {packet}.",
                    "The Windows dispatcher routes the +0x10 payload to one unique direct target that is not shared by another candidate.",
                ],
                "ps3IdbUrl": f"idb://ffxivgame.ppu.elf.i64:{ps3_address:08X}",
                "channel": "zone-down",
            }
        )

    print(json.dumps({"promotable": len(promoted), "entries": promoted}, indent=2))
    if args.apply:
        mapping["matches"].extend(promoted)
        write(args.matches, mapping)


if __name__ == "__main__":
    main()

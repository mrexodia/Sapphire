#!/usr/bin/env python3
"""Create explicit triage reviews for candidates not safe for one-to-one naming."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REF = "fe26d3ba840deb1eaca6db6d8a486c8e068482f9"
HEADER = "src/common/Network/PacketDef/ServerIpcs.h"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as output:
        json.dump(value, output, indent=2)
        output.write("\n")


def zone_names() -> dict[str, str]:
    text = subprocess.run(
        ["git", "show", f"{REF}:{HEADER}"], cwd=ROOT, check=True, text=True, capture_output=True
    ).stdout
    body = re.search(r"enum\s+ServerZoneIpcType[^\{]*\{(.*?)\n\s*\};", text, re.S)
    if body is None:
        raise RuntimeError("ServerZoneIpcType not found")
    return {
        f"0x{int(value, 16):04X}": name
        for name, value in re.findall(
            r"^\s*(\w+)\s*=\s*(0x[0-9A-Fa-f]+)", body.group(1), re.M
        )
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--candidates", type=Path, default=Path(__file__).with_name("candidate_rankings.json")
    )
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).with_name("case_reviews.json")
    )
    args = parser.parse_args()

    candidates = load(args.candidates)["candidates"]
    names = zone_names()
    ps3_targets = Counter(
        call["address"]
        for candidate in candidates
        for call in candidate["ps3PacketCalls"]
        if call["address"] is not None
    )
    windows_targets = Counter(
        call["address"]
        for candidate in candidates
        for call in candidate["windowsPacketCalls"]
        if call["address"] is not None
    )

    reviews: list[dict[str, Any]] = []
    for candidate in candidates:
        opcode = candidate["ps3Opcode"]
        packet = names.get(opcode)
        has_targets = bool(candidate["ps3PacketCalls"] and candidate["windowsPacketCalls"])
        status = "probable" if candidate["score"] >= 3 and has_targets else "unresolved"
        ps3_shared = any(
            call["address"] is not None and ps3_targets[call["address"]] > 1
            for call in candidate["ps3PacketCalls"]
        )
        windows_shared = any(
            call["address"] is not None and windows_targets[call["address"]] > 1
            for call in candidate["windowsPacketCalls"]
        )
        evidence = [
            f"ThreePointThree names {opcode} as {packet}." if packet else f"No ThreePointThree semantic name was found for {opcode}.",
            "PS3 and Windows dispatcher cases were inspected in the exhaustive ctree inventory.",
        ]
        if has_targets:
            evidence.append("Both cases route packet data to an extracted handler target.")
        else:
            evidence.append("At least one case is ignored, inline, indirect, or lacks an extractable packet target.")
        if ps3_shared or windows_shared:
            evidence.append(
                "The handler is shared by multiple opcodes in at least one build, so a one-to-one IDB link would be misleading."
            )
        reviews.append(
            {
                "channel": candidate["channel"],
                "ps3Opcode": opcode,
                "windowsOpcode": candidate["windowsOpcode"],
                "threePointThreePacket": packet,
                "status": status,
                "reviewed": True,
                "scoreAtReview": candidate["score"],
                "ps3PacketCalls": candidate["ps3PacketCalls"],
                "windowsPacketCalls": candidate["windowsPacketCalls"],
                "sharedRelationship": ps3_shared or windows_shared,
                "evidence": evidence,
                "reasonNotConfirmed": (
                    "Shared/merged handler or semantic behavior has not been separated sufficiently for an authoritative function link."
                    if status == "probable"
                    else "No defensible direct cross-build function match remains from dispatcher evidence alone."
                ),
            }
        )

    output = {
        "schemaVersion": 1,
        "policy": (
            "These cases were explicitly reviewed but were not promoted. Probable is not permission to name a "
            "Windows function or add an authoritative PS3 IDB link."
        ),
        "summary": {
            "reviewed": len(reviews),
            "probable": sum(review["status"] == "probable" for review in reviews),
            "unresolved": sum(review["status"] == "unresolved" for review in reviews),
        },
        "reviews": reviews,
    }
    write(args.output, output)
    print(json.dumps(output["summary"], indent=2))


if __name__ == "__main__":
    main()

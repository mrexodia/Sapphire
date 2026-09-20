#!/usr/bin/env python3
"""Merge read-only IDA dispatcher exports into the research inventory."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

ALLOWED_STATUSES = {
    "confirmed",
    "probable",
    "candidate",
    "ps3-only",
    "windows-only",
    "unresolved",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as output:
        json.dump(value, output, indent=2)
        output.write("\n")


def index_cases(cases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {case["opcode"]: case for case in cases if case["opcode"] is not None}


def assign_statuses(
    channel: str,
    ps3_cases: list[dict[str, Any]],
    windows_cases: list[dict[str, Any]],
    confirmed_opcodes: set[str],
) -> None:
    ps3_index = index_cases(ps3_cases)
    windows_index = index_cases(windows_cases)
    for build, cases, other_index in (
        ("ps3", ps3_cases, windows_index),
        ("windows", windows_cases, ps3_index),
    ):
        for case in cases:
            opcode = case["opcode"]
            case["counterpartOpcode"] = opcode if opcode in other_index else None
            if opcode is None:
                case["status"] = "unresolved"
            elif opcode in confirmed_opcodes:
                case["status"] = "confirmed"
            elif opcode in other_index:
                case["status"] = "candidate"
            elif opcode not in other_index:
                case["status"] = "ps3-only" if build == "ps3" else "windows-only"
            else:
                case["status"] = "unresolved"
            assert case["status"] in ALLOWED_STATUSES


def apply_reviews(
    ps3: dict[str, Any], windows: dict[str, Any], reviews: dict[str, Any]
) -> None:
    channel_keys = {"zone-down": "zone", "chat-down": "chat"}
    for review in reviews.get("reviews", []):
        channel = review["channel"]
        channel_key = channel_keys[channel]
        ps3_index = index_cases(ps3[channel_key]["cases"])
        windows_index = index_cases(windows[channel_key]["cases"])
        ps3_case = ps3_index[review["ps3Opcode"]]
        windows_case = windows_index[review["windowsOpcode"]]
        ps3_case["status"] = review["status"]
        windows_case["status"] = review["status"]
        ps3_case["reviewReference"] = "case_reviews.json"
        windows_case["reviewReference"] = "case_reviews.json"


def summarize(dispatcher: dict[str, Any]) -> dict[str, Any]:
    cases = dispatcher["cases"]
    return {
        "totalCasesIncludingDefault": len(cases),
        "explicitOpcodes": sum(case["opcode"] is not None for case in cases),
        "dispatchKinds": dict(sorted(Counter(case["dispatchKind"] for case in cases).items())),
        "statuses": dict(sorted(Counter(case["status"] for case in cases).items())),
    }


def build_candidates(
    ps3: dict[str, Any], windows: dict[str, Any]
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for channel_key, channel_name in (("zone", "zone-down"), ("chat", "chat-down")):
        ps3_index = index_cases(ps3[channel_key]["cases"])
        windows_index = index_cases(windows[channel_key]["cases"])
        for opcode in sorted(ps3_index.keys() & windows_index.keys()):
            ps3_case = ps3_index[opcode]
            windows_case = windows_index[opcode]
            if ps3_case["status"] != "candidate":
                continue
            ps3_packet_calls = ps3_case["packetCalls"]
            windows_packet_calls = windows_case["packetCalls"]
            score = 1  # Same explicit opcode.
            reasons = ["same explicit opcode"]
            if ps3_packet_calls and ps3_packet_calls[0].get("name"):
                score += 1
                reasons.append("named PS3 packet handler")
            if ps3_case["packetDataOffset"] == windows_case["packetDataOffset"] == "0x10":
                score += 1
                reasons.append("both pass payload at +0x10")
            if len(ps3_packet_calls) == len(windows_packet_calls) == 1:
                score += 1
                reasons.append("one direct packet target in each build")
            if not ps3_packet_calls or not windows_packet_calls:
                score -= 1
            candidates.append(
                {
                    "channel": channel_name,
                    "ps3Opcode": opcode,
                    "windowsOpcode": opcode,
                    "score": score,
                    "status": "candidate",
                    "rankingReasons": reasons,
                    "ps3PacketCalls": ps3_packet_calls,
                    "windowsPacketCalls": windows_packet_calls,
                    "requiredNextEvidence": (
                        "Verify handler field accesses, secondary switches, callees, constants, "
                        "or state effects; opcode equality is not confirmation."
                    ),
                }
            )
    candidates.sort(key=lambda item: (-item["score"], item["channel"], item["ps3Opcode"]))
    return candidates


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ps3", type=Path, required=True, help="PS3 IDA export JSON")
    parser.add_argument("--windows", type=Path, required=True, help="Windows IDA export JSON")
    parser.add_argument(
        "--matches",
        type=Path,
        default=Path(__file__).with_name("packet_matches.json"),
    )
    parser.add_argument(
        "--reviews",
        type=Path,
        default=Path(__file__).with_name("case_reviews.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("dispatcher_cases.json"),
    )
    parser.add_argument(
        "--candidates",
        type=Path,
        default=Path(__file__).with_name("candidate_rankings.json"),
    )
    args = parser.parse_args()

    ps3 = load_json(args.ps3)
    windows = load_json(args.windows)
    matches = load_json(args.matches)
    reviews = load_json(args.reviews) if args.reviews.exists() else {"reviews": []}
    confirmed_by_channel = {
        channel: {
            match["opcode"]
            for match in matches["matches"]
            if match.get("channel", "zone-down") == channel
        }
        for channel in ("zone-down", "chat-down")
    }

    assign_statuses(
        "zone-down",
        ps3["zone"]["cases"],
        windows["zone"]["cases"],
        confirmed_by_channel["zone-down"],
    )
    assign_statuses(
        "chat-down",
        ps3["chat"]["cases"],
        windows["chat"]["cases"],
        confirmed_by_channel["chat-down"],
    )
    apply_reviews(ps3, windows, reviews)

    dispatchers = [ps3["zone"], windows["zone"], ps3["chat"], windows["chat"]]
    for dispatcher in dispatchers:
        dispatcher["summary"] = summarize(dispatcher)

    inventory = {
        "schemaVersion": 1,
        "method": (
            "IDA decompiler ctree export. PS3 optimized comparisons are evaluated for every "
            "16-bit opcode; Windows and chat dispatchers use their explicit top-level switches."
        ),
        "limitations": [
            "ps3-only/windows-only describe same-opcode dispatcher-case presence, not proof that the semantic feature has no changed-opcode counterpart.",
            "Candidate status is triage only and is not evidence of a semantic match.",
            "Runtime branches are conservatively unioned when exporting direct calls.",
            "Indirect calls have a null target address and require manual review.",
        ],
        "dispatchers": dispatchers,
    }
    candidate_file = {
        "schemaVersion": 1,
        "policy": (
            "Ranking only. Every entry requires independent semantic evidence before naming "
            "or adding a PS3 IDB link to the Windows database."
        ),
        "candidates": build_candidates(ps3, windows),
    }
    write_json(args.output, inventory)
    write_json(args.candidates, candidate_file)

    print(
        json.dumps(
            {
                "dispatchers": {
                    f"{item['build']}:{item['channel']}": item["summary"]
                    for item in dispatchers
                },
                "rankedCandidates": len(candidate_file["candidates"]),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

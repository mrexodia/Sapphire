#!/usr/bin/env python3
"""Validate PS3 Monitor packet-matching research artifacts."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
ALLOWED_STATUSES = {
    "confirmed",
    "probable",
    "candidate",
    "ps3-only",
    "windows-only",
    "unresolved",
}
PS3_URL_RE = re.compile(r"^idb://ffxivgame\.ppu\.elf\.i64:([0-9A-F]{8})$")
OPCODE_RE = re.compile(r"^0x[0-9A-F]{4}$")


def load(name: str) -> dict[str, Any]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def expected_url(address: str) -> str:
    return f"idb://ffxivgame.ppu.elf.i64:{int(address, 16):08X}"


def validate_matches(matches: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entries = matches["dispatchers"] + matches["matches"] + matches.get(
        "supportingFunctions", []
    )
    seen_windows: set[str] = set()
    for entry in entries:
        assert entry["ps3IdbUrl"] == expected_url(entry["ps3Address"]), entry
        assert PS3_URL_RE.fullmatch(entry["ps3IdbUrl"]), entry["ps3IdbUrl"]
        assert entry["windowsAddress"] not in seen_windows, entry["windowsAddress"]
        seen_windows.add(entry["windowsAddress"])
        assert entry["evidence"], entry
    return {entry["opcode"]: entry for entry in matches["matches"]}


def dispatcher_key(dispatcher: dict[str, Any]) -> tuple[str, str]:
    return dispatcher["build"], dispatcher["channel"]


def validate_dispatchers(
    inventory: dict[str, Any], confirmed: dict[str, dict[str, Any]]
) -> dict[tuple[str, str], dict[str, Any]]:
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for dispatcher in inventory["dispatchers"]:
        key = dispatcher_key(dispatcher)
        assert key not in by_key, key
        by_key[key] = dispatcher
        opcodes: set[str] = set()
        defaults = 0
        for case in dispatcher["cases"]:
            opcode = case["opcode"]
            if opcode is None:
                defaults += 1
            else:
                assert OPCODE_RE.fullmatch(opcode), (key, opcode)
                assert opcode not in opcodes, (key, opcode)
                opcodes.add(opcode)
            assert case["status"] in ALLOWED_STATUSES, (key, opcode, case["status"])
            if case["packetCalls"]:
                assert case["packetDataOffset"] is not None, (key, opcode)
            for call in case["packetCalls"] + case["directCalls"]:
                assert "callsite" in call and "address" in call and "name" in call
        assert defaults == 1, (key, defaults)

        calculated = {
            "totalCasesIncludingDefault": len(dispatcher["cases"]),
            "explicitOpcodes": len(opcodes),
            "dispatchKinds": dict(
                sorted(Counter(case["dispatchKind"] for case in dispatcher["cases"]).items())
            ),
            "statuses": dict(
                sorted(Counter(case["status"] for case in dispatcher["cases"]).items())
            ),
        }
        assert dispatcher["summary"] == calculated, key

    expected_keys = {
        ("ps3-monitor-2.3", "zone-down"),
        ("windows-3.x", "zone-down"),
        ("ps3-monitor-2.3", "chat-down"),
        ("windows-3.x", "chat-down"),
    }
    assert set(by_key) == expected_keys, set(by_key)

    ps3_zone = {
        case["opcode"]: case
        for case in by_key[("ps3-monitor-2.3", "zone-down")]["cases"]
        if case["opcode"] is not None
    }
    windows_zone = {
        case["opcode"]: case
        for case in by_key[("windows-3.x", "zone-down")]["cases"]
        if case["opcode"] is not None
    }
    for opcode, match in confirmed.items():
        assert ps3_zone[opcode]["status"] == "confirmed", opcode
        assert windows_zone[opcode]["status"] == "confirmed", opcode
        assert any(
            call["address"] is not None
            and int(call["address"], 16) == int(match["ps3Address"], 16)
            for call in ps3_zone[opcode]["packetCalls"]
        ), opcode
        assert any(
            call["address"] is not None
            and int(call["address"], 16) == int(match["windowsAddress"], 16)
            for call in windows_zone[opcode]["directCalls"]
        ), opcode
    return by_key


def validate_candidates(
    candidate_file: dict[str, Any], dispatchers: dict[tuple[str, str], dict[str, Any]]
) -> None:
    seen: set[tuple[str, str, str]] = set()
    indexes = {
        key: {case["opcode"]: case for case in dispatcher["cases"]}
        for key, dispatcher in dispatchers.items()
    }
    for candidate in candidate_file["candidates"]:
        key = (
            candidate["channel"],
            candidate["ps3Opcode"],
            candidate["windowsOpcode"],
        )
        assert key not in seen, key
        seen.add(key)
        assert candidate["status"] == "candidate", key
        ps3_case = indexes[("ps3-monitor-2.3", candidate["channel"])][
            candidate["ps3Opcode"]
        ]
        windows_case = indexes[("windows-3.x", candidate["channel"])][
            candidate["windowsOpcode"]
        ]
        assert ps3_case["status"] == "candidate", key
        assert windows_case["status"] == "candidate", key


def main() -> None:
    matches = load("packet_matches.json")
    inventory = load("dispatcher_cases.json")
    candidates = load("candidate_rankings.json")
    confirmed = validate_matches(matches)
    dispatchers = validate_dispatchers(inventory, confirmed)
    validate_candidates(candidates, dispatchers)
    print(
        "validated: "
        f"{len(confirmed)} confirmed packet matches, "
        f"{sum(len(item['cases']) for item in inventory['dispatchers'])} dispatcher cases, "
        f"{len(candidates['candidates'])} ranked candidates"
    )


if __name__ == "__main__":
    main()

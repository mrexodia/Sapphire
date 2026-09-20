#!/usr/bin/env python3
"""Validate PS3 Monitor packet-matching research artifacts."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from build_packet_catalog import build_outputs
from build_readability_plan import build as build_readability

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


def validate_matches(matches: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    entries = (
        matches["dispatchers"]
        + matches["matches"]
        + matches.get("sharedMatches", [])
        + matches.get("supportingFunctions", [])
    )
    seen_windows: set[str] = set()
    for entry in entries:
        assert entry["ps3IdbUrl"] == expected_url(entry["ps3Address"]), entry
        assert PS3_URL_RE.fullmatch(entry["ps3IdbUrl"]), entry["ps3IdbUrl"]
        assert entry["windowsAddress"] not in seen_windows, entry["windowsAddress"]
        seen_windows.add(entry["windowsAddress"])
        assert entry["evidence"], entry
    for entry in matches.get("windowsMappings", []):
        assert len(entry["opcodes"]) == len(entry["packets"]), entry
        assert entry["confidence"] == "high", entry
        assert entry["mappingKind"] == "windows-semantic", entry
        assert entry["evidence"], entry
        assert "ps3IdbUrl" not in entry and "ps3Address" not in entry, entry
        assert entry["windowsAddress"] not in seen_windows, entry["windowsAddress"]
        seen_windows.add(entry["windowsAddress"])
        for opcode in entry["opcodes"]:
            assert OPCODE_RE.fullmatch(opcode), (entry, opcode)
    for entry in matches.get("windowsSupportingFunctions", []):
        assert entry["confidence"] == "high", entry
        assert entry["mappingKind"] == "windows-supporting", entry
        assert entry["roles"] and entry["evidence"], entry
        assert "ps3IdbUrl" not in entry and "ps3Address" not in entry, entry
        assert entry["windowsAddress"] not in seen_windows, entry["windowsAddress"]
        seen_windows.add(entry["windowsAddress"])
    seen_inline: set[tuple[str, str]] = set()
    for entry in matches.get("windowsInlineMappings", []):
        key = (entry["channel"], entry["opcode"])
        assert key not in seen_inline, key
        seen_inline.add(key)
        assert OPCODE_RE.fullmatch(entry["opcode"]), entry
        assert entry["confidence"] == "high", entry
        assert entry["mappingKind"] == "windows-inline", entry
        assert entry["evidence"] and entry["windowsCaseEa"].startswith("0x"), entry
    confirmed = {
        (entry.get("channel", "zone-down"), entry["opcode"]): entry
        for entry in matches["matches"]
    }
    for entry in matches.get("sharedMatches", []):
        assert len(entry["opcodes"]) == len(entry["packets"]), entry
        assert set(entry.get("inlineOpcodes", [])).issubset(entry["opcodes"]), entry
        for opcode, packet in zip(entry["opcodes"], entry["packets"]):
            key = (entry.get("channel", "zone-down"), opcode)
            assert key not in confirmed, key
            confirmed[key] = entry | {"opcode": opcode, "packet": packet}
    return confirmed


def dispatcher_key(dispatcher: dict[str, Any]) -> tuple[str, str]:
    return dispatcher["build"], dispatcher["channel"]


def validate_dispatchers(
    inventory: dict[str, Any], confirmed: dict[tuple[str, str], dict[str, Any]]
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

    indexes = {
        key: {
            case["opcode"]: case
            for case in dispatcher["cases"]
            if case["opcode"] is not None
        }
        for key, dispatcher in by_key.items()
    }
    for (channel, opcode), match in confirmed.items():
        ps3_case = indexes[("ps3-monitor-2.3", channel)][opcode]
        windows_case = indexes[("windows-3.x", channel)][opcode]
        assert ps3_case["status"] == "confirmed", (channel, opcode)
        assert windows_case["status"] == "confirmed", (channel, opcode)
        assert any(
            call["address"] is not None
            and int(call["address"], 16) == int(match["ps3Address"], 16)
            for call in ps3_case["packetCalls"]
        ), (channel, opcode)
        if opcode not in match.get("inlineOpcodes", []):
            assert any(
                call["address"] is not None
                and int(call["address"], 16) == int(match["windowsAddress"], 16)
                for call in windows_case["directCalls"]
            ), (channel, opcode)
    return by_key


def validate_structures(
    structures: dict[str, Any], confirmed: dict[tuple[str, str], dict[str, Any]]
) -> None:
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    missing: list[str] = []
    deltas: list[dict[str, Any]] = []
    for structure in structures["structures"]:
        key = (structure["channel"], structure["packet"])
        assert key not in indexed, key
        indexed[key] = structure
        assert structure["status"] == "exported", key
        assert structure["ps3Size"] > 0, key
        if structure["sapphire"]["currentStatus"] == "missing":
            missing.append(f"{key[0]}:{key[1]}")
        for member in structure["members"]:
            validation = member["windowsValidation"]
            assert validation["status"] in {
                "unreviewed",
                "confirmed-same-offset",
                "confirmed-version-delta",
            }, (key, member["name"], validation)
            if validation["status"] == "confirmed-version-delta":
                deltas.append(
                    {
                        "packet": structure["packet"],
                        "field": member["name"],
                        "ps3Offset": member["offset"],
                        "windowsOffset": validation["offset"],
                    }
                )
    expected = {(channel, match["packet"]) for (channel, _), match in confirmed.items()}
    assert set(indexed) == expected, (expected - set(indexed), set(indexed) - expected)
    assert structures["summary"]["structures"] == len(indexed)
    assert structures["summary"]["missingCurrentDeclarations"] == sorted(missing)
    assert structures["summary"]["confirmedVersionDeltas"] == deltas


def validate_reviews(
    review_file: dict[str, Any], dispatchers: dict[tuple[str, str], dict[str, Any]]
) -> None:
    indexes = {
        key: {case["opcode"]: case for case in dispatcher["cases"]}
        for key, dispatcher in dispatchers.items()
    }
    seen: set[tuple[str, str, str]] = set()
    for review in review_file["reviews"]:
        key = (review["channel"], review["ps3Opcode"], review["windowsOpcode"])
        assert key not in seen, key
        seen.add(key)
        assert review["reviewed"] is True, key
        assert review["status"] in {"probable", "unresolved"}, key
        assert review["evidence"] and review["reasonNotConfirmed"], key
        assert indexes[("ps3-monitor-2.3", review["channel"])][review["ps3Opcode"]]["status"] == review["status"], key
        assert indexes[("windows-3.x", review["channel"])][review["windowsOpcode"]]["status"] == review["status"], key
    assert review_file["summary"] == {
        "reviewed": len(review_file["reviews"]),
        "probable": sum(item["status"] == "probable" for item in review_file["reviews"]),
        "unresolved": sum(item["status"] == "unresolved" for item in review_file["reviews"]),
    }


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
    assert not candidate_file["candidates"], "unreviewed ranked candidates remain"
    assert not any(
        case["status"] == "candidate"
        for dispatcher in dispatchers.values()
        for case in dispatcher["cases"]
    ), "dispatcher inventory still contains candidate status"


def validate_readability(matches: dict[str, Any]) -> dict[str, int]:
    header, plan = build_readability()
    assert (ROOT / "windows_readability_types.h").read_text(encoding="utf-8") == header, "stale windows_readability_types.h"
    assert load("readability_plan.json") == plan, "stale readability_plan.json"
    assert plan["summary"] == {
        "opcodeTypes": 2,
        "knownFieldTypes": len(plan["knownFieldTypes"]),
        "typedPayloadHandlers": len(plan["payloadHandlerTypes"]),
        "typedIpcWrappers": len(plan["ipcWrapperTypes"]),
        "typedSupportingFunctions": len(plan["supportingFunctionTypes"]),
        "typedGlobals": len(plan["globalTypes"]),
        "dispatcherCaseComments": len(plan["caseComments"]),
    }
    assert len({item["address"] for item in plan["caseComments"]}) == len(plan["caseComments"])
    assert len({item["windowsAddress"] for item in plan["payloadHandlerTypes"]}) == len(plan["payloadHandlerTypes"])
    for record in plan["knownFieldTypes"]:
        assert record["fields"] and record["knownSize"] > 0, record
        end = 0
        for field in record["fields"]:
            assert field["offset"] >= end, (record["packet"], field)
            end = field["offset"] + field["size"]
        assert end == record["knownSize"], record["packet"]

    graph = load("subsystem_callgraph.json")
    assert graph["schemaVersion"] == 1
    assert {cluster["name"] for cluster in graph["clusters"]} == {
        "quest-leve",
        "retainer-inventory",
    }
    mapped_addresses = {
        f"0x{int(item['windowsAddress'], 16):016X}"
        for item in matches["matches"]
        + matches.get("sharedMatches", [])
        + matches.get("windowsMappings", [])
    }
    callee_addresses: set[str] = set()
    for cluster in graph["clusters"]:
        assert cluster["summary"] == {
            "roots": len(cluster["rootFunctions"]),
            "directCallees": len(cluster["directCallees"]),
            "autoNamedCallees": sum(item["autoNamed"] for item in cluster["directCallees"]),
        }
        for root in cluster["rootFunctions"]:
            assert root["windowsAddress"] in mapped_addresses, root
        callee_addresses.update(item["windowsAddress"] for item in cluster["directCallees"])
    for item in matches.get("windowsSupportingFunctions", []):
        assert f"0x{int(item['windowsAddress'], 16):016X}" in callee_addresses, item
    return {
        "knownFieldTypes": len(plan["knownFieldTypes"]),
        "typedFunctions": len(plan["dispatcherTypes"])
        + 2
        + len(plan["payloadHandlerTypes"])
        + len(plan["ipcWrapperTypes"])
        + len(plan["supportingFunctionTypes"]),
        "typedGlobals": len(plan["globalTypes"]),
        "caseComments": len(plan["caseComments"]),
    }


def main() -> None:
    matches = load("packet_matches.json")
    inventory = load("dispatcher_cases.json")
    candidates = load("candidate_rankings.json")
    reviews = load("case_reviews.json")
    structures = load("packet_structures.json")
    confirmed = validate_matches(matches)
    dispatchers = validate_dispatchers(inventory, confirmed)
    validate_structures(structures, confirmed)
    validate_reviews(reviews, dispatchers)
    validate_candidates(candidates, dispatchers)
    readability = validate_readability(matches)
    markdown, html_catalog = build_outputs(ROOT)
    assert (ROOT / "PACKET_CATALOG.md").read_text(encoding="utf-8") == markdown, "stale PACKET_CATALOG.md"
    assert (ROOT / "packet_catalog.html").read_text(encoding="utf-8") == html_catalog, "stale packet_catalog.html"
    print(
        "validated: "
        f"{len(confirmed)} confirmed packet cases and structures, "
        f"{sum(len(item['cases']) for item in inventory['dispatchers'])} dispatcher cases, "
        f"{len(candidates['candidates'])} ranked candidates, "
        f"{len(matches.get('windowsMappings', []))} Windows-only semantic functions, "
        f"{len(matches.get('windowsSupportingFunctions', []))} Windows supporting functions, "
        f"{len(matches.get('windowsInlineMappings', []))} Windows inline cases, "
        f"{readability['knownFieldTypes']} readability types, "
        f"{readability['typedFunctions']} typed functions, "
        f"{readability['typedGlobals']} typed globals, "
        f"{readability['caseComments']} case comments"
    )


if __name__ == "__main__":
    main()

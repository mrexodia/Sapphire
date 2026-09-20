"""Read-only PS3 DWARF packet-type exporter for IDA Nexus."""

from __future__ import annotations

from typing import Any


NO_UNDERSCORE_SUFFIXES = {"Tracking"}

TYPE_SUFFIX_OVERRIDES = {
    "RequestItmeResult": "RequestItemResult",
    "Create": "Create",
    "HousingGetHouseBuddyStableListResult": "Housing_GetHouseBuddyStableListResult",
    "EventPlay2": "PlayEventScene2",
    "EventPlay4": "PlayEventScene4",
    "EventPlay8": "PlayEventScene8",
    "EventPlay16": "PlayEventScene16",
    "EventPlay32": "PlayEventScene32",
    "EventPlay64": "PlayEventScene64",
    "EventPlay128": "PlayEventScene128",
    "EventPlay255": "PlayEventScene255",
    "ChatToChannel": "Chat",
    "ActorMove": "Move",
}


def _type_prefix(channel: str) -> str:
    if channel == "chat-down":
        return "Client::Network::Protocol::Chat::ChatProtoDown"
    if channel == "zone-down":
        return "Client::Network::Protocol::Zone::ZoneProtoDown"
    raise ValueError(f"unsupported channel: {channel}")


def mapping_packet_entries(mapping: dict[str, Any]) -> list[dict[str, Any]]:
    entries = list(mapping["matches"])
    for shared in mapping.get("sharedMatches", []):
        entries.extend(
            {
                "channel": shared.get("channel", "zone-down"),
                "opcode": opcode,
                "packet": packet,
            }
            for opcode, packet in zip(shared["opcodes"], shared["packets"])
        )
    return entries


def export_confirmed_packet_types(
    db: Any, matches: list[dict[str, Any]]
) -> dict[str, Any]:
    all_types = list(db.types.get_all())
    output: list[dict[str, Any]] = []
    for match in matches:
        channel = match.get("channel", "zone-down")
        packet = match["packet"]
        suffix = TYPE_SUFFIX_OVERRIDES.get(packet, packet)
        prefix = _type_prefix(channel)
        ending = suffix if packet in NO_UNDERSCORE_SUFFIXES else f"_{suffix}"
        candidates = [
            type_info
            for type_info in all_types
            if (type_info.get_type_name() or "").startswith(prefix)
            and (type_info.get_type_name() or "").endswith(ending)
        ]
        if len(candidates) != 1:
            output.append(
                {
                    "channel": channel,
                    "packet": packet,
                    "status": "unresolved",
                    "error": f"expected one PS3 type, found {len(candidates)}",
                    "candidateNames": [item.get_type_name() for item in candidates],
                }
            )
            continue
        type_info = candidates[0]
        members = []
        for member in db.types.get_udt_members(type_info):
            members.append(
                {
                    "name": member.name,
                    "offset": f"0x{member.offset:X}",
                    "size": member.size,
                    "type": str(member.type),
                    "windowsValidation": "unreviewed",
                }
            )
        output.append(
            {
                "channel": channel,
                "packet": packet,
                "ps3Type": type_info.get_type_name(),
                "ps3Size": type_info.get_size(),
                "members": members,
                "status": "exported",
            }
        )
    return {
        "schemaVersion": 1,
        "source": "PS3 Monitor DWARF imported into IDA",
        "structures": output,
    }

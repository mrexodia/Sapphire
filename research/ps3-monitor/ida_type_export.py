"""Read-only PS3 DWARF packet-type exporter for IDA Nexus."""

from __future__ import annotations

from typing import Any


TYPE_SUFFIX_OVERRIDES = {
    "RequestItmeResult": "RequestItemResult",
    "Create": "Create",
}


def _type_prefix(channel: str) -> str:
    if channel == "chat-down":
        return "Client::Network::Protocol::Chat::ChatProtoDown"
    if channel == "zone-down":
        return "Client::Network::Protocol::Zone::ZoneProtoDown"
    raise ValueError(f"unsupported channel: {channel}")


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
        candidates = [
            type_info
            for type_info in all_types
            if (type_info.get_type_name() or "").startswith(prefix)
            and (type_info.get_type_name() or "").endswith(f"_{suffix}")
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

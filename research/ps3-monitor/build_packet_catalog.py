#!/usr/bin/env python3
"""Generate browsable Markdown and HTML views of the packet research ledgers."""

from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]


def load(root: Path, name: str) -> dict[str, Any]:
    return json.loads((root / name).read_text(encoding="utf-8"))


def source_link(sapphire: dict[str, Any], *, html_view: bool = False) -> str:
    path = sapphire.get("path")
    line = sapphire.get("currentLine")
    label = sapphire.get("type") or (Path(path).name if path else "unknown")
    if sapphire.get("currentStatus") != "present":
        text = f"missing: {label}"
        return f"<code>{html.escape(text)}</code>" if html_view else f"`{text}`"
    if not path:
        return "—"
    href = f"../../{path}" + (f"#L{line}" if line else "")
    if html_view:
        return f'<a href="{html.escape(href, quote=True)}"><code>{html.escape(label)}</code></a>'
    return f"[`{label}`]({href})"


def flatten_confirmed(mapping: dict[str, Any], structures: dict[str, Any]) -> list[dict[str, Any]]:
    opcode_names = {
        "zone-down": enum_names("ServerZoneIpcType"),
        "chat-down": enum_names("ServerChatIpcType"),
    }
    structure_index = {
        (item["channel"], item["packet"]): item for item in structures["structures"]
    }
    rows: list[dict[str, Any]] = []
    for entry in mapping["matches"]:
        channel = entry.get("channel", "zone-down")
        rows.append(
            {
                **entry,
                "channel": channel,
                "mappingKind": "one-to-one",
                "sapphireOpcode": opcode_names[channel].get(entry["opcode"]),
                "structure": structure_index[(channel, entry["packet"])],
            }
        )
    for entry in mapping.get("sharedMatches", []):
        channel = entry.get("channel", "zone-down")
        for opcode, packet in zip(entry["opcodes"], entry["packets"]):
            rows.append(
                {
                    **entry,
                    "channel": channel,
                    "opcode": opcode,
                    "packet": packet,
                    "mappingKind": "shared",
                    "sapphireOpcode": opcode_names[channel].get(opcode),
                    "structure": structure_index[(channel, packet)],
                }
            )
    return sorted(rows, key=lambda row: (row["channel"], int(row["opcode"], 16)))


def enum_names(enum_name: str) -> dict[str, str]:
    text = (REPO_ROOT / "src/common/Network/PacketDef/ServerIpcs.h").read_text(
        encoding="utf-8"
    )
    pattern = r"enum\s+" + re.escape(enum_name) + r"[^\{]*\{(.*?)\n\s*\};"
    match = re.search(pattern, text, re.S)
    if match is None:
        raise RuntimeError(f"could not find {enum_name}")
    return {
        f"0x{int(value, 16):04X}": name
        for name, value in re.findall(
            r"^\s*(\w+)\s*=\s*(0x[0-9A-Fa-f]+)", match.group(1), re.M
        )
    }


def one_sided_cases(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    names = {
        "zone-down": enum_names("ServerZoneIpcType"),
        "chat-down": enum_names("ServerChatIpcType"),
    }
    output: list[dict[str, Any]] = []
    for dispatcher in inventory["dispatchers"]:
        for case in dispatcher["cases"]:
            if case["status"] not in {"ps3-only", "windows-only"}:
                continue
            calls = [call for call in case["packetCalls"] if call.get("address")]
            output.append(
                {
                    "build": dispatcher["build"],
                    "channel": dispatcher["channel"],
                    "opcode": case["opcode"],
                    "status": case["status"],
                    "sapphireName": names[dispatcher["channel"]].get(case["opcode"]),
                    "dispatchKind": case["dispatchKind"],
                    "targetAddress": calls[0]["address"] if calls else None,
                    "targetName": calls[0]["name"] if calls else None,
                }
            )
    return sorted(output, key=lambda row: (row["status"], row["channel"], int(row["opcode"], 16)))


def opcode_label(row: dict[str, Any]) -> str:
    current = row.get("sapphireOpcode")
    ledger = row["packet"]
    if not current:
        return ledger
    return current if current == ledger else f"{current} (ledger: {ledger})"


def md_escape(value: Any) -> str:
    return str(value if value is not None else "—").replace("|", "\\|").replace("\n", " ")


def short_type(type_name: str | None) -> str:
    if not type_name:
        return "—"
    return type_name.rsplit("::", 1)[-1]


def call_text(calls: list[dict[str, Any]]) -> str:
    values = []
    for call in calls:
        if call.get("address"):
            values.append(f"{call.get('name') or '?'} ({call['address']})")
    return "; ".join(values) or "—"


def render_markdown(
    confirmed: list[dict[str, Any]],
    reviews: dict[str, Any],
    one_sided: list[dict[str, Any]],
    mapping: dict[str, Any],
) -> str:
    status_counts = Counter(review["status"] for review in reviews["reviews"])
    lines = [
        "# PS3 Monitor packet catalog",
        "",
        "> Generated by `python research/ps3-monitor/build_packet_catalog.py`. Do not edit manually.",
        "",
        "This view joins Sapphire opcode and payload names with PS3 Monitor DWARF types and handlers,",
        "the matched Windows handlers, structure sizes, and layout-review status. A matching numeric",
        "opcode is not by itself proof of equivalent semantics.",
        "",
        "## Summary",
        "",
        "| Item | Count |",
        "| --- | ---: |",
        f"| Confirmed opcode cases | {len(confirmed)} |",
        f"| One-to-one handler functions | {len(mapping['matches'])} |",
        f"| Shared handler functions | {len(mapping.get('sharedMatches', []))} |",
        f"| Probable reviewed cases | {status_counts['probable']} |",
        f"| Unresolved reviewed cases | {status_counts['unresolved']} |",
        f"| PS3-only numeric cases | {sum(row['status'] == 'ps3-only' for row in one_sided)} |",
        f"| Windows-only numeric cases | {sum(row['status'] == 'windows-only' for row in one_sided)} |",
        "",
        "Directions are from the server/client protocol perspective: `zone-down` and `chat-down`",
        "are server-to-client packets. Open [`packet_catalog.html`](packet_catalog.html) for searchable",
        "rows, field-level layouts, evidence, and filters.",
        "",
        "## Confirmed Sapphire ↔ PS3 ↔ Windows mappings",
        "",
        "| Channel | Opcode | Sapphire opcode | Sapphire payload | PS3 payload (size) | PS3 handler | Windows handler | Mapping | Layout |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in confirmed:
        structure = row["structure"]
        sapphire = structure["sapphire"]
        ps3_handler = f"[`{short_type(row['ps3Name'])}`]({row['ps3IdbUrl']}) `{row['ps3Address']}`"
        windows_handler = f"`{short_type(row['windowsName'])}` `{row['windowsAddress']}`"
        lines.append(
            "| "
            + " | ".join(
                md_escape(value)
                for value in (
                    row["channel"],
                    row["opcode"],
                    opcode_label(row),
                    source_link(sapphire),
                    f"`{short_type(structure['ps3Type'])}` ({structure['ps3Size']:#x})",
                    ps3_handler,
                    windows_handler,
                    row["mappingKind"],
                    structure["comparisonStatus"],
                )
            )
            + " |"
        )

    deltas = []
    for row in confirmed:
        for member in row["structure"]["members"]:
            validation = member["windowsValidation"]
            if validation["status"] == "confirmed-version-delta":
                deltas.append((row, member, validation))
    lines.extend(
        [
            "",
            "## Confirmed field-layout differences",
            "",
            "| Channel | Opcode | Packet | Field | PS3 offset | Windows offset | Evidence |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    if not deltas:
        lines.append("| — | — | — | — | — | — | None recorded |")
    for row, member, validation in deltas:
        lines.append(
            f"| {row['channel']} | {row['opcode']} | {row['packet']} | {member['name']} | "
            f"{member['offset']} | {validation['offset']} | {md_escape(validation.get('evidence'))} |"
        )

    lines.extend(
        [
            "",
            "## Reviewed but not promoted",
            "",
            "These relationships do not authorize Windows IDB names or PS3 backlinks.",
            "",
            "| Status | Channel | Opcode | Sapphire name | PS3 target | Windows target | Reason |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for review in sorted(
        reviews["reviews"], key=lambda row: (row["status"], row["channel"], int(row["ps3Opcode"], 16))
    ):
        lines.append(
            "| "
            + " | ".join(
                md_escape(value)
                for value in (
                    review["status"],
                    review["channel"],
                    review["ps3Opcode"],
                    review.get("threePointThreePacket"),
                    call_text(review["ps3PacketCalls"]),
                    call_text(review["windowsPacketCalls"]),
                    review["reasonNotConfirmed"],
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Build-only numeric dispatcher cases",
            "",
            "`ps3-only` and `windows-only` only describe numeric case presence. The Sapphire name",
            "shown is the current name at that number and is not proof of semantic equivalence.",
            "",
            "| Status | Channel | Opcode | Sapphire same-number name | Dispatch | Extracted target |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in one_sided:
        target = (
            f"{row['targetName'] or '?'} ({row['targetAddress']})" if row["targetAddress"] else "—"
        )
        lines.append(
            f"| {row['status']} | {row['channel']} | {row['opcode']} | "
            f"{md_escape(row['sapphireName'])} | {row['dispatchKind']} | {md_escape(target)} |"
        )
    lines.extend(
        [
            "",
            "## Source artifacts",
            "",
            "- [`packet_matches.json`](packet_matches.json): confirmed function mappings and evidence.",
            "- [`packet_structures.json`](packet_structures.json): PS3 layouts and Windows/Sapphire comparisons.",
            "- [`case_reviews.json`](case_reviews.json): probable and unresolved reviews.",
            "- [`dispatcher_cases.json`](dispatcher_cases.json): exhaustive dispatcher inventory.",
            "",
        ]
    )
    return "\n".join(lines)


def field_details(row: dict[str, Any]) -> str:
    structure = row["structure"]
    fields = []
    for member in structure["members"]:
        validation = member["windowsValidation"]
        win = validation["status"]
        if validation.get("offset"):
            win += f" at {validation['offset']}"
        fields.append(
            "<tr>"
            f"<td><code>{html.escape(member['offset'])}</code></td>"
            f"<td>{member['size']}</td>"
            f"<td><code>{html.escape(member['type'])}</code></td>"
            f"<td><code>{html.escape(member['name'])}</code></td>"
            f"<td>{html.escape(win)}</td>"
            "</tr>"
        )
    evidence = "".join(f"<li>{html.escape(item)}</li>" for item in row.get("evidence", []))
    return (
        f"<details><summary>{len(fields)} fields; evidence</summary>"
        '<table class="fields"><thead><tr><th>Offset</th><th>Size</th><th>Type</th><th>Name</th><th>Windows validation</th></tr></thead>'
        f"<tbody>{''.join(fields)}</tbody></table><ul>{evidence}</ul>"
        f"<p><strong>Production decision:</strong> {html.escape(structure['productionDecision'])}</p></details>"
    )


def render_html(
    confirmed: list[dict[str, Any]],
    reviews: dict[str, Any],
    one_sided: list[dict[str, Any]],
    mapping: dict[str, Any],
) -> str:
    status_counts = Counter(review["status"] for review in reviews["reviews"])
    confirmed_rows = []
    for row in confirmed:
        structure = row["structure"]
        sapphire = structure["sapphire"]
        confirmed_rows.append(
            f'<tr class="catalog-row" data-status="confirmed" data-channel="{html.escape(row["channel"])}">'
            f"<td><span class=\"badge confirmed\">confirmed</span></td>"
            f"<td>{html.escape(row['channel'])}</td><td><code>{html.escape(row['opcode'])}</code></td>"
            f"<td><strong>{html.escape(opcode_label(row))}</strong></td>"
            f"<td>{source_link(sapphire, html_view=True)}</td>"
            f"<td><code>{html.escape(short_type(structure['ps3Type']))}</code><br>{structure['ps3Size']:#x} bytes</td>"
            f'<td><a href="{html.escape(row["ps3IdbUrl"], quote=True)}"><code>{html.escape(short_type(row["ps3Name"]))}</code></a><br><code>{html.escape(row["ps3Address"])}</code></td>'
            f"<td><code>{html.escape(short_type(row['windowsName']))}</code><br><code>{html.escape(row['windowsAddress'])}</code></td>"
            f"<td>{html.escape(row['mappingKind'])}<br>{html.escape(structure['comparisonStatus'])}</td>"
            f"<td>{field_details(row)}</td></tr>"
        )

    review_rows = []
    for review in sorted(
        reviews["reviews"], key=lambda row: (row["status"], row["channel"], int(row["ps3Opcode"], 16))
    ):
        evidence = review.get("manualReview") or review["evidence"]
        details = "".join(f"<li>{html.escape(item)}</li>" for item in evidence)
        review_rows.append(
            f'<tr class="catalog-row" data-status="{html.escape(review["status"])}" data-channel="{html.escape(review["channel"])}">'
            f'<td><span class="badge {html.escape(review["status"])}">{html.escape(review["status"])}</span></td>'
            f"<td>{html.escape(review['channel'])}</td><td><code>{html.escape(review['ps3Opcode'])}</code></td>"
            f"<td>{html.escape(review.get('threePointThreePacket') or '—')}</td>"
            f"<td>{html.escape(call_text(review['ps3PacketCalls']))}</td>"
            f"<td>{html.escape(call_text(review['windowsPacketCalls']))}</td>"
            f"<td>{html.escape(review['reasonNotConfirmed'])}<details><summary>Evidence</summary><ul>{details}</ul></details></td></tr>"
        )

    one_sided_rows = []
    for row in one_sided:
        target = (
            f"{row['targetName'] or '?'} ({row['targetAddress']})" if row["targetAddress"] else "—"
        )
        one_sided_rows.append(
            f'<tr class="catalog-row" data-status="{html.escape(row["status"])}" data-channel="{html.escape(row["channel"])}">'
            f'<td><span class="badge {html.escape(row["status"])}">{html.escape(row["status"])}</span></td>'
            f"<td>{html.escape(row['channel'])}</td><td><code>{html.escape(row['opcode'])}</code></td>"
            f"<td>{html.escape(row['sapphireName'] or '—')}</td><td>{html.escape(row['dispatchKind'])}</td>"
            f"<td>{html.escape(target)}</td></tr>"
        )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PS3 Monitor packet catalog</title>
<style>
:root{{--bg:#101419;--panel:#182028;--text:#e6edf3;--muted:#9da7b1;--line:#35404b;--accent:#58a6ff;--good:#3fb950;--warn:#d29922;--bad:#f85149}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 system-ui,sans-serif}}
main{{max-width:1800px;margin:auto;padding:24px}} h1,h2{{margin-top:1.3em}} a{{color:var(--accent)}} code{{font-family:ui-monospace,monospace}}
.summary{{display:flex;flex-wrap:wrap;gap:12px}} .card{{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px 16px;min-width:150px}} .card b{{display:block;font-size:24px}}
.controls{{position:sticky;top:0;z-index:2;display:flex;gap:8px;flex-wrap:wrap;background:rgba(16,20,25,.96);padding:12px 0}} input,select{{background:var(--panel);color:var(--text);border:1px solid var(--line);border-radius:6px;padding:8px}}
input{{min-width:320px}} .table-wrap{{overflow:auto;border:1px solid var(--line);border-radius:8px}} table{{border-collapse:collapse;width:100%;background:var(--panel)}} th,td{{border-bottom:1px solid var(--line);padding:8px;vertical-align:top;text-align:left}} th{{position:sticky;top:0;background:#202a34}} tr:hover{{background:#202a34}}
.badge{{display:inline-block;border-radius:999px;padding:2px 7px;font-size:12px}} .confirmed{{background:#173d25;color:#7ee787}} .probable{{background:#453715;color:#e3b341}} .unresolved{{background:#472024;color:#ff7b72}} .ps3-only,.windows-only{{background:#27384a;color:#79c0ff}}
details{{max-width:700px}} summary{{cursor:pointer;color:var(--accent)}} .fields{{margin-top:8px;font-size:12px}} .fields th{{position:static}} .muted{{color:var(--muted)}} .hidden{{display:none}}
</style></head><body><main>
<h1>PS3 Monitor packet catalog</h1>
<p class="muted">Generated from the source-controlled dispatcher, match, structure, and review ledgers. Numeric opcode equality alone is not semantic proof.</p>
<div class="summary">
<div class="card"><b>{len(confirmed)}</b>confirmed cases</div><div class="card"><b>{len(mapping['matches'])}</b>one-to-one functions</div><div class="card"><b>{len(mapping.get('sharedMatches', []))}</b>shared functions</div>
<div class="card"><b>{status_counts['probable']}</b>probable</div><div class="card"><b>{status_counts['unresolved']}</b>unresolved</div>
<div class="card"><b>{sum(row['status']=='ps3-only' for row in one_sided)}</b>PS3-only numbers</div><div class="card"><b>{sum(row['status']=='windows-only' for row in one_sided)}</b>Windows-only numbers</div>
</div>
<div class="controls"><input id="search" type="search" placeholder="Search opcode, packet, type, handler, evidence…"><select id="status"><option value="">All statuses</option><option>confirmed</option><option>probable</option><option>unresolved</option><option>ps3-only</option><option>windows-only</option></select><select id="channel"><option value="">All channels</option><option>zone-down</option><option>chat-down</option></select><span id="visible" class="muted"></span></div>
<h2>Confirmed Sapphire ↔ PS3 ↔ Windows mappings</h2>
<div class="table-wrap"><table><thead><tr><th>Status</th><th>Channel</th><th>Opcode</th><th>Sapphire opcode</th><th>Sapphire payload</th><th>PS3 payload</th><th>PS3 handler</th><th>Windows handler</th><th>Mapping/layout</th><th>Fields/evidence</th></tr></thead><tbody>{''.join(confirmed_rows)}</tbody></table></div>
<h2>Reviewed but not promoted</h2><p class="muted">These rows do not authorize Windows IDB names or PS3 backlinks.</p>
<div class="table-wrap"><table><thead><tr><th>Status</th><th>Channel</th><th>Opcode</th><th>Sapphire name</th><th>PS3 target</th><th>Windows target</th><th>Reason/evidence</th></tr></thead><tbody>{''.join(review_rows)}</tbody></table></div>
<h2>Build-only numeric dispatcher cases</h2><p class="muted">The Sapphire name is the current name at the same number, not proof of semantic equivalence.</p>
<div class="table-wrap"><table><thead><tr><th>Status</th><th>Channel</th><th>Opcode</th><th>Sapphire same-number name</th><th>Dispatch</th><th>Extracted target</th></tr></thead><tbody>{''.join(one_sided_rows)}</tbody></table></div>
<p>Machine-readable sources: <a href="packet_matches.json">matches</a>, <a href="packet_structures.json">structures</a>, <a href="case_reviews.json">reviews</a>, and <a href="dispatcher_cases.json">dispatchers</a>.</p>
</main><script>
const search=document.querySelector('#search'),status=document.querySelector('#status'),channel=document.querySelector('#channel'),visible=document.querySelector('#visible');
function filter(){{const q=search.value.toLowerCase();let shown=0,total=0;document.querySelectorAll('.catalog-row').forEach(row=>{{total++;const ok=(!q||row.textContent.toLowerCase().includes(q))&&(!status.value||row.dataset.status===status.value)&&(!channel.value||row.dataset.channel===channel.value);row.classList.toggle('hidden',!ok);if(ok)shown++;}});visible.textContent=`${{shown}} / ${{total}} rows`;}}
search.addEventListener('input',filter);status.addEventListener('change',filter);channel.addEventListener('change',filter);filter();
</script></body></html>"""


def build_outputs(root: Path = ROOT) -> tuple[str, str]:
    mapping = load(root, "packet_matches.json")
    structures = load(root, "packet_structures.json")
    reviews = load(root, "case_reviews.json")
    inventory = load(root, "dispatcher_cases.json")
    confirmed = flatten_confirmed(mapping, structures)
    one_sided = one_sided_cases(inventory)
    return (
        render_markdown(confirmed, reviews, one_sided, mapping),
        render_html(confirmed, reviews, one_sided, mapping),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if generated files are stale")
    args = parser.parse_args()
    markdown, html_text = build_outputs()
    outputs = {ROOT / "PACKET_CATALOG.md": markdown, ROOT / "packet_catalog.html": html_text}
    if args.check:
        stale = [str(path) for path, content in outputs.items() if not path.exists() or path.read_text(encoding="utf-8") != content]
        if stale:
            raise SystemExit("stale generated packet catalogs: " + ", ".join(stale))
        print("packet catalogs are current")
        return
    for path, content in outputs.items():
        path.write_text(content, encoding="utf-8", newline="\n")
    print(f"wrote {len(outputs)} catalogs")


if __name__ == "__main__":
    main()

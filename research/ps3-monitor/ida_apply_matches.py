"""Apply or verify confirmed PS3 Monitor mappings in the Windows IDB.

Load through IDA Nexus with an active Windows database, then call
`apply_confirmed_matches(db, mapping_path)` or
`verify_confirmed_matches(db, mapping_path)`. The PS3 database is never opened
or modified by this module.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _entries(mapping: dict[str, Any]) -> list[dict[str, Any]]:
    return (
        mapping.get("dispatchers", [])
        + mapping.get("supportingFunctions", [])
        + mapping.get("matches", [])
        + mapping.get("sharedMatches", [])
    )


def _load(mapping_path: str | Path) -> dict[str, Any]:
    return json.loads(Path(mapping_path).read_text(encoding="utf-8"))


def _comment(entry: dict[str, Any]) -> str:
    evidence = " ".join(entry.get("evidence", []))
    first_line = f"PS3 Monitor: {entry['ps3IdbUrl']}"
    return first_line if not evidence else f"{first_line}\nEvidence: {evidence}"


def verify_confirmed_matches(db: Any, mapping_path: str | Path) -> dict[str, Any]:
    mapping = _load(mapping_path)
    failures: list[dict[str, Any]] = []
    checked = 0
    for entry in _entries(mapping):
        if entry.get("confidence") != "high":
            continue
        checked += 1
        address = int(entry["windowsAddress"], 16)
        function = db.functions.get_at(address)
        if function is None:
            failures.append({"windowsAddress": entry["windowsAddress"], "error": "missing function"})
            continue
        actual_name = db.functions.get_name(function)
        actual_comment = db.functions.get_comment(function, repeatable=True) or ""
        expected_first_line = f"PS3 Monitor: {entry['ps3IdbUrl']}"
        if actual_name != entry["windowsName"]:
            failures.append(
                {
                    "windowsAddress": entry["windowsAddress"],
                    "error": "name mismatch",
                    "expected": entry["windowsName"],
                    "actual": actual_name,
                }
            )
        if not actual_comment.startswith(expected_first_line):
            failures.append(
                {
                    "windowsAddress": entry["windowsAddress"],
                    "error": "comment link mismatch",
                    "expected": expected_first_line,
                    "actual": actual_comment.splitlines()[0] if actual_comment else "",
                }
            )
    return {"checked": checked, "failures": failures, "ok": not failures}


def apply_confirmed_matches(
    db: Any, mapping_path: str | Path, *, force_names: bool = False
) -> dict[str, Any]:
    mapping = _load(mapping_path)
    applied: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for entry in _entries(mapping):
        if entry.get("confidence") != "high":
            continue
        address = int(entry["windowsAddress"], 16)
        function = db.functions.get_at(address)
        if function is None:
            failures.append({"windowsAddress": entry["windowsAddress"], "error": "missing function"})
            continue
        current_name = db.functions.get_name(function)
        expected_name = entry["windowsName"]
        auto_name = current_name.startswith(("sub_", "nullsub_", "j_sub_"))
        if current_name != expected_name and not (auto_name or force_names):
            failures.append(
                {
                    "windowsAddress": entry["windowsAddress"],
                    "error": "refusing to replace intentional name",
                    "expected": expected_name,
                    "actual": current_name,
                }
            )
            continue
        name_ok = current_name == expected_name or db.functions.set_name(function, expected_name)
        comment_ok = db.functions.set_comment(function, _comment(entry), repeatable=True)
        if name_ok and comment_ok:
            applied.append(
                {
                    "windowsAddress": entry["windowsAddress"],
                    "windowsName": expected_name,
                    "ps3IdbUrl": entry["ps3IdbUrl"],
                }
            )
        else:
            failures.append(
                {
                    "windowsAddress": entry["windowsAddress"],
                    "error": "IDA rejected name or comment",
                    "nameOk": name_ok,
                    "commentOk": comment_ok,
                }
            )
    return {"applied": applied, "failures": failures, "ok": not failures}

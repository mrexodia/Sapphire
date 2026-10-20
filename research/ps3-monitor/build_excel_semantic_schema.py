"""Build a version-specific semantic-schema seed for the PS3 EXD explorer.

The output keeps physical EXH columns, monitor-DWARF labels, typed DataManager
getters, and newer EXDSchema hints as separate evidence layers. Newer schemas
are never silently treated as PS3 truth: hints are admitted only when their
flattened field count matches the PS3 sheet and remain cross-version candidates.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - only used by the optional hint source
    yaml = None


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def flatten_schema_fields(fields: list[dict[str, Any]], prefix: str = "") -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    unknown = 0
    for field in fields:
        name = field.get("name")
        if not name:
            unknown += 1
            name = f"Unknown{unknown}"
        path = f"{prefix}.{name}" if prefix else name
        if field.get("type") == "array":
            count = int(field.get("count", 0))
            children = field.get("fields") or []
            for index in range(count):
                item = f"{path}[{index}]"
                if children:
                    result.extend(flatten_schema_fields(children, item))
                else:
                    result.append({"name": item, "definition": field})
        else:
            result.append({"name": path, "definition": field})
    return result


def modern_hints(root: Path | None, sheet: str, columns: int) -> list[dict[str, Any]] | None:
    if root is None or yaml is None:
        return None
    path = root / f"{sheet}.yml"
    if not path.is_file():
        return None
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    fields = flatten_schema_fields(document.get("fields", []))
    if len(fields) != columns:
        return None
    result = []
    for field in fields:
        definition = field["definition"]
        hint: dict[str, Any] = {"name": field["name"]}
        if definition.get("type") == "link":
            if "targets" in definition:
                hint["reference"] = {"targets": definition["targets"]}
            elif "condition" in definition:
                hint["reference"] = {"condition": definition["condition"]}
        if "comment" in definition:
            hint["comment"] = definition["comment"]
        result.append(hint)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=Path("build"))
    parser.add_argument("--modern-schemas", type=Path,
                        default=Path("C:/CodeBlocks/EXDSchema/schemas/latest"))
    parser.add_argument("--overrides", type=Path,
                        default=Path(__file__).with_name("ps3-exd-overrides.json"))
    parser.add_argument("--output", type=Path, default=Path("build/ps3-exd-semantic-schema.json"))
    args = parser.parse_args()

    scan = load(args.build / "ps3-exd-scan.json")
    candidates = load(args.build / "ps3-excel-column-candidates.json")
    getters = load(args.build / "ps3-excel-getters.json")
    candidate_by_sheet = {entry["sheet"]: entry for entry in candidates}
    getter_by_index: dict[int, list[dict[str, Any]]] = {}
    for getter in getters["getters"]:
        getter_by_index.setdefault(getter["sheet_index"], []).append(getter)
    overrides = load(args.overrides).get("sheets", {}) if args.overrides.is_file() else {}

    output_sheets = []
    monitor_named = modern_compatible = typed_getter_sheets = 0
    for source in scan["sheets"]:
        if "schema" not in source:
            continue
        name = source["name"]
        root_id = int(source["root_id"])
        physical = source["schema"]
        monitor = candidate_by_sheet.get(name, {}).get("columns", [])
        modern = modern_hints(args.modern_schemas, name, len(physical["columns"]))
        if modern:
            modern_compatible += 1
        sheet_getters = getter_by_index.get(root_id, [])
        if sheet_getters:
            typed_getter_sheets += 1

        fields = []
        sheet_has_monitor_name = False
        script_text_layout = ("/" in name and len(physical["columns"]) == 2 and
                              all(column["type_name"] == "string" for column in physical["columns"]))
        for index, column in enumerate(physical["columns"]):
            labels = []
            if script_text_layout:
                labels.append({
                    "name": ("Symbol" if index == 0 else "Text"),
                    "confidence": "format_inferred_candidate",
                    "evidence": "all 1,798 slash-named PS3 sheets share the same two-string script-localization layout",
                })
            if index < len(monitor):
                names = monitor[index].get("debug_field_candidates", [])
                for label in names:
                    labels.append({
                        "name": label,
                        "confidence": "metadata_candidate",
                        "evidence": "monitor DWARF member matched by offset, width, and packed bit",
                    })
                sheet_has_monitor_name |= len(names) == 1
            if modern:
                hint = modern[index]
                labels.append({
                    "name": hint["name"],
                    "confidence": "cross_version_candidate",
                    "evidence": "newer EXDSchema flattened column count matches PS3 sheet",
                })
            preferred = next((item["name"] for item in labels
                              if item["confidence"] == "metadata_candidate"),
                             labels[0]["name"] if labels else f"Column{index}")
            field: dict[str, Any] = {
                "column": index,
                "name": preferred,
                "physical": column,
                "labels": labels,
                "references": [],
            }
            if modern and "reference" in modern[index]:
                field["references"].append({
                    **modern[index]["reference"],
                    "lookup": "unresolved",
                    "confidence": "cross_version_candidate",
                    "evidence": "newer EXDSchema only; consumer tracing required",
                })
            fields.append(field)
        monitor_named += sheet_has_monitor_name

        override = overrides.get(name, {})
        for column_text, label in override.get("labels", {}).items():
            column = int(column_text)
            if column < 0 or column >= len(fields):
                raise RuntimeError(f"Override label column {name}[{column}] does not exist")
            item = {
                "name": label["name"],
                "confidence": label["confidence"],
                "evidence": label["evidence"],
            }
            fields[column]["labels"].insert(0, item)
            fields[column]["name"] = item["name"]
        fields_by_name = {field["name"]: field for field in fields}
        for field_name, relation_spec in override.get("fields", {}).items():
            if field_name not in fields_by_name:
                raise RuntimeError(f"Override field {name}.{field_name} does not exist")
            relations = relation_spec if isinstance(relation_spec, list) else [relation_spec]
            fields_by_name[field_name]["references"] = [{
                "targets": relation["targets"],
                "lookup": relation.get("lookup", "main_key"),
                "sentinels": relation.get("sentinels", [0]),
                "confidence": relation["confidence"],
                "evidence": relation["evidence"],
                **( {"when": relation["when"]} if "when" in relation else {} ),
                **( {"source_rows": relation["source_rows"]} if "source_rows" in relation else {} ),
            } for relation in relations]

        output_sheets.append({
            "name": name,
            "root_id": root_id,
            "display_field": override.get("display_field"),
            "physical": {
                key: physical[key]
                for key in ("version", "fixed_size", "key_count", "row_count", "languages", "pages")
            },
            "getters": [{
                key: getter.get(key)
                for key in ("address", "function", "return_type", "lookup", "argument_expression")
            } for getter in sheet_getters],
            "consumers": override.get("consumers", []),
            "fields": fields,
        })

    result = {
        "schema_version": 1,
        "source_build": "PS3 Monitor corpus",
        "confidence_levels": {
            "format_inferred_candidate": "uniform PS3 corpus layout and value role; consumer-level proof is incomplete",
            "legacy_struct_candidate": "PS3 typed reader layout matches physical size, offsets and types; consumer-level proof is incomplete",
            "metadata_candidate": "PS3 DWARF layout match; semantic relation not implied",
            "cross_version_candidate": "newer EXDSchema hint with matching flattened count; must be verified",
            "conditional_candidate": "target set is known but a selector-dependent resolver is incomplete",
            "content_workflow_candidate": "same-content sequence evidence suggests a runtime relationship; no client-side arithmetic lookup is proven",
            "source_code_confirmed": "Sapphire server/tool code resolves the field as the target row type",
            "disassembly_confirmed": "a traced PS3 consumer callsite resolves the field through the target getter",
            "runtime_confirmed": "observed monitor behavior",
        },
        "statistics": {
            "sheets": len(output_sheets),
            "sheets_with_monitor_label_candidates": monitor_named,
            "sheets_with_typed_getters": typed_getter_sheets,
            "sheets_with_column-count-compatible_modern_schema": modern_compatible,
        },
        "sheets": output_sheets,
    }
    save(args.output, result)
    print(json.dumps(result["statistics"], indent=2))


if __name__ == "__main__":
    main()

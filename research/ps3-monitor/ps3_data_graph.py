"""Build and query an evidence-qualified PS3 game-data graph.

The graph combines decoded EXD rows, semantic-schema fields/links, asset paths,
and lexical references from Sapphire's server/tool source. Numeric coincidences
remain searchable facts; only declared resolvers become graph edges.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
import difflib
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
from typing import Any, Iterable

WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]{2,}")
NUMBER_RE = re.compile(r"(?<![A-Za-z0-9_])(?:0[xX][0-9A-Fa-f]+|[1-9][0-9]*)(?![A-Za-z0-9_])")
ASSET_RE = re.compile(r"(?i)(?:^|/)[^\x00]+\.(?:lvb|lgb|sgb)$")
STOP_WORDS = {"a", "all", "and", "are", "based", "how", "in", "involved", "is", "of", "on", "the", "to", "what"}
SOURCE_SUFFIXES = {".cpp", ".h", ".hpp", ".c", ".sql", ".json", ".md"}


def connect(path: Path, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        db = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    else:
        db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


def schema_sql(db: sqlite3.Connection) -> None:
    db.executescript("""
    PRAGMA journal_mode=WAL;
    PRAGMA synchronous=OFF;
    PRAGMA temp_store=MEMORY;
    CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE sheet(
      sheet_id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, root_id INTEGER NOT NULL,
      display_column INTEGER, physical_json TEXT NOT NULL, getters_json TEXT NOT NULL,
      consumers_json TEXT NOT NULL);
    CREATE TABLE field(
      field_id INTEGER PRIMARY KEY, sheet_id INTEGER NOT NULL REFERENCES sheet(sheet_id),
      column_index INTEGER NOT NULL, name TEXT NOT NULL, confidence TEXT NOT NULL,
      type_name TEXT NOT NULL, type_code INTEGER NOT NULL, fixed_offset INTEGER NOT NULL,
      references_json TEXT NOT NULL, labels_json TEXT NOT NULL,
      UNIQUE(sheet_id, column_index));
    CREATE TABLE row_data(
      row_pk INTEGER PRIMARY KEY, sheet_id INTEGER NOT NULL REFERENCES sheet(sheet_id),
      language INTEGER NOT NULL, main_id INTEGER NOT NULL, ordinal INTEGER NOT NULL,
      subkeys_json TEXT NOT NULL, values_json TEXT NOT NULL, display TEXT,
      UNIQUE(sheet_id, main_id, ordinal));
    CREATE INDEX row_key_idx ON row_data(sheet_id, main_id);
    CREATE TABLE number_cell(
      row_pk INTEGER NOT NULL REFERENCES row_data(row_pk), field_id INTEGER NOT NULL REFERENCES field(field_id),
      value INTEGER NOT NULL, PRIMARY KEY(row_pk, field_id));
    CREATE INDEX number_value_idx ON number_cell(value);
    CREATE TABLE text_cell(
      row_pk INTEGER NOT NULL REFERENCES row_data(row_pk), field_id INTEGER NOT NULL REFERENCES field(field_id),
      value TEXT NOT NULL, PRIMARY KEY(row_pk, field_id));
    CREATE TABLE edge(
      edge_id INTEGER PRIMARY KEY, source_row INTEGER NOT NULL REFERENCES row_data(row_pk),
      source_field INTEGER REFERENCES field(field_id), target_row INTEGER REFERENCES row_data(row_pk),
      target_kind TEXT NOT NULL, target_name TEXT NOT NULL, confidence TEXT NOT NULL,
      evidence TEXT NOT NULL, UNIQUE(source_row, source_field, target_kind, target_name));
    CREATE INDEX edge_source_idx ON edge(source_row);
    CREATE INDEX edge_target_idx ON edge(target_row);
    CREATE TABLE asset(asset_id INTEGER PRIMARY KEY, path TEXT NOT NULL UNIQUE, kind TEXT NOT NULL);
    CREATE TABLE asset_edge(
      source_asset INTEGER NOT NULL REFERENCES asset(asset_id), target_asset INTEGER NOT NULL REFERENCES asset(asset_id),
      relation TEXT NOT NULL, confidence TEXT NOT NULL, evidence TEXT NOT NULL,
      PRIMARY KEY(source_asset,target_asset,relation));
    CREATE TABLE layer_set(
      lvb_asset INTEGER NOT NULL REFERENCES asset(asset_id), layer_set_id INTEGER NOT NULL,
      territory_type_id INTEGER NOT NULL, name TEXT NOT NULL, navmesh_path TEXT, references_json TEXT NOT NULL,
      PRIMARY KEY(lvb_asset,layer_set_id));
    CREATE TABLE placement(
      placement_id INTEGER PRIMARY KEY, lgb_asset INTEGER NOT NULL REFERENCES asset(asset_id),
      group_id INTEGER NOT NULL, group_name TEXT NOT NULL, entry_index INTEGER NOT NULL,
      type INTEGER NOT NULL, type_name TEXT NOT NULL, instance_id INTEGER NOT NULL,
      name TEXT NOT NULL, base_id INTEGER, sgb_path TEXT,
      UNIQUE(lgb_asset,group_id,entry_index));
    CREATE INDEX placement_instance_idx ON placement(instance_id);
    CREATE INDEX placement_base_idx ON placement(base_id);
    CREATE TABLE sgb_timeline(
      sgb_asset INTEGER NOT NULL REFERENCES asset(asset_id), member_id INTEGER NOT NULL,
      name TEXT NOT NULL, timeline_id INTEGER NOT NULL, auto_play INTEGER NOT NULL,
      loop_playback INTEGER NOT NULL, collision_state INTEGER NOT NULL,
      PRIMARY KEY(sgb_asset,member_id));
    CREATE TABLE sgb_slot(
      sgb_asset INTEGER NOT NULL REFERENCES asset(asset_id), slot_index INTEGER NOT NULL,
      mask INTEGER NOT NULL, member_id INTEGER NOT NULL, name TEXT,
      PRIMARY KEY(sgb_asset,slot_index));
    CREATE TABLE lua_script(
      script_id INTEGER PRIMARY KEY, directory_hash TEXT NOT NULL, filename_hash TEXT NOT NULL,
      logical_offset INTEGER NOT NULL, source_names_json TEXT NOT NULL, display_path TEXT NOT NULL);
    CREATE TABLE lua_symbol(
      script_id INTEGER NOT NULL REFERENCES lua_script(script_id), symbol TEXT NOT NULL,
      kind TEXT NOT NULL, uses INTEGER NOT NULL, PRIMARY KEY(script_id,symbol));
    CREATE INDEX lua_symbol_idx ON lua_symbol(symbol);
    CREATE VIRTUAL TABLE lua_fts USING fts5(script_id UNINDEXED, path, symbol, kind,
      tokenize='unicode61 remove_diacritics 2');
    CREATE TABLE lua_row_link(
      script_id INTEGER NOT NULL REFERENCES lua_script(script_id), symbol TEXT NOT NULL,
      row_pk INTEGER NOT NULL REFERENCES row_data(row_pk), field_id INTEGER NOT NULL REFERENCES field(field_id),
      confidence TEXT NOT NULL, evidence TEXT NOT NULL,
      PRIMARY KEY(script_id,symbol,row_pk,field_id));
    CREATE INDEX lua_row_target_idx ON lua_row_link(row_pk);
    CREATE TABLE lua_source_file(
      file_id INTEGER PRIMARY KEY, script_id INTEGER REFERENCES lua_script(script_id),
      path TEXT NOT NULL UNIQUE, sha256 TEXT NOT NULL, provenance TEXT NOT NULL);
    CREATE TABLE lua_source_reference(
      file_id INTEGER NOT NULL REFERENCES lua_source_file(file_id), line INTEGER NOT NULL,
      qualifier TEXT NOT NULL, symbol TEXT NOT NULL, context TEXT NOT NULL,
      PRIMARY KEY(file_id,line,qualifier,symbol));
    CREATE INDEX lua_source_symbol_idx ON lua_source_reference(symbol);
    CREATE VIRTUAL TABLE lua_source_fts USING fts5(file_id UNINDEXED, path UNINDEXED, content,
      tokenize='unicode61 remove_diacritics 2');
    CREATE TABLE source_number(value INTEGER NOT NULL, path TEXT NOT NULL, line INTEGER NOT NULL,
      context TEXT NOT NULL, semantic TEXT);
    CREATE INDEX source_number_idx ON source_number(value);
    CREATE TABLE word(word TEXT PRIMARY KEY, uses INTEGER NOT NULL);
    CREATE VIRTUAL TABLE row_fts USING fts5(row_pk UNINDEXED, sheet, row_key, content, tokenize='unicode61 remove_diacritics 2');
    CREATE VIRTUAL TABLE source_fts USING fts5(path UNINDEXED, content, tokenize='unicode61 remove_diacritics 2');
    """)


def label_confidence(field: dict[str, Any]) -> str:
    for label in field.get("labels", []):
        if label.get("name") == field["name"]:
            return label.get("confidence", "candidate")
    return "physical_only"


def insert_schema(db: sqlite3.Connection, schema: dict[str, Any]) -> tuple[dict[str, int], dict[str, list[int]], dict[str, int | None]]:
    sheet_ids: dict[str, int] = {}
    field_ids: dict[str, list[int]] = {}
    display_columns: dict[str, int | None] = {}
    for sheet in schema["sheets"]:
        display = sheet.get("display_field")
        display_column = next((f["column"] for f in sheet["fields"] if f["name"] == display), None)
        cursor = db.execute(
            "INSERT INTO sheet(name,root_id,display_column,physical_json,getters_json,consumers_json) VALUES(?,?,?,?,?,?)",
            (sheet["name"], sheet["root_id"], display_column, json.dumps(sheet["physical"], separators=(",", ":")),
             json.dumps(sheet.get("getters", []), separators=(",", ":")),
             json.dumps(sheet.get("consumers", []), separators=(",", ":"))))
        sid = int(cursor.lastrowid)
        sheet_ids[sheet["name"]] = sid
        display_columns[sheet["name"]] = display_column
        ids: list[int] = []
        for field in sheet["fields"]:
            physical = field["physical"]
            cursor = db.execute(
                "INSERT INTO field(sheet_id,column_index,name,confidence,type_name,type_code,fixed_offset,references_json,labels_json) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (sid, field["column"], field["name"], label_confidence(field), physical["type_name"], physical["type"],
                 physical["offset"], json.dumps(field.get("references", []), separators=(",", ":")),
                 json.dumps(field.get("labels", []), separators=(",", ":"))))
            ids.append(int(cursor.lastrowid))
        field_ids[sheet["name"]] = ids
    return sheet_ids, field_ids, display_columns


def words(text: str) -> Iterable[str]:
    return (match.group(0).lower() for match in WORD_RE.finditer(text))


def stream_rows(db: sqlite3.Connection, inspector: Path, sqpack: Path, language: int,
                sheet_ids: dict[str, int], field_ids: dict[str, list[int]],
                display_columns: dict[str, int | None]) -> tuple[int, Counter[str]]:
    command = [str(inspector), "exd-stream", str(sqpack), str(language)]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               encoding="utf-8", errors="replace", bufsize=1024 * 1024)
    assert process.stdout is not None
    vocabulary: Counter[str] = Counter()
    count = 0
    for line in process.stdout:
        record = json.loads(line)
        if record.get("error"):
            process.kill()
            raise RuntimeError(f"{record['sheet']}: {record['message']}")
        name = record["s"]
        sid = sheet_ids[name]
        values = record["v"]
        display_column = display_columns[name]
        display = values[display_column] if display_column is not None and display_column < len(values) and isinstance(values[display_column], str) else None
        cursor = db.execute(
            "INSERT INTO row_data(sheet_id,language,main_id,ordinal,subkeys_json,values_json,display) VALUES(?,?,?,?,?,?,?)",
            (sid, record["l"], record["i"], record["o"], json.dumps(record["k"], separators=(",", ":")),
             json.dumps(values, ensure_ascii=False, separators=(",", ":")), display))
        row_pk = int(cursor.lastrowid)
        searchable: list[str] = []
        ids = field_ids[name]
        for index, value in enumerate(values):
            if index >= len(ids):
                continue
            if isinstance(value, str):
                if value:
                    db.execute("INSERT INTO text_cell(row_pk,field_id,value) VALUES(?,?,?)", (row_pk, ids[index], value))
                    searchable.append(value)
                    vocabulary.update(words(value))
            elif isinstance(value, int) and not isinstance(value, bool) and value != 0 and -(1 << 63) <= value < (1 << 63):
                db.execute("INSERT INTO number_cell(row_pk,field_id,value) VALUES(?,?,?)", (row_pk, ids[index], value))
        key = f"{record['i']}" + (":" + ":".join(map(str, record["k"])) if record["k"] else "")
        db.execute("INSERT INTO row_fts(row_pk,sheet,row_key,content) VALUES(?,?,?,?)",
                   (row_pk, name, key, "\n".join(searchable)))
        count += 1
        if count % 5000 == 0:
            db.commit()
            print(f"indexed {count} EXD rows", file=sys.stderr)
    stderr = process.stderr.read() if process.stderr else ""
    code = process.wait()
    if code:
        raise RuntimeError(f"EXD streamer failed ({code}): {stderr.strip()}")
    print(stderr.strip(), file=sys.stderr)
    return count, vocabulary


def lua_sheet_name(source: str) -> str:
    name = source.lstrip("@")
    name = re.sub(r"\.(?:cli|cmn)\.lua$", "", name, flags=re.IGNORECASE)
    return name


def index_lua(db: sqlite3.Connection, sqpack: Path) -> tuple[int, int, int]:
    import inspect_monitor_scripts as lua
    base = sqpack / "ffxiv"
    payload, _ = lua.unwrap(base / "0b0000.ps3.d.dat0.sdat")
    scripts = symbols = 0
    for directory, filename, offset, data in lua.records(base / "0b0000.ps3.d.index", payload):
        if not data.startswith(b"\x1bLua"):
            continue
        chunk = lua.Chunk(data)
        chunk.prototype()
        lua.check(chunk.pos == len(data), "Unconsumed bytes after Lua prototype")
        sources = sorted(chunk.sources)
        display = next((source for source in sources if source != "=(luac)"),
                       f"{directory:08x}/{filename:08x}.luac")
        cursor = db.execute(
            "INSERT INTO lua_script(directory_hash,filename_hash,logical_offset,source_names_json,display_path) VALUES(?,?,?,?,?)",
            (f"{directory:08x}", f"{filename:08x}", offset,
             json.dumps(sources, separators=(",", ":")), display))
        script_id = int(cursor.lastrowid)
        for symbol, uses in chunk.strings.items():
            kind = "table_member" if symbol in chunk.table_members else "string_constant"
            actual_uses = chunk.table_members.get(symbol, uses)
            db.execute("INSERT INTO lua_symbol VALUES(?,?,?,?)", (script_id, symbol, kind, actual_uses))
            db.execute("INSERT INTO lua_fts VALUES(?,?,?,?)", (script_id, display, symbol, kind))
            symbols += 1
        scripts += 1
    # A globally unique exact value is useful as a candidate; repeated tokens such as
    # ACTOR0 are deliberately not sprayed across every script-local sheet.
    db.execute("""
      INSERT OR IGNORE INTO lua_row_link(script_id,symbol,row_pk,field_id,confidence,evidence)
      SELECT ls.script_id,ls.symbol,t.row_pk,t.field_id,'exact_value_candidate',
             'Lua table-member operand exactly matches one unique PS3 EXD string cell'
      FROM lua_symbol ls JOIN text_cell t ON t.value=ls.symbol
      JOIN (SELECT value FROM text_cell GROUP BY value HAVING COUNT(*)=1) unique_value ON unique_value.value=ls.symbol
      WHERE ls.kind='table_member'
    """)
    # A debug source path matching the script-local sheet plus an exact member token
    # is stronger structural evidence, including intentionally repeated symbols.
    for script in db.execute("SELECT script_id,source_names_json FROM lua_script").fetchall():
        sheets = {lua_sheet_name(source).lower() for source in json.loads(script["source_names_json"])}
        if not sheets:
            continue
        placeholders = ",".join("?" for _ in sheets)
        db.execute(f"""
          INSERT OR REPLACE INTO lua_row_link(script_id,symbol,row_pk,field_id,confidence,evidence)
          SELECT ls.script_id,ls.symbol,t.row_pk,t.field_id,'structural_candidate',
            'Lua debug source path names this script-local EXD sheet and the member token exactly matches its Symbol cell'
          FROM lua_symbol ls JOIN text_cell t ON t.value=ls.symbol JOIN row_data r USING(row_pk)
          JOIN sheet s USING(sheet_id)
          WHERE ls.script_id=? AND ls.kind='table_member' AND lower(s.name) IN ({placeholders})
        """, (script["script_id"], *sheets))
    links = db.execute("SELECT COUNT(*) FROM lua_row_link").fetchone()[0]
    return scripts, symbols, links


def index_lua_sources(db: sqlite3.Connection, root: Path) -> tuple[int, int, int]:
    if not root.is_dir():
        return 0, 0, 0
    exact: dict[str, set[int]] = {}
    basename: dict[str, set[int]] = {}
    for script in db.execute("SELECT script_id,source_names_json FROM lua_script"):
        for source in json.loads(script["source_names_json"]):
            if source == "=(luac)":
                continue
            normalized = lua_sheet_name(source).replace(chr(92), "/").lower()
            exact.setdefault(normalized, set()).add(script["script_id"])
            basename.setdefault(normalized.rsplit("/", 1)[-1], set()).add(script["script_id"])

    files = references = mapped = 0
    member_pattern = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*[.:]\s*([A-Z][A-Z0-9_]{2,})\b")
    for path in sorted(root.rglob("*.lua")):
        content = path.read_text(encoding="utf-8", errors="replace")
        relative = path.relative_to(root).as_posix()
        key = path.relative_to(root).with_suffix("").as_posix().lower()
        candidates = exact.get(key, set())
        if len(candidates) != 1:
            candidates = basename.get(path.stem.lower(), set())
        script_id = next(iter(candidates)) if len(candidates) == 1 else None
        mapped += script_id is not None
        provenance = "authentic_source_payload" if relative.lower() == "leve/gld10000.lua" else "recovered_decompilation"
        cursor = db.execute("INSERT INTO lua_source_file(script_id,path,sha256,provenance) VALUES(?,?,?,?)",
                            (script_id, relative, hashlib.sha256(content.encode("utf-8")).hexdigest(), provenance))
        file_id = int(cursor.lastrowid)
        db.execute("INSERT INTO lua_source_fts VALUES(?,?,?)", (file_id, relative, content))
        for line_number, line in enumerate(content.splitlines(), 1):
            for match in member_pattern.finditer(line):
                db.execute("INSERT OR IGNORE INTO lua_source_reference VALUES(?,?,?,?,?)",
                           (file_id, line_number, match.group(1), match.group(2), line.strip()))
                references += 1
        files += 1
    references = db.execute("SELECT COUNT(*) FROM lua_source_reference").fetchone()[0]
    return files, mapped, references


def index_source(db: sqlite3.Connection, root: Path) -> tuple[int, int]:
    files = numbers = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        relative = path.relative_to(root).as_posix()
        db.execute("INSERT INTO source_fts(path,content) VALUES(?,?)", (relative, content))
        files += 1
        for line_number, line in enumerate(content.splitlines(), 1):
            semantic_spans: list[tuple[int, int, str]] = []
            for match in re.finditer(r'addEObj\s*\(\s*"([^"]*)"\s*,\s*(0[xX][0-9A-Fa-f]+|[0-9]+)', line):
                semantic_spans.append((match.start(2), match.end(2), f"EObj main key ({match.group(1)})"))
            for match in re.finditer(r'InstanceContentScript\s*\(\s*(0[xX][0-9A-Fa-f]+|[0-9]+)', line):
                semantic_spans.append((match.start(1), match.end(1), "InstanceContent main key"))
            for match in re.finditer(r'getRow\s*<\s*Excel::(?:(?:Ps3)::)?(\w+)\s*>\s*\(\s*(0[xX][0-9A-Fa-f]+|[0-9]+)', line):
                semantic_spans.append((match.start(2), match.end(2), f"{match.group(1)} main key"))
            seen = set()
            for match in NUMBER_RE.finditer(line):
                value = int(match.group(0), 0)
                if value in seen or value >= (1 << 63):
                    continue
                seen.add(value)
                semantic = next((label for start, end, label in semantic_spans
                                 if start == match.start() and end == match.end()), None)
                db.execute("INSERT INTO source_number(value,path,line,context,semantic) VALUES(?,?,?,?,?)",
                           (value, relative, line_number, line.strip()[:1000], semantic))
                numbers += 1
        if files % 500 == 0:
            db.commit()
    return files, numbers


def stream_levels(db: sqlite3.Connection, inspector: Path, sqpack: Path, language: int) -> tuple[int, int, int, int, int, int]:
    process = subprocess.Popen([str(inspector), "level-stream", str(sqpack), str(language)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               encoding="utf-8", errors="replace", bufsize=1024 * 1024)
    assert process.stdout is not None
    levels = links = placements = sgb_links = 0
    for line in process.stdout:
        record = json.loads(line)
        if record.get("error"):
            process.kill()
            raise RuntimeError(f"{record['lvb_path']}: {record['message']}")
        lvb_path = record["lvb_path"]
        db.execute("INSERT OR IGNORE INTO asset(path,kind) VALUES(?,'lvb')", (lvb_path,))
        lvb_id = db.execute("SELECT asset_id FROM asset WHERE path=?", (lvb_path,)).fetchone()[0]
        for lgb_path in record["lgb_paths"]:
            db.execute("INSERT OR IGNORE INTO asset(path,kind) VALUES(?,'lgb')", (lgb_path,))
            lgb_id = db.execute("SELECT asset_id FROM asset WHERE path=?", (lgb_path,)).fetchone()[0]
            db.execute("INSERT OR IGNORE INTO asset_edge VALUES(?,?,?,?,?)",
                       (lvb_id, lgb_id, "contains", "physical_only", "LGB path serialized in LVB"))
            links += 1
        for layer in record["layer_sets"]:
            db.execute("INSERT OR REPLACE INTO layer_set VALUES(?,?,?,?,?,?)",
                       (lvb_id, layer["layer_set_id"], layer["territory_type_id"], layer["name"],
                        layer.get("navmesh_path"), json.dumps(layer["references"], separators=(",", ":"))))
        for lgb in record.get("lgb_files", []):
            lgb_path = lgb["path"]
            lgb_id = db.execute("SELECT asset_id FROM asset WHERE path=?", (lgb_path,)).fetchone()[0]
            for group in lgb["groups"]:
                for entry_index, entry in enumerate(group["entries"]):
                    sgb_path = entry.get("sgb_path")
                    if sgb_path:
                        db.execute("INSERT OR IGNORE INTO asset(path,kind) VALUES(?,'sgb')", (sgb_path,))
                        sgb_id = db.execute("SELECT asset_id FROM asset WHERE path=?", (sgb_path,)).fetchone()[0]
                        db.execute("INSERT OR IGNORE INTO asset_edge VALUES(?,?,?,?,?)",
                                   (lgb_id, sgb_id, "placement_reference", "physical_only", "SharedGroup asset path serialized in LGB"))
                        sgb_links += 1
                    db.execute("INSERT OR REPLACE INTO placement(lgb_asset,group_id,group_name,entry_index,type,type_name,instance_id,name,base_id,sgb_path) "
                               "VALUES(?,?,?,?,?,?,?,?,?,?)",
                               (lgb_id, group["id"], group["name"], entry_index, entry["type"], entry["type_name"],
                                entry["instance_id"], entry["name"], entry.get("base_id"), sgb_path))
                    placements += 1
        for sgb in record.get("sgb_files", []):
            sgb_id = db.execute("SELECT asset_id FROM asset WHERE path=?", (sgb["path"],)).fetchone()[0]
            for timeline in sgb["timelines"]:
                db.execute("INSERT OR REPLACE INTO sgb_timeline VALUES(?,?,?,?,?,?,?)",
                           (sgb_id, timeline["member_id"], timeline["name"], timeline["timeline_id"],
                            int(timeline["auto_play"]), int(timeline["loop_playback"]), timeline["collision_state"]))
            for slot in sgb["general_purpose_slots"]:
                db.execute("INSERT OR REPLACE INTO sgb_slot VALUES(?,?,?,?,?)",
                           (sgb_id, slot["index"], slot["mask"], slot["member_id"], slot.get("name")))
        levels += 1
    stderr = process.stderr.read() if process.stderr else ""
    code = process.wait()
    if code:
        raise RuntimeError(f"Level streamer failed ({code}): {stderr.strip()}")
    print(stderr.strip(), file=sys.stderr)
    placements = db.execute("SELECT COUNT(*) FROM placement").fetchone()[0]
    sgb_links = db.execute("SELECT COUNT(*) FROM asset_edge WHERE relation='placement_reference'").fetchone()[0]
    timelines = db.execute("SELECT COUNT(*) FROM sgb_timeline").fetchone()[0]
    timeline_assets = db.execute("SELECT COUNT(DISTINCT sgb_asset) FROM sgb_slot").fetchone()[0]
    return levels, links, placements, sgb_links, timeline_assets, timelines


def build_edges(db: sqlite3.Connection) -> tuple[int, int]:
    relational = 0
    fields = db.execute("SELECT field_id,sheet_id,name,references_json FROM field WHERE references_json != '[]'").fetchall()
    for field in fields:
        references = json.loads(field["references_json"])
        for reference in references:
            lookup = reference.get("lookup")
            if lookup == "main_key":
                key_delta = 0
            elif isinstance(lookup, str) and lookup.startswith("main_key_plus_"):
                try:
                    key_delta = int(lookup.removeprefix("main_key_plus_"))
                except ValueError:
                    continue
            else:
                continue
            sentinels = set(reference.get("sentinels", [0]))
            source_rows = {int(value) for value in reference.get("source_rows", [])}
            condition_field_id = None
            condition_values: set[int] = set()
            if "when" in reference:
                condition = reference["when"]
                condition_field = db.execute(
                    "SELECT field_id FROM field WHERE sheet_id=? AND name=?",
                    (field["sheet_id"], condition["field"])).fetchone()
                if not condition_field:
                    raise RuntimeError(f"Conditional reference field not found: {condition['field']}")
                condition_field_id = condition_field["field_id"]
                condition_values = {int(value) for value in condition["values"]}
            for target in reference.get("targets", []):
                target_sheet = db.execute("SELECT sheet_id FROM sheet WHERE name=?", (target,)).fetchone()
                if not target_sheet:
                    continue
                query = """
                  SELECT n.row_pk AS source_row, n.value, source.main_id AS source_main_id,
                         target.main_id AS target_main_id,target.row_pk AS target_row,target.ordinal
                  FROM number_cell n JOIN row_data source ON source.row_pk=n.row_pk
                  JOIN row_data target ON target.sheet_id=? AND target.main_id=n.value+?
                  WHERE n.field_id=? ORDER BY n.row_pk,target.ordinal
                """
                for match in db.execute(query, (target_sheet["sheet_id"], key_delta, field["field_id"])):
                    if match["value"] in sentinels or source_rows and match["source_main_id"] not in source_rows:
                        continue
                    if condition_field_id is not None:
                        condition_cell = db.execute(
                            "SELECT value FROM number_cell WHERE row_pk=? AND field_id=?",
                            (match["source_row"], condition_field_id)).fetchone()
                        if not condition_cell or condition_cell["value"] not in condition_values:
                            continue
                    target_name = f"{target}:{match['target_main_id']}:{match['ordinal']}"
                    db.execute("INSERT OR IGNORE INTO edge(source_row,source_field,target_row,target_kind,target_name,confidence,evidence) "
                               "VALUES(?,?,?,?,?,?,?)",
                               (match["source_row"], field["field_id"], match["target_row"], "row", target_name,
                                reference.get("confidence", "candidate"), reference.get("evidence", "")))
                    relational += 1
    assets = 0
    query = """
      SELECT t.row_pk,t.field_id,t.value,f.name AS field_name,s.name AS sheet_name
      FROM text_cell t JOIN field f ON f.field_id=t.field_id JOIN sheet s ON s.sheet_id=f.sheet_id
    """
    for cell in db.execute(query):
        paths: list[str] = []
        value = cell["value"].replace("\\", "/")
        if ASSET_RE.search(value):
            paths.append(value)
        if cell["sheet_name"] == "TerritoryType" and cell["field_name"] == "LVB" and value:
            paths.append(f"bg/{value}.lvb")
        for path in paths:
            kind = Path(path).suffix.lower().lstrip(".") or "asset"
            db.execute("INSERT OR IGNORE INTO asset(path,kind) VALUES(?,?)", (path, kind))
            db.execute("INSERT OR IGNORE INTO edge(source_row,source_field,target_row,target_kind,target_name,confidence,evidence) "
                       "VALUES(?,?,NULL,'asset',?,?,?)",
                       (cell["row_pk"], cell["field_id"], path, "source_code_confirmed" if kind == "lvb" else "metadata_candidate",
                        "Path-valued field or territory LVB path recipe"))
            assets += 1
    return relational, assets


def build(args: argparse.Namespace) -> None:
    if args.database.exists():
        args.database.unlink()
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    db = connect(args.database)
    try:
        schema_sql(db)
        sheet_ids, field_ids, display_columns = insert_schema(db, schema)
        db.execute("INSERT INTO metadata VALUES('schema_version','5')")
        db.execute("INSERT INTO metadata VALUES('semantic_schema',?)", (str(args.schema),))
        db.execute("INSERT INTO metadata VALUES('sqpack',?)", (str(args.sqpack),))
        db.execute("INSERT INTO metadata VALUES('language',?)", (str(args.language),))
        db.execute("INSERT INTO metadata VALUES('source_root',?)",
                   (str(args.source_root.resolve()) if args.source_root else "",))
        db.execute("INSERT INTO metadata VALUES('lua_source_root',?)",
                   (str(args.lua_source_root.resolve()) if args.lua_source_root else "",))
        db.commit()
        rows, vocabulary = stream_rows(db, args.inspector, args.sqpack, args.language,
                                       sheet_ids, field_ids, display_columns)
        for sheet in schema["sheets"]:
            vocabulary.update(words(sheet["name"]))
            vocabulary.update(words(" ".join(field["name"] for field in sheet["fields"])))
        db.executemany("INSERT INTO word(word,uses) VALUES(?,?)", vocabulary.items())
        source_files = source_numbers = 0
        if args.source_root:
            source_files, source_numbers = index_source(db, args.source_root)
        lua_scripts, lua_symbols, lua_links = index_lua(db, args.sqpack)
        lua_source_files, lua_source_mapped, lua_source_references = index_lua_sources(db, args.lua_source_root)
        relational, assets = build_edges(db)
        levels, level_links, placements, sgb_links, timeline_assets, timelines = stream_levels(db, args.inspector, args.sqpack, args.language)
        db.execute("INSERT INTO metadata VALUES('statistics',?)", (json.dumps({
            "rows": rows, "words": len(vocabulary), "source_files": source_files,
            "source_numbers": source_numbers, "lua_scripts": lua_scripts,
            "lua_symbols": lua_symbols, "lua_exd_links": lua_links,
            "lua_source_files": lua_source_files, "lua_source_mapped": lua_source_mapped,
            "lua_source_references": lua_source_references,
            "relational_edges": relational, "asset_edges": assets,
            "lvb_files": levels, "lvb_to_lgb_edges": level_links,
            "lgb_placements": placements, "lgb_to_sgb_edges": sgb_links,
            "timeline_sgb_files": timeline_assets, "sgb_timelines": timelines,
        }, separators=(",", ":")),))
        db.commit()
        db.execute("PRAGMA optimize")
        print(json.dumps(json.loads(db.execute("SELECT value FROM metadata WHERE key='statistics'").fetchone()[0]), indent=2))
    finally:
        db.close()


def corrected_terms(db: sqlite3.Connection, query: str) -> tuple[list[str], dict[str, str]]:
    terms = [word for word in words(query) if word not in STOP_WORDS]
    vocabulary = None
    corrections: dict[str, str] = {}
    for index, term in enumerate(terms):
        exists = db.execute("SELECT 1 FROM word WHERE word=?", (term,)).fetchone()
        if exists:
            continue
        if vocabulary is None:
            vocabulary = [row[0] for row in db.execute("SELECT word FROM word")]
        match = difflib.get_close_matches(term, vocabulary, n=1, cutoff=0.78)
        if match:
            corrections[term] = match[0]
            terms[index] = match[0]
    return list(dict.fromkeys(terms)), corrections


def row_identity(db: sqlite3.Connection, row_pk: int) -> dict[str, Any]:
    row = db.execute("SELECT r.*,s.name AS sheet FROM row_data r JOIN sheet s USING(sheet_id) WHERE row_pk=?", (row_pk,)).fetchone()
    return {"row_pk": row_pk, "sheet": row["sheet"], "id": row["main_id"], "ordinal": row["ordinal"],
            "subkeys": json.loads(row["subkeys_json"]), "display": row["display"]}


def search_data(db: sqlite3.Connection, query: str, limit: int) -> dict[str, Any]:
    numeric_text = query[3:] if query.lower().startswith("id:") else query
    numeric = None
    try:
        numeric = int(numeric_text, 0) if re.fullmatch(r"(?:0[xX][0-9A-Fa-f]+|[0-9]+)", numeric_text) else None
    except ValueError:
        numeric = None
    result: dict[str, Any] = {"query": query, "rows": [], "cells": [], "lua": [], "source": []}
    if numeric is not None:
        for row in db.execute("SELECT r.row_pk FROM row_data r WHERE main_id=? LIMIT ?", (numeric, limit)):
            result["rows"].append({**row_identity(db, row["row_pk"]), "match": "main_key"})
        cell_query = """
          SELECT n.row_pk,f.name AS field,s.name AS sheet,n.value
          FROM number_cell n JOIN field f USING(field_id) JOIN sheet s USING(sheet_id)
          WHERE n.value=? LIMIT ?
        """
        for row in db.execute(cell_query, (numeric, limit)):
            result["cells"].append({**row_identity(db, row["row_pk"]), "field": row["field"], "value": row["value"]})
        for row in db.execute("SELECT path,line,context,semantic FROM source_number WHERE value=? ORDER BY semantic IS NULL,path,line LIMIT ?", (numeric, limit)):
            result["source"].append(dict(row))
        return result

    for row in db.execute("""
      SELECT DISTINCT t.row_pk FROM text_cell t WHERE t.value=? LIMIT ?
    """, (query, limit)):
        result["rows"].append({**row_identity(db, row["row_pk"]), "match": "exact_text"})
    for row in db.execute("""
      SELECT source.path AS display_path,script.display_path AS bytecode_path,reference.line,
             reference.context,source.provenance,reference.symbol,
             coalesce(symbol.kind,'source_reference') AS kind,coalesce(symbol.uses,1) AS uses,
             link.row_pk,link.confidence
      FROM lua_source_reference reference JOIN lua_source_file source USING(file_id)
      LEFT JOIN lua_script script USING(script_id)
      LEFT JOIN lua_symbol symbol ON symbol.script_id=source.script_id AND symbol.symbol=reference.symbol
      LEFT JOIN lua_row_link link ON link.script_id=source.script_id AND link.symbol=reference.symbol
      WHERE reference.symbol=? ORDER BY source.path,reference.line LIMIT ?
    """, (query, limit)):
        result["lua"].append(dict(row))
    for row in db.execute("""
      SELECT script.display_path,NULL AS bytecode_path,NULL AS line,NULL AS context,
             'bytecode_only' AS provenance,symbol.symbol,symbol.kind,symbol.uses,link.row_pk,link.confidence
      FROM lua_symbol symbol JOIN lua_script script USING(script_id)
      LEFT JOIN lua_row_link link USING(script_id,symbol)
      WHERE symbol.symbol=? AND NOT EXISTS(
        SELECT 1 FROM lua_source_file source JOIN lua_source_reference reference USING(file_id)
        WHERE source.script_id=symbol.script_id AND reference.symbol=symbol.symbol)
      LIMIT ?
    """, (query, limit)):
        result["lua"].append(dict(row))
    terms, corrections = corrected_terms(db, query)
    result["terms"] = terms
    result["corrections"] = corrections
    if not terms:
        return result
    expression = " OR ".join(f'"{term.replace(chr(34), chr(34) * 2)}"' for term in terms)
    sql = """
      SELECT CAST(row_pk AS INTEGER) AS row_pk, bm25(row_fts) AS rank,
             snippet(row_fts,3,'[',']',' … ',24) AS snippet
      FROM row_fts WHERE row_fts MATCH ? ORDER BY rank LIMIT ?
    """
    for row in db.execute(sql, (expression, limit)):
        if any(existing["row_pk"] == row["row_pk"] for existing in result["rows"]):
            continue
        result["rows"].append({**row_identity(db, row["row_pk"]), "rank": row["rank"], "snippet": row["snippet"]})
    source_sql = """
      SELECT path,bm25(source_fts) AS rank,snippet(source_fts,1,'[',']',' … ',32) AS snippet
      FROM source_fts WHERE source_fts MATCH ? ORDER BY rank LIMIT ?
    """
    if not result["lua"]:
        for row in db.execute("""
          SELECT source.path AS display_path,script.display_path AS bytecode_path,NULL AS line,
                 snippet(lua_source_fts,2,'[',']',' … ',32) AS context,source.provenance,
                 NULL AS symbol,'decompiled_source' AS kind,0 AS uses,NULL AS row_pk,NULL AS confidence
          FROM lua_source_fts JOIN lua_source_file source
            ON source.file_id=CAST(lua_source_fts.file_id AS INTEGER)
          LEFT JOIN lua_script script USING(script_id)
          WHERE lua_source_fts MATCH ? ORDER BY bm25(lua_source_fts) LIMIT ?
        """, (expression, limit)):
            result["lua"].append(dict(row))
    if not result["lua"]:
        for row in db.execute("""
          SELECT script.display_path,NULL AS bytecode_path,NULL AS line,NULL AS context,
                 'bytecode_only' AS provenance,symbol.symbol,symbol.kind,symbol.uses,link.row_pk,link.confidence
          FROM lua_fts JOIN lua_script script ON script.script_id=CAST(lua_fts.script_id AS INTEGER)
          JOIN lua_symbol symbol ON symbol.script_id=script.script_id AND symbol.symbol=lua_fts.symbol
          LEFT JOIN lua_row_link link USING(script_id,symbol)
          WHERE lua_fts MATCH ? ORDER BY bm25(lua_fts) LIMIT ?
        """, (expression, limit)):
            result["lua"].append(dict(row))
    for row in db.execute(source_sql, (expression, limit)):
        result["source"].append(dict(row))
    return result


def row_detail(db: sqlite3.Connection, sheet: str, main_id: int, ordinal: int) -> dict[str, Any]:
    row = db.execute("SELECT r.* FROM row_data r JOIN sheet s USING(sheet_id) WHERE s.name=? AND main_id=? AND ordinal=?",
                     (sheet, main_id, ordinal)).fetchone()
    if not row:
        raise RuntimeError(f"Row not found: {sheet}:{main_id}:{ordinal}")
    values = json.loads(row["values_json"])
    fields = db.execute("SELECT * FROM field WHERE sheet_id=? ORDER BY column_index", (row["sheet_id"],)).fetchall()
    cells = [{"column": field["column_index"], "field": field["name"], "confidence": field["confidence"],
              "type": field["type_name"], "offset": field["fixed_offset"],
              "value": values[field["column_index"]]} for field in fields]
    outgoing = [dict(edge) for edge in db.execute(
        "SELECT e.confidence,e.target_kind,e.target_name,e.evidence,f.name AS field FROM edge e LEFT JOIN field f ON f.field_id=e.source_field WHERE source_row=?",
        (row["row_pk"],))]
    for edge in outgoing:
        if edge["target_kind"] != "asset":
            continue
        edge["children"] = [dict(child) for child in db.execute("""
          SELECT target.path,target.kind,link.relation,link.confidence,link.evidence
          FROM asset source JOIN asset_edge link ON link.source_asset=source.asset_id
          JOIN asset target ON target.asset_id=link.target_asset WHERE source.path=? ORDER BY target.path
        """, (edge["target_name"],))]
        edge["layer_sets"] = [dict(layer) for layer in db.execute("""
          SELECT layer_set_id,territory_type_id,name,navmesh_path,references_json
          FROM asset JOIN layer_set ON layer_set.lvb_asset=asset.asset_id WHERE asset.path=? ORDER BY layer_set_id
        """, (edge["target_name"],))]
    lua_references = [dict(reference) for reference in db.execute("""
      SELECT coalesce(source.path,script.display_path) AS display_path,
             script.display_path AS bytecode_path,reference.line,reference.context,source.provenance,
             symbol.symbol,symbol.kind,symbol.uses,link.confidence,link.evidence
      FROM lua_row_link link JOIN lua_script script USING(script_id)
      JOIN lua_symbol symbol USING(script_id,symbol)
      LEFT JOIN lua_source_file source USING(script_id)
      LEFT JOIN lua_source_reference reference
        ON reference.file_id=source.file_id AND reference.symbol=symbol.symbol
      WHERE link.row_pk=? ORDER BY symbol.symbol,source.path,reference.line,script.display_path
    """, (row["row_pk"],))]
    incoming = []
    for edge in db.execute("SELECT e.source_row,e.confidence,e.evidence,f.name AS field FROM edge e LEFT JOIN field f ON f.field_id=e.source_field WHERE target_row=? LIMIT 500",
                           (row["row_pk"],)):
        incoming.append({**row_identity(db, edge["source_row"]), "field": edge["field"],
                         "confidence": edge["confidence"], "evidence": edge["evidence"]})
    consumers = json.loads(db.execute("SELECT consumers_json FROM sheet WHERE sheet_id=?",
                                      (row["sheet_id"],)).fetchone()[0])
    exact_candidates = [{**row_identity(db, candidate["row_pk"]), "field": candidate["field"],
                         "stored_value": candidate["value"], "confidence": "exact_value_candidate",
                         "evidence": "Exact numeric coincidence only; no resolver to this target row is declared"}
                        for candidate in db.execute("""
      SELECT n.row_pk,f.name AS field,n.value FROM number_cell n JOIN field f USING(field_id)
      WHERE n.value=? AND n.row_pk<>? AND (f.references_json='[]' OR f.references_json LIKE ?)
        AND NOT EXISTS(
          SELECT 1 FROM edge e WHERE e.source_row=n.row_pk AND e.source_field=n.field_id AND e.target_row=?)
      ORDER BY n.row_pk LIMIT 250
    """, (main_id, row["row_pk"], f'%"{sheet}"%', row["row_pk"]))]
    encoded_candidates = [{**row_identity(db, candidate["row_pk"]), "field": candidate["field"],
                           "stored_value": candidate["value"], "transform": "stored_value & 0xffff",
                           "confidence": "encoded_value_candidate",
                           "evidence": "Low 16 bits equal the target key; target domain and encoding are unresolved"}
                          for candidate in db.execute("""
      SELECT n.row_pk,f.name AS field,n.value FROM number_cell n JOIN field f USING(field_id)
      WHERE (n.value & 65535)=? AND n.value<>?
        AND (f.references_json='[]' OR f.references_json LIKE ?) ORDER BY n.row_pk LIMIT 250
    """, (main_id, main_id, f'%"{sheet}"%'))]
    offset_candidates = []
    for candidate in db.execute("""
      SELECT n.row_pk,r.sheet_id,r.main_id AS source_main_id,f.name AS field,n.value,
             f.references_json,r.values_json
      FROM number_cell n JOIN row_data r USING(row_pk) JOIN field f USING(field_id)
      WHERE n.value BETWEEN ? AND ? AND n.value<>? AND f.references_json<>'[]'
        AND NOT EXISTS(
          SELECT 1 FROM edge e WHERE e.source_row=n.row_pk AND e.source_field=n.field_id AND e.target_row=?)
      ORDER BY abs(n.value-?),n.row_pk LIMIT 500
    """, (main_id - 16, main_id + 16, main_id, row["row_pk"], main_id)):
        values = json.loads(candidate["values_json"])
        for relation in json.loads(candidate["references_json"]):
            if sheet not in relation.get("targets", []):
                continue
            source_rows = relation.get("source_rows", [])
            if source_rows and candidate["source_main_id"] not in source_rows:
                continue
            condition = relation.get("when")
            if condition:
                condition_field = db.execute(
                    "SELECT column_index FROM field WHERE sheet_id=? AND name=?",
                    (candidate["sheet_id"], condition["field"])).fetchone()
                if not condition_field or values[condition_field["column_index"]] not in condition["values"]:
                    continue
            delta = main_id - candidate["value"]
            offset_candidates.append({
                **row_identity(db, candidate["row_pk"]), "field": candidate["field"],
                "stored_value": candidate["value"], "transform": f"stored_value{delta:+d}",
                "confidence": "offset_hypothesis",
                "evidence": "Declared target domain and nearby key only; this offset is not established. " +
                            relation.get("evidence", ""),
            })
    return {**row_identity(db, row["row_pk"]), "cells": cells, "outgoing": outgoing,
            "incoming": incoming, "lua_references": lua_references, "consumers": consumers,
            "exact_numeric_candidates": exact_candidates, "encoded_numeric_candidates": encoded_candidates,
            "offset_candidates": offset_candidates}


def asset_detail(db: sqlite3.Connection, path: str, limit: int = 1000) -> dict[str, Any]:
    asset = db.execute("SELECT * FROM asset WHERE path=?", (path,)).fetchone()
    if not asset:
        raise RuntimeError(f"Asset not found: {path}")
    children = [dict(row) for row in db.execute("""
      SELECT target.path,target.kind,link.relation,link.confidence,link.evidence
      FROM asset_edge link JOIN asset target ON target.asset_id=link.target_asset
      WHERE link.source_asset=? ORDER BY target.path LIMIT ?
    """, (asset["asset_id"], limit))]
    placements = [dict(row) for row in db.execute("""
      SELECT group_id,group_name,entry_index,type,type_name,instance_id,name,base_id,sgb_path
      FROM placement WHERE lgb_asset=? ORDER BY group_id,entry_index LIMIT ?
    """, (asset["asset_id"], limit))]
    layers = [dict(row) for row in db.execute("""
      SELECT layer_set_id,territory_type_id,name,navmesh_path,references_json
      FROM layer_set WHERE lvb_asset=? ORDER BY layer_set_id
    """, (asset["asset_id"],))]
    timelines = [dict(row) for row in db.execute("""
      SELECT member_id,name,timeline_id,auto_play,loop_playback,collision_state
      FROM sgb_timeline WHERE sgb_asset=? ORDER BY member_id
    """, (asset["asset_id"],))]
    slots = [dict(row) for row in db.execute("""
      SELECT slot_index,mask,member_id,name FROM sgb_slot WHERE sgb_asset=? ORDER BY slot_index
    """, (asset["asset_id"],))]
    return {"path": asset["path"], "kind": asset["kind"], "children": children,
            "layer_sets": layers, "placements": placements, "timelines": timelines, "slots": slots}


def explain(db: sqlite3.Connection, query: str, limit: int, depth: int) -> dict[str, Any]:
    found = search_data(db, query, limit)
    seeds = [row["row_pk"] for row in found["rows"][: min(20, limit)]]
    queue = deque((row_pk, 0) for row_pk in seeds)
    visited = set(seeds)
    graph_edges = []
    while queue and len(visited) < 500:
        current, level = queue.popleft()
        if level >= depth:
            continue
        sql = """
          SELECT source_row,target_row,target_kind,target_name,confidence,evidence
          FROM edge WHERE source_row=? OR target_row=? LIMIT 250
        """
        for edge in db.execute(sql, (current, current)):
            record = dict(edge)
            graph_edges.append(record)
            other = edge["target_row"] if edge["source_row"] == current else edge["source_row"]
            if other is not None and other not in visited:
                visited.add(other)
                queue.append((other, level + 1))
    asset_paths = sorted({edge["target_name"] for edge in graph_edges if edge["target_kind"] == "asset"})
    assets = []
    for path in asset_paths:
        asset = db.execute("SELECT asset_id,path,kind FROM asset WHERE path=?", (path,)).fetchone()
        if not asset:
            continue
        children = [dict(row) for row in db.execute("""
          SELECT target.path,target.kind,link.relation,link.confidence,link.evidence
          FROM asset_edge link JOIN asset target ON target.asset_id=link.target_asset
          WHERE link.source_asset=? ORDER BY target.path
        """, (asset["asset_id"],))]
        assets.append({"path": asset["path"], "kind": asset["kind"], "children": children})
    return {"search": found, "graph": {"nodes": [row_identity(db, row_pk) for row_pk in sorted(visited)],
                                        "edges": graph_edges, "assets": assets, "depth": depth}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build_parser = sub.add_parser("build", help="decode the corpus and create the SQLite graph")
    build_parser.add_argument("database", type=Path)
    build_parser.add_argument("--sqpack", type=Path, required=True)
    build_parser.add_argument("--schema", type=Path, default=Path("build/ps3-exd-semantic-schema.json"))
    build_parser.add_argument("--inspector", type=Path, default=Path("bin/tools/ps3_data_inspector.exe"))
    build_parser.add_argument("--source-root", type=Path, default=Path("src"))
    build_parser.add_argument("--lua-source-root", type=Path,
                              default=Path(__file__).resolve().parent / "game_script")
    build_parser.add_argument("--language", type=int, default=2)
    search_parser = sub.add_parser("search", help="search text, IDs, values, and source references")
    search_parser.add_argument("database", type=Path)
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=int, default=50)
    row_parser = sub.add_parser("row", help="show one semantic row and its graph edges")
    row_parser.add_argument("database", type=Path)
    row_parser.add_argument("sheet")
    row_parser.add_argument("id", type=int)
    row_parser.add_argument("--ordinal", type=int, default=0)
    asset_parser = sub.add_parser("asset", help="show LVB/LGB/SGB hierarchy and placements")
    asset_parser.add_argument("database", type=Path)
    asset_parser.add_argument("path")
    asset_parser.add_argument("--limit", type=int, default=1000)
    explain_parser = sub.add_parser("explain", help="search and traverse nearby evidence-qualified edges")
    explain_parser.add_argument("database", type=Path)
    explain_parser.add_argument("query")
    explain_parser.add_argument("--limit", type=int, default=50)
    explain_parser.add_argument("--depth", type=int, default=2)
    args = parser.parse_args()

    if args.command == "build":
        build(args)
        return
    db = connect(args.database, readonly=True)
    try:
        if args.command == "search":
            output = search_data(db, args.query, args.limit)
        elif args.command == "row":
            output = row_detail(db, args.sheet, args.id, args.ordinal)
        elif args.command == "asset":
            output = asset_detail(db, args.path, args.limit)
        else:
            output = explain(db, args.query, args.limit, args.depth)
        print(json.dumps(output, indent=2, ensure_ascii=False))
    finally:
        db.close()


if __name__ == "__main__":
    main()

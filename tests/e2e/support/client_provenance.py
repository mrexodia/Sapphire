"""Strict read-only binding of a graphical result to its prepared source manifest.

This identifies committed coordinator bytes. It is not a signature, native-binary
source attestation, or evidence that any client/gameplay operation ran.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath

from .client_smoke import CLIENT_SHA256
from .development import DevelopmentError

SOURCE_SCOPE = "committed-coordinator-source-not-native-build-attestation"
BINDING_SCOPE = "exact-prepared-source-manifest-bytes-and-revision-not-native-build-attestation"


def _hex(value, length):
    return (isinstance(value, str) and len(value) == length
            and all(char in "0123456789abcdef" for char in value))


def _read(path, label):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DevelopmentError(f"cannot read prepared {label}") from error
    if not isinstance(value, dict):
        raise DevelopmentError(f"prepared {label} is not an object")
    return value


def _sha256(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError as error:
        raise DevelopmentError("cannot hash prepared source manifest") from error


def _safe_hash_map(value, label):
    if not isinstance(value, dict) or not value:
        raise DevelopmentError(f"prepared {label} hash map is empty or malformed")
    for relative, digest in value.items():
        pure = PurePosixPath(relative) if isinstance(relative, str) else None
        if (pure is None or pure.is_absolute() or not pure.parts
                or pure.as_posix() != relative
                or any(part in {"", ".", ".."} for part in pure.parts)
                or "\\" in relative or not _hex(digest, 64)):
            raise DevelopmentError(f"prepared {label} hash entry is unsafe or malformed")
    return value


def require_prepared_source(prepared, expected_revision, report_manifest_sha256=None):
    """Bind source.json bytes/revision through inputs.json and optionally result.json."""
    prepared = Path(prepared).resolve()
    inputs_path, source_path = prepared / "inputs.json", prepared / "input/source.json"
    inputs, source = _read(inputs_path, "input manifest"), _read(source_path, "source manifest")
    if (set(inputs) != {"version", "status", "client_sha256", "config_sha256",
                        "source_revision", "source_manifest_sha256",
                        "working_tree_changes_included", "inputs"}
            or type(inputs.get("version")) is not int or inputs["version"] != 1
            or inputs.get("status") != "prepared_not_executed"
            or inputs.get("client_sha256") != CLIENT_SHA256
            or not _hex(inputs.get("config_sha256"), 64)
            or inputs.get("working_tree_changes_included") is not False):
        raise DevelopmentError("prepared graphical input manifest is malformed")
    input_hashes = _safe_hash_map(inputs.get("inputs"), "input")
    source_hash = _sha256(source_path)
    if (input_hashes.get("source.json") != source_hash
            or inputs.get("source_manifest_sha256") != source_hash
            or (report_manifest_sha256 is not None
                and report_manifest_sha256 != source_hash)):
        raise DevelopmentError("prepared source-manifest hash binding differs")
    if (set(source) != {"version", "scope", "revision", "dirty", "sha256",
                        "gitlinks", "submodule_fetch_performed", "remote_configured"}
            or type(source.get("version")) is not int or source["version"] != 1
            or source.get("scope") != SOURCE_SCOPE
            or source.get("dirty") is not False
            or source.get("submodule_fetch_performed") is not False
            or source.get("remote_configured") is not False
            or not _hex(source.get("revision"), 40)
            or source.get("revision") != inputs.get("source_revision")
            or source.get("revision") != expected_revision):
        raise DevelopmentError("prepared source-manifest revision or boundary is invalid")
    files = _safe_hash_map(source.get("sha256"), "source")
    links = source.get("gitlinks")
    if not isinstance(links, list):
        raise DevelopmentError("prepared source gitlink list is malformed")
    paths = set(files)
    for row in links:
        if (not isinstance(row, dict) or set(row) != {"path", "revision", "materialized"}
                or row.get("materialized") is not False or not _hex(row.get("revision"), 40)):
            raise DevelopmentError("prepared source gitlink is malformed")
        relative = row.get("path")
        pure = PurePosixPath(relative) if isinstance(relative, str) else None
        if (pure is None or pure.is_absolute() or not pure.parts or "\\" in relative
                or pure.as_posix() != relative
                or any(part in {"", ".", ".."} for part in pure.parts)
                or relative in paths):
            raise DevelopmentError("prepared source gitlink path is unsafe or duplicate")
        paths.add(relative)
    return {"verified": True, "scope": BINDING_SCOPE,
            "revision": source["revision"], "source_manifest_sha256": source_hash,
            "tracked_source_files": len(files), "unmaterialized_gitlinks": len(links)}


def require_prepared_inputs(prepared, expected_revision, report_manifest_sha256=None):
    """Rehash every exact staged input; external readonly mappings remain out of scope."""
    prepared = Path(prepared).resolve()
    source = require_prepared_source(
        prepared, expected_revision, report_manifest_sha256)
    inputs_manifest = _read(prepared / "inputs.json", "input manifest")
    expected = inputs_manifest["inputs"]  # Already shape/path/digest validated above.
    input_root = prepared / "input"
    actual = {}
    try:
        entries = list(input_root.rglob("*"))
    except OSError as error:
        raise DevelopmentError("cannot enumerate prepared graphical inputs") from error
    for path in entries:
        if path.is_symlink():
            raise DevelopmentError("prepared graphical input contains a symbolic link")
        if path.is_dir():
            continue
        if not path.is_file():
            raise DevelopmentError("prepared graphical input is not a regular file")
        relative = path.relative_to(input_root).as_posix()
        try:
            actual[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as error:
            raise DevelopmentError("cannot hash prepared graphical input") from error
    if actual != expected:
        raise DevelopmentError("prepared graphical input files differ from inputs.json")
    return {"verified": True,
            "scope": "all-exact-staged-graphical-input-files-match-preparation-manifest",
            "file_count": len(actual), "source": source,
            "note": "External readonly mappings and native-build provenance are out of scope."}

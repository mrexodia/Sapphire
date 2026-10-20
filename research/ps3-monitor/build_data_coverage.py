"""Summarize local inspector output and independently cross-check raw PS3 indices.

python research/ps3-monitor/build_data_coverage.py --game E:/FFXIV-Monitor-PS3/game
Large per-file inventories and metadata stay in build/, not in source control.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path, required=True)
    parser.add_argument("--build", type=Path, default=Path("build"))
    parser.add_argument("--output", type=Path, default=Path("research/ps3-monitor/data_coverage.json"))
    args = parser.parse_args()
    scan = json.loads((args.build / "ps3-exd-scan.json").read_text())
    inventory = json.loads((args.build / "ps3-inventory.json").read_text())
    metadata = json.loads((args.build / "ps3-monitor-metadata.json").read_text())
    archives = []
    for archive in inventory["archives"]:
        if "error" in archive:
            raise RuntimeError(archive["error"])
        path = args.game / "sqpack" / archive["path"]
        raw = path.read_bytes()
        if raw[:8] != b"SqPack\0\0" or raw[8] != 1:
            raise ValueError(f"Not a PS3 SqPack index: {path}")
        start, size = struct.unpack_from(">II", raw, 0x408)
        expected = {(e["directory_hash"], e["filename_hash"]): e["offset"] for e in archive["entries"]}
        if size % 16 or start + size > len(raw) or size // 16 != len(expected):
            raise ValueError(f"Index record count mismatch: {path}")
        for p in range(start, start + size, 16):
            directory, filename, offset, padding = struct.unpack_from(">IIII", raw, p)
            if expected[(directory, filename)] != offset * 128:
                raise ValueError(f"Index offset mismatch: {path} at {p:#x}")
        high = sum(e["offset"] > 0xFFFFFFFF for e in archive["entries"])
        archives.append({"index": archive["path"], "sha256": sha256(path),
                         "entries": len(archive["entries"]), "offsets_above_4gib": high,
                         "data_files": archive["data_files"], "raw_index_crosscheck": "passed"})
    counts = Counter(c["type_name"] for s in scan["sheets"] for c in s.get("schema", {}).get("columns", []))
    subrows = [s["name"] for s in scan["sheets"] if s.get("schema", {}).get("key_count", 0) > 1]
    output = {"schema_version": 1, "source_elf_sha256": sha256(args.game / "ffxivgame.ppu.elf"),
              "exd": {"root_listed_sheets": len(scan["sheets"]), "validated_pages": scan["validated_pages"],
                      "decoded_rows_including_languages_and_subrows": scan["decoded_rows"],
                      "errors": scan["error_count"], "column_types": dict(sorted(counts.items())),
                      "subrow_sheets": subrows},
              "sqpack": {"index_count": len(archives), "entry_count": inventory["entry_count"],
                         "errors": inventory["error_count"], "archives": archives},
              "idb_metadata": {"types": len(metadata["types"]), "symbols": len(metadata["symbols"]),
                               "candidate_paths": len(metadata["candidate_paths"])},
              "limits": ["Only EXH v3 is decoded; all root-listed sheets in this corpus use v3.",
                         "TYPE_F16 is retained as raw bits; TYPE_BIN and other unsupported types fail explicitly.",
                         "C++ backend lacks SDAT framing support; both local containers were later verified as debug/plain by inspect_monitor_scripts.py. General integrity/decryption is unsupported.",
                         "Archive inventory is not proof of complete model/texture/audio/etc. format decoding.",
                         "Imported IDB types are PS3 ABI metadata, not verified Windows or file layouts."]}
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output["exd"], indent=2))


if __name__ == "__main__":
    main()

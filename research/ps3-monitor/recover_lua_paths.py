"""Recover monitor script archive filenames from a candidate path dictionary.

Matches BOTH PS3 index CRCs after case folding; never guesses from Lua globals.
Copies already-extracted, SHA-256-verified payloads under dictionary filenames.
No Lua execution/decompilation. Unmatched and ambiguous records stay unnamed.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import zlib


HERE = Path(__file__).resolve().parent
EXTENSIONS = {'lua51_bytecode': '.luac', 'source_text_candidate': '.lua', 'placeholder': '.txt'}


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as source:
        for data in iter(lambda: source.read(1024 * 1024), b''):
            value.update(data)
    return value.hexdigest()


def path_hashes(path):
    directory, filename = path.lower().rsplit('/', 1)
    return (zlib.crc32(directory.encode('ascii')) ^ 0xFFFFFFFF,
            zlib.crc32(filename.encode('ascii')) ^ 0xFFFFFFFF)


def candidate(text):
    path = text.strip().replace(chr(92), '/')
    if not path.lower().startswith('game_script/'):
        return None
    if not re.fullmatch(r'[A-Za-z0-9_./-]+', path):
        return None
    if any(part in ('', '.', '..') for part in path.split('/')):
        return None
    return path


def index_entries(path):
    raw = path.read_bytes()
    if len(raw) < 0x410 or raw[:8] != b'SqPack\0\0' or raw[8] != 1:
        raise ValueError('Expected PS3 SqPack index')
    start, size = struct.unpack_from('>II', raw, 0x408)
    if size % 16 or start + size > len(raw):
        raise ValueError('Invalid PS3 index table')
    entries = {}
    for p in range(start, start + size, 16):
        directory, filename, offset, _ = struct.unpack_from('>IIII', raw, p)
        key = (directory, filename)
        if key in entries:
            raise ValueError('Duplicate index hash pair')
        entries[key] = offset * 128
    return entries


def match_dictionary(path, entries):
    matches = {}
    counts = Counter()
    with path.open(encoding='utf-8-sig') as source:
        for number, line in enumerate(source, 1):
            counts['dictionary_lines'] += 1
            value = candidate(line)
            if value is None:
                continue
            counts['script_candidate_lines'] += 1
            key = path_hashes(value)
            if key not in entries:
                continue
            counts['matching_candidate_lines'] += 1
            paths = matches.setdefault(key, {})
            # Case aliases are not distinct names in SqPack's folded namespace.
            item = paths.setdefault(value.lower(), {'path': value, 'normalized_path': value.lower(), 'lines': []})
            item['lines'].append(number)
    return matches, dict(counts)


def copy_verified(source, target, expected):
    if digest(source) != expected:
        raise ValueError(f'Extracted payload hash mismatch: {source}')
    if target.exists():
        if digest(target) != expected:
            raise ValueError(f'Refusing to overwrite a differing output: {target}')
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    if digest(target) != expected:
        raise ValueError(f'Copied payload hash mismatch: {target}')


def recover(path_list, index, runtime, extracted, output):
    entries = index_entries(index)
    ledger = json.loads(runtime.read_text(encoding='utf-8'))
    scripts = {(int(s['directory_hash'], 16), int(s['filename_hash'], 16)): s for s in ledger['scripts']}
    if len(scripts) != len(ledger['scripts']) or scripts.keys() != entries.keys():
        raise ValueError('Runtime ledger does not cover exactly this index')
    for key, script in scripts.items():
        if script['logical_offset'] != entries[key]:
            raise ValueError('Runtime ledger/index logical offset mismatch')
    matches, dictionary_counts = match_dictionary(path_list, entries)
    records = []
    counts = Counter()
    named_kinds = Counter()
    debug_sources = set()
    for key, script in scripts.items():
        paths = list(matches.get(key, {}).values())
        record = {name: script[name] for name in ['directory_hash', 'filename_hash', 'logical_offset', 'size', 'sha256', 'kind']}
        record['dictionary_candidates'] = paths
        record['debug_source_names'] = script.get('source_names', [])
        debug_sources.update(s for s in record['debug_source_names'] if s != '=(luac)')
        if not paths:
            record['status'] = 'unmatched'
        elif len(paths) > 1:
            record['status'] = 'ambiguous_hash_pair'
        else:
            record['status'] = 'unique_dictionary_hash_pair_match'
            record['recovered_path'] = paths[0]['path']
            if script['kind'] == 'lua51_bytecode':
                basename = Path(record['recovered_path']).name.lower().removesuffix('.luab')
                stems = [s.rsplit('/', 1)[-1].lower().removesuffix('.cli.lua').removesuffix('.cmn.lua')
                         for s in record['debug_source_names'] if s != '=(luac)']
                record['debug_source_basename_agreement'] = bool(stems) and all(s == basename for s in stems)
            source = extracted / (script['directory_hash'] + '_' + script['filename_hash'] + EXTENSIONS[script['kind']])
            target = output / paths[0]['path']
            copy_verified(source, target, script['sha256'])
            named_kinds[script['kind']] += 1
        counts[record['status']] += 1
        records.append(record)
    summary = {
        'schema_version': 1,
        'method': 'case-folded CRC32(directory) and CRC32(filename), each XOR 0xFFFFFFFF, matched to raw PS3 index',
        'path_list': str(path_list), 'path_list_sha256': digest(path_list),
        'index': str(index), 'index_sha256': digest(index),
        'runtime_ledger_sha256': digest(runtime),
        **dictionary_counts, 'archive_records': len(records), 'status_counts': dict(counts),
        'named_payload_kinds': dict(named_kinds), 'nonwrapper_debug_source_names': len(debug_sources),
        'named_bytecode_with_matching_debug_basenames': sum(r.get('debug_source_basename_agreement', False) for r in records),
        'output_directory': str(output),
        'limits': ['Candidate dictionary match, not a mathematical proof against CRC collisions.',
                   'Preserved spelling/capitalization comes from PathList, not from the case-folded hashes.',
                   'A .luab resource can contain source text or bundle multiple original .cli.lua/.cmn.lua sources.',
                   'No guesses for unresolved records; no Lua execution or decompilation.']}
    output.mkdir(parents=True, exist_ok=True)
    manifest = {**summary, 'records': records}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return summary, records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--path-list', type=Path, default=HERE / 'PathList.txt')
    parser.add_argument('--index', type=Path, default=Path('E:/FFXIV-Monitor-PS3/game/sqpack/ffxiv/0b0000.ps3.d.index'))
    parser.add_argument('--runtime', type=Path, default=Path('build/ps3-script-runtime.json'))
    parser.add_argument('--extracted', type=Path, default=Path('build/ps3-lua'))
    parser.add_argument('--output-dir', type=Path, default=Path('build/ps3-lua-named'))
    parser.add_argument('--summary', type=Path, default=HERE / 'lua_path_recovery.json')
    args = parser.parse_args()
    summary, records = recover(args.path_list, args.index, args.runtime, args.extracted, args.output_dir)
    summary['examples'] = [
        {key: r[key] for key in ['directory_hash', 'filename_hash', 'recovered_path', 'debug_source_names']}
        for r in records if r.get('recovered_path', '').lower().endswith((
            '/aetheryte.luab', '/cmndefretainercall_00010.luab',
            '/cmndefmateriaslot_00174.luab', '/cmndefbeautysalon_00148.luab'))]
    summary['unresolved'] = [{k: r[k] for k in ['directory_hash', 'filename_hash', 'kind', 'status']}
                             for r in records if r['status'] != 'unique_dictionary_hash_pair_match']
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: summary[k] for k in ['archive_records', 'status_counts', 'named_payload_kinds',
                                             'nonwrapper_debug_source_names', 'output_directory']}, indent=2))


if __name__ == '__main__':
    main()

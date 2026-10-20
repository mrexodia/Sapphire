"""Measure known-path lower bounds and recover candidate EXD column labels.

This uses previously exported monitor metadata and inspector scan/inventory.
It does NOT reverse CRCs, prove foreign keys, or infer complete ID semantics.
Full path/column ledgers stay under build/; the compact report is reviewable.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import zlib

CATEGORIES = dict(zip(
    ('common', 'bgcommon', 'bg', 'cut', 'chara', 'shader', 'ui', 'sound', 'vfx',
     'ui_script', 'exd', 'game_script', 'music'), range(13)))
WIDTHS = {0: 4, 1: 1, 2: 1, 3: 1, 4: 2, 5: 2, 6: 4, 7: 4, 8: 2, 9: 4, 10: 8, 11: 8,
          **{i: 1 for i in range(25, 33)}}


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')


def crc(text):
    return zlib.crc32(text.encode('ascii')) ^ 0xFFFFFFFF


def flatten(name, types, base=0, prefix='', seen=()):
    """Flatten only well-bounded UDTs/one-dimensional arrays; keep ambiguity."""
    if name in seen or len(seen) > 12:
        return []
    result = []
    for member in types.get(name, {}).get('members', []):
        if 'offset' not in member or member['offset'] is None:
            continue
        offset = base + member['offset']
        path = prefix + member['name']
        typ = member['type']
        array = re.fullmatch(r'(.+)\[(\d+)\]', typ)
        if array and int(array[2]) and member['size'] % int(array[2]) == 0:
            size = member['size'] // int(array[2])
            for i in range(int(array[2])):
                nested = array[1].strip()
                itempath = f'{path}[{i}]'
                if types.get(nested, {}).get('kind') == 'udt' and not nested.endswith('::StringOffset'):
                    result.extend(flatten(nested, types, offset + i * size, itempath + '.', seen + (name,)))
                else:
                    result.append({'name': itempath, 'offset': offset + i * size, 'size': size,
                                   'type': nested, 'bitfield': False})
        elif types.get(typ, {}).get('kind') == 'udt' and not typ.endswith('::StringOffset'):
            result.extend(flatten(typ, types, offset, path + '.', seen + (name,)))
        else:
            result.append({**member, 'name': path, 'offset': offset})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, default=Path('build'))
    parser.add_argument('--output', type=Path, default=Path('research/ps3-monitor/monitor_recovery.json'))
    args = parser.parse_args()
    scan = load(args.build / 'ps3-exd-scan.json')
    inventory = load(args.build / 'ps3-inventory.json')
    metadata = load(args.build / 'ps3-monitor-metadata.json')
    types = {t['name']: t for t in metadata['types']}

    candidates = {}

    def add(path, source):
        path = path.replace('\\', '/').lower()
        if not re.fullmatch(r'[a-z0-9_./-]+', path) or '.' not in path.rsplit('/', 1)[-1]:
            return
        if path.split('/')[0] not in CATEGORIES or '..' in path.split('/'):
            return
        candidates.setdefault(path, set()).add(source)

    add('exd/root.exl', 'root catalog')
    for sheet in scan['sheets']:
        add(f"exd/{sheet['name']}.exh", 'root catalog')
        for page in sheet.get('validated_pages', []):
            if 'error' not in page:
                add(page['path'], 'validated EXD page')
    for item in metadata['candidate_paths']:
        add(item['text'], 'compiled-in literal (unexpanded)')
    # Explicitly partial decoded sheets from previous investigations.
    for filename in ['ps3-eobj.json', 'ps3-territory.json', 'ps3-exportedsg.json']:
        file = args.build / filename
        if not file.is_file():
            continue
        for row in load(file).get('rows', []):
            for value in row['fields']:
                if isinstance(value, dict) and 'text' in value:
                    add(value['text'], f'decoded {filename} string')
                    if filename == 'ps3-territory.json' and value['text'].startswith('ffxiv/'):
                        add('bg/' + value['text'] + '.lvb', 'TerritoryType LVB path recipe')
    sgb = Path(__file__).with_name('sastasha_grate_timelines.json')
    if sgb.is_file():
        add(load(sgb)['asset'], 'extracted Sastasha SGB')

    matched, archives = [], []
    for archive in inventory['archives']:
        category = int(Path(archive['path']).name[:2], 16)
        entries = {(e['directory_hash'], e['filename_hash']) for e in archive['entries']}
        found = set()
        for path, sources in candidates.items():
            if CATEGORIES[path.split('/')[0]] != category:
                continue
            directory, filename = path.rsplit('/', 1)
            key = (crc(directory), crc(filename))
            if key in entries:
                found.add(key)
                matched.append({'index': archive['path'], 'path': path, 'directory_hash': key[0],
                                'filename_hash': key[1], 'sources': sorted(sources)})
        archives.append({'index': archive['path'], 'entries': len(entries),
                         'entries_with_candidate_path_hash_match': len(found),
                         'not_named_by_these_sources': len(entries) - len(found)})
    assert any(m['path'] == 'exd/root.exl' for m in matched), 'CRC convention did not match root.exl'
    assert any(m['path'].endswith('sgbg_s1d1_m1_bos1.sgb') for m in matched), 'Known SGB hash mismatch'

    labels = []
    for sheet in scan['sheets']:
        name = sheet['name'] + 'Struct'
        typ = types.get(name)
        if not typ or typ.get('kind') != 'udt' or typ['size'] != sheet['schema']['fixed_size']:
            continue
        members = flatten(name, types)
        columns = []
        for i, column in enumerate(sheet['schema']['columns']):
            compatible = []
            for member in members:
                if member['offset'] != column['offset'] or member['size'] != WIDTHS.get(column['type']):
                    continue
                if column['type'] >= 25:
                    if not member.get('bitfield') or member.get('bit_size') != 1 or member.get('bit_offset') != column['type'] - 25:
                        continue
                elif member.get('bitfield'):
                    continue
                if column['type'] == 0 and not member['type'].endswith('::StringOffset'):
                    continue
                if 'padding' in member['name'].lower() or '_gap' in member['name'].lower():
                    continue
                compatible.append(member['name'])
            columns.append({'column': i, **column, 'debug_field_candidates': compatible,
                            'status': 'metadata offset/width match; not a verified foreign key'})
        labels.append({'sheet': sheet['name'], 'row_type': name, 'columns': columns})

    named = sum(len(c['debug_field_candidates']) == 1 for s in labels for c in s['columns'])
    all_columns = sum(len(s['schema']['columns']) for s in scan['sheets'])
    example_names = {'EObj', 'TerritoryType', 'Item'}
    report = {
        'schema_version': 1,
        'paths': {'indexed_entries': inventory['entry_count'], 'conservative_candidate_strings': len(candidates),
                  'entries_with_candidate_path_hash_match': sum(a['entries_with_candidate_path_hash_match'] for a in archives),
                  'archives': archives, 'complete': False,
                  'limits': ['Exact index hash-pair matches are candidate-name evidence, not a collision-free proof of original spelling.',
                             'Only catalog/page paths, fixed binary literals, three decoded sheets and one SGB were used.',
                             'No general traversal of model/material/texture/sound dependencies or expansion of printf templates.']},
        'excel': {'root_sheets': len(scan['sheets']), 'exact_name_and_size_row_struct_matches': len(labels),
                  'total_schema_columns': all_columns, 'columns_with_one_debug_field_candidate': named,
                  'matched_row_struct_sheets': [s['sheet'] for s in labels],
                  'examples': [s for s in labels if s['sheet'] in example_names],
                  'foreign_key_graph_complete': False,
                  'warning': 'Metadata-based candidate names; equal row size or integer values do not prove relationships.'},
        'types': {'imported_records': len(metadata['types']), 'kinds': dict(Counter(t['kind'] for t in metadata['types'])),
                  'names_containing_Id_or_ID': sum(bool(t['name']) and ('Id' in t['name'] or 'ID' in t['name']) for t in metadata['types']),
                  'id_semantics_complete': False,
                  'warning': 'ID-like names are a search heuristic. Enum records include unrelated enums and alternate views.'}
    }
    save(args.build / 'ps3-known-paths.json', matched)
    save(args.build / 'ps3-excel-column-candidates.json', labels)
    save(args.output, report)
    print(json.dumps({k: report[k] for k in ['types']}, indent=2))
    print(f"Path hash matches: {report['paths']['entries_with_candidate_path_hash_match']} / {inventory['entry_count']}")
    print(f'Row struct matches: {len(labels)} / {len(scan["sheets"])}; unambiguous label candidates: {named} / {all_columns}')


if __name__ == '__main__':
    main()

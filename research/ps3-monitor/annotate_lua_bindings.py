"""Comment-only Lua binding cross-references from the offline PS3 EXD graph.

Never executes Lua. Writes a separate annotated corpus, preserving recommended
sources and their verification manifest. Stored EXD values are facts; runtime
scope/precedence is not inferred from a matching name. Conflicts stay visible.
"""
import argparse
from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess


IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
NUMBER = re.compile(r'(?:0[xX][0-9A-Fa-f]+|(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)')
ARRAY_NAME = re.compile(r'^(.*\[[0-9]+\])\.(?:Name|DefineName)$')
SAFE_SYMBOL = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
FAMILY = {'quest': ['QuestSystemDefine'], 'opening': ['OpeningSystemDefine'],
          'story': ['StorySystemDefine'], 'leve': ['LeveSystemDefine'],
          'raid': ['DirectorSystemDefine'], 'guild_order': ['DirectorSystemDefine']}


@dataclass
class Token:
    kind: str
    raw: str
    line: int
    offset: int


def lex(source):
    """Lua 5.1 lexical spans, skipping comments but preserving exact token text."""
    starts = [0] + [m.end() for m in re.finditer('\n', source)]
    unsafe = set()
    tokens = []
    i = 0
    def line(pos):
        return bisect_right(starts, pos)
    def multiline(start, end):
        for number in range(line(start) + 1, line(end - 1) + 1):
            unsafe.add(number)
    def long_end(pos):
        opener = re.match(r'\[(=*)\[', source[pos:])
        if not opener:
            return None
        marker = ']' + opener.group(1) + ']'
        found = source.find(marker, pos + len(opener.group(0)))
        if found < 0:
            raise ValueError('Unterminated long string/comment')
        return found + len(marker)
    while i < len(source):
        ch = source[i]
        if ch.isspace():
            i += 1
            continue
        if source.startswith('--', i):
            end = long_end(i + 2)
            if end is None:
                end = source.find('\n', i)
                if end < 0:
                    end = len(source)
            multiline(i, end)
            i = end
            continue
        start = i
        end = long_end(i) if ch == '[' else None
        if end is not None:
            kind = 'string'
            i = end
        elif ch in ('"', "'"):
            quote = ch
            i += 1
            while i < len(source):
                if source[i] == '\\':
                    i += 2
                elif source[i] == quote:
                    i += 1
                    break
                else:
                    i += 1
            else:
                raise ValueError('Unterminated quoted string')
            kind = 'string'
        else:
            match = IDENT.match(source, i)
            numeric = NUMBER.match(source, i)
            if match:
                kind, i = 'identifier', match.end()
            elif numeric:
                kind, i = 'number', numeric.end()
            else:
                symbol = next((s for s in ['...', '..', '==', '~=', '<=', '>='] if source.startswith(s, i)), ch)
                kind, i = 'symbol', i + len(symbol)
        multiline(start, i)
        tokens.append(Token(kind, source[start:i], line(start), start))
    return tokens, unsafe


def signature(tokens):
    return [(t.kind, t.raw) for t in tokens]


def row_fact(sheet, row, name, value, field, kind, confidence):
    return {'name': name, 'value': value, 'source': sheet, 'row': row['main_id'],
            'ordinal': row['ordinal'], 'language': row['language'], 'field': field,
            'kind': kind, 'schema_confidence': confidence}


def load_facts(database):
    db = sqlite3.connect(f'file:{database.resolve().as_posix()}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    metadata = dict(db.execute('SELECT key,value FROM metadata'))
    bindings, globals_, text_maps = defaultdict(list), defaultdict(list), defaultdict(list)
    unmapped = []
    for sheet in db.execute('SELECT sheet_id,name FROM sheet'):
        name, sid = sheet['name'], sheet['sheet_id']
        fields = {f['name']: dict(f) for f in db.execute('SELECT name,column_index,confidence,type_name FROM field WHERE sheet_id=?', (sid,))}
        pairs = []
        for fname, field in fields.items():
            match = ARRAY_NAME.match(fname)
            if match:
                prefix = match.group(1)
                target = prefix + ('.DefineValue' if fname.endswith('.DefineName') else '.Value')
                if target in fields:
                    pairs.append((fname, target))
        script_column = fields.get('Script')
        shared = 'DefineName' in fields and 'DefineValue' in fields and name.endswith('SystemDefine')
        text = fields.get('Symbol') and fields.get('Text') and '/' in name
        if not (pairs or shared or text):
            continue
        for row in db.execute('SELECT main_id,ordinal,language,values_json FROM row_data WHERE sheet_id=?', (sid,)):
            values = json.loads(row['values_json'])
            if shared:
                symbol, value = values[fields['DefineName']['column_index']], values[fields['DefineValue']['column_index']]
                if symbol and SAFE_SYMBOL.fullmatch(symbol) and isinstance(value, int) and not isinstance(value, bool):
                    globals_[name].append(row_fact(name, row, symbol, value, 'DefineValue', 'shared_table', fields['DefineValue']['confidence']))
            if text:
                symbol = values[fields['Symbol']['column_index']]
                if symbol and SAFE_SYMBOL.fullmatch(symbol):
                    fact = row_fact(name, row, symbol, row['main_id'], 'main_id', 'text_row_key', fields['Symbol']['confidence'])
                    # Not decoded as a binding Value. Explicitly label this as a
                    # text-row-key cross-reference, not a numeric runtime guarantee.
                    text_maps[name.lower()].append(fact)
            if pairs:
                facts = []
                for nfield, vfield in pairs:
                    symbol, value = values[fields[nfield]['column_index']], values[fields[vfield]['column_index']]
                    if symbol and SAFE_SYMBOL.fullmatch(symbol) and isinstance(value, int) and not isinstance(value, bool):
                        facts.append(row_fact(name, row, symbol, value, vfield, 'handler_define', fields[vfield]['confidence']))
                script = values[script_column['column_index']] if script_column else None
                if isinstance(script, str) and script:
                    key = Path(script.replace(chr(92), '/')).stem.lower()
                    bindings[key].extend(facts)
                elif facts:
                    unmapped.append({'sheet': name, 'row': row['main_id'], 'reason': 'No direct Script field; not sprayed across scripts', 'facts': len(facts)})
    db.close()
    return bindings, globals_, text_maps, metadata, unmapped


def load_native(path):
    groups = {}
    if not path.is_file():
        return groups
    for group in json.loads(path.read_text(encoding='utf-8'))['classes']:
        facts = []
        for item in group['constants']:
            if item['assembly_immediate_confirmed']:
                facts.append({'name': item['name'], 'value': item['value'],
                              'source': 'Native:' + group['class'], 'row': group['function'],
                              'ordinal': 0, 'language': None, 'field': 'DefineLuaClass SetField',
                              'kind': 'native_literal', 'schema_confidence': 'assembly_witness'})
        groups['Native:' + group['class']] = facts
    return groups


def define_module_name(source):
    if not source.startswith('Native:'):
        return source.removesuffix('Define')
    name = source.removeprefix('Native:')
    if name == 'LuaEventHandler':
        return 'EventSystem'
    return name.removesuffix('EventHandler').removesuffix('Director') + 'System' if name != 'Director' else 'DirectorSystem'


def strip_annotations(source):
    """Remove our previous comments, never similarly spelled text in strings."""
    marker = '-- BEGIN PS3 BINDING CROSS-REFERENCES (generated comments only)\n'
    while source.startswith(marker):
        end = source.find('-- END PS3 BINDING CROSS-REFERENCES\n')
        if end < 0:
            raise ValueError('Incomplete generated annotation header')
        source = source[end + len('-- END PS3 BINDING CROSS-REFERENCES\n'):]
    strings = [(t.offset, t.offset + len(t.raw)) for t in lex(source)[0] if t.kind == 'string']
    starts = [a for a, _ in strings]
    result, offset = [], 0
    for line in source.splitlines(keepends=True):
        position = bisect_right(starts, offset) - 1
        inside_string = position >= 0 and offset < strings[position][1]
        if inside_string or not line.lstrip().startswith('-- @ps3-bind '):
            result.append(line)
        offset += len(line)
    return ''.join(result)


def write_define_modules(shared, output, luac):
    """Static reference modules. EXD and native namespaces never overwrite each other."""
    modules = defaultdict(lambda: defaultdict(list))
    for source, facts in shared.items():
        if facts:
            modules[define_module_name(source)][source].extend(facts)
    records = []
    for name, sources in sorted(modules.items()):
        lines = ['-- Generated PS3 reference data; NOT an automatically loaded game script.',
                 '-- Separate EXD/native namespaces preserve provenance, not runtime lookup precedence.',
                 'return {', '  exd = {']
        def entries(facts, indent):
            grouped = defaultdict(list)
            for fact in facts:
                grouped[fact['name']].append(fact)
            result = []
            for symbol, items in sorted(grouped.items()):
                values = {json.dumps(f['value']) for f in items}
                if len(values) != 1:
                    raise ValueError(f'Conflicting values within one definition source: {name}/{symbol}')
                for fact in items:
                    result.append(indent + '-- ' + fact_text(fact, definition=True))
                result.append(indent + symbol + ' = ' + str(items[0]['value']) + ',')
            return result
        for source, facts in sorted(sources.items()):
            if not source.startswith('Native:'):
                lines.extend(entries(facts, '    '))
        lines.extend(['  },', '  native = {'])
        for source, facts in sorted(sources.items()):
            if source.startswith('Native:'):
                lines.append('    ' + source.removeprefix('Native:') + ' = {')
                lines.extend(entries(facts, '      '))
                lines.append('    },')
        lines.extend(['  },', '}', ''])
        path = output / 'defines' / (name + '.lua')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('\n'.join(lines), encoding='utf-8', newline='\n')
        check = subprocess.run([str(luac.resolve()), '-p', str(path)], capture_output=True, timeout=30)
        if check.returncode:
            raise ValueError(f'Definition module syntax error: {path}: {check.stderr!r}')
        records.append({'path': path.relative_to(output).as_posix(), 'sources': sorted(sources),
                        'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'lua51_syntax_valid': True})
    return records


def literal(tokens, at):
    negative = False
    if at < len(tokens) and tokens[at].raw == '-':
        negative = True
        at += 1
    if at >= len(tokens):
        return None
    token = tokens[at]
    if token.kind == 'number':
        try:
            value = int(token.raw, 16) if token.raw.lower().startswith('0x') else float(token.raw)
            value = -value if negative else value
            if isinstance(value, float) and value.is_integer():
                value = int(value)
            return value, at
        except ValueError:
            return None
    if not negative and token.raw in ('true', 'false'):
        return token.raw == 'true', at
    return None


def references(tokens, class_name):
    """Direct self/class member reads/writes; quoted identifier bracket keys too.

    Do not claim constants for arbitrary actor/userdata receivers or shadowed
    bare identifiers. Dynamic keys remain unresolved.
    """
    reads, writes, assignments = defaultdict(set), set(), []
    for i, token in enumerate(tokens):
        if token.kind != 'identifier' or token.raw.lower() not in ('self', class_name.lower()):
            continue
        if i and tokens[i - 1].raw in ('.', ':'):
            continue
        end = None
        symbol = None
        if i + 2 < len(tokens) and tokens[i + 1].raw == '.' and tokens[i + 2].kind == 'identifier':
            symbol, end = tokens[i + 2].raw, i + 2
        elif i + 3 < len(tokens) and tokens[i + 1].raw == '[' and tokens[i + 3].raw == ']':
            raw = tokens[i + 2].raw
            if len(raw) >= 2 and raw[0] in ('"', "'") and raw[-1] == raw[0] and SAFE_SYMBOL.fullmatch(raw[1:-1]):
                symbol, end = raw[1:-1], i + 3
        if symbol is None:
            continue
        write = end + 1 < len(tokens) and tokens[end + 1].raw == '='
        if write:
            writes.add(symbol)
            item = literal(tokens, end + 2)
            if item:
                value, last = item
                following = tokens[last + 1] if last + 1 < len(tokens) else None
                # Reject expressions: no partial claim from "1 + function()".
                if following is None or following.raw in (';', 'end') or (following.line > tokens[last].line and following.raw not in ('+', '-', '*', '/', '^', '%', '..', 'and', 'or', '[', '.', '(', ':')):
                    assignments.append({'name': symbol, 'value': value, 'source': 'Lua literal assignment', 'row': token.line,
                                        'ordinal': 0, 'language': None, 'field': token.raw + '.' + symbol,
                                        'kind': 'lua_literal', 'schema_confidence': 'source_literal'})
        else:
            reads[token.line].add(symbol)
    return reads, writes, assignments


def value_text(value):
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return f'{value} (0x{value:08X})' if value >= 0 else str(value)
    return json.dumps(value, ensure_ascii=True)


def fact_text(fact, definition=False):
    if fact['kind'] == 'native_literal' and not definition:
        return f"{fact['name']} <- defines/{define_module_name(fact['source'])}.lua native.{fact['source'].removeprefix('Native:')} [scope candidate]"
    if fact['kind'] == 'lua_literal':
        location = f"Lua L{fact['row']} {fact['field']}"
    else:
        location = f"{fact['source']}[{fact['row']}]/{fact['ordinal']} lang={fact['language']} {fact['field']}"
    suffix = ' [text row key, NOT stored DefineValue]' if fact['kind'] == 'text_row_key' else ''
    return f"{fact['name']} = {value_text(fact['value'])} <- {location}{suffix}"


def annotate(source, relative, binding_facts, shared, text_facts):
    source = strip_annotations(source)
    tokens, unsafe = lex(source)
    reads, writes, _ = references(tokens, relative.stem)
    used = set().union(*reads.values()) if reads else set()
    family = relative.parts[0]
    selected = {'EventSystemDefine', *FAMILY.get(family, [])}
    stem = relative.stem.lower()
    if 'Native:LuaEventHandler' in shared:
        selected.add('Native:LuaEventHandler')
    native_family = {'quest': 'QuestEventHandler', 'custom': 'CustomTalkEventHandler',
                     'opening': 'OpeningEventHandler', 'story': 'StoryEventHandler', 'warp': 'WarpEventHandler'}
    if family in native_family:
        selected.add('Native:' + native_family[family])
    for name, facts in shared.items():
        if name.removeprefix('Native:').removesuffix('EventHandler').removesuffix('SystemDefine').lower() == stem or any(f['name'] in used for f in facts):
            selected.add(name)
    facts = [*binding_facts, *text_facts]
    for name in sorted(selected):
        # Shared/native inventories live in defines/, not in every script header.
        facts.extend(f for f in shared.get(name, []) if f['name'] in used)
    index = defaultdict(list)
    for fact in facts:
        if fact not in index[fact['name']]:
            index[fact['name']].append(fact)
    header = ['-- BEGIN PS3 BINDING CROSS-REFERENCES (generated comments only)',
              '-- Stored EXD numbers are concrete for this dataset, NOT immutable runtime properties.',
              '-- Exact Script/name matches are cross-references; native scope/override precedence is not proven here.',
              '-- Shared table selection: EventSystemDefine, family candidates, matching stem or referenced names.',
              '-- "Unused" means no direct self/class read in this source, not unreachable/unused at runtime.',
              '-- Dynamic keys, other receivers and bare identifiers are not assigned guessed values.']
    groups = [('Handler Name/Value pairs', 'handler_define'),
              ('Shared definition table snapshots (scope candidates)', 'shared_table'),
              ('Native definition references (values in defines/; scope candidates)', 'native_literal'),
              ('Script-local text symbol row keys (separate from binding data)', 'text_row_key')]
    for label, kind in groups:
        relevant = [f for f in facts if f['kind'] == kind]
        if not relevant:
            continue
        for is_used in (True, False):
            group = [f for f in relevant if (f['name'] in used) == is_used]
            if not group:
                continue
            header.append(f"-- {label}: {'REFERENCED' if is_used else 'NOT DIRECTLY REFERENCED'}")
            for fact in sorted(group, key=lambda f: (f['name'], f['source'], str(f['row']), f['field'])):
                header.append('--   ' + fact_text(fact))
    conflicts = {name for name, fs in index.items() if len({json.dumps(f['value']) for f in fs if f['kind'] != 'text_row_key'}) > 1}
    if conflicts:
        header.append('-- Multiple stored/literal values (no precedence guessed): ' + ', '.join(sorted(conflicts)))
    if writes & index.keys():
        header.append('-- Written in this source (snapshot is not an immutability claim): ' + ', '.join(sorted(writes & index.keys())))
    unresolved_members = sorted(used - index.keys() - writes)
    if unresolved_members:
        header.append('-- Direct members without a recovered constant fact (may be methods/state): ' + ', '.join(unresolved_members))
    header.append('-- END PS3 BINDING CROSS-REFERENCES')
    insertions = defaultdict(set)
    unknown = set()
    for line, symbols in reads.items():
        safe_line = line
        while safe_line in unsafe and safe_line > 1:
            safe_line -= 1
        for symbol in sorted(symbols):
            if symbol not in index:
                if symbol not in writes:
                    unknown.add(symbol)
                continue
            for fact in index[symbol]:
                note = fact_text(fact)
                if symbol in conflicts:
                    note += ' [multiple source values; precedence unresolved]'
                if symbol in writes:
                    note += ' [also assigned in source]'
                insertions[safe_line].add(note)
    output = ['\n'.join(header) + '\n']
    for number, line in enumerate(source.splitlines(keepends=True), 1):
        indent = re.match(r'[ \t]*', line).group(0)
        for note in sorted(insertions.get(number, [])):
            output.append(indent + '-- @ps3-bind ' + note + '\n')
        output.append(line)
    result = ''.join(output)
    if signature(lex(result)[0]) != signature(tokens):
        raise ValueError(f'Annotation changed lexical code tokens: {relative}')
    return result, {'facts': len(facts), 'inline_comments': sum(map(len, insertions.values())),
                    'handler_facts': len(binding_facts), 'selected_shared_tables': sorted(selected),
                    'unknown_direct_members': sorted(unknown), 'conflicting_names': sorted(conflicts),
                    'written_names': sorted(writes & index.keys()), 'facts_provenance': facts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--graph', type=Path, default=Path('build/ps3-data-graph.sqlite'))
    parser.add_argument('--input', type=Path, default=Path('build/ps3-lua-decompiled/recommended/game_script'))
    parser.add_argument('--output', type=Path, default=Path('build/ps3-lua-annotated/game_script'))
    parser.add_argument('--luac', type=Path, default=Path('build/lua51-reference/luac51.exe'))
    parser.add_argument('--native', type=Path, default=Path('build/ps3-native-lua-defines.json'))
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve() or args.output.resolve().is_relative_to(args.input.resolve()):
        parser.error('Output must be separate from the verified input corpus')
    bindings, shared, texts, metadata, unmapped = load_facts(args.graph)
    shared.update(load_native(args.native))
    files = sorted(p for p in args.input.rglob('*.lua') if p.relative_to(args.input).parts[0] != 'defines')
    stems = Counter(p.stem.lower() for p in files)
    records, totals = [], Counter()
    fact_ids, fact_registry = {}, []
    for path in files:
        relative = path.relative_to(args.input)
        matches = bindings.get(path.stem.lower(), []) if stems[path.stem.lower()] == 1 else []
        # Basename collisions are not silently resolved using guessed families.
        raw = path.read_bytes()
        source = raw.decode('utf-8')
        result, details = annotate(source, relative, matches, shared, texts.get(relative.with_suffix('').as_posix().lower(), []))
        if signature(lex(result)[0]) != signature(lex(source)[0]):
            raise ValueError(f'Reannotation changed input code tokens: {relative}')
        output = args.output / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(result, encoding='utf-8', newline='\n')
        check = subprocess.run([str(args.luac.resolve()), '-p', str(output)], capture_output=True, timeout=30)
        if check.returncode:
            raise ValueError(f'Annotated source syntax error: {output}: {check.stderr.decode(errors="replace")}')
        details.update({'path': relative.as_posix(), 'input_sha256': hashlib.sha256(raw).hexdigest(),
                        'output_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                        'code_tokens_identical': True, 'lua51_syntax_valid': True,
                        'ambiguous_binding_stem': stems[path.stem.lower()] > 1 and path.stem.lower() in bindings})
        references_ = []
        for fact in details.pop('facts_provenance'):
            key = json.dumps(fact, sort_keys=True)
            if key not in fact_ids:
                fact_ids[key] = len(fact_registry)
                fact_registry.append(fact)
            references_.append(fact_ids[key])
        details['fact_ids'] = references_
        records.append(details)
        for key in ['facts', 'inline_comments', 'handler_facts']:
            totals[key] += details[key]
        totals['files'] += 1
        totals['files_with_handler_bindings'] += bool(matches)
    definition_records = write_define_modules(shared, args.output, args.luac)
    summary = {'schema_version': 3, 'input': str(args.input), 'output': str(args.output),
               'native': str(args.native) if args.native.is_file() else None,
               'native_sha256': hashlib.sha256(args.native.read_bytes()).hexdigest() if args.native.is_file() else None,
               'unique_facts': len(fact_registry), 'definition_modules': definition_records,
               'graph': str(args.graph), 'graph_metadata': metadata, 'totals': dict(totals),
               'unmapped_binding_rows': unmapped,
               'unmatched_binding_script_stems': sorted(set(bindings) - set(stems)),
               'limits': ['Comment-only snapshot annotations; exact code tokens and Lua 5.1 syntax checked for every file.',
                          'Scope/override precedence not proven. Multiple values and source writes are retained.',
                          'Text symbols are row-key cross-references, not stored Name/Value entries.',
                          'Only referenced shared/native names appear in scripts; full inventories are in defines/.',
                          'Lua literal assignments are not annotated; native values are displayed in reference modules only.',
                          'Native literals require assembly witnesses; their script-class scope is still a candidate.',
                          'fact_ids in each record index the manifest-wide fact_registry (zero-based).',
                          'No Lua execution; original recommended corpus untouched.']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    (args.output.parent / 'manifest.json').write_text(json.dumps({**summary, 'fact_registry': fact_registry, 'records': records}, indent=2) + '\n', encoding='utf-8')
    (args.output.parent / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary['totals'], indent=2))


if __name__ == '__main__':
    main()

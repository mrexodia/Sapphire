"""Batch-decompile named monitor Lua resources without executing game scripts.

Keeps unluac, cLuaDecompiler and disassembly outputs separately. Lua 5.1's
reference luac validates syntax by compiling, never running, each source.
Exact instruction/constant tree comparisons are corroboration, not a general
semantic-equivalence test; differences are not automatically decompiler bugs.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import time


HERE = Path(__file__).resolve().parent
TOOLS = ['unluac', 'unluac-2015', 'cLuaDecompiler']


def sha(data):
    return hashlib.sha256(data).hexdigest()


class PrototypeReader:
    """Lua 5.1 float64 chunks: endian/size_t-aware, retaining raw string bytes.

    Fingerprints include arity, instruction words, exact constant bytes and
    ordered children, excluding debug information, stack-size and vararg flags.
    Those exclusions mean a matching fingerprint is NOT full behavior proof.
    """
    def __init__(self, data):
        if len(data) < 12 or data[:6] != b'\x1bLua\x51\0':
            raise ValueError('Expected Lua 5.1 format-0 chunk')
        endian, int_size, size_t, instruction, number, integral = data[6:12]
        if endian not in (0, 1) or int_size != 4 or size_t not in (4, 8) or instruction != 4 or number != 8 or integral != 0:
            raise ValueError('Unsupported Lua chunk profile')
        self.data, self.pos = data, 12
        self.endian = 'little' if endian else 'big'
        self.size_t = size_t
        self.stats = Counter()
        self.bodies = Counter()
        self.metadata = []  # preorder; retained separately from fingerprints

    def take(self, size):
        if not 0 <= size <= len(self.data) - self.pos:
            raise ValueError('Truncated Lua chunk')
        out = self.data[self.pos:self.pos + size]
        self.pos += size
        return out

    def integer(self, width=4):
        return int.from_bytes(self.take(width), self.endian)

    def string(self):
        size = self.integer(self.size_t)
        if not size:
            return None
        data = self.take(size)
        if data[-1:] != b'\0':
            raise ValueError('Missing string terminator')
        return data[:-1].hex()

    def prototype(self):
        self.stats['prototypes'] += 1
        self.string()
        self.take(8)  # line definitions
        nups, params, vararg, stack = self.take(4)
        self.metadata.append({'nups': nups, 'params': params, 'vararg_flags': vararg, 'maxstack': stack})
        code = [self.integer() for _ in range(self.integer())]
        self.stats['code_words'] += len(code)
        constants = []
        for _ in range(self.integer()):
            tag = self.take(1)[0]
            if tag == 0:
                value = None
            elif tag == 1:
                value = self.take(1).hex()
            elif tag == 3:
                raw = self.take(8)
                value = (raw[::-1] if self.endian == 'little' else raw).hex()
            elif tag == 4:
                value = self.string()
            else:
                raise ValueError(f'Unknown constant tag {tag}')
            constants.append([tag, value])
        body = [nups, params, code, constants]
        self.bodies[sha(json.dumps(body, separators=(',', ':')).encode('ascii'))] += 1
        children = [self.prototype() for _ in range(self.integer())]
        self.take(self.integer() * 4)  # line information
        for _ in range(self.integer()):
            self.string()
            self.take(8)
        for _ in range(self.integer()):
            self.string()
        return [nups, params, code, constants, children]

    def fingerprint(self):
        tree = self.prototype()
        self.tree = tree
        if self.pos != len(self.data):
            raise ValueError('Trailing data after chunk')
        return sha(json.dumps(tree, separators=(',', ':')).encode('ascii'))


def java_path():
    found = shutil.which('java')
    if found:
        return Path(found)
    home = os.environ.get('JAVA_HOME')
    if home and (Path(home) / 'bin/java.exe').is_file():
        return Path(home) / 'bin/java.exe'
    base = Path(os.environ.get('ProgramFiles', 'C:/Program Files'))
    for directory in ['Eclipse Adoptium', 'AdoptOpenJDK', 'Java']:
        paths = sorted((base / directory).glob('*/bin/java.exe'), reverse=True)
        if paths:
            return paths[0]
    raise ValueError('Java not found; supply --java')


def run_tool(command, output, stderr, timeout):
    output.parent.mkdir(parents=True, exist_ok=True)
    stderr.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    with output.open('wb') as stdout, stderr.open('wb') as errors:
        try:
            result = subprocess.run(command, stdout=stdout, stderr=errors, timeout=timeout)
            status, code = ('ok' if result.returncode == 0 else 'nonzero_exit'), result.returncode
        except subprocess.TimeoutExpired:
            status, code = 'timeout', None
    return {'status': status, 'return_code': code, 'seconds': round(time.monotonic() - start, 3),
            'output': str(output), 'output_sha256': sha(output.read_bytes()),
            'output_bytes': output.stat().st_size, 'stderr': str(stderr), 'stderr_bytes': stderr.stat().st_size}


def compile_check(source, bytecode, stderr, compiler, original_fingerprint, original_bodies, timeout):
    result = run_tool([str(compiler), '-s', '-o', str(bytecode), str(source)],
                      stderr.with_suffix('.stdout.txt'), stderr, timeout)
    result['syntax_status'] = result.pop('status')
    # luac prints no source output: discard generic stdout output fields here.
    for key in ['output', 'output_sha256', 'output_bytes']:
        result.pop(key)
    if result['syntax_status'] == 'ok':
        reader = PrototypeReader(bytecode.read_bytes())
        fingerprint = reader.fingerprint()
        result.update({'instruction_constant_tree_match': fingerprint == original_fingerprint,
                       'recompiled_tree_sha256': fingerprint, 'recompiled_stats': dict(reader.stats),
                       'matching_prototype_bodies': sum((reader.bodies & original_bodies).values()),
                       'bytecode': str(bytecode)})
    return result


def decompile_one(record, args):
    relative = Path(record['recovered_path'])
    source = args.named / relative
    data = source.read_bytes()
    if sha(data) != record['sha256'] or len(data) != record['size']:
        raise ValueError(f'Input hash/size mismatch: {source}')
    reader = PrototypeReader(data)
    fingerprint = reader.fingerprint()
    result = {'path': relative.as_posix(), 'input_sha256': record['sha256'],
              'original_tree_sha256': fingerprint, 'original_stats': dict(reader.stats), 'tools': {}}
    name = relative.with_suffix('.lua')
    commands = {
        'unluac': [str(args.java), '-Xmx256m', '-jar', str(args.unluac), str(source)],
        'unluac-2015': [str(args.java), '-Xmx256m', '-jar', str(args.legacy_unluac), str(source)],
        'cLuaDecompiler': [str(args.clua), '--dec', '--annotate', str(source)]}
    for tool, command in commands.items():
        output = args.output / tool / name
        stderr = args.output / 'diagnostics' / tool / name.with_suffix('.stderr.txt')
        outcome = run_tool(command, output, stderr, args.timeout)
        if outcome['status'] == 'ok' and outcome['output_bytes']:
            bytecode = args.output / 'recompiled' / tool / name.with_suffix('.luac')
            bytecode.parent.mkdir(parents=True, exist_ok=True)
            check_stderr = args.output / 'diagnostics' / tool / name.with_suffix('.luac.stderr.txt')
            outcome['validation'] = compile_check(output, bytecode, check_stderr, args.luac, fingerprint, reader.bodies, args.timeout)
        result['tools'][tool] = outcome
    dis = args.output / 'disassembly' / relative.with_suffix('.dis.txt')
    result['disassembly'] = run_tool([str(args.clua), '--dis', str(source)], dis,
                                    args.output / 'diagnostics' / 'disassembly' / name.with_suffix('.stderr.txt'), args.timeout)
    # Rank syntax-valid candidates by exact tree/body corroboration; ties favor
    # current unluac. Record the choice instead of silently combining methods.
    candidates = []
    for rank, tool in enumerate(TOOLS):
        validation = result['tools'][tool].get('validation', {})
        if validation.get('syntax_status') == 'ok':
            candidates.append((validation['instruction_constant_tree_match'],
                               validation['matching_prototype_bodies'], -rank, tool))
    if candidates:
        tool = max(candidates)[-1]
        result['preferred_tool'] = tool
        recommended = args.output / 'recommended' / name
        recommended.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(result['tools'][tool]['output'], recommended)
    return result


def aggregate(records):
    totals = {}
    for tool in TOOLS:
        states, checks = Counter(), Counter()
        for record in records:
            item = record['tools'][tool]
            states[item['status']] += 1
            validation = item.get('validation')
            if validation:
                checks['syntax_' + validation['syntax_status']] += 1
                if validation.get('instruction_constant_tree_match'):
                    checks['exact_instruction_constant_tree_match'] += 1
                if validation['syntax_status'] == 'ok':
                    checks['matching_prototype_bodies'] += validation['matching_prototype_bodies']
                    checks['original_prototypes_in_syntax_valid_files'] += record['original_stats']['prototypes']
                    checks['recompiled_prototypes'] += validation['recompiled_stats']['prototypes']
        totals[tool] = {'process_statuses': dict(states), 'validation': dict(checks)}
    totals['disassembly'] = dict(Counter(r['disassembly']['status'] for r in records))
    totals['preferred'] = dict(Counter(r.get('preferred_tool', 'none') for r in records))
    return totals


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--named', type=Path, default=Path('build/ps3-lua-named'))
    parser.add_argument('--output', type=Path, default=Path('build/ps3-lua-decompiled'))
    parser.add_argument('--summary', type=Path, default=HERE / 'lua_decompilation.json')
    parser.add_argument('--java', type=Path)
    parser.add_argument('--unluac', type=Path, default=Path('build/unluac-current.jar'))
    parser.add_argument('--legacy-unluac', type=Path, default=Path('bin/tools/unluac_2015_06_13.jar'))
    parser.add_argument('--clua', type=Path, default=Path('build/cLuaDecompiler.exe'))
    parser.add_argument('--luac', type=Path, default=Path('build/lua51-reference/luac51.exe'))
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--timeout', type=float, default=45)
    parser.add_argument('--limit', type=int, help='Smoke-test just the first N sorted bytecode resources')
    args = parser.parse_args()
    if args.jobs < 1 or args.timeout <= 0 or (args.limit is not None and args.limit < 1):
        parser.error('jobs, timeout and limit must be positive')
    args.java = args.java or java_path()
    for key in ['named', 'output', 'java', 'unluac', 'legacy_unluac', 'clua', 'luac']:
        setattr(args, key, getattr(args, key).resolve())
    for path in [args.java, args.unluac, args.legacy_unluac, args.clua, args.luac]:
        if not path.is_file():
            parser.error(f'Tool not found: {path}')
    manifest_path = args.named / 'manifest.json'
    named = json.loads(manifest_path.read_text(encoding='utf-8'))
    bytecode = sorted([r for r in named['records'] if r['kind'] == 'lua51_bytecode'], key=lambda r: r['recovered_path'])
    for record in bytecode:
        relative = Path(record['recovered_path'])
        if relative.is_absolute() or any(p in ('', '.', '..') for p in relative.parts):
            parser.error('Unsafe resource path')
    if args.limit:
        bytecode = bytecode[:args.limit]
    args.output.mkdir(parents=True, exist_ok=True)
    source_records = []
    for record in named['records']:
        if record['kind'] != 'source_text_candidate' or 'recovered_path' not in record:
            continue
        relative = Path(record['recovered_path'])
        data = (args.named / relative).read_bytes()
        if sha(data) != record['sha256']:
            raise ValueError('Source text payload hash mismatch')
        target = args.output / 'original-source' / relative.with_suffix('.lua')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        recommended = args.output / 'recommended' / relative.with_suffix('.lua')
        recommended.parent.mkdir(parents=True, exist_ok=True)
        recommended.write_bytes(data)
        source_records.append({'path': str(target), 'sha256': sha(data), 'kind': 'authentic_source_payload'})
    start = time.monotonic()
    results = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(decompile_one, r, args): r['recovered_path'] for r in bytecode}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            if len(results) % 100 == 0 or len(results) == len(bytecode):
                progress = {'completed': len(results), 'total': len(bytecode), 'seconds': round(time.monotonic() - start, 1),
                            'counts': aggregate(results)}
                (args.output / 'progress.json').write_text(json.dumps(progress, indent=2) + '\n', encoding='utf-8')
                print(f"{len(results)}/{len(bytecode)} completed ({progress['seconds']}s)", flush=True)
    results.sort(key=lambda r: r['path'])
    summary = {'schema_version': 1, 'bytecode_records': len(results), 'source_text_records': source_records,
               'seconds': round(time.monotonic() - start, 1), 'counts': aggregate(results),
               'unresolved': [r['path'] for r in results if 'preferred_tool' not in r],
               'input_manifest_sha256': sha(manifest_path.read_bytes()),
               'tools': {key: {'path': str(getattr(args, key)), 'sha256': sha(getattr(args, key).read_bytes())}
                         for key in ['java', 'unluac', 'legacy_unluac', 'clua', 'luac']},
               'reference_lua': {'version': '5.1.5', 'source_url': 'https://www.lua.org/ftp/lua-5.1.5.tar.gz',
                                 'source_sha256': '2640fc56a795f29d28ef15e13c34a47e223960b0240e8cb0a82d9b0738695333'},
               'current_unluac_source': 'https://sourceforge.net/projects/unluac/files/Unstable/unluac_2025_12_23.jar',
               'output_directory': str(args.output),
               'validation_scope': ['Lua 5.1 syntax checked by compilation only; no game script execution.',
                                    'Tree fingerprint includes arity, raw instructions, constants and ordered children.',
                                    'Debug info, stack size and vararg flags excluded; matching is not full behavior proof.',
                                    'Nonmatching trees can be equivalent; differences are not automatic bug verdicts.',
                                    'Matching prototype bodies are unordered multiset counts, not function-identity proof.',
                                    'Recommended candidate: syntax-valid, then exact tree, then most matching bodies; ties favor current unluac.']}
    (args.output / 'manifest.json').write_text(json.dumps({**summary, 'records': results}, indent=2) + '\n', encoding='utf-8')
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary['counts'], indent=2))


if __name__ == '__main__':
    main()

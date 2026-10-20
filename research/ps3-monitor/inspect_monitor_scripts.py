"""Inspect/extract the local monitor's known debug/plain SDAT + SqPack scripts.

Accepts only the observed 0x8100003C / 0x4000 interleaved framing profile.
No decryption, integrity verification, Lua execution or general EDAT support.
Usage: python research/ps3-monitor/inspect_monitor_scripts.py SQPACK_ROOT
       --output build/ps3-script-runtime.json [--extract build/ps3-lua]
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import zlib

LUA_HEADER = bytes.fromhex('1b4c75615100000404040800')


def check(condition, message):
    if not condition:
        raise ValueError(message)


def unwrap(path):
    raw = path.read_bytes()
    check(len(raw) >= 0x120 and raw[:4] == b'NPD\0', 'Missing NPD header')
    flags, block, size = struct.unpack_from('>IIQ', raw, 0x80)
    check(flags == 0x8100003C and block == 0x4000, 'Unsupported SDAT profile; do not assume plaintext')
    payload = bytearray()
    for i in range((size + block - 1) // block):
        start = 0x120 + i * (block + 0x20)
        length = min(block, size - len(payload))
        check(start + length <= len(raw), 'Truncated SDAT block')
        payload.extend(raw[start:start + length])
    check(len(payload) == size and payload[:8] == b'SqPack\0\0', 'Invalid logical SqPack stream')
    return payload, {'flags': hex(flags), 'block_size': block, 'logical_size': size,
                     'physical_size': len(raw), 'physical_sha256': hashlib.sha256(raw).hexdigest(),
                     'logical_sha256': hashlib.sha256(payload).hexdigest(),
                     'integrity_metadata': 'skipped, not authenticated'}


def records(index, payload):
    raw = index.read_bytes()
    start, length = struct.unpack_from('>II', raw, 0x408)
    check(length % 16 == 0 and start + length <= len(raw), 'Invalid index range')
    for p in range(start, start + length, 16):
        directory, filename, offset, _ = struct.unpack_from('>IIII', raw, p)
        offset *= 128
        header, typ, total = struct.unpack_from('>III', payload, offset)
        check(typ == 2, 'Only standard SqPack records supported')
        count = struct.unpack_from('>I', payload, offset + 20)[0]
        result = bytearray()
        for i in range(count):
            relative = struct.unpack_from('>I', payload, offset + 24 + i * 8)[0]
            pos = offset + header + relative
            block_header, _, compressed, uncompressed = struct.unpack_from('>IIII', payload, pos)
            check(block_header == 16, 'Unsupported SqPack block header')
            size = uncompressed if compressed == 32000 else compressed
            block = payload[pos + 16:pos + 16 + size]
            check(len(block) == size, 'Truncated SqPack payload')
            if compressed != 32000:
                stream = zlib.decompressobj(-15)
                block = stream.decompress(block) + stream.flush()
                check(stream.eof and not stream.unused_data, 'Incomplete/raw-DEFLATE block mismatch')
            check(len(block) == uncompressed, 'Block length mismatch')
            result.extend(block)
        check(len(result) == total, 'Record length mismatch')
        yield directory, filename, offset, bytes(result)


class Chunk:
    def __init__(self, data):
        check(data[:12] == LUA_HEADER, 'Unsupported Lua chunk profile')
        self.data, self.pos = data, 12
        self.stats = Counter()
        self.methods, self.globals = Counter(), Counter()
        self.strings, self.table_members = Counter(), Counter()
        self.scene_names = set()
        self.sources = set()

    def take(self, count):
        check(0 <= count <= len(self.data) - self.pos, 'Truncated Lua chunk')
        value = self.data[self.pos:self.pos + count]
        self.pos += count
        return value

    def integer(self):
        return int.from_bytes(self.take(4), 'big')

    def string(self):
        count = self.integer()
        if count == 0:
            return None
        value = self.take(count)
        check(value[-1:] == b'\0', 'Lua string missing terminator')
        return value[:-1].decode('utf-8', errors='replace')

    def prototype(self):
        self.stats['prototypes'] += 1
        source = self.string()
        if source:
            self.sources.add(source)
        self.take(8)  # linedefined, lastlinedefined
        self.take(4)  # nups, numparams, vararg flags, maxstacksize
        code = [self.integer() for _ in range(self.integer())]
        self.stats['code_words'] += len(code)
        constants = []
        for _ in range(self.integer()):
            typ = self.take(1)[0]
            if typ == 0:
                value = None
            elif typ == 1:
                value = bool(self.take(1)[0])
            elif typ == 3:
                value = struct.unpack('>d', self.take(8))[0]
            elif typ == 4:
                value = self.string()
                if value:
                    self.strings[value] += 1
                if value and value.startswith('OnScene'):
                    self.scene_names.add(value)
            else:
                raise ValueError(f'Unknown Lua constant type {typ}')
            constants.append(value)
        # Static operands under Lua 5.1's opcode interpretation, NOT execution
        # counts or proof that each operand reaches a runtime call.
        skip = False
        for word in code:
            if skip:
                skip = False
                continue
            opcode = word & 63
            c = (word >> 14) & 511
            if opcode == 34 and c == 0:  # SETLIST extended table-size word
                skip = True
            if opcode in (5, 7):  # GETGLOBAL / SETGLOBAL
                index = word >> 14
                if index < len(constants) and isinstance(constants[index], str):
                    self.globals[constants[index]] += 1
            if opcode == 6 and c & 256:  # GETTABLE A B RK(C)
                index = c & 255
                if index < len(constants) and isinstance(constants[index], str):
                    self.table_members[constants[index]] += 1
            if opcode == 11 and c & 256:  # SELF, RK(C) references a constant
                index = c & 255
                if index < len(constants) and isinstance(constants[index], str):
                    self.methods[constants[index]] += 1
        for _ in range(self.integer()):
            self.prototype()
        lines = self.integer()
        self.take(lines * 4)
        self.stats['prototypes_with_line_info'] += bool(lines)
        locals_ = self.integer()
        self.stats['local_variable_entries'] += locals_
        for _ in range(locals_):
            self.string()
            self.take(8)  # startpc, endpc
        upvalues = self.integer()
        self.stats['upvalue_name_entries'] += upvalues
        for _ in range(upvalues):
            self.string()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sqpack', type=Path)
    parser.add_argument('--output', type=Path, default=Path('build/ps3-script-runtime.json'))
    parser.add_argument('--extract', type=Path)
    args = parser.parse_args()
    base = args.sqpack / 'ffxiv'
    report = {'profile_scope': 'local debug/plain SDAT only; no authentication/decryption',
              'lua_header': LUA_HEADER.hex(), 'scripts': [], 'archives': []}
    totals, methods = Counter(), Counter()
    if args.extract:
        args.extract.mkdir(parents=True, exist_ok=True)
    for category in ['0b0000', '050000']:
        stem = category + '.ps3.d'
        payload, framing = unwrap(base / (stem + '.dat0.sdat'))
        count = 0
        kinds = Counter()
        for directory, filename, offset, data in records(base / (stem + '.index'), payload):
            count += 1
            if category != '0b0000':
                continue
            entry = {'directory_hash': f'{directory:08x}', 'filename_hash': f'{filename:08x}',
                     'logical_offset': offset, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
            if data.startswith(b'\x1bLua'):
                chunk = Chunk(data)
                chunk.prototype()
                check(chunk.pos == len(data), 'Unconsumed bytes after Lua prototype')
                kinds['lua51_bytecode'] += 1
                entry.update({'kind': 'lua51_bytecode', 'stats': dict(chunk.stats),
                              'source_names': sorted(chunk.sources), 'scene_name_constants': sorted(chunk.scene_names),
                              'string_constants': dict(chunk.strings), 'table_member_operands': dict(chunk.table_members),
                              'static_method_operands': dict(chunk.methods), 'global_operands': dict(chunk.globals)})
                totals.update(chunk.stats)
                methods.update(chunk.methods)
                extension = '.luac'
            elif data == b'placeholder':
                entry['kind'] = 'placeholder'
                kinds['placeholder'] += 1
                extension = '.txt'
            else:
                entry.update({'kind': 'source_text_candidate', 'preview': data[:500].decode('utf-8', errors='replace')})
                kinds['source_text_candidate'] += 1
                extension = '.lua'
            report['scripts'].append(entry)
            if args.extract:
                (args.extract / (f'{directory:08x}_{filename:08x}' + extension)).write_bytes(data)
        report['archives'].append({'category': category, 'records_validated': count, 'script_kinds': dict(kinds), **framing})
    report['prototype_totals'] = dict(totals)
    report['static_method_operands'] = dict(methods.most_common())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
    print(json.dumps({'archives': report['archives'], 'prototype_totals': dict(totals)}, indent=2))


if __name__ == '__main__':
    main()

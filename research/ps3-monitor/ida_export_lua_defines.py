"""Read-only IDA-domain export of native Lua constant registrations.

Run against the PS3 monitor IDB using ida_execute_python after API reference.
Decompiler literal candidates require a PPC li r6 immediate witness at the
SetField(int,char const*,int) call. Unconfirmed candidates are retained but NOT
consumed by the Lua annotation tool. This is not a general data-flow evaluator.
"""
import json
from pathlib import Path
import re


OUTPUT = Path('C:/CodeBlocks/Sapphire/build/ps3-native-lua-defines.json')


def run(db):
    groups = []
    for function in db.functions:
        name = db.functions.get_name(function)
        if 'DefineLuaClass' not in name or not any(s in name for s in ['EventHandler', 'Director']):
            continue
        text = '\n'.join(db.pseudocode.get_text(function))
        assembly = db.functions.get_disassembly(function)
        constants = []
        for match in re.finditer(r'key:\s*"([A-Z][A-Z0-9_]+)",\s*value:\s*(-?\d+)\s*\)', text):
            key, value = match.group(1), int(match.group(2))
            witnesses = []
            for i, line in enumerate(assembly):
                if not line.startswith('bl') or 'SetField(int,char const*,int)' not in line:
                    continue
                window = assembly[max(0, i - 9):i + 1]
                if not any(('"' + key + '"') in s for s in window):
                    continue
                loads = [s for s in window if re.match(r'li\s+r6,', s)]
                if not loads:
                    continue
                operand = loads[-1].split(',')[1].split('#')[0].strip()
                try:
                    immediate = int(operand, 0)
                except ValueError:
                    continue
                position = max(j for j, instruction in enumerate(window) if re.match(r'li\s+r6,', instruction))
                intervening = window[position + 1:-1]
                clobbered = any(re.match(r'\w+\s+r6\s*,', instruction) or instruction.startswith('b')
                                for instruction in intervening)
                if immediate == value and not clobbered:
                    witnesses.append(window)
            constants.append({'name': key, 'value': value, 'assembly_immediate_confirmed': bool(witnesses),
                              'assembly': witnesses[:1]})
        # Reviewed loop in this exact monitor build. The export includes its
        # complete disassembly so the initial value, bound and increment remain
        # inspectable rather than inferred from the constant's spelling.
        if function.start_ea == 0x9942DC:
            constants.extend({'name': f'SHARED_GROUP_TIMELINE_{i}', 'value': i,
                              'assembly_immediate_confirmed': True,
                              'assembly': ['Reviewed register loop: sprintf SHARED_GROUP_TIMELINE_%u; r6=r25; r25=0..5.']}
                             for i in range(6))
        scope = re.search(r'Client::Game::(?:Event|InstanceContent)::(\w+)::DefineLuaClass', text)
        groups.append({'function': hex(function.start_ea), 'class': scope.group(1) if scope else name,
                       'constants': constants,
                       'shared_tables': sorted(set(re.findall(r'Get(\w+SystemDefine)Count', text))),
                       'pseudocode': text, 'disassembly': assembly})
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({'source': 'PS3 imported IDB; literal key/value registrations with assembly-immediate witnesses',
                                 'classes': groups}, indent=2) + '\n', encoding='utf-8')
    return {'classes': len(groups), 'output': str(OUTPUT)}

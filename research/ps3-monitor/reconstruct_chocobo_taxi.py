"""Reconstruct ChocoboTaxiStand's loop region from Lua 5.1 bytecode.

Outputs stay under build/. Does not execute game scripts. Promotion requires
an exact ordered instruction/constant/arity tree match to the original payload.
The raw decompiler outputs and original .luab remain untouched.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from decompile_monitor_scripts import PrototypeReader, compile_check, sha


RESOURCE = 'game_script/transport/ChocoboTaxiStand.luab'
INPUT_SHA256 = '011d0a510845a9bc9f1bd6df83af0ba95ce59b003d046e922f8e513dadc5b66f'

# Bytecode scene PCs 78..125. Nonpositive taxi ID returns to the MAIN menu;
# confirmation != true retries the TAXI menu. Preserve exact boolean tests,
# argument counts and the original gil/buddy elseif chain.
REPAIRED_LOOP = '''        else
          while true do
            local taxiId, terminusId, fare, timeRequired = self:ChocoboTaxiMenu(standId)
            if taxiId > 0 then
              local message = self:FormatString(self.TEXT_CHOCOBOTAXISTAND_00000_CONFIRM_Q_1, terminusId, fare, timeRequired)
              local confirm = self:YesNo(message, self.TEXT_CHOCOBOTAXISTAND_00000_CONFIRM_YES, self.TEXT_CHOCOBOTAXISTAND_00000_CONFIRM_NO, self.DEFAULT_YES)
              if confirm == true then
                if self:checkGil(pc, fare) == false then
                  target:Talk(pc, self, self.TEXT_CHOCOBOTAXISTAND_00000_SHORT_OF_GIL)
                  return 0
                elseif pc:IsBuddyExist() == true then
                  self:LogMessage(self.LOGMSG_CHOCOBO_SUMMON_FAIL_FOR_BUDDY)
                  return 0
                else
                  return taxiId
                end
              end
            else
              break
            end
          end
        end
'''


def reconstruct(raw):
    begin = '        while true do\n          else\n'
    end = '      elseif ret == 2 then\n'
    if raw.count(begin) != 1 or raw.count(end) != 1:
        raise ValueError('Unexpected raw decompiler loop layout; refusing an unreviewed repair')
    first, last = raw.index(begin), raw.index(end)
    if last <= first:
        raise ValueError('Unexpected loop marker order')
    return ('-- Manually reconstructed from PS3 Lua 5.1 bytecode, not original source.\n'
            '-- Verified by recompilation: ordered arity/instruction/constant trees match.\n'
            '-- Debug info and unused outer-wrapper flags/stack sizing differ.\n' +
            raw[:first] + REPAIRED_LOOP + raw[last:])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--named', type=Path, default=Path('build/ps3-lua-named'))
    parser.add_argument('--output', type=Path, default=Path('build/ps3-lua-decompiled'))
    parser.add_argument('--luac', type=Path, default=Path('build/lua51-reference/luac51.exe'))
    parser.add_argument('--no-promote', action='store_true', help='Verify without updating corpus recommendations')
    args = parser.parse_args()
    resource = Path(RESOURCE)
    original = (args.named / resource).read_bytes()
    if sha(original) != INPUT_SHA256:
        raise ValueError('Original payload identity mismatch')
    manifest_path = args.output / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    record = next(r for r in manifest['records'] if r['path'] == RESOURCE)
    raw_path = args.output / 'unluac-2015' / resource.with_suffix('.lua')
    if sha(raw_path.read_bytes()) != record['tools']['unluac-2015']['output_sha256']:
        raise ValueError('Raw decompiler output identity mismatch')
    source = args.output / 'manual' / resource.with_suffix('.lua')
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(reconstruct(raw_path.read_text(encoding='utf-8')), encoding='utf-8', newline='\n')
    reader = PrototypeReader(original)
    fingerprint = reader.fingerprint()
    bytecode = args.output / 'recompiled/manual' / resource.with_suffix('.luac')
    bytecode.parent.mkdir(parents=True, exist_ok=True)
    diagnostics = args.output / 'diagnostics/manual' / resource.with_suffix('.luac.stderr.txt')
    validation = compile_check(source, bytecode, diagnostics, args.luac.resolve(), fingerprint, reader.bodies, 30)
    if validation.get('syntax_status') != 'ok' or not validation.get('instruction_constant_tree_match'):
        raise ValueError(f'Reconstruction did not match the original tree: {validation}')
    compiled = PrototypeReader(bytecode.read_bytes())
    compiled.fingerprint()
    wrappers = [reader.tree, reader.tree[4][0], reader.tree[4][1]]
    if any((word & 63) == 37 for node in wrappers for word in node[2]):
        raise ValueError('Wrapper consumes varargs; flag normalization is not justified')
    differences = [{'prototype_preorder_index': i, 'original': a, 'recompiled': b}
                   for i, (a, b) in enumerate(zip(reader.metadata, compiled.metadata)) if a != b]
    # Only the synthetic root / CLI / common wrappers may differ. Scene and
    # helpers must retain all four execution-header bytes exactly.
    for difference in differences:
        a, b = difference['original'], difference['recompiled']
        if (difference['prototype_preorder_index'] not in (0, 1, 3) or
                a['nups'] != b['nups'] or a['params'] != b['params'] or
                a['vararg_flags'] not in (0, 2) or b['vararg_flags'] not in (0, 2) or
                a['maxstack'] > b['maxstack']):
            raise ValueError(f'Unreviewed execution-header difference: {difference}')
    result = {'path': RESOURCE, 'input_sha256': INPUT_SHA256, 'original_tree_sha256': fingerprint,
              'source': str(source), 'source_sha256': sha(source.read_bytes()), 'validation': validation,
              'execution_header_differences': differences,
              'header_difference_scope': 'Unused vararg capability in wrappers with no VARARG opcode; root stack 1 -> 2. Scene and helpers exact.',
              'basis': 'Manual recovery of scene PCs 78..125; other code retained from verified raw output.'}
    (args.output / 'manual/ChocoboTaxiStand-verification.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    if not args.no_promote:
        target = args.output / 'recommended' / resource.with_suffix('.lua')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        record['manual_reconstruction'] = result
        record['preferred_tool'] = 'manual'
        manifest['unresolved'] = [r['path'] for r in manifest['records'] if 'preferred_tool' not in r]
        manifest['counts']['preferred'] = dict(Counter(r.get('preferred_tool', 'none') for r in manifest['records']))
        manifest['manual_reconstructions'] = [result]
        # Keep the measured automatic tool results unchanged.
        summary_path = Path(__file__).resolve().parent / 'lua_decompilation.json'
        summary = {k: v for k, v in manifest.items() if k != 'records'}
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        summary_path.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

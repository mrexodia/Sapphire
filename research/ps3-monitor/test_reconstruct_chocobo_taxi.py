"""Reconstruction guards and compile-only regression tests; no Lua execution."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from decompile_monitor_scripts import PrototypeReader
from reconstruct_chocobo_taxi import reconstruct, RESOURCE, INPUT_SHA256, sha


ROOT = Path(__file__).resolve().parents[2]


class RepairGuards(unittest.TestCase):
    def test_unknown_layout_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unexpected'):
            reconstruct('not the expected decompiler output')

    def test_duplicate_markers_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unexpected'):
            reconstruct('        while true do\n          else\n' * 2 + '      elseif ret == 2 then\n')


class CompileOnlyRegression(unittest.TestCase):
    def setUp(self):
        self.original = ROOT / 'build/ps3-lua-named' / RESOURCE
        self.raw = ROOT / 'build/ps3-lua-decompiled/unluac-2015' / Path(RESOURCE).with_suffix('.lua')
        self.compiler = ROOT / 'build/lua51-reference/luac51.exe'
        if not all(p.is_file() for p in [self.original, self.raw, self.compiler]):
            self.skipTest('Requires the local extracted corpus and reference compiler')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def compile_tree(self, text):
        source = Path(self.temp.name) / 'reconstruction.lua'
        bytecode = source.with_suffix('.luac')
        source.write_text(text, encoding='utf-8')
        result = subprocess.run([str(self.compiler), '-s', '-o', str(bytecode), str(source)], capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        reader = PrototypeReader(bytecode.read_bytes())
        return reader, reader.fingerprint()

    def test_all_seven_ordered_prototypes_and_scene_header_match(self):
        original = self.original.read_bytes()
        self.assertEqual(sha(original), INPUT_SHA256)
        reader = PrototypeReader(original)
        expected = reader.fingerprint()
        compiled, actual = self.compile_tree(reconstruct(self.raw.read_text(encoding='utf-8')))
        self.assertEqual(actual, expected)
        self.assertEqual(compiled.stats, {'prototypes': 7, 'code_words': 234})
        self.assertEqual(compiled.bodies, reader.bodies)
        self.assertEqual(compiled.metadata[2], reader.metadata[2])  # scene's complete execution header
        self.assertEqual(compiled.metadata[4:], reader.metadata[4:])  # three helpers

    def test_confirmation_branch_mutation_detected(self):
        reader = PrototypeReader(self.original.read_bytes())
        expected = reader.fingerprint()
        text = reconstruct(self.raw.read_text(encoding='utf-8'))
        text = text.replace('if confirm == true then', 'if confirm ~= true then')
        _, actual = self.compile_tree(text)
        self.assertNotEqual(actual, expected)

    def test_wrong_menu_retry_mutation_detected(self):
        reader = PrototypeReader(self.original.read_bytes())
        expected = reader.fingerprint()
        text = reconstruct(self.raw.read_text(encoding='utf-8'))
        text = text.replace('              if confirm == true then',
                            '              if confirm ~= true then break end\n              if confirm == true then')
        _, actual = self.compile_tree(text)
        self.assertNotEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()

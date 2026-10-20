"""Synthetic tests for dictionary-based Lua filename recovery."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import recover_lua_paths as recovery


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = 'game_script/test/Example.luab'
        self.key = recovery.path_hashes(self.path)
        self.index = self.root / '0b0000.ps3.d.index'
        raw = bytearray(0x810)
        raw[:8] = b'SqPack\0\0'
        raw[8] = 1
        struct.pack_into('>II', raw, 0x408, 0x800, 16)
        struct.pack_into('>IIII', raw, 0x800, *self.key, 1, 0)
        self.index.write_bytes(raw)
        self.dictionary = self.root / 'paths.txt'
        self.dictionary.write_text(self.path + '\n', encoding='utf-8')
        self.extracted = self.root / 'extracted'
        self.extracted.mkdir()
        self.payload = b'print("example")\n'
        self.hash_name = f'{self.key[0]:08x}_{self.key[1]:08x}.lua'
        self.raw_file = self.extracted / self.hash_name
        self.raw_file.write_bytes(self.payload)
        self.record = {'directory_hash': f'{self.key[0]:08x}', 'filename_hash': f'{self.key[1]:08x}',
                       'logical_offset': 128, 'size': len(self.payload),
                       'sha256': hashlib.sha256(self.payload).hexdigest(), 'kind': 'source_text_candidate'}
        self.runtime = self.root / 'runtime.json'
        self.write_runtime()
        self.output = self.root / 'named'

    def write_runtime(self):
        self.runtime.write_text(json.dumps({'scripts': [self.record]}), encoding='utf-8')

    def run_recovery(self):
        return recovery.recover(self.dictionary, self.index, self.runtime, self.extracted, self.output)

    def test_two_hash_case_folded_match_and_byte_identical_copy(self):
        summary, rows = self.run_recovery()
        self.assertEqual(summary['status_counts'], {'unique_dictionary_hash_pair_match': 1})
        self.assertEqual(rows[0]['recovered_path'], self.path)
        self.assertEqual((self.output / self.path).read_bytes(), self.payload)
        self.assertEqual(self.raw_file.read_bytes(), self.payload)
        self.assertTrue((self.output / 'manifest.json').is_file())
        self.run_recovery()  # idempotent rerun

    def test_case_and_separator_aliases_do_not_create_ambiguity(self):
        alias = self.path.upper().replace('/', chr(92))
        self.dictionary.write_text(self.path + '\n' + alias + '\n', encoding='utf-8-sig')
        summary, rows = self.run_recovery()
        self.assertEqual(summary['matching_candidate_lines'], 2)
        self.assertEqual(len(rows[0]['dictionary_candidates']), 1)
        self.assertEqual(rows[0]['dictionary_candidates'][0]['lines'], [1, 2])

    def test_filename_alone_is_not_a_match(self):
        self.dictionary.write_text('game_script/wrong-directory/Example.luab\n', encoding='utf-8')
        summary, rows = self.run_recovery()
        self.assertEqual(summary['status_counts'], {'unmatched': 1})
        self.assertNotIn('recovered_path', rows[0])

    def test_ambiguous_hash_pair_is_not_silently_named(self):
        self.dictionary.write_text(self.path + '\ngame_script/test/Other.luab\n', encoding='utf-8')
        with patch.object(recovery, 'path_hashes', return_value=self.key):
            summary, rows = self.run_recovery()
        self.assertEqual(summary['status_counts'], {'ambiguous_hash_pair': 1})
        self.assertNotIn('recovered_path', rows[0])
        self.assertFalse((self.output / self.path).exists())

    def test_stale_ledger_offset_rejected(self):
        self.record['logical_offset'] = 129
        self.write_runtime()
        with self.assertRaisesRegex(ValueError, 'offset mismatch'):
            self.run_recovery()

    def test_payload_tampering_rejected(self):
        self.raw_file.write_bytes(b'not the extracted payload')
        with self.assertRaisesRegex(ValueError, 'payload hash mismatch'):
            self.run_recovery()

    def test_differing_existing_output_preserved(self):
        target = self.output / self.path
        target.parent.mkdir(parents=True)
        target.write_bytes(b'user changes')
        with self.assertRaisesRegex(ValueError, 'Refusing to overwrite'):
            self.run_recovery()
        self.assertEqual(target.read_bytes(), b'user changes')

    def test_unsafe_or_non_script_candidates_rejected(self):
        for text in ['game_script/../outside.luab', '/game_script/test/a.luab',
                     'game_script//test/a.luab', 'game_script/test/a:bad.luab', 'chara/test/a.luab']:
            self.assertIsNone(recovery.candidate(text))


if __name__ == '__main__':
    unittest.main()

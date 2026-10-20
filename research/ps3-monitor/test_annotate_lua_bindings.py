"""Synthetic comment-only tests. No Lua script execution."""
import json
from pathlib import Path
import tempfile
import unittest

from annotate_lua_bindings import annotate, lex, load_native, references, signature


def fact(name, value, kind='handler_define', source='Quest'):
    return {'name': name, 'value': value, 'source': source, 'row': 1,
            'ordinal': 0, 'language': 0, 'field': 'Define[0].Value',
            'kind': kind, 'schema_confidence': 'synthetic'}


class AnnotationTests(unittest.TestCase):
    def render(self, source, bindings=(), shared=None):
        result, info = annotate(source, Path('quest/000/Example.lua'), bindings, shared or {}, [])
        self.assertEqual(signature(lex(source)[0]), signature(lex(result)[0]))
        return result, info

    def test_used_and_unused(self):
        result, info = self.render('return self.USED\n', [fact('USED', 7), fact('UNUSED', 8)])
        self.assertIn('NOT DIRECTLY REFERENCED', result)
        self.assertIn('-- @ps3-bind USED = 7', result)
        self.assertNotIn('-- @ps3-bind UNUSED', result)
        self.assertEqual(info['handler_facts'], 2)

    def test_conflict_is_not_silently_resolved(self):
        result, info = self.render('return self.VALUE\n', [fact('VALUE', 1)],
                                   {'EventSystemDefine': [fact('VALUE', 2, 'shared_table', 'EventSystemDefine')]})
        self.assertEqual(info['conflicting_names'], ['VALUE'])
        self.assertIn('precedence unresolved', result)
        self.assertIn('VALUE = 1', result)
        self.assertIn('VALUE = 2', result)

    def test_quoted_and_dynamic_keys_other_receivers(self):
        tokens, _ = lex('return self["KNOWN"], self[key], actor.KNOWN, KNOWN\n')
        reads, _, _ = references(tokens, 'Example')
        self.assertEqual(reads[1], {'KNOWN'})

    def test_multiline_string_comment_safety(self):
        source = 'local x = [=[hello\nworld]=] .. self.VALUE -- self.IGNORED\n'
        result, info = self.render(source, [fact('VALUE', 5)])
        self.assertEqual(info['inline_comments'], 1)
        self.assertLess(result.index('-- @ps3-bind'), result.index('local x'))

    def test_assignments_not_partial_expressions(self):
        tokens, _ = lex('Example.A = 1 + 2\nExample.B = -4\nreturn self.B\n')
        _, writes, assignments = references(tokens, 'Example')
        self.assertEqual(writes, {'A', 'B'})
        self.assertEqual([(f['name'], f['value']) for f in assignments], [('B', -4)])

    def test_text_row_keys_are_not_binding_conflicts(self):
        source = 'return self.TEXT\n'
        result, info = annotate(source, Path('quest/000/Example.lua'), [fact('TEXT', 4)], {},
                                [fact('TEXT', 7, 'text_row_key')])
        self.assertIn('NOT stored DefineValue', result)
        self.assertEqual(info['conflicting_names'], [])

    def test_unconfirmed_native_literals_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'native.json'
            path.write_text(json.dumps({'classes': [{'class': 'LuaEventHandler', 'function': '0x9942dc',
                'constants': [{'name': 'YES', 'value': 0, 'assembly_immediate_confirmed': True},
                              {'name': 'NO', 'value': 1, 'assembly_immediate_confirmed': False}]}]}))
            groups = load_native(path)
            self.assertEqual([f['name'] for f in groups['Native:LuaEventHandler']], ['YES'])
            result, info = self.render('return self.YES, self.NO\n', shared=groups)
            self.assertIn('NO', info['unknown_direct_members'])
            self.assertIn('YES <- defines/EventSystem.lua native.LuaEventHandler', result)
            self.assertNotIn('YES = 0', result)

    def test_shared_unused_and_literals_are_not_displayed(self):
        result, info = self.render('Example.LOCAL = 10\nreturn self.USED, self.LOCAL\n',
            shared={'EventSystemDefine': [fact('USED', 5, 'shared_table', 'EventSystemDefine'),
                                          fact('UNUSED', 6, 'shared_table', 'EventSystemDefine')]})
        self.assertIn('USED = 5', result)
        self.assertNotIn('UNUSED', result)
        self.assertNotIn('Lua literal assignments', result)
        self.assertNotIn('LOCAL', info['unknown_direct_members'])
        self.assertEqual(info['facts'], 1)

    def test_reannotation_replaces_generated_comments(self):
        source = 'return self.USED\n'
        old, _ = self.render(source, [fact('USED', 7)])
        new, _ = self.render(old, [fact('USED', 8)])
        self.assertEqual(new.count('BEGIN PS3 BINDING'), 1)
        self.assertIn('USED = 8', new)
        self.assertNotIn('USED = 7', new)

    def test_generated_marker_inside_string_is_preserved(self):
        source = 'local x = [=[\n-- @ps3-bind KEEP_THIS_STRING\n]=]\nreturn self.USED\n'
        result, _ = self.render(source, [fact('USED', 7)])
        self.assertIn('-- @ps3-bind KEEP_THIS_STRING', result)


if __name__ == '__main__':
    unittest.main()

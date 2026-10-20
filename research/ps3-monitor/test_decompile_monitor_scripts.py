"""Tests for cross-profile Lua 5.1 decompilation fingerprinting (no execution)."""
import struct
import unittest

from decompile_monitor_scripts import PrototypeReader


def chunk(endian='big', size_t=4, word=0x0080001E, number=-0.0, source=b'@example.lua'):
    order = '>' if endian == 'big' else '<'
    def integer(value, size=4):
        return value.to_bytes(size, endian)
    def string(value):
        return integer(len(value) + 1, size_t) + value + b'\0'
    data = b'\x1bLua\x51\0' + bytes([endian == 'little', 4, size_t, 4, 8, 0])
    data += string(source) + integer(0) * 2 + bytes([0, 0, 2, 2])
    data += integer(1) + integer(word)
    data += integer(4)  # constants: nil, bool, double, raw byte string
    data += b'\0\1\1\3' + struct.pack(order + 'd', number)
    data += b'\4' + string(b'\xff\0\xe3\x81\x82')
    data += integer(0) * 4  # children, lines, locals, upvalue names
    return data


class FingerprintTests(unittest.TestCase):
    def test_big_endian_size_t4_matches_little_endian_size_t8(self):
        original = PrototypeReader(chunk())
        host = PrototypeReader(chunk('little', 8))
        self.assertEqual(original.fingerprint(), host.fingerprint())
        self.assertEqual(original.bodies, host.bodies)
        self.assertEqual(original.stats, {'prototypes': 1, 'code_words': 1})

    def test_debug_source_names_do_not_affect_fingerprint(self):
        self.assertEqual(PrototypeReader(chunk()).fingerprint(),
                         PrototypeReader(chunk(source=b'@different.lua')).fingerprint())

    def test_instruction_changes_detected(self):
        self.assertNotEqual(PrototypeReader(chunk()).fingerprint(),
                            PrototypeReader(chunk(word=0x0100001E)).fingerprint())

    def test_numeric_bit_patterns_preserved(self):
        self.assertNotEqual(PrototypeReader(chunk(number=-0.0)).fingerprint(),
                            PrototypeReader(chunk(number=0.0)).fingerprint())

    def test_truncation_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Truncated'):
            PrototypeReader(chunk()[:-1]).fingerprint()

    def test_trailing_bytes_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Trailing'):
            PrototypeReader(chunk() + b'extra').fingerprint()

    def test_other_lua_versions_rejected(self):
        altered = bytearray(chunk())
        altered[4] = 0x52
        with self.assertRaisesRegex(ValueError, 'Lua 5.1'):
            PrototypeReader(altered)


if __name__ == '__main__':
    unittest.main()

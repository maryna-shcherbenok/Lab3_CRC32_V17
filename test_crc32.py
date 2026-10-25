"""Автоматичні тести лабораторної роботи №3 (нова нумерація)."""
import random
import unittest
import zlib

from crc32_lab import (
    BYTE_REVERSE, DIRECT_TABLE, REFLECTED_TABLE, POLY, REFLECTED_POLY,
    bits_from_bytes, calculate_four, check_message, crc32_ieee_standard,
    crc_direct_serial, crc_long_division_reference,
    crc_reflected_serial, crc_direct_table, crc_reflected_table,
    prepare_message, reverse_bits,
)


class CRCTests(unittest.TestCase):
    def test_polynomials_and_tables(self):
        self.assertEqual(reverse_bits(POLY, 32), REFLECTED_POLY)
        self.assertEqual(len(DIRECT_TABLE), 256)
        self.assertEqual(len(REFLECTED_TABLE), 256)
        self.assertEqual(bytes(BYTE_REVERSE)[0b00010110], 0b01101000)

    def test_manual_example_4bit(self):
        # Посібник, рис. 4.1: 1101011011 / 10011 -> 1110.
        bits = tuple(int(x) for x in "1101011011")
        self.assertEqual(crc_long_division_reference(bits, 0b10011), 0b1110)

    def test_empty_and_zero_messages(self):
        for n in (0, 1, 8, 32, 1000):
            bits = (0,) * n
            self.assertEqual(crc_direct_serial(bits), 0)
            self.assertEqual(crc_reflected_serial(bits), 0)
            if n % 8 == 0:
                msg = prepare_message(bytes(n // 8))
                self.assertEqual(len(set(check_message(msg).values())), 1)

    def test_random_messages_four_algorithms_agree(self):
        rng = random.Random(1704)
        for n_bytes in (1, 2, 3, 4, 7, 8, 15, 16, 125, 250):
            for _ in range(12):
                case = prepare_message(rng.randbytes(n_bytes))
                results = check_message(case)
                self.assertEqual(len(set(results.values())), 1)
                self.assertEqual(len(case.reflected_payload), n_bytes)
                self.assertEqual(len(case.padded), n_bytes + 4)

    def test_non_byte_multiple_serial_vs_longdivision(self):
        rng = random.Random(17)
        for length in (1, 2, 7, 9, 11, 17, 31, 33, 101):
            bits = tuple(rng.randrange(2) for _ in range(length))
            expected = crc_long_division_reference(bits)
            self.assertEqual(crc_direct_serial(bits), expected)
            self.assertEqual(crc_reflected_serial(bits), expected)

    def test_single_bit_change_detected(self):
        data = random.Random(17).randbytes(125)
        original = check_message(prepare_message(data))
        expected = next(iter(original.values()))
        for index in (0, 1, 7, 8, 31, 32, 63, 64, 123, 555, 999):
            mutated = bytearray(data)
            mutated[index // 8] ^= 1 << (7 - index % 8)
            changed = check_message(prepare_message(mutated))
            self.assertNotEqual(next(iter(changed.values())), expected)

    def test_ieee_reference_123456789(self):
        self.assertEqual(crc32_ieee_standard(b"123456789"), 0xCBF43926)
        self.assertEqual(crc32_ieee_standard(b"123456789"), zlib.crc32(b"123456789"))

    def test_standard_vs_zlib_multiple_messages(self):
        rng = random.Random(2026)
        for n in (0, 1, 4, 8, 16, 125, 1000):
            data = rng.randbytes(n)
            self.assertEqual(crc32_ieee_standard(data), zlib.crc32(data))


if __name__ == "__main__":
    unittest.main(verbosity=2)

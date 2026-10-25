"""ЛР №3, варіант 17: CRC-32 (IEEE 802.3), чотири алгоритми.

Порівнювані 4 варіанти: init=0, xorout=0, однаковий логічний потік бітів.
Прямі алгоритми дописують 32 нулі; дзеркальні використовують неаугментований
алгоритм (без дописування нулів) з XOR вхідного біта та молодшого біта регістра.
Дзеркальні байти надходять LSB-first після відбиття кожного вхідного байта.
Результат дзеркальних алгоритмів відбивається в пряме представлення.

Окремо: повна стандартизована CRC-32/ISO-HDLC (IEEE 802.3),
init=0xFFFFFFFF, RefIn=True, RefOut=True, XorOut=0xFFFFFFFF.
"""

from __future__ import annotations

from collections.abc import Iterable
from itertools import chain, repeat
from dataclasses import dataclass
import zlib

WIDTH = 32
POLY = 0x04C11DB7
REFLECTED_POLY = 0xEDB88320
MASK = (1 << WIDTH) - 1
BYTE_REVERSE = bytes(int(f"{n:08b}"[::-1], 2) for n in range(256))


def reverse_bits(value: int, width: int) -> int:
    """Переставити біти в протилежному порядку (фіксована ширина)."""
    result = 0
    for _ in range(width):
        result = (result << 1) | (value & 1)
        value >>= 1
    return result


def bits_from_bytes(payload: bytes) -> tuple[int, ...]:
    """Перетворити байти на послідовність бітів MSB-first."""
    return tuple((byte >> pos) & 1 for byte in payload for pos in range(7, -1, -1))


def bytes_from_bits(bits: Iterable[int]) -> bytes:
    """Упакувати послідовність бітів у байти (MSB-first), довжина кратна 8."""
    bits = tuple(bits)
    if len(bits) % 8:
        raise ValueError("Для байтового алгоритму довжина повинна бути кратна 8")
    if any(bit not in (0, 1) for bit in bits):
        raise ValueError("Повідомлення може містити лише 0 та 1")
    out = bytearray()
    for i in range(0, len(bits), 8):
        byte = 0
        for bit in bits[i:i + 8]:
            byte = (byte << 1) | bit
        out.append(byte)
    return bytes(out)


def crc_direct_serial(bits: tuple[int, ...]) -> int:
    """Пряме побітове ділення: залишок (M(x)*x^32) mod G(x)."""
    reg = 0
    for bit in chain(bits, repeat(0, WIDTH)):
        leaving = (reg >> (WIDTH - 1)) & 1
        reg = ((reg << 1) | bit) & MASK
        if leaving:
            reg ^= POLY
    return reg


def crc_reflected_serial(bits: tuple[int, ...]) -> int:
    """Неаугментований дзеркальний алгоритм: без 32 нулів наприкінці.

    Логічні біти в тому ж порядку, що в прямому алгоритмі;
    кожний біт XOR-иться з молодшим бітом (зсув регістра вправо).
    Для цілих байтів це відповідає обробці відбитих байтів LSB-first.
    """
    reg = 0
    for bit in bits:
        feedback = (reg & 1) ^ bit
        reg >>= 1
        if feedback:
            reg ^= REFLECTED_POLY
    return reverse_bits(reg, WIDTH)


def make_direct_table() -> tuple[int, ...]:
    """Вплив виведеного за 8 тактів старшого байта регістра."""
    table = []
    for index in range(256):
        reg = index << (WIDTH - 8)
        for _ in range(8):
            leaving = (reg >> (WIDTH - 1)) & 1
            reg = (reg << 1) & MASK
            if leaving:
                reg ^= POLY
        table.append(reg)
    return tuple(table)


def make_reflected_table() -> tuple[int, ...]:
    """Вплив виведеного за 8 тактів молодшого байта регістра."""
    table = []
    for index in range(256):
        reg = index
        for _ in range(8):
            leaving = reg & 1
            reg >>= 1
            if leaving:
                reg ^= REFLECTED_POLY
        table.append(reg)
    return tuple(table)


DIRECT_TABLE = make_direct_table()
REFLECTED_TABLE = make_reflected_table()


def crc_direct_table(padded_data: bytes) -> int:
    """Прямий байтовий алгоритм: padded_data = payload + 4 нульові байти.

    Рекурентне співвідношення: R' = (R << 8 | b) XOR T[R >> 24].
    """
    reg = 0
    for byte in padded_data:
        index = reg >> 24
        reg = (((reg << 8) & MASK) | byte) ^ DIRECT_TABLE[index]
    return reg


def crc_reflected_table(reflected_payload: bytes) -> int:
    """Дзеркальний табличний алгоритм БЕЗ дописування нулів.

    На вхід отримуємо payload.translate(BYTE_REVERSE): байти відбиті,
    отже молодші біти кожного такого байта обробляються першими.
    Стандартна таблична формула: i = (R ^ b) & 0xFF;
                                R = (R >> 8) ^ Tref[i].
    Кінцеве відбиття переводить значення CRC у пряме представлення.
    """
    reg = 0
    for byte in reflected_payload:
        index = (reg ^ byte) & 0xFF
        reg = (reg >> 8) ^ REFLECTED_TABLE[index]
    return reverse_bits(reg, WIDTH)


def crc32_ieee_standard(payload: bytes) -> int:
    """CRC-32/ISO-HDLC: поліном 0x04C11DB7, init=FFFFFFFF, refin/refout=1, xorout=FFFFFFFF.

    Дані обробляються як послідовність байтів, починаючи з молодшого біта.
    Може бути перевірено незалежною реалізацією zlib.crc32.
    """
    reg = MASK
    for byte in payload:
        reg ^= byte
        for _ in range(8):
            if reg & 1:
                reg = (reg >> 1) ^ REFLECTED_POLY
            else:
                reg >>= 1
    return reg ^ MASK


@dataclass(frozen=True)
class PreparedMessage:
    bits: tuple[int, ...]
    payload: bytes
    padded: bytes
    reflected_payload: bytes


def prepare_message(payload: bytes) -> PreparedMessage:
    """У цій ЛР рівно 1000 біт = 125 байтів."""
    bits = bits_from_bytes(payload)
    padded = payload + b"\x00" * 4
    return PreparedMessage(bits, payload, padded,
                           payload.translate(BYTE_REVERSE))


def calculate_four(message: PreparedMessage) -> dict[str, int]:
    return {
        "Прямий послідовний": crc_direct_serial(message.bits),
        "Прямий табличний": crc_direct_table(message.padded),
        "Дзеркальний послідовний": crc_reflected_serial(message.bits),
        "Дзеркальний табличний": crc_reflected_table(message.reflected_payload),
    }


def crc_long_division_reference(bits: tuple[int, ...], polynomial: int = (1 << 32) | POLY) -> int:
    """Незалежна пряма перевірка GF(2)-ділення (допоміжна, не для бенчмарку)."""
    degree = polynomial.bit_length() - 1
    dividend = 0
    for bit in bits:
        dividend = (dividend << 1) | bit
    dividend <<= degree
    while dividend.bit_length() >= polynomial.bit_length():
        shift = dividend.bit_length() - polynomial.bit_length()
        dividend ^= polynomial << shift
    return dividend


def check_message(message: PreparedMessage) -> dict[str, int]:
    results = calculate_four(message)
    if len(set(results.values())) != 1:
        raise AssertionError(f"Алгоритми не збігаються: {results}")
    reference = crc_long_division_reference(message.bits)
    if next(iter(results.values())) != reference:
        raise AssertionError(f"Розбіжність із незалежним діленням: {results}, reference={reference}")
    return results


if __name__ == "__main__":
    import random

    rng = random.Random(17)
    data = rng.randbytes(125)
    case = prepare_message(data)
    results = check_message(case)
    print("ЛР №3 | Варіант 17 | CRC-32/IEEE 802.3")
    print(f"Генеруючий поліном: 0x{POLY:08X}; дзеркальний: 0x{REFLECTED_POLY:08X}")
    print(f"Випадкове повідомлення: {len(case.bits)} біт / {len(data)} байтів, seed=17")
    print(f"Біти, перші 64: {''.join(map(str, case.bits[:64]))}")
    for name, crc in results.items():
        print(f"{name:27s} -> 0x{crc:08X} ({crc:032b})")
    ieee = crc32_ieee_standard(data)
    print(f"Стандартний CRC-32/IEEE: 0x{ieee:08X} (zlib: 0x{zlib.crc32(data):08X})")
    print("Чотири реалізації дають однакову нормалізовану CRC.")

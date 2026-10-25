"""Вимірювання середнього часу обчислення CRC для варіанта 17.

Запуск: python benchmark.py --messages 1000 --repeats 10 --seed 17 --output results_final
Після вимірювання автоматично створює crc_timing.png у папці --output.
Вимірюємо лише обчислення CRC, НЕ підготовку повідомлень і таблиць.
"""
from __future__ import annotations
import argparse
import csv
import gc
import json
import random
import statistics
import time
from pathlib import Path

from crc32_lab import (
    calculate_four, check_message, crc32_ieee_standard,
    crc_direct_serial, crc_direct_table,
    crc_reflected_serial, crc_reflected_table, prepare_message,
)

ALGORITHMS = {
    "direct_serial": lambda x: crc_direct_serial(x.bits),
    "direct_table": lambda x: crc_direct_table(x.padded),
    "reflected_serial": lambda x: crc_reflected_serial(x.bits),
    "reflected_table": lambda x: crc_reflected_table(x.reflected_payload),
    "ieee_standard_optional": lambda x: crc32_ieee_standard(x.payload),
}

UKR = {
    "direct_serial": "Прямий послідовний",
    "direct_table": "Прямий табличний",
    "reflected_serial": "Дзеркальний послідовний",
    "reflected_table": "Дзеркальний табличний",
    "ieee_standard_optional": "IEEE (додатковий)",
}


def benchmark(num_messages: int, repeats: int, seed: int, out_dir: Path) -> dict:
    if num_messages < 1 or repeats < 1:
        raise ValueError("Параметри messages та repeats мають бути додатними")
    rng = random.Random(seed)
    prepared = [prepare_message(rng.randbytes(125)) for _ in range(num_messages)]
    for case in prepared:
        check_message(case)

    records = {name: [] for name in ALGORITHMS}
    # Прогрів кожної реалізації до вимірювань (компілятор/кеш CPU).
    for func in ALGORITHMS.values():
        for msg in prepared[:min(20, num_messages)]:
            func(msg)

    old_gc = gc.isenabled()
    gc.disable()
    checksums = {}
    try:
        for round_idx in range(repeats):
            names = list(ALGORITHMS)
            random.Random(seed + 10_000 + round_idx).shuffle(names)
            for name in names:
                func = ALGORITHMS[name]
                accumulator = 0
                start = time.perf_counter_ns()
                for case in prepared:
                    accumulator ^= func(case)
                elapsed_ns = time.perf_counter_ns() - start
                records[name].append(elapsed_ns / num_messages / 1000.0)
                # CRC-32 IEEE із іншою конфігурацією має іншу контрольну суму.
                if name != "ieee_standard_optional":
                    checksums[name] = accumulator
    finally:
        if old_gc:
            gc.enable()

    if len(set(checksums.values())) != 1:
        raise AssertionError(f"Невідповідність алгоритмів: {checksums}")

    means = {key: statistics.mean(values) for key, values in records.items()}
    results = {
        "message_bits": 1000,
        "message_bytes": 125,
        "number_of_messages": num_messages,
        "repeats": repeats,
        "total_crc_calls_per_algorithm": num_messages * repeats,
        "seed": seed,
        "unit": "microseconds per CRC",
        "notice": "Підготовка даних і 256-елементних таблиць не включені у вимірювання",
        "measurements_us": records,
        "mean_us": means,
        "std_dev_us": {k: statistics.stdev(v) if len(v) >= 2 else 0 for k, v in records.items()},
        "relative_speed_vs_direct_serial": {k: means["direct_serial"] / v for k, v in means.items()},
        "xor_checksum_of_all_normalized_methods": next(iter(checksums.values())),
    }
    out_dir.mkdir(exist_ok=True, parents=True)
    (out_dir / "benchmark_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    with (out_dir / "benchmark_results.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["algorithm", "description", "average_us", "stdev_us", "speedup", *[f"round_{i + 1}_us" for i in range(repeats)]])
        for k, timings in records.items():
            writer.writerow([k, UKR[k], round(means[k], 4), round(results["std_dev_us"][k], 4),
                             round(results["relative_speed_vs_direct_serial"][k], 4),
                             *[round(x, 4) for x in timings]])

    print(f"Вхід: {num_messages} повідомлень по 1000 біт, {repeats} повторів, seed={seed}")
    print("Обчислення таблиць, генерація даних і підготовка бітів НЕ входять у замір")
    print(f"{'Алгоритм':29s} {'Середнє, мкс':>14s} {'SD, мкс':>11s} {'Прискорення':>12s}")
    for k in ALGORITHMS:
        print(f"{UKR[k]:29s} {means[k]:14.3f} {results['std_dev_us'][k]:11.3f} {results['relative_speed_vs_direct_serial'][k]:12.2f}x")
    # Графік будується за тим самим JSON, без повторного експерименту.
    from plot_results import plot_benchmark_results
    try:
        png = plot_benchmark_results(out_dir / "benchmark_results.json")
    except RuntimeError as exc:
        print(f"Увага: CSV та JSON збережено, але графік не побудовано: {exc}")
    else:
        print(f"Графік PNG: {png}")
    print(f"CSV та JSON: {out_dir}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Бенчмарк лабораторної №3 CRC-32 / варіант 17")
    parser.add_argument("--messages", type=int, default=1000)
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--output", default="results")
    args = parser.parse_args()
    benchmark(args.messages, args.repeats, args.seed, Path(args.output))

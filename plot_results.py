"""Побудова графіка за фактичними вимірюваннями CRC-32.

Приклад: python plot_results.py --input results_final
Не виконує експеримент заново; використовує збережений JSON.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

NAMES = {
    "direct_serial": "Прямий послідовний",
    "direct_table": "Прямий табличний",
    "reflected_serial": "Дзеркальний послідовний",
    "reflected_table": "Дзеркальний табличний",
    "ieee_standard_optional": "IEEE (додатково)",
}


def plot_benchmark_results(json_path: Path, png_path: Path | None = None) -> Path:
    """Створює PNG із середнім часом і ±1 вибірковим SD усіх алгоритмів."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError(
            "Для створення графіка встанови matplotlib командою: "
            "python -m pip install matplotlib"
        ) from exc

    json_path = Path(json_path)
    with json_path.open(encoding="utf-8") as f:
        results = json.load(f)

    keys = list(NAMES)
    means = [float(results["mean_us"][k]) for k in keys]
    deviations = [float(results["std_dev_us"][k]) for k in keys]
    if any(x < 0 for x in means + deviations):
        raise ValueError("Час і стандартне відхилення не можуть бути від’ємними")
    output = Path(png_path) if png_path is not None else json_path.with_name("crc_timing.png")
    output.parent.mkdir(parents=True, exist_ok=True)

    plt.rcParams["font.family"] = "DejaVu Sans"
    fig, ax = plt.subplots(figsize=(11.4, 5.7))
    y = list(range(len(keys)))
    bars = ax.barh(y, means, xerr=deviations, capsize=3.5,
                   color="#2878B5", error_kw={"ecolor":"#383838", "elinewidth":1.2})
    ax.set_yticks(y, [NAMES[k] for k in keys])
    ax.invert_yaxis()
    ax.set_xlabel("Середній час на одне повідомлення з 1000 бітів, мкс")
    ax.set_title("CRC-32, варіант 17: порівняння часу")
    ax.grid(axis="x", alpha=0.23)
    ax.set_axisbelow(True)
    max_value = max((v + s) for v, s in zip(means, deviations))
    ax.set_xlim(0, max_value * 1.24 if max_value else 1)
    for bar, mean, sd in zip(bars, means, deviations):
        ax.text(mean + sd + max_value * 0.014, bar.get_y() + bar.get_height()/2,
                f"{mean:.3f}", va="center", fontsize=10)
    n = results.get("number_of_messages", "?")
    repeats = results.get("repeats", "?")
    fig.text(0.5, 0.015,
             f"{n} повідомлень, {repeats} повторів. Відрізки похибки: ±1 стандартне відхилення.",
             ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.045, 1, 1))
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Графік за збереженими результатами CRC-32")
    parser.add_argument("--input", default="results_final", help="Папка з benchmark_results.json")
    parser.add_argument("--output", default=None, help="Шлях до PNG (необов’язково)")
    args = parser.parse_args()
    file_path = Path(args.input)
    if file_path.is_dir() or file_path.suffix.lower() != ".json":
        file_path = file_path / "benchmark_results.json"
    target = plot_benchmark_results(file_path, Path(args.output) if args.output else None)
    print(f"Графік створено: {target}")

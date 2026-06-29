from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class _All2AllPoint:
    transfer_size: float
    runtime_cycles: float


def plot_all2all_stress(
    csv_path: Path,
    png_path: Path,
    pdf_path: Path | None = None,
    *,
    x_scale: str = "linear",
    y_scale: str = "linear",
    y_max: float | None = None,
) -> list[Path]:
    rows = _load_ok_rows(csv_path)
    if not rows:
        return []
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return []

    series = _all2all_series(rows)
    if not series:
        return []

    png_path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(7.0, 4.5))
    all_runtimes: list[float] = []
    for system, points in sorted(series.items()):
        x_values = [point.transfer_size for point in points]
        y_values = [point.runtime_cycles for point in points]
        all_runtimes.extend(y_values)
        plt.plot(x_values, y_values, marker="o", linewidth=1.8, label=system)
    plt.xlabel(_x_axis_label(rows))
    plt.ylabel("All-to-all runtime (cycles)")
    title_suffix = []
    if x_scale == "log":
        title_suffix.append("log x")
        plt.xscale("log")
    if y_scale == "log":
        title_suffix.append("log y")
        plt.yscale("log")
    title = "All-to-All Runtime vs Transfer Size"
    if title_suffix:
        title += " (" + ", ".join(title_suffix) + ")"
    plt.title(title)
    if y_max is not None:
        bottom, top = _y_limits_for_max(y_max, y_scale == "log", all_runtimes, plt.ylim()[0])
        plt.ylim(bottom=bottom, top=top)
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(png_path, dpi=180)
    written = [png_path]
    if pdf_path is not None:
        plt.savefig(pdf_path)
        written.append(pdf_path)
    plt.close()
    return written


def _load_ok_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        return []
    rows: list[dict[str, str]] = []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("status") != "ok":
                continue
            if not row.get("average_runtime_cycles"):
                continue
            rows.append(row)
    return rows


def _all2all_series(
    rows: list[dict[str, str]]
) -> dict[str, list[_All2AllPoint]]:
    buckets: dict[str, dict[float, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        transfer_size = _parse_float(row.get("transfer_size"))
        runtime = _parse_float(row.get("average_runtime_cycles"))
        if transfer_size is None or runtime is None:
            continue
        label = row.get("case") or row["system"]
        buckets[label][transfer_size].append(runtime)

    series: dict[str, list[_All2AllPoint]] = {}
    for label, values in buckets.items():
        series[label] = [
            _All2AllPoint(
                transfer_size=transfer_size,
                runtime_cycles=sum(samples) / len(samples),
            )
            for transfer_size, samples in sorted(values.items())
        ]
    return series


def _x_axis_label(rows: list[dict[str, str]]) -> str:
    units = {
        row.get("transfer_size_unit", "").strip()
        for row in rows
        if row.get("transfer_size_unit")
    }
    if len(units) == 1:
        return f"Transfer size per source-destination pair ({next(iter(units))})"
    if len(units) > 1:
        return "Transfer size per source-destination pair (mixed units)"
    return "Transfer size per source-destination pair"


def _y_limits_for_max(
    y_max: float,
    log_y: bool,
    runtimes: list[float],
    current_bottom: float,
) -> tuple[float, float]:
    if log_y:
        bottom = current_bottom
        if bottom <= 0:
            positive = [runtime for runtime in runtimes if runtime > 0]
            bottom = min(positive) / 1.5 if positive else y_max / 10.0
        if bottom >= y_max:
            bottom = y_max / 10.0
        return bottom, y_max
    return 0.0, y_max


def _parse_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None

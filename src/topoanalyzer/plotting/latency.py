from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class _LatencyPoint:
    injection_rate: float
    measured_injection_rate: float
    latency: float


def plot_latency_vs_injection(
    csv_path: Path,
    png_path: Path,
    pdf_path: Path | None = None,
    *,
    log_y: bool = False,
    y_max: float | None = None,
) -> list[Path]:
    rows = _load_ok_rows(csv_path)
    if not rows:
        return []
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return []

    series = _latency_series(rows)
    if not series:
        return []

    png_path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(7.0, 4.5))
    all_latencies: list[float] = []
    for system, points in sorted(series.items()):
        x_values = [point.measured_injection_rate for point in points]
        y_values = [point.latency for point in points]
        all_latencies.extend(y_values)
        plt.plot(x_values, y_values, marker="o", linewidth=1.8, label=system)
    plt.xlabel(_x_axis_label(rows))
    plt.ylabel("Average packet latency (cycles)")
    plt.title("Latency vs Injection Rate" + (" (log scale)" if log_y else ""))
    if log_y:
        plt.yscale("log")
    if y_max is not None:
        bottom, top = _y_limits_for_max(y_max, log_y, all_latencies, plt.ylim()[0])
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
            if not row.get("average_packet_latency") and not row.get("average_network_latency"):
                continue
            rows.append(row)
    return rows


def _latency_series(
    rows: list[dict[str, str]]
) -> dict[str, list[_LatencyPoint]]:
    buckets: dict[str, dict[float, list[tuple[float, float]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in rows:
        injection_rate = _parse_float(row.get("injection_rate"))
        if injection_rate is None:
            continue
        accepted_rate = _parse_float(row.get("accepted_rate"))
        if accepted_rate is None:
            continue
        packet_size = _parse_float(row.get("packet_size"))
        if packet_size is None:
            packet_size = 1.0
        if packet_size <= 0:
            continue
        latency = _parse_float(row.get("average_packet_latency"))
        if latency is None:
            latency = _parse_float(row.get("average_network_latency"))
        if latency is None:
            continue
        label = row.get("case") or row["system"]
        measured_injection_rate = accepted_rate * packet_size
        buckets[label][injection_rate].append((measured_injection_rate, latency))

    series: dict[str, list[_LatencyPoint]] = {}
    for label, values in buckets.items():
        series[label] = [
            _LatencyPoint(
                injection_rate=injection_rate,
                measured_injection_rate=sum(sample[0] for sample in samples)
                / len(samples),
                latency=sum(sample[1] for sample in samples) / len(samples),
            )
            for injection_rate, samples in sorted(values.items())
        ]
    return series


def _x_axis_label(rows: list[dict[str, str]]) -> str:
    units = {
        row.get("injection_rate_unit", "").strip()
        for row in rows
        if row.get("injection_rate_unit")
    }
    if len(units) == 1:
        return f"Injection rate ({next(iter(units))})"
    if len(units) > 1:
        return "Injection rate (mixed units)"
    return "Injection rate"


def _y_limits_for_max(
    y_max: float,
    log_y: bool,
    latencies: list[float],
    current_bottom: float,
) -> tuple[float, float]:
    if log_y:
        bottom = current_bottom
        if bottom <= 0:
            positive_latencies = [latency for latency in latencies if latency > 0]
            bottom = (
                min(positive_latencies) / 1.5
                if positive_latencies
                else y_max / 10.0
            )
        if bottom >= y_max:
            bottom = y_max / 10.0
        return bottom, y_max
    if current_bottom >= y_max:
        return 0.0, y_max
    return current_bottom, y_max


def _parse_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None

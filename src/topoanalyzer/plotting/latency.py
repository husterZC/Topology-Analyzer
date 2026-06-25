from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


def plot_latency_vs_injection(
    csv_path: Path,
    png_path: Path,
    pdf_path: Path | None = None,
    *,
    log_y: bool = False,
) -> list[Path]:
    rows = _load_ok_rows(csv_path)
    if not rows:
        return []
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return []

    series: dict[str, dict[float, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        latency = row.get("average_packet_latency") or row.get("average_network_latency")
        if latency is None:
            continue
        label = row.get("case") or row["system"]
        series[label][float(row["injection_rate"])].append(float(latency))
    if not series:
        return []

    png_path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(7.0, 4.5))
    for system, values in sorted(series.items()):
        x_values = sorted(values)
        y_values = [
            sum(values[inj]) / len(values[inj])
            for inj in x_values
        ]
        plt.plot(x_values, y_values, marker="o", linewidth=1.8, label=system)
    plt.xlabel(_x_axis_label(rows))
    plt.ylabel("Average packet latency (cycles)")
    plt.title("Latency vs Injection Rate" + (" (log scale)" if log_y else ""))
    if log_y:
        plt.yscale("log")
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

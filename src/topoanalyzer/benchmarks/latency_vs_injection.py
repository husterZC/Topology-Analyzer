from __future__ import annotations

import csv
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from topoanalyzer.benchmarks.progress import AnsiProgressBar
from topoanalyzer.model.system import System
from topoanalyzer.plotting.latency import plot_latency_vs_injection
from topoanalyzer.simulators.booksim.backend import BookSimBackend
from topoanalyzer.simulators.booksim.config import BookSimOptions
from topoanalyzer.simulators.booksim.parser import SimulationMetrics, parse_booksim_output


@dataclass(frozen=True)
class LatencyInjectionBenchmark:
    injection_rates: list[float]
    injection_rate_unit: str = "packets/node/cycle"
    packet_size: int = 1
    traffic: str = "uniform"
    warmup_cycles: int = 10000
    sample_cycles: int = 50000
    max_samples: int = 10
    repetitions: int = 1
    num_vcs: int = 2
    vc_buffer_size: int = 8
    router_latency: int = 1
    timeout_seconds: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "injection_rate_unit",
            _normalize_injection_rate_unit(self.injection_rate_unit),
        )
        if self.packet_size <= 0:
            raise ValueError(f"packet_size must be positive, got {self.packet_size}")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LatencyInjectionBenchmark":
        if data.get("type") not in (None, "latency_vs_injection_rate"):
            raise ValueError(f"unsupported benchmark type: {data.get('type')}")
        if "injection_rates" not in data:
            raise ValueError("benchmark requires injection_rates")
        packet_size = int(data.get("packet_size", 1))
        if packet_size <= 0:
            raise ValueError(f"packet_size must be positive, got {packet_size}")
        return cls(
            injection_rates=_parse_injection_rates(data["injection_rates"]),
            injection_rate_unit=_normalize_injection_rate_unit(
                str(data.get("injection_rate_unit", "packets/node/cycle"))
            ),
            packet_size=packet_size,
            traffic=str(data.get("traffic", "uniform")),
            warmup_cycles=int(data.get("warmup_cycles", 10000)),
            sample_cycles=int(data.get("sample_cycles", 50000)),
            max_samples=int(data.get("max_samples", 10)),
            repetitions=int(data.get("repetitions", 1)),
            num_vcs=int(data.get("num_vcs", 2)),
            vc_buffer_size=int(data.get("vc_buffer_size", 8)),
            router_latency=int(data.get("router_latency", 1)),
            timeout_seconds=(
                None
                if data.get("timeout_seconds") is None
                else int(data["timeout_seconds"])
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "latency_vs_injection_rate",
            "injection_rates": list(self.injection_rates),
            "injection_rate_unit": self.injection_rate_unit,
            "packet_size": self.packet_size,
            "traffic": self.traffic,
            "warmup_cycles": self.warmup_cycles,
            "sample_cycles": self.sample_cycles,
            "max_samples": self.max_samples,
            "repetitions": self.repetitions,
            "num_vcs": self.num_vcs,
            "vc_buffer_size": self.vc_buffer_size,
            "router_latency": self.router_latency,
            "timeout_seconds": self.timeout_seconds,
        }

    def with_overrides(self, overrides: dict[str, Any] | None) -> "LatencyInjectionBenchmark":
        if not overrides:
            return self
        data = self.to_dict()
        data.update(overrides)
        return self.from_dict(data)

    def booksim_options(self, injection_rate: float) -> BookSimOptions:
        return BookSimOptions(
            traffic=self.traffic,
            injection_rate=injection_rate,
            injection_rate_unit=self.injection_rate_unit,
            packet_size=self.packet_size,
            warmup_cycles=self.warmup_cycles,
            sample_cycles=self.sample_cycles,
            max_samples=self.max_samples,
            num_vcs=self.num_vcs,
            vc_buffer_size=self.vc_buffer_size,
            router_latency=self.router_latency,
        )


@dataclass(frozen=True)
class LatencyInjectionPlotSettings:
    y_scale: str = "linear"
    emit_companion_plot: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "LatencyInjectionPlotSettings":
        if not data:
            return cls()
        y_scale = str(data.get("y_scale", data.get("y_axis", "linear"))).lower()
        if y_scale in {"log", "log_y", "logarithmic"}:
            y_scale = "log"
        elif y_scale not in {"linear"}:
            raise ValueError(f"unsupported plot y_scale: {y_scale}")
        return cls(
            y_scale=y_scale,
            emit_companion_plot=bool(data.get("emit_companion_plot", True)),
        )


@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    system: System
    benchmark: LatencyInjectionBenchmark

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "system": self.system.name,
            "benchmark": self.benchmark.to_dict(),
        }


@dataclass(frozen=True)
class BenchmarkRecord:
    case: str
    system: str
    injection_rate: float
    repetition: int
    status: str
    injection_rate_unit: str = "packets/node/cycle"
    packet_size: int = 1
    average_packet_latency: float | None = None
    average_network_latency: float | None = None
    accepted_rate: float | None = None
    config_path: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "case": self.case,
            "system": self.system,
            "injection_rate": self.injection_rate,
            "injection_rate_unit": self.injection_rate_unit,
            "packet_size": self.packet_size,
            "repetition": self.repetition,
            "status": self.status,
            "average_packet_latency": self.average_packet_latency,
            "average_network_latency": self.average_network_latency,
            "accepted_rate": self.accepted_rate,
            "config_path": self.config_path,
            "error": self.error,
        }


class LatencyInjectionRunner:
    def __init__(self, backend: BookSimBackend | None = None) -> None:
        self.backend = backend or BookSimBackend()

    def run(
        self,
        systems: list[System] | list[BenchmarkCase],
        benchmark: LatencyInjectionBenchmark,
        output_root: Path,
        *,
        dry_run: bool = False,
        progress: bool = True,
        run_name: str | None = None,
        plot_settings: LatencyInjectionPlotSettings | None = None,
    ) -> Path:
        if not systems:
            raise ValueError("benchmark requires at least one system")
        cases = _normalize_cases(systems, benchmark)
        plot_settings = plot_settings or LatencyInjectionPlotSettings()
        output_dir = self._create_output_dir(output_root, run_name)
        self._write_system_artifacts([case.system for case in cases], output_dir)
        self._write_case_artifacts(cases, output_dir)

        records: list[BenchmarkRecord] = []
        total = sum(
            len(case.benchmark.injection_rates) * case.benchmark.repetitions
            for case in cases
        )
        bar = AnsiProgressBar(total=total, title="BookSim sweep", enabled=progress)
        try:
            for case in cases:
                for rate in case.benchmark.injection_rates:
                    for repetition in range(case.benchmark.repetitions):
                        label = f"{case.name} inj={rate:g} rep={repetition}"
                        record = self._run_one(
                            case,
                            rate,
                            repetition,
                            output_dir,
                            dry_run=dry_run,
                        )
                        records.append(record)
                        self._write_results(records, output_dir)
                        bar.advance(label)
        finally:
            bar.finish()

        plot_latency_vs_injection(
            output_dir / "results" / "latency_vs_injection.csv",
            output_dir / "plots" / "latency_vs_injection.png",
            output_dir / "plots" / "latency_vs_injection.pdf",
            log_y=plot_settings.y_scale == "log",
        )
        if plot_settings.emit_companion_plot:
            suffix = "linear" if plot_settings.y_scale == "log" else "log"
            plot_latency_vs_injection(
                output_dir / "results" / "latency_vs_injection.csv",
                output_dir / "plots" / f"latency_vs_injection_{suffix}.png",
                output_dir / "plots" / f"latency_vs_injection_{suffix}.pdf",
                log_y=suffix == "log",
            )
        return output_dir

    def _run_one(
        self,
        case: BenchmarkCase,
        rate: float,
        repetition: int,
        output_dir: Path,
        *,
        dry_run: bool,
    ) -> BenchmarkRecord:
        system = case.system
        benchmark = case.benchmark
        run_dir = (
            output_dir
            / "booksim"
            / case.name
            / f"inj_{rate:.6f}_rep_{repetition}"
        )
        options = benchmark.booksim_options(rate)
        try:
            config_path = self.backend.materialize(system, options, run_dir)
            if dry_run:
                return BenchmarkRecord(
                    case=case.name,
                    system=system.name,
                    injection_rate=rate,
                    repetition=repetition,
                    status="dry_run",
                    injection_rate_unit=benchmark.injection_rate_unit,
                    packet_size=benchmark.packet_size,
                    config_path=str(config_path),
                )
            raw = self.backend.run_config(
                config_path,
                timeout_seconds=benchmark.timeout_seconds,
            )
            metrics = parse_booksim_output(raw.stdout)
            status = "ok" if metrics.average_packet_latency is not None else "failed"
            return _record_from_metrics(
                case.name,
                system.name,
                rate,
                repetition,
                status,
                benchmark.injection_rate_unit,
                benchmark.packet_size,
                metrics,
                config_path,
                None if status == "ok" else raw.stderr or raw.stdout,
            )
        except Exception as exc:
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "error.txt").write_text(str(exc), encoding="utf-8")
            return BenchmarkRecord(
                case=case.name,
                system=system.name,
                injection_rate=rate,
                repetition=repetition,
                status="error",
                injection_rate_unit=benchmark.injection_rate_unit,
                packet_size=benchmark.packet_size,
                error=str(exc),
            )

    @staticmethod
    def _create_output_dir(output_root: Path, run_name: str | None) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = run_name or f"{timestamp}_latency_vs_injection"
        output_dir = output_root / name
        output_dir.mkdir(parents=True, exist_ok=False)
        (output_dir / "results").mkdir()
        (output_dir / "plots").mkdir()
        return output_dir

    @staticmethod
    def _write_system_artifacts(systems: list[System], output_dir: Path) -> None:
        root = output_dir / "systems"
        root.mkdir()
        written: set[str] = set()
        for system in systems:
            if system.name in written:
                continue
            written.add(system.name)
            system_dir = root / system.name
            system_dir.mkdir()
            _write_json(system_dir / "system.json", system.to_dict())
            _write_json(system_dir / "topology.json", system.graph.to_dict())
            _write_json(system_dir / "routing_table.json", system.routing_table.to_dict())
            _write_json(system_dir / "validation.json", system.validate().to_dict())

    @staticmethod
    def _write_case_artifacts(cases: list[BenchmarkCase], output_dir: Path) -> None:
        root = output_dir / "cases"
        root.mkdir()
        for case in cases:
            case_dir = root / case.name
            case_dir.mkdir()
            _write_json(case_dir / "case.json", case.to_dict())

    @staticmethod
    def _write_results(records: list[BenchmarkRecord], output_dir: Path) -> None:
        results_dir = output_dir / "results"
        json_path = results_dir / "latency_vs_injection.json"
        csv_path = results_dir / "latency_vs_injection.csv"
        _write_json(json_path, [record.to_dict() for record in records])
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=list(BenchmarkRecord("", "", 0.0, 0, "").to_dict().keys()),
            )
            writer.writeheader()
            for record in records:
                writer.writerow(record.to_dict())


def _record_from_metrics(
    case: str,
    system: str,
    rate: float,
    repetition: int,
    status: str,
    unit: str,
    packet_size: int,
    metrics: SimulationMetrics,
    config_path: Path,
    error: str | None,
) -> BenchmarkRecord:
    return BenchmarkRecord(
        case=case,
        system=system,
        injection_rate=rate,
        repetition=repetition,
        status=status,
        injection_rate_unit=unit,
        packet_size=packet_size,
        average_packet_latency=metrics.average_packet_latency,
        average_network_latency=metrics.average_network_latency,
        accepted_rate=metrics.accepted_rate,
        config_path=str(config_path),
        error=error,
    )


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _normalize_cases(
    systems: list[System] | list[BenchmarkCase],
    benchmark: LatencyInjectionBenchmark,
) -> list[BenchmarkCase]:
    cases: list[BenchmarkCase] = []
    for item in systems:
        if isinstance(item, BenchmarkCase):
            cases.append(item)
        else:
            cases.append(
                BenchmarkCase(
                    name=item.name,
                    system=item,
                    benchmark=benchmark,
                )
            )
    return cases


def _normalize_injection_rate_unit(unit: str) -> str:
    normalized = unit.strip().lower().replace("_", "/").replace(" ", "")
    aliases = {
        "flit/node/cycle": "flits/node/cycle",
        "flits/node/cycle": "flits/node/cycle",
        "flits/cycle/node": "flits/node/cycle",
        "flits": "flits/node/cycle",
        "flit": "flits/node/cycle",
        "packet/node/cycle": "packets/node/cycle",
        "packets/node/cycle": "packets/node/cycle",
        "packets/cycle/node": "packets/node/cycle",
        "packets": "packets/node/cycle",
        "packet": "packets/node/cycle",
    }
    if normalized not in aliases:
        raise ValueError(
            "unsupported injection_rate_unit: "
            f"{unit!r}; expected flits/node/cycle or packets/node/cycle"
        )
    return aliases[normalized]


_RANGE_PATTERN = re.compile(r"^range\((?P<args>.*)\)$")


def _parse_injection_rates(spec: Any) -> list[float]:
    if isinstance(spec, str):
        return _parse_injection_rate_range_string(spec)
    if isinstance(spec, dict):
        return _parse_injection_rate_range_mapping(spec)
    try:
        return _validate_injection_rates([float(value) for value in spec])
    except TypeError as exc:
        raise ValueError(
            "injection_rates must be a list or a range specification"
        ) from exc


def _parse_injection_rate_range_string(spec: str) -> list[float]:
    match = _RANGE_PATTERN.fullmatch(spec.strip())
    if not match:
        raise ValueError(
            "string injection_rates must use range(start, stop, step)"
        )
    args = [arg.strip() for arg in match.group("args").split(",")]
    if len(args) != 3 or any(not arg for arg in args):
        raise ValueError(
            "range injection_rates must provide start, stop, and step"
        )
    return _expand_injection_rate_range(
        start=_decimal_from_value(args[0], "start"),
        stop=_decimal_from_value(args[1], "stop"),
        step=_decimal_from_value(args[2], "step"),
        inclusive=False,
    )


def _parse_injection_rate_range_mapping(spec: dict[str, Any]) -> list[float]:
    inclusive = bool(spec.get("inclusive", False))
    if "range" in spec:
        range_spec = spec["range"]
        if not isinstance(range_spec, dict):
            raise ValueError("injection_rates.range must be a mapping")
        inclusive = bool(range_spec.get("inclusive", inclusive))
    else:
        range_spec = spec

    missing = [
        field for field in ("start", "stop", "step") if field not in range_spec
    ]
    if missing:
        raise ValueError(
            "range injection_rates missing field(s): " + ", ".join(missing)
        )
    return _expand_injection_rate_range(
        start=_decimal_from_value(range_spec["start"], "start"),
        stop=_decimal_from_value(range_spec["stop"], "stop"),
        step=_decimal_from_value(range_spec["step"], "step"),
        inclusive=inclusive,
    )


def _expand_injection_rate_range(
    *,
    start: Decimal,
    stop: Decimal,
    step: Decimal,
    inclusive: bool,
) -> list[float]:
    if step == 0:
        raise ValueError("range injection_rates step must be non-zero")
    values: list[float] = []
    current = start
    increasing = step > 0

    def in_bounds(value: Decimal) -> bool:
        if increasing:
            return value <= stop if inclusive else value < stop
        return value >= stop if inclusive else value > stop

    while in_bounds(current):
        values.append(float(current))
        if len(values) > 100000:
            raise ValueError("range injection_rates produced too many values")
        current += step

    return _validate_injection_rates(values)


def _decimal_from_value(value: Any, field: str) -> Decimal:
    try:
        decimal_value = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"range injection_rates {field} must be numeric") from exc
    if not decimal_value.is_finite():
        raise ValueError(f"range injection_rates {field} must be finite")
    return decimal_value


def _validate_injection_rates(rates: list[float]) -> list[float]:
    if not rates:
        raise ValueError("injection_rates must produce at least one value")
    for rate in rates:
        if not math.isfinite(rate):
            raise ValueError(f"injection_rates must be finite, got {rate}")
        if rate < 0:
            raise ValueError(f"injection_rates must be non-negative, got {rate}")
    return rates

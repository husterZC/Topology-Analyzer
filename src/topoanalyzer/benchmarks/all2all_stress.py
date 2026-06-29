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

from topoanalyzer.benchmarks.network_metrics import write_metrics_text
from topoanalyzer.benchmarks.progress import AnsiProgressBar
from topoanalyzer.model.system import System
from topoanalyzer.plotting.all2all import plot_all2all_stress
from topoanalyzer.simulators.booksim.anynet import AnyNetTableExporter
from topoanalyzer.simulators.booksim.backend import BookSimBackend
from topoanalyzer.simulators.booksim.config import BookSimOptions
from topoanalyzer.simulators.booksim.parser import SimulationMetrics, parse_booksim_output


@dataclass(frozen=True)
class All2AllStressBenchmark:
    transfer_sizes: list[int]
    transfer_size_unit: str = "flits"
    flit_size_bytes: int = 8
    injection_rate: float = 1.0
    injection_rate_unit: str = "packets/node/cycle"
    packet_size: int = 1
    packetization: str = "fixed_packet_size"
    traffic: str = "all2all"
    batch_count: int = 1
    repetitions: int = 1
    num_vcs: int = 2
    vc_buffer_size: int = 8
    router_latency: int = 1
    timeout_seconds: int | None = None
    stop_on_error: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "transfer_size_unit",
            _normalize_transfer_size_unit(self.transfer_size_unit),
        )
        object.__setattr__(
            self,
            "injection_rate_unit",
            _normalize_injection_rate_unit(self.injection_rate_unit),
        )
        object.__setattr__(
            self,
            "packetization",
            _normalize_packetization(self.packetization),
        )
        if self.flit_size_bytes <= 0:
            raise ValueError(
                f"flit_size_bytes must be positive, got {self.flit_size_bytes}"
            )
        if self.packet_size <= 0:
            raise ValueError(f"packet_size must be positive, got {self.packet_size}")
        if self.batch_count <= 0:
            raise ValueError(f"batch_count must be positive, got {self.batch_count}")
        if self.repetitions <= 0:
            raise ValueError(f"repetitions must be positive, got {self.repetitions}")
        if not math.isfinite(self.injection_rate) or self.injection_rate < 0:
            raise ValueError(
                f"injection_rate must be a finite non-negative value, got {self.injection_rate}"
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "All2AllStressBenchmark":
        if data.get("type") != "all2all_stress":
            raise ValueError(f"unsupported benchmark type: {data.get('type')}")
        if "transfer_sizes" not in data:
            raise ValueError("all2all_stress benchmark requires transfer_sizes")
        packetization = data.get(
            "packetization",
            data.get("packet_size_mode", "fixed_packet_size"),
        )
        packet_size_value = data.get("packet_size", 1)
        if _is_transfer_size_packet_size_alias(packet_size_value):
            packetization = "one_packet_per_pair"
            packet_size = 1
        else:
            packet_size = int(packet_size_value)
        return cls(
            transfer_sizes=_parse_transfer_sizes(data["transfer_sizes"]),
            transfer_size_unit=str(data.get("transfer_size_unit", "flits")),
            flit_size_bytes=int(data.get("flit_size_bytes", 8)),
            injection_rate=float(data.get("injection_rate", 1.0)),
            injection_rate_unit=str(data.get("injection_rate_unit", "packets/node/cycle")),
            packet_size=packet_size,
            packetization=str(packetization),
            traffic=str(data.get("traffic", "all2all")),
            batch_count=int(data.get("batch_count", 1)),
            repetitions=int(data.get("repetitions", 1)),
            num_vcs=int(data.get("num_vcs", 2)),
            vc_buffer_size=int(data.get("vc_buffer_size", 8)),
            router_latency=int(data.get("router_latency", 1)),
            timeout_seconds=(
                None
                if data.get("timeout_seconds") is None
                else int(data["timeout_seconds"])
            ),
            stop_on_error=bool(data.get("stop_on_error", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "all2all_stress",
            "transfer_sizes": list(self.transfer_sizes),
            "transfer_size_unit": self.transfer_size_unit,
            "flit_size_bytes": self.flit_size_bytes,
            "injection_rate": self.injection_rate,
            "injection_rate_unit": self.injection_rate_unit,
            "packet_size": self.packet_size,
            "packetization": self.packetization,
            "traffic": self.traffic,
            "batch_count": self.batch_count,
            "repetitions": self.repetitions,
            "num_vcs": self.num_vcs,
            "vc_buffer_size": self.vc_buffer_size,
            "router_latency": self.router_latency,
            "timeout_seconds": self.timeout_seconds,
            "stop_on_error": self.stop_on_error,
        }

    def with_overrides(self, overrides: dict[str, Any] | None) -> "All2AllStressBenchmark":
        if not overrides:
            return self
        data = self.to_dict()
        data.update(overrides)
        return self.from_dict(data)

    def transfer_size_flits(self, transfer_size: int) -> int:
        if self.transfer_size_unit == "flits":
            return transfer_size
        return math.ceil(transfer_size / self.flit_size_bytes)

    def packets_per_pair(self, transfer_size: int) -> int:
        return math.ceil(
            self.transfer_size_flits(transfer_size)
            / self.packet_size_for_transfer(transfer_size)
        )

    def packet_size_for_transfer(self, transfer_size: int) -> int:
        if self.packetization == "one_packet_per_pair":
            return self.transfer_size_flits(transfer_size)
        return self.packet_size

    def actual_transfer_size_flits(self, transfer_size: int) -> int:
        return (
            self.packets_per_pair(transfer_size)
            * self.packet_size_for_transfer(transfer_size)
        )

    def batch_size_packets_per_node(self, transfer_size: int, terminal_count: int) -> int:
        return self.packets_per_pair(transfer_size) * (terminal_count - 1)

    def booksim_options(self, transfer_size: int, terminal_count: int) -> BookSimOptions:
        return BookSimOptions(
            traffic=self.traffic,
            injection_rate=self.injection_rate,
            injection_rate_unit=self.injection_rate_unit,
            packet_size=self.packet_size_for_transfer(transfer_size),
            sim_type="batch",
            batch_size=self.batch_size_packets_per_node(transfer_size, terminal_count),
            batch_count=self.batch_count,
            num_vcs=self.num_vcs,
            vc_buffer_size=self.vc_buffer_size,
            router_latency=self.router_latency,
        )


@dataclass(frozen=True)
class All2AllStressPlotSettings:
    x_scale: str = "linear"
    y_scale: str = "linear"
    y_max: float | None = None
    emit_companion_plot: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "All2AllStressPlotSettings":
        if not data:
            return cls()
        x_scale = _normalize_axis_scale(str(data.get("x_scale", "linear")), "x_scale")
        y_scale = _normalize_axis_scale(
            str(data.get("y_scale", data.get("y_axis", "linear"))),
            "y_scale",
        )
        y_max = None
        if data.get("y_max") is not None:
            y_max = float(data["y_max"])
            if not math.isfinite(y_max) or y_max <= 0:
                raise ValueError(
                    f"plot y_max must be a positive finite value, got {y_max}"
                )
        return cls(
            x_scale=x_scale,
            y_scale=y_scale,
            y_max=y_max,
            emit_companion_plot=bool(data.get("emit_companion_plot", True)),
        )


@dataclass(frozen=True)
class All2AllBenchmarkCase:
    name: str
    system: System
    benchmark: All2AllStressBenchmark

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "system": self.system.name,
            "benchmark": self.benchmark.to_dict(),
        }


@dataclass(frozen=True)
class All2AllStressRecord:
    case: str
    system: str
    transfer_size: int
    transfer_size_unit: str
    packetization: str
    requested_transfer_size_flits: int
    actual_transfer_size_flits: int
    packet_size: int
    packets_per_pair: int
    batch_size_packets_per_node: int
    batch_count: int
    injection_rate: float
    injection_rate_unit: str
    repetition: int
    status: str
    average_runtime_cycles: float | None = None
    min_runtime_cycles: float | None = None
    max_runtime_cycles: float | None = None
    config_path: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "case": self.case,
            "system": self.system,
            "transfer_size": self.transfer_size,
            "transfer_size_unit": self.transfer_size_unit,
            "packetization": self.packetization,
            "requested_transfer_size_flits": self.requested_transfer_size_flits,
            "actual_transfer_size_flits": self.actual_transfer_size_flits,
            "packet_size": self.packet_size,
            "packets_per_pair": self.packets_per_pair,
            "batch_size_packets_per_node": self.batch_size_packets_per_node,
            "batch_count": self.batch_count,
            "injection_rate": self.injection_rate,
            "injection_rate_unit": self.injection_rate_unit,
            "repetition": self.repetition,
            "status": self.status,
            "average_runtime_cycles": self.average_runtime_cycles,
            "min_runtime_cycles": self.min_runtime_cycles,
            "max_runtime_cycles": self.max_runtime_cycles,
            "config_path": self.config_path,
            "error": self.error,
        }


class All2AllStressRunner:
    def __init__(self, backend: BookSimBackend | None = None) -> None:
        self.backend = backend or BookSimBackend()

    def run(
        self,
        cases: list[All2AllBenchmarkCase],
        benchmark: All2AllStressBenchmark,
        output_root: Path,
        *,
        dry_run: bool = False,
        progress: bool = True,
        run_name: str | None = None,
        plot_settings: All2AllStressPlotSettings | None = None,
    ) -> Path:
        if not cases:
            raise ValueError("all2all_stress benchmark requires at least one system")
        plot_settings = plot_settings or All2AllStressPlotSettings()
        output_dir = self._create_output_dir(output_root, run_name)
        self._write_system_artifacts([case.system for case in cases], output_dir)
        self._write_case_artifacts(cases, output_dir)
        self._write_network_metrics([case.system for case in cases], output_dir)

        records: list[All2AllStressRecord] = []
        total = sum(
            len(case.benchmark.transfer_sizes) * case.benchmark.repetitions
            for case in cases
        )
        bar = AnsiProgressBar(total=total, title="BookSim all2all", enabled=progress)
        try:
            for case in cases:
                terminal_count = _terminal_count(case.system)
                if terminal_count < 2:
                    raise ValueError(
                        f"all2all_stress requires at least two terminals, got {terminal_count}"
                    )
                for transfer_size in case.benchmark.transfer_sizes:
                    for repetition in range(case.benchmark.repetitions):
                        label = (
                            f"{case.name} size={transfer_size:g} "
                            f"rep={repetition}"
                        )
                        record = self._run_one(
                            case,
                            transfer_size,
                            terminal_count,
                            repetition,
                            output_dir,
                            dry_run=dry_run,
                        )
                        records.append(record)
                        self._write_results(records, output_dir)
                        bar.advance(label)
                        if case.benchmark.stop_on_error and record.status in {
                            "error",
                            "failed",
                        }:
                            raise RuntimeError(
                                "all2all_stress stopped after "
                                f"{record.status} in {case.name} "
                                f"at transfer_size={transfer_size:g}, "
                                f"repetition={repetition}: {record.error or ''}"
                            )
        finally:
            bar.finish()

        plot_all2all_stress(
            output_dir / "results" / "all2all_stress.csv",
            output_dir / "plots" / "all2all_stress.png",
            output_dir / "plots" / "all2all_stress.pdf",
            x_scale=plot_settings.x_scale,
            y_scale=plot_settings.y_scale,
            y_max=plot_settings.y_max,
        )
        if plot_settings.emit_companion_plot:
            companion_y = "linear" if plot_settings.y_scale == "log" else "log"
            plot_all2all_stress(
                output_dir / "results" / "all2all_stress.csv",
                output_dir / "plots" / f"all2all_stress_{companion_y}.png",
                output_dir / "plots" / f"all2all_stress_{companion_y}.pdf",
                x_scale=plot_settings.x_scale,
                y_scale=companion_y,
                y_max=plot_settings.y_max,
            )
        return output_dir

    def _run_one(
        self,
        case: All2AllBenchmarkCase,
        transfer_size: int,
        terminal_count: int,
        repetition: int,
        output_dir: Path,
        *,
        dry_run: bool,
    ) -> All2AllStressRecord:
        system = case.system
        benchmark = case.benchmark
        run_dir = (
            output_dir
            / "booksim"
            / case.name
            / f"size_{transfer_size}_rep_{repetition}"
        )
        try:
            options = benchmark.booksim_options(transfer_size, terminal_count)
            config_path = self.backend.materialize(system, options, run_dir)
            if dry_run:
                return _record_from_metrics(
                    case,
                    transfer_size,
                    terminal_count,
                    repetition,
                    "dry_run",
                    None,
                    config_path,
                    None,
                )
            raw = self.backend.run_config(
                config_path,
                timeout_seconds=benchmark.timeout_seconds,
            )
            metrics = parse_booksim_output(raw.stdout)
            status = "ok" if metrics.average_batch_duration is not None else "failed"
            return _record_from_metrics(
                case,
                transfer_size,
                terminal_count,
                repetition,
                status,
                metrics,
                config_path,
                None if status == "ok" else raw.stderr or raw.stdout,
            )
        except Exception as exc:
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "error.txt").write_text(str(exc), encoding="utf-8")
            return _record_from_metrics(
                case,
                transfer_size,
                terminal_count,
                repetition,
                "error",
                None,
                None,
                str(exc),
            )

    @staticmethod
    def _create_output_dir(output_root: Path, run_name: str | None) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = run_name or f"{timestamp}_all2all_stress"
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
    def _write_case_artifacts(
        cases: list[All2AllBenchmarkCase],
        output_dir: Path,
    ) -> None:
        root = output_dir / "cases"
        root.mkdir()
        for case in cases:
            case_dir = root / case.name
            case_dir.mkdir()
            _write_json(case_dir / "case.json", case.to_dict())

    @staticmethod
    def _write_network_metrics(systems: list[System], output_dir: Path) -> None:
        write_metrics_text(
            systems,
            output_dir / "results" / "metrics.txt",
            benchmark_type="all2all_stress",
        )

    @staticmethod
    def _write_results(records: list[All2AllStressRecord], output_dir: Path) -> None:
        results_dir = output_dir / "results"
        json_path = results_dir / "all2all_stress.json"
        csv_path = results_dir / "all2all_stress.csv"
        _write_json(json_path, [record.to_dict() for record in records])
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=list(
                    All2AllStressRecord(
                        "", "", 1, "flits", "", 1, 1, 1, 1, 1, 1, 1.0, "", 0, ""
                    ).to_dict().keys()
                ),
            )
            writer.writeheader()
            for record in records:
                writer.writerow(record.to_dict())


def _record_from_metrics(
    case: All2AllBenchmarkCase,
    transfer_size: int,
    terminal_count: int,
    repetition: int,
    status: str,
    metrics: SimulationMetrics | None,
    config_path: Path | None,
    error: str | None,
) -> All2AllStressRecord:
    benchmark = case.benchmark
    return All2AllStressRecord(
        case=case.name,
        system=case.system.name,
        transfer_size=transfer_size,
        transfer_size_unit=benchmark.transfer_size_unit,
        packetization=benchmark.packetization,
        requested_transfer_size_flits=benchmark.transfer_size_flits(transfer_size),
        actual_transfer_size_flits=benchmark.actual_transfer_size_flits(transfer_size),
        packet_size=benchmark.packet_size_for_transfer(transfer_size),
        packets_per_pair=benchmark.packets_per_pair(transfer_size),
        batch_size_packets_per_node=benchmark.batch_size_packets_per_node(
            transfer_size,
            terminal_count,
        ),
        batch_count=benchmark.batch_count,
        injection_rate=benchmark.injection_rate,
        injection_rate_unit=benchmark.injection_rate_unit,
        repetition=repetition,
        status=status,
        average_runtime_cycles=(
            None if metrics is None else metrics.average_batch_duration
        ),
        min_runtime_cycles=None if metrics is None else metrics.min_batch_duration,
        max_runtime_cycles=None if metrics is None else metrics.max_batch_duration,
        config_path=None if config_path is None else str(config_path),
        error=error,
    )


def _terminal_count(system: System) -> int:
    terminal_count = system.graph.metadata.get("terminal_count")
    if terminal_count is not None:
        return int(terminal_count)
    exporter = AnyNetTableExporter()
    router_ids = exporter.router_ids(system)
    return len(exporter.terminal_mappings(system, router_ids))


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


_RANGE_PATTERN = re.compile(r"^range\((?P<args>.*)\)$")


def _parse_transfer_sizes(spec: Any) -> list[int]:
    if isinstance(spec, str):
        return _parse_transfer_size_range_string(spec)
    if isinstance(spec, dict):
        return _parse_transfer_size_range_mapping(spec)
    try:
        return _validate_transfer_sizes([_int_from_value(value, "transfer_size") for value in spec])
    except TypeError as exc:
        raise ValueError(
            "transfer_sizes must be a list or a range specification"
        ) from exc


def _parse_transfer_size_range_string(spec: str) -> list[int]:
    match = _RANGE_PATTERN.fullmatch(spec.strip())
    if not match:
        raise ValueError("string transfer_sizes must use range(start, stop, step)")
    args = [arg.strip() for arg in match.group("args").split(",")]
    if len(args) != 3 or any(not arg for arg in args):
        raise ValueError("range transfer_sizes must provide start, stop, and step")
    return _expand_transfer_size_range(
        start=_decimal_from_value(args[0], "start"),
        stop=_decimal_from_value(args[1], "stop"),
        step=_decimal_from_value(args[2], "step"),
        inclusive=False,
    )


def _parse_transfer_size_range_mapping(spec: dict[str, Any]) -> list[int]:
    inclusive = bool(spec.get("inclusive", False))
    if "range" in spec:
        range_spec = spec["range"]
        if not isinstance(range_spec, dict):
            raise ValueError("transfer_sizes.range must be a mapping")
        inclusive = bool(range_spec.get("inclusive", inclusive))
    else:
        range_spec = spec

    missing = [
        field for field in ("start", "stop", "step") if field not in range_spec
    ]
    if missing:
        raise ValueError("range transfer_sizes missing field(s): " + ", ".join(missing))
    return _expand_transfer_size_range(
        start=_decimal_from_value(range_spec["start"], "start"),
        stop=_decimal_from_value(range_spec["stop"], "stop"),
        step=_decimal_from_value(range_spec["step"], "step"),
        inclusive=inclusive,
    )


def _expand_transfer_size_range(
    *,
    start: Decimal,
    stop: Decimal,
    step: Decimal,
    inclusive: bool,
) -> list[int]:
    if step == 0:
        raise ValueError("range transfer_sizes step must be non-zero")
    values: list[int] = []
    current = start
    increasing = step > 0

    def in_bounds(value: Decimal) -> bool:
        if increasing:
            return value <= stop if inclusive else value < stop
        return value >= stop if inclusive else value > stop

    while in_bounds(current):
        values.append(_int_from_decimal(current, "transfer_size"))
        if len(values) > 100000:
            raise ValueError("range transfer_sizes produced too many values")
        current += step

    return _validate_transfer_sizes(values)


def _decimal_from_value(value: Any, field: str) -> Decimal:
    try:
        decimal_value = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"range transfer_sizes {field} must be numeric") from exc
    if not decimal_value.is_finite():
        raise ValueError(f"range transfer_sizes {field} must be finite")
    return decimal_value


def _int_from_value(value: Any, field: str) -> int:
    return _int_from_decimal(_decimal_from_value(value, field), field)


def _int_from_decimal(value: Decimal, field: str) -> int:
    if value != value.to_integral_value():
        raise ValueError(f"{field} must be an integer value, got {value}")
    return int(value)


def _validate_transfer_sizes(sizes: list[int]) -> list[int]:
    if not sizes:
        raise ValueError("transfer_sizes must produce at least one value")
    for size in sizes:
        if size <= 0:
            raise ValueError(f"transfer_sizes must be positive, got {size}")
    return sizes


def _normalize_transfer_size_unit(unit: str) -> str:
    normalized = unit.strip().lower().replace("_", "").replace(" ", "")
    aliases = {
        "flit": "flits",
        "flits": "flits",
        "byte": "bytes",
        "bytes": "bytes",
        "b": "bytes",
    }
    if normalized not in aliases:
        raise ValueError(
            f"unsupported transfer_size_unit: {unit!r}; expected flits or bytes"
        )
    return aliases[normalized]


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


def _normalize_packetization(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "fixed": "fixed_packet_size",
        "fixed_packet": "fixed_packet_size",
        "fixed_packet_size": "fixed_packet_size",
        "fixed_packets": "fixed_packet_size",
        "one_packet": "one_packet_per_pair",
        "single_packet": "one_packet_per_pair",
        "one_packet_per_pair": "one_packet_per_pair",
        "single_packet_per_pair": "one_packet_per_pair",
        "transfer_size": "one_packet_per_pair",
        "packet_size_transfer_size": "one_packet_per_pair",
        "packet_size_equals_transfer_size": "one_packet_per_pair",
    }
    if normalized not in aliases:
        raise ValueError(
            "unsupported packetization: "
            f"{value!r}; expected fixed_packet_size or one_packet_per_pair"
        )
    return aliases[normalized]


def _is_transfer_size_packet_size_alias(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    return normalized in {
        "transfer_size",
        "transfer_size_flits",
        "packet_size_equals_transfer_size",
    }


def _normalize_axis_scale(value: str, field: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"log", "log_y", "logarithmic"}:
        return "log"
    if normalized == "linear":
        return "linear"
    raise ValueError(f"unsupported plot {field}: {value}")

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from topoanalyzer.benchmarks.latency_vs_injection import (
    BenchmarkCase,
    LatencyInjectionBenchmark,
    LatencyInjectionPlotSettings,
    LatencyInjectionRunner,
)
from topoanalyzer.experiments.factory import build_system_from_dict
from topoanalyzer.experiments.loader import load_document
from topoanalyzer.model.system import System
from topoanalyzer.simulators.booksim.backend import BookSimBackend
from topoanalyzer.viewer import export_viewer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="topoanalyzer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="validate a system file")
    validate_parser.add_argument("system_file", type=Path)

    build_parser = subparsers.add_parser("build", help="build system artifacts")
    build_parser.add_argument("system_file", type=Path)
    build_parser.add_argument("--output-dir", type=Path, default=Path("build/system"))

    view_parser = subparsers.add_parser("view", help="export an interactive 3D topology viewer")
    view_parser.add_argument("system_file", type=Path)
    view_parser.add_argument("--output-dir", type=Path)
    view_parser.add_argument("--title")

    benchmark_parser = subparsers.add_parser("benchmark", help="run a benchmark file")
    benchmark_parser.add_argument("benchmark_file", type=Path)
    benchmark_parser.add_argument("--dry-run", action="store_true")
    benchmark_parser.add_argument("--no-progress", action="store_true")
    benchmark_parser.add_argument("--run-name")
    benchmark_parser.add_argument("--booksim-executable")

    args = parser.parse_args(argv)
    if args.command == "validate":
        return _cmd_validate(args.system_file)
    if args.command == "build":
        return _cmd_build(args.system_file, args.output_dir)
    if args.command == "view":
        return _cmd_view(args.system_file, args.output_dir, args.title)
    if args.command == "benchmark":
        return _cmd_benchmark(
            args.benchmark_file,
            dry_run=args.dry_run,
            progress=not args.no_progress,
            run_name=args.run_name,
            booksim_executable=args.booksim_executable,
        )
    raise AssertionError(args.command)


def _cmd_validate(system_file: Path) -> int:
    system = _load_system(system_file)
    report = system.validate()
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0 if report.ok else 1


def _cmd_build(system_file: Path, output_dir: Path) -> int:
    system = _load_system(system_file)
    report = system.validate()
    report.raise_if_errors()
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "system.json", system.to_dict())
    _write_json(output_dir / "topology.json", system.graph.to_dict())
    _write_json(output_dir / "routing_table.json", system.routing_table.to_dict())
    _write_json(output_dir / "validation.json", report.to_dict())
    print(output_dir)
    return 0


def _cmd_view(system_file: Path, output_dir: Path | None, title: str | None) -> int:
    system = _load_system(system_file)
    report = system.validate()
    report.raise_if_errors()
    target_dir = output_dir or Path("views") / system.name
    output = export_viewer(system, target_dir, title=title)
    print(output / "index.html")
    return 0


def _cmd_benchmark(
    benchmark_file: Path,
    *,
    dry_run: bool,
    progress: bool,
    run_name: str | None,
    booksim_executable: str | None,
) -> int:
    spec = load_document(benchmark_file)
    benchmark = LatencyInjectionBenchmark.from_dict(spec["benchmark"])
    cases = _load_benchmark_cases(spec, benchmark_file.parent, benchmark)
    plot_settings = LatencyInjectionPlotSettings.from_dict(spec.get("plot"))
    booksim_spec = spec.get("booksim", {})
    executable = booksim_executable or str(booksim_spec.get("executable", "booksim"))
    backend_name = str(booksim_spec.get("backend", "anynet_table"))
    backend = BookSimBackend(executable=executable, backend=backend_name)
    output_root = Path(spec.get("output_dir", "runs"))
    runner = LatencyInjectionRunner(backend)
    output_dir = runner.run(
        cases,
        benchmark,
        output_root,
        dry_run=dry_run,
        progress=progress,
        run_name=run_name,
        plot_settings=plot_settings,
    )
    print(output_dir)
    return 0


def _load_system(path: Path) -> System:
    return build_system_from_dict(load_document(path))


def _load_benchmark_cases(
    spec: dict[str, Any],
    base_dir: Path,
    benchmark: LatencyInjectionBenchmark,
) -> list[BenchmarkCase]:
    cases: list[BenchmarkCase] = []
    for item in spec["systems"]:
        if isinstance(item, str):
            system = _load_system(base_dir / item)
            cases.append(BenchmarkCase(system.name, system, benchmark))
        elif isinstance(item, dict):
            system = _load_system_from_benchmark_entry(item, base_dir)
            case_name = str(
                item.get("case")
                or item.get("case_name")
                or item.get("label")
                or system.name
            )
            case_benchmark = benchmark.with_overrides(
                item.get("benchmark") or item.get("settings") or item.get("parameters")
            )
            cases.append(BenchmarkCase(case_name, system, case_benchmark))
        else:
            raise ValueError(f"invalid system entry: {item!r}")
    return cases


def _load_system_from_benchmark_entry(item: dict[str, Any], base_dir: Path) -> System:
    path = item.get("path") or item.get("system_file")
    if path is not None:
        return _load_system(base_dir / str(path))
    system_spec = item.get("system")
    if isinstance(system_spec, str):
        return _load_system(base_dir / system_spec)
    if isinstance(system_spec, dict):
        return build_system_from_dict(system_spec)
    inline_keys = {"name", "topology", "links", "routing"}
    if inline_keys.issubset(item):
        return build_system_from_dict(
            {key: value for key, value in item.items() if key in inline_keys}
        )
    raise ValueError(f"benchmark system entry needs `path`, `system`, or inline system fields: {item!r}")


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())

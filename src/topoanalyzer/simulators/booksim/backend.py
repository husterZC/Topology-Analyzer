from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from topoanalyzer.model.system import System
from topoanalyzer.simulators.booksim.anynet import AnyNetTableExporter
from topoanalyzer.simulators.booksim.config import BookSimConfigGenerator, BookSimOptions


@dataclass(frozen=True)
class BookSimRawResult:
    returncode: int
    stdout: str
    stderr: str
    config_path: Path


class BookSimBackend:
    def __init__(self, executable: str = "booksim", backend: str = "anynet_table") -> None:
        self.executable = executable
        self.config_generator = BookSimConfigGenerator(backend=backend)
        self.anynet_exporter = AnyNetTableExporter()

    def materialize(
        self,
        system: System,
        options: BookSimOptions,
        run_dir: Path,
    ) -> Path:
        run_dir.mkdir(parents=True, exist_ok=True)
        if self.config_generator.resolved_backend(system) == "anynet_table":
            _validate_vc_count(system, options)
            artifacts = self.anynet_exporter.materialize(system, run_dir)
            config = self.config_generator.generate(
                system,
                options,
                network_file=artifacts.network_file.resolve(),
                route_table_file=artifacts.route_table_file.resolve(),
            )
        else:
            config = self.config_generator.generate(system, options)
        config_path = run_dir / "booksim.cfg"
        config_path.write_text(config, encoding="utf-8")
        return config_path

    def run_config(
        self,
        config_path: Path,
        timeout_seconds: int | None = None,
    ) -> BookSimRawResult:
        completed = subprocess.run(
            [self.executable, str(config_path)],
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
        stdout_path = config_path.parent / "stdout.txt"
        stderr_path = config_path.parent / "stderr.txt"
        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        return BookSimRawResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            config_path=config_path,
        )

    def run(
        self,
        system: System,
        options: BookSimOptions,
        run_dir: Path,
        timeout_seconds: int | None = None,
    ) -> BookSimRawResult:
        config_path = self.materialize(system, options, run_dir)
        return self.run_config(config_path, timeout_seconds=timeout_seconds)


def _validate_vc_count(system: System, options: BookSimOptions) -> None:
    max_vc = max(
        [
            *system.routing_table.route_vcs.values(),
            *_terminal_route_vcs(system),
        ],
        default=0,
    )
    if max_vc >= options.num_vcs:
        raise ValueError(
            f"routing table {system.routing_table.name!r} uses VC {max_vc}, "
            f"but benchmark num_vcs is {options.num_vcs}"
        )


def _terminal_route_vcs(system: System) -> list[int]:
    terminal_routes = system.routing_table.metadata.get("terminal_next_hops")
    if not isinstance(terminal_routes, dict):
        return []
    vcs: list[int] = []
    for current_routes in terminal_routes.values():
        if not isinstance(current_routes, dict):
            continue
        for route in current_routes.values():
            if isinstance(route, dict):
                vcs.append(int(route.get("vc", 0)))
    return vcs

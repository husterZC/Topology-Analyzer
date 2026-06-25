from __future__ import annotations

import shutil
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
        self.executable = _resolve_executable(executable)
        self.config_generator = BookSimConfigGenerator(backend=backend)
        self.anynet_exporter = AnyNetTableExporter()

    def materialize(
        self,
        system: System,
        options: BookSimOptions,
        run_dir: Path,
    ) -> Path:
        run_dir.mkdir(parents=True, exist_ok=True)
        backend = self.config_generator.resolved_backend(system)
        if backend == "anynet_table":
            _validate_vc_count(system, options)
            artifacts = self.anynet_exporter.materialize(system, run_dir)
            config = self.config_generator.generate(
                system,
                options,
                network_file=artifacts.network_file.resolve(),
                route_table_file=artifacts.route_table_file.resolve(),
            )
        elif backend == "ubmesh_apr_runtime":
            artifacts = self.anynet_exporter.materialize_network(system, run_dir)
            config = self.config_generator.generate(
                system,
                options,
                network_file=artifacts.network_file.resolve(),
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
        try:
            completed = subprocess.run(
                [self.executable, str(config_path)],
                check=False,
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
            )
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"BookSim executable {self.executable!r} was not found. "
                "Run `make bootstrap`, activate `.venv`, set `booksim.executable`, "
                "or pass `--booksim-executable /path/to/booksim`."
            ) from exc
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
            *(
                hop_vc
                for hop_vcs in system.routing_table.path_vcs.values()
                for hop_vc in hop_vcs
            ),
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


def _resolve_executable(executable: str) -> str:
    if _has_path_separator(executable):
        return executable
    resolved = shutil.which(executable)
    if resolved is not None:
        return resolved
    if executable != "booksim":
        return executable

    repo_root = Path(__file__).resolve().parents[4]
    candidates = [
        Path.cwd() / ".venv" / "bin" / "booksim",
        Path.cwd() / "bin" / "booksim",
        repo_root / ".venv" / "bin" / "booksim",
        repo_root / "bin" / "booksim",
        repo_root / "external" / "booksim2" / "src" / "booksim",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return executable


def _has_path_separator(value: str) -> bool:
    return "/" in value or "\\" in value

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from topoanalyzer.model.system import System
from topoanalyzer.simulators.booksim.config import BookSimConfigGenerator, BookSimOptions


@dataclass(frozen=True)
class BookSimRawResult:
    returncode: int
    stdout: str
    stderr: str
    config_path: Path


class BookSimBackend:
    def __init__(self, executable: str = "booksim") -> None:
        self.executable = executable
        self.config_generator = BookSimConfigGenerator()

    def materialize(
        self,
        system: System,
        options: BookSimOptions,
        run_dir: Path,
    ) -> Path:
        run_dir.mkdir(parents=True, exist_ok=True)
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

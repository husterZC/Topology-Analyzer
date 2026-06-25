from __future__ import annotations

import sys
import time


class AnsiProgressBar:
    def __init__(self, total: int, title: str = "progress", enabled: bool = True) -> None:
        self.total = max(total, 1)
        self.title = title
        self.enabled = enabled
        self.current = 0
        self.started_at = time.monotonic()

    def advance(self, label: str = "") -> None:
        self.current += 1
        if not self.enabled:
            return
        elapsed = time.monotonic() - self.started_at
        fraction = min(self.current / self.total, 1.0)
        width = 32
        filled = int(width * fraction)
        bar = "\033[36m" + "█" * filled + "\033[90m" + "░" * (width - filled) + "\033[0m"
        percent = f"{fraction * 100:5.1f}%"
        sys.stderr.write(
            f"\r\033[1m{self.title}\033[0m {bar} {self.current}/{self.total} "
            f"{percent} {elapsed:6.1f}s {label[:48]:48}"
        )
        sys.stderr.flush()

    def finish(self) -> None:
        if self.enabled:
            sys.stderr.write("\n")
            sys.stderr.flush()

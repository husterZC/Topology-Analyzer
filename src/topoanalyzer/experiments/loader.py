from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_document(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    if source.suffix.lower() == ".json":
        return json.loads(text)
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError(
            "PyYAML is required for YAML experiment files. Install the project with "
            "`pip install -e .` or use JSON input."
        ) from exc
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"expected mapping at top level: {source}")
    return data

from __future__ import annotations

import json
import shutil
from pathlib import Path

from topoanalyzer.model.system import System
from topoanalyzer.viewer.scene import build_scene


def export_viewer(system: System, output_dir: Path, *, title: str | None = None) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    scene = build_scene(system)
    scene_path = output_dir / "scene.json"
    scene_json = json.dumps(scene, indent=2, sort_keys=True)
    scene_path.write_text(scene_json + "\n", encoding="utf-8")

    assets = _asset_dir()
    shutil.copyfile(assets / "viewer.js", output_dir / "viewer.js")
    shutil.copyfile(assets / "style.css", output_dir / "style.css")
    shutil.copytree(assets / "vendor", output_dir / "vendor", dirs_exist_ok=True)
    html = (assets / "index.html").read_text(encoding="utf-8")
    html = html.replace("__VIEWER_TITLE__", title or system.name)
    html = html.replace("__SCENE_JSON__", _script_safe_json(scene))
    (output_dir / "index.html").write_text(html, encoding="utf-8")
    return output_dir


def _asset_dir() -> Path:
    repo_root = Path(__file__).resolve().parents[3]
    path = repo_root / "tools" / "topology_viewer"
    if not path.exists():
        raise FileNotFoundError(f"viewer assets not found: {path}")
    return path


def _script_safe_json(scene: dict) -> str:
    return json.dumps(scene, sort_keys=True).replace("</", "<\\/")

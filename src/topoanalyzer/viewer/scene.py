from __future__ import annotations

from dataclasses import asdict
from typing import Any

from topoanalyzer.model.system import System
from topoanalyzer.viewer.layouts import strategy_for


def build_scene(system: System) -> dict[str, Any]:
    graph = system.graph
    layout = strategy_for(graph)
    routers = sorted(
        graph.routers(),
        key=lambda node: (
            int(node.metadata.get("booksim_order", 0)),
            node.id,
        ),
    )
    node_ids = {node.id for node in routers}
    nodes = []
    positions = {}
    node_groups: dict[str, str] = {}
    link_groups: dict[str, str] = {}

    for node in routers:
        position = layout.position(node, graph)
        positions[node.id] = position
        style = layout.node_style(node, graph)
        node_groups[style.group] = style.color
        nodes.append(
            {
                "id": node.id,
                "label": _node_label(node.id, node.metadata),
                "kind": node.kind,
                "group": style.group,
                "position": list(position),
                "style": {
                    "color": style.color,
                    "size": style.size,
                },
                "metadata": _jsonable(node.metadata),
            }
        )

    links = []
    for link in graph.links:
        if link.src not in node_ids or link.dst not in node_ids:
            continue
        style = layout.link_style(link, graph)
        link_groups[style.group] = style.color
        links.append(
            {
                "src": link.src,
                "dst": link.dst,
                "class": str(link.metadata.get("class", style.group)),
                "group": style.group,
                "sourcePosition": list(positions[link.src]),
                "targetPosition": list(positions[link.dst]),
                "style": {
                    "color": style.color,
                    "opacity": style.opacity,
                    "width": style.width,
                    "curveHeight": style.curve_height,
                },
                "metadata": _jsonable(link.metadata),
            }
        )

    bounds = _bounds([tuple(node["position"]) for node in nodes])
    return {
        "schema": "topoanalyzer.viewer.scene.v1",
        "system": {
            "name": system.name,
            "topology_type": system.topology_type,
            "topology_params": _jsonable(system.topology_params),
            "routing": system.routing_table.name,
            "router_count": len(routers),
            "terminal_count": int(graph.metadata.get("terminal_count", len(routers))),
            "link_count": len(links),
        },
        "layout": {
            "name": layout.name,
            "description": layout.description,
            "cameraPresets": [asdict(preset) for preset in layout.camera_presets(graph)],
            "bounds": bounds,
        },
        "nodes": nodes,
        "links": links,
        "legend": {
            "nodeGroups": [
                {"name": name, "color": color}
                for name, color in sorted(node_groups.items())
            ],
            "linkGroups": [
                {"name": name, "color": color}
                for name, color in sorted(link_groups.items())
            ],
        },
        "metadata": _jsonable(graph.metadata),
    }


def _node_label(node_id: str, metadata: dict[str, Any]) -> str:
    label = metadata.get("label")
    if isinstance(label, (list, tuple)):
        return ".".join(str(item) for item in label)
    if label is not None:
        return str(label)
    bits = metadata.get("bits")
    if isinstance(bits, list):
        return "".join(str(bit) for bit in reversed(bits))
    return node_id


def _bounds(points: list[tuple[float, float, float]]) -> dict[str, list[float]]:
    if not points:
        return {"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0], "center": [0.0, 0.0, 0.0]}
    mins = [min(point[idx] for point in points) for idx in range(3)]
    maxs = [max(point[idx] for point in points) for idx in range(3)]
    center = [(mins[idx] + maxs[idx]) / 2.0 for idx in range(3)]
    return {"min": mins, "max": maxs, "center": center}


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)

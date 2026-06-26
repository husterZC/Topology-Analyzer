from __future__ import annotations

from dataclasses import asdict
from math import cos, pi, sin
from typing import Any

from topoanalyzer.model.graph import Node, TopologyGraph
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
    router_ids = {node.id for node in routers}
    nodes = []
    positions: dict[str, tuple[float, float, float]] = {}
    node_groups: dict[str, str] = {}
    link_groups: dict[str, str] = {}

    for router in routers:
        position = layout.position(router, graph)
        positions[router.id] = position
        style = layout.node_style(router, graph)
        node_groups[style.group] = style.color
        nodes.append(
            {
                "id": router.id,
                "label": _node_label(router.id, router.metadata),
                "kind": router.kind,
                "group": style.group,
                "position": list(position),
                "style": {
                    "color": style.color,
                    "size": style.size,
                    "shape": "sphere",
                },
                "metadata": _jsonable(router.metadata),
            }
        )

    terminal_nodes = _terminal_nodes(graph, routers, positions)
    for node in terminal_nodes:
        position = tuple(node["position"])
        positions[str(node["id"])] = position
        node_groups[str(node["group"])] = str(node["style"]["color"])
        nodes.append(node)

    links = []
    for link in graph.links:
        if link.src not in router_ids or link.dst not in router_ids:
            continue
        style = layout.link_style(link, graph)
        link_groups[style.group] = style.color
        links.append(
            {
                "id": f"{link.src}->{link.dst}:{len(links)}",
                "kind": "network",
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

    for link in _terminal_attachment_links(terminal_nodes, positions):
        link_groups[link["group"]] = link["style"]["color"]
        links.append(link)

    bounds = _bounds([tuple(node["position"]) for node in nodes])
    return {
        "schema": "topoanalyzer.viewer.scene.v2",
        "system": {
            "name": system.name,
            "topology_type": system.topology_type,
            "topology_params": _jsonable(system.topology_params),
            "routing": system.routing_table.name,
            "router_count": len(routers),
            "terminal_count": len(terminal_nodes),
            "display_node_count": len(nodes),
            "link_count": sum(1 for link in links if link["kind"] == "network"),
            "display_link_count": len(links),
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


def _terminal_nodes(
    graph: TopologyGraph,
    routers: list[Node],
    router_positions: dict[str, tuple[float, float, float]],
) -> list[dict[str, Any]]:
    raw_nodes = _raw_terminal_nodes(graph, routers)
    per_router_counts: dict[str, int] = {}
    for node in raw_nodes:
        router_id = node.get("attached_router")
        if router_id is not None:
            router_key = str(router_id)
            per_router_counts[router_key] = (
                per_router_counts.get(router_key, 0) + 1
            )

    per_router_seen: dict[str, int] = {}
    terminal_nodes = []
    for index, node in enumerate(raw_nodes):
        router_id = node.get("attached_router")
        router_key = str(router_id) if router_id is not None else ""
        local_index = per_router_seen.get(router_key, 0)
        per_router_seen[router_key] = local_index + 1
        local_count = per_router_counts.get(router_key, 1)
        if router_key in router_positions:
            position = _terminal_position(
                router_positions[router_key],
                local_index,
                local_count,
            )
        else:
            position = _fallback_terminal_position(index)
        metadata = dict(node.get("metadata", {}))
        metadata.update(
            {
                "attached_router": router_id,
                "terminal_index": node.get("terminal_index", index),
                "local_index": local_index,
            }
        )
        terminal_nodes.append(
            {
                "id": str(node["id"]),
                "label": str(node["label"]),
                "kind": "terminal",
                "group": "terminal nodes",
                "position": list(position),
                "style": {
                    "color": "#334155",
                    "size": 0.09,
                    "shape": "cuboid",
                    "scale": [1.45, 0.72, 1.45],
                },
                "metadata": _jsonable(metadata),
            }
        )
    return terminal_nodes


def _raw_terminal_nodes(
    graph: TopologyGraph,
    routers: list[Node],
) -> list[dict[str, Any]]:
    router_ids = {router.id for router in routers}
    explicit = sorted(
        (node for node in graph.nodes.values() if node.kind == "terminal"),
        key=lambda node: (
            int(node.metadata.get("booksim_order", 0)),
            node.id,
        ),
    )
    if explicit:
        return [
            {
                "id": node.id,
                "label": _node_label(node.id, node.metadata),
                "attached_router": _attached_router_for_terminal(
                    graph,
                    node.id,
                    router_ids,
                ),
                "terminal_index": index,
                "metadata": node.metadata,
            }
            for index, node in enumerate(explicit)
        ]

    terminal_index = 0
    terminals: list[dict[str, Any]] = []
    attachments = graph.metadata.get("terminal_attachments")
    if isinstance(attachments, list) and attachments:
        for attachment in attachments:
            if not isinstance(attachment, dict):
                continue
            router_id = attachment.get("router_id")
            if router_id not in router_ids:
                continue
            for _ in range(int(attachment.get("count", 0))):
                terminals.append(_implicit_terminal(str(router_id), terminal_index))
                terminal_index += 1
        return terminals

    concentration = int(graph.metadata.get("concentration", 1))
    for router in routers:
        for _ in range(concentration):
            terminals.append(_implicit_terminal(router.id, terminal_index))
            terminal_index += 1
    return terminals


def _implicit_terminal(router_id: str, terminal_index: int) -> dict[str, Any]:
    return {
        "id": f"n.{terminal_index}",
        "label": f"n{terminal_index}",
        "attached_router": router_id,
        "terminal_index": terminal_index,
        "metadata": {},
    }


def _attached_router_for_terminal(
    graph: TopologyGraph,
    terminal_id: str,
    router_ids: set[str],
) -> str | None:
    for link in graph.links:
        if link.src == terminal_id and link.dst in router_ids:
            return link.dst
        if link.dst == terminal_id and link.src in router_ids:
            return link.src
    return None


def _terminal_position(
    router_position: tuple[float, float, float],
    local_index: int,
    local_count: int,
) -> tuple[float, float, float]:
    angle = (2.0 * pi * local_index / max(local_count, 1)) - (pi / 2.0)
    radius = 0.42 + min(0.32, max(local_count - 1, 0) * 0.025)
    return (
        router_position[0] + radius * cos(angle),
        router_position[1] - 0.24,
        router_position[2] + radius * sin(angle),
    )


def _fallback_terminal_position(index: int) -> tuple[float, float, float]:
    angle = index * 2.399963229728653
    radius = 1.0 + 0.03 * index
    return (radius * cos(angle), -0.24, radius * sin(angle))


def _terminal_attachment_links(
    terminal_nodes: list[dict[str, Any]],
    positions: dict[str, tuple[float, float, float]],
) -> list[dict[str, Any]]:
    links = []
    for node in terminal_nodes:
        router_id = node["metadata"].get("attached_router")
        terminal_id = str(node["id"])
        if router_id is None or str(router_id) not in positions:
            continue
        router_id = str(router_id)
        links.append(
            {
                "id": f"{terminal_id}->{router_id}:terminal",
                "kind": "terminal_attachment",
                "src": terminal_id,
                "dst": router_id,
                "class": "terminal_attachment",
                "group": "terminal attachments",
                "sourcePosition": list(positions[terminal_id]),
                "targetPosition": list(positions[router_id]),
                "style": {
                    "color": "#64748b",
                    "opacity": 0.38,
                    "width": 0.8,
                    "curveHeight": 0.0,
                },
                "metadata": {
                    "terminal": terminal_id,
                    "router": router_id,
                },
            }
        )
    return links


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

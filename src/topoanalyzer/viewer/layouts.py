from __future__ import annotations

from dataclasses import dataclass
from math import ceil, cos, pi, sin, sqrt
from typing import Any

from topoanalyzer.model.graph import Link, Node, TopologyGraph


Vector3 = tuple[float, float, float]


@dataclass(frozen=True)
class NodeStyle:
    color: str
    size: float
    group: str


@dataclass(frozen=True)
class LinkStyle:
    color: str
    opacity: float
    width: float
    group: str
    curve_height: float = 0.0


@dataclass(frozen=True)
class CameraPreset:
    name: str
    position: Vector3
    target: Vector3


class LayoutStrategy:
    name = "generic"
    description = "Generic coordinate layout."

    def supports(self, graph: TopologyGraph) -> bool:
        return True

    def position(self, node: Node, graph: TopologyGraph) -> Vector3:
        coord = _coord(node)
        if coord:
            return _coord_position(coord)
        index = int(node.metadata.get("booksim_order", 0))
        angle = index * 2.399963229728653
        radius = 4.0 + 0.08 * index
        return (radius * cos(angle), 0.06 * index, radius * sin(angle))

    def node_style(self, node: Node, graph: TopologyGraph) -> NodeStyle:
        return NodeStyle(color="#244c66", size=0.12, group=str(node.kind))

    def link_style(self, link: Link, graph: TopologyGraph) -> LinkStyle:
        group = str(link.metadata.get("class", "default"))
        return LinkStyle(color=_color_for_key(group), opacity=0.42, width=1.0, group=group)

    def camera_presets(self, graph: TopologyGraph) -> list[CameraPreset]:
        return _default_cameras()


class LLNLayout(LayoutStrategy):
    name = "lln_layered"
    description = "LLN core mesh and cache layers stacked vertically."

    def supports(self, graph: TopologyGraph) -> bool:
        return graph.topology_type == "lln"

    def position(self, node: Node, graph: TopologyGraph) -> Vector3:
        x, y, z = _coord3(node)
        dims = graph.metadata.get("dimensions", {})
        width = int(dims.get("x", 1))
        depth = int(dims.get("y", 1))
        return (
            (x - (width - 1) / 2.0) * 1.4,
            z * 1.15,
            (y - (depth - 1) / 2.0) * 1.4,
        )

    def node_style(self, node: Node, graph: TopologyGraph) -> NodeStyle:
        role = str(node.metadata.get("layer_role", "cache"))
        if role == "core":
            return NodeStyle(color="#2563eb", size=0.16, group="core routers")
        return NodeStyle(color="#f59e0b", size=0.13, group="cache routers")

    def link_style(self, link: Link, graph: TopologyGraph) -> LinkStyle:
        kind = str(link.metadata.get("kind", link.metadata.get("class", "default")))
        if kind == "core_mesh":
            return LinkStyle("#64748b", 0.55, 1.2, "core mesh")
        if kind == "vertical_pillar":
            return LinkStyle("#0891b2", 0.38, 1.0, "vertical pillars")
        if kind == "long":
            return LinkStyle("#dc2626", 0.72, 1.6, "long links", curve_height=0.2)
        return super().link_style(link, graph)

    def camera_presets(self, graph: TopologyGraph) -> list[CameraPreset]:
        return [
            CameraPreset("paper", (0.0, 7.0, 9.0), (0.0, 1.8, 0.0)),
            CameraPreset("layered", (7.5, 5.8, 7.5), (0.0, 1.8, 0.0)),
            CameraPreset("top", (0.0, 11.0, 0.001), (0.0, 1.8, 0.0)),
        ]


class UBMeshLayout(LayoutStrategy):
    name = "ubmesh_dimension_slabs"
    description = "nD full-mesh dimensions rendered as colored slabs and dimension lines."

    def supports(self, graph: TopologyGraph) -> bool:
        return graph.topology_type == "ubmesh"

    def position(self, node: Node, graph: TopologyGraph) -> Vector3:
        coord = _coord(node)
        dims = _dimensions_list(graph)
        if not coord:
            return super().position(node, graph)
        padded = list(coord) + [0] * (4 - len(coord))
        dim0 = dims[0] if len(dims) > 0 else 1
        dim1 = dims[1] if len(dims) > 1 else 1
        dim2 = dims[2] if len(dims) > 2 else 1
        dim3 = dims[3] if len(dims) > 3 else 1
        x = (padded[0] - (dim0 - 1) / 2.0) * 1.1
        z = (padded[1] - (dim1 - 1) / 2.0) * 1.1
        y = (padded[2] - (dim2 - 1) / 2.0) * 1.0
        if len(coord) > 3:
            rooms_per_row = ceil(sqrt(dim3))
            room_x = padded[3] % rooms_per_row
            room_z = padded[3] // rooms_per_row
            x += (room_x - (rooms_per_row - 1) / 2.0) * max(8.0, dim0 * 1.3)
            z += (room_z - ((ceil(dim3 / rooms_per_row)) - 1) / 2.0) * max(8.0, dim1 * 1.3)
        return (x, y, z)

    def node_style(self, node: Node, graph: TopologyGraph) -> NodeStyle:
        return NodeStyle(color="#0f766e", size=0.11, group="ubmesh routers")

    def link_style(self, link: Link, graph: TopologyGraph) -> LinkStyle:
        dimension = int(link.metadata.get("dimension", 0))
        name = str(link.metadata.get("dimension_name", f"dim_{dimension}"))
        color = _DIMENSION_COLORS[dimension % len(_DIMENSION_COLORS)]
        return LinkStyle(color, 0.35, 0.9, f"dimension {name}")

    def camera_presets(self, graph: TopologyGraph) -> list[CameraPreset]:
        return [
            CameraPreset("paper", (0.0, 10.0, 12.0), (0.0, 0.0, 0.0)),
            CameraPreset("slabs", (12.0, 8.0, 12.0), (0.0, 0.0, 0.0)),
            CameraPreset("top", (0.0, 18.0, 0.001), (0.0, 0.0, 0.0)),
        ]


class SlimNoCLayout(LayoutStrategy):
    name = "slimnoc_groups"
    description = "SlimNoC/SlimFly groups with algebraic subgroups and cross links."

    def supports(self, graph: TopologyGraph) -> bool:
        return graph.topology_type == "slimnoc"

    def position(self, node: Node, graph: TopologyGraph) -> Vector3:
        subgroup_type = int(node.metadata.get("subgroup_type", 0))
        subgroup = int(node.metadata.get("subgroup", 0))
        position = int(node.metadata.get("position", 0))
        q = int(graph.metadata.get("q", 1))
        group_side = _square_side(q)
        if _uses_slimnoc_group_layout(graph) and group_side is not None:
            pos_side = group_side
            group_x = subgroup % group_side
            group_z = subgroup // group_side
            pos_x = position % pos_side
            pos_z = position // pos_side
            group_gap = max(4.4, q * 0.55)
            return (
                (group_x - (group_side - 1) / 2.0) * group_gap
                + (pos_x - (pos_side - 1) / 2.0) * 0.58,
                (subgroup_type - 0.5) * 0.95,
                (group_z - (group_side - 1) / 2.0) * group_gap
                + (pos_z - (pos_side - 1) / 2.0) * 0.58,
            )

        plane = -1 if subgroup_type == 0 else 1
        return (
            plane * max(3.0, q * 0.55),
            (position - (q - 1) / 2.0) * 0.8,
            (subgroup - (q - 1) / 2.0) * 0.8,
        )

    def node_style(self, node: Node, graph: TopologyGraph) -> NodeStyle:
        subgroup_type = int(node.metadata.get("subgroup_type", 0))
        if subgroup_type == 0:
            return NodeStyle(color="#2563eb", size=0.095, group="subgraph 0")
        return NodeStyle(color="#16a34a", size=0.095, group="subgraph 1")

    def link_style(self, link: Link, graph: TopologyGraph) -> LinkStyle:
        link_class = str(link.metadata.get("class", "default"))
        if link_class == "intra_0":
            return LinkStyle("#60a5fa", 0.28, 0.7, "intra subgraph 0")
        if link_class == "intra_1":
            return LinkStyle("#4ade80", 0.28, 0.7, "intra subgraph 1")
        if link_class == "cross":
            left = link.metadata.get("left_subgroup")
            right = link.metadata.get("right_subgroup")
            if left == right:
                return LinkStyle(
                    "#f97316",
                    0.38,
                    0.9,
                    "local cross links",
                    curve_height=0.2,
                )
            return LinkStyle(
                "#dc2626",
                0.24,
                1.0,
                "inter-group cross links",
                curve_height=1.15,
            )
        return super().link_style(link, graph)

    def camera_presets(self, graph: TopologyGraph) -> list[CameraPreset]:
        q = int(graph.metadata.get("q", 1))
        if _uses_slimnoc_group_layout(graph) and _square_side(q) is not None:
            return [
                CameraPreset("paper", (0.0, 17.0, 0.001), (0.0, 0.0, 0.0)),
                CameraPreset("groups", (10.5, 8.0, 12.0), (0.0, 0.0, 0.0)),
                CameraPreset("cross", (0.0, 7.5, 15.5), (0.0, 0.0, 0.0)),
            ]
        return [
            CameraPreset("paper", (0.0, 0.0, 15.0), (0.0, 0.0, 0.0)),
            CameraPreset("exploded", (12.0, 9.0, 14.0), (0.0, 0.0, 0.0)),
            CameraPreset("side", (16.0, 0.0, 0.001), (0.0, 0.0, 0.0)),
        ]


class DragonflyLayout(LayoutStrategy):
    name = "dragonfly_groups"
    description = "Dragonfly groups arranged around a ring with local routers clustered."

    def supports(self, graph: TopologyGraph) -> bool:
        return graph.topology_type == "dragonfly"

    def position(self, node: Node, graph: TopologyGraph) -> Vector3:
        group = int(node.metadata.get("group", 0))
        router = int(node.metadata.get("router", 0))
        groups = int(graph.metadata.get("groups", 1))
        a = int(graph.metadata.get("a", 1))
        group_angle = 2 * pi * group / max(groups, 1)
        router_angle = 2 * pi * router / max(a, 1)
        radius = max(4.5, groups * 0.32)
        local_radius = 0.55 + 0.08 * a
        return (
            radius * cos(group_angle) + local_radius * cos(router_angle),
            (router - (a - 1) / 2.0) * 0.18,
            radius * sin(group_angle) + local_radius * sin(router_angle),
        )

    def node_style(self, node: Node, graph: TopologyGraph) -> NodeStyle:
        group = int(node.metadata.get("group", 0))
        return NodeStyle(color=_color_for_key(f"group_{group}"), size=0.12, group=f"group {group}")

    def link_style(self, link: Link, graph: TopologyGraph) -> LinkStyle:
        scope = str(link.metadata.get("scope", link.metadata.get("class", "default")))
        if scope == "local":
            return LinkStyle("#64748b", 0.35, 0.8, "local links")
        if scope == "global":
            return LinkStyle("#db2777", 0.62, 1.3, "global links", curve_height=0.85)
        return super().link_style(link, graph)

    def camera_presets(self, graph: TopologyGraph) -> list[CameraPreset]:
        return [
            CameraPreset("paper", (0.0, 13.0, 0.001), (0.0, 0.0, 0.0)),
            CameraPreset("groups", (10.5, 7.0, 10.5), (0.0, 0.0, 0.0)),
            CameraPreset("front", (0.0, 3.0, 14.0), (0.0, 0.0, 0.0)),
        ]


class FatTreeLayout(LayoutStrategy):
    name = "fattree_layers"
    description = "Fat-tree routers arranged by switch level from leaves to roots."

    def supports(self, graph: TopologyGraph) -> bool:
        return graph.topology_type == "fattree"

    def position(self, node: Node, graph: TopologyGraph) -> Vector3:
        level = int(node.metadata.get("level", 0))
        coord = _coord(node)
        routers_per_level = int(graph.metadata.get("routers_per_level", 1))
        columns = max(1, ceil(sqrt(routers_per_level)))
        if coord:
            index = _fattree_coord_index(coord, graph)
        else:
            index = int(node.metadata.get("booksim_order", 0)) % routers_per_level
        row_count = ceil(routers_per_level / columns)
        x = (index % columns - (columns - 1) / 2.0) * 1.0
        z = (index // columns - (row_count - 1) / 2.0) * 1.0
        if "plane" in node.metadata:
            plane_count = max(1, int(graph.metadata.get("plane_count", 1)))
            plane = int(node.metadata["plane"])
            x += (plane - (plane_count - 1) / 2.0) * max(1.25, columns * 0.45)
        return (x, level * 1.25, z)

    def node_style(self, node: Node, graph: TopologyGraph) -> NodeStyle:
        role = str(node.metadata.get("role", "intermediate"))
        if role == "leaf":
            return NodeStyle(color="#2563eb", size=0.13, group="leaf routers")
        if role == "root":
            return NodeStyle(color="#dc2626", size=0.13, group="root routers")
        return NodeStyle(color="#16a34a", size=0.12, group="intermediate routers")

    def link_style(self, link: Link, graph: TopologyGraph) -> LinkStyle:
        direction = str(link.metadata.get("direction", "default"))
        lower_level = int(link.metadata.get("lower_level", 0))
        if direction == "up":
            return LinkStyle(
                _DIMENSION_COLORS[lower_level % len(_DIMENSION_COLORS)],
                0.52,
                1.0,
                f"level {lower_level} up links",
            )
        if direction == "down":
            return LinkStyle(
                "#94a3b8",
                0.24,
                0.75,
                f"level {lower_level} down links",
            )
        return super().link_style(link, graph)

    def camera_presets(self, graph: TopologyGraph) -> list[CameraPreset]:
        levels = int(graph.metadata.get("levels", 1))
        target_y = max(0.0, (levels - 1) * 0.62)
        return [
            CameraPreset("hierarchy", (7.5, 5.5, 9.0), (0.0, target_y, 0.0)),
            CameraPreset("front", (0.0, 3.5, 10.5), (0.0, target_y, 0.0)),
            CameraPreset("top", (0.0, 12.0, 0.001), (0.0, target_y, 0.0)),
        ]


class HypercubeLayout(LayoutStrategy):
    name = "hypercube_stacked_cubes"
    description = "Hypercube bits rendered as cube dimensions and stacked higher-dimensional cubes."

    def supports(self, graph: TopologyGraph) -> bool:
        return graph.topology_type == "hypercube"

    def position(self, node: Node, graph: TopologyGraph) -> Vector3:
        bits = node.metadata.get("bits", [])
        if not isinstance(bits, list):
            return super().position(node, graph)
        padded = [int(bit) for bit in bits] + [0] * 8
        extra = sum(bit << idx for idx, bit in enumerate(padded[3:]))
        extra_count = 1 << max(len(bits) - 3, 0)
        columns = max(1, ceil(sqrt(extra_count)))
        cube_gap = 3.0
        cube_x = extra % columns
        cube_z = extra // columns
        return (
            (padded[0] - 0.5) * 1.5 + (cube_x - (columns - 1) / 2.0) * cube_gap,
            (padded[2] - 0.5) * 1.5,
            (padded[1] - 0.5) * 1.5 + (cube_z - (ceil(extra_count / columns) - 1) / 2.0) * cube_gap,
        )

    def node_style(self, node: Node, graph: TopologyGraph) -> NodeStyle:
        bits = node.metadata.get("bits", [])
        label = "".join(str(bit) for bit in reversed(bits)) if isinstance(bits, list) else ""
        return NodeStyle(color="#7c3aed", size=0.14, group=f"binary {label}")

    def link_style(self, link: Link, graph: TopologyGraph) -> LinkStyle:
        dimension = int(link.metadata.get("dimension", 0))
        color = _DIMENSION_COLORS[dimension % len(_DIMENSION_COLORS)]
        return LinkStyle(color, 0.62, 1.2, f"bit dimension {dimension}")

    def camera_presets(self, graph: TopologyGraph) -> list[CameraPreset]:
        return [
            CameraPreset("cube", (4.0, 4.0, 6.0), (0.0, 0.0, 0.0)),
            CameraPreset("top", (0.0, 8.0, 0.001), (0.0, 0.0, 0.0)),
            CameraPreset("front", (0.0, 2.0, 8.0), (0.0, 0.0, 0.0)),
        ]


def strategy_for(graph: TopologyGraph) -> LayoutStrategy:
    for strategy in (
        LLNLayout(),
        UBMeshLayout(),
        SlimNoCLayout(),
        DragonflyLayout(),
        FatTreeLayout(),
        HypercubeLayout(),
    ):
        if strategy.supports(graph):
            return strategy
    return LayoutStrategy()


_DIMENSION_COLORS = [
    "#2563eb",
    "#16a34a",
    "#f97316",
    "#db2777",
    "#0891b2",
    "#7c3aed",
    "#ca8a04",
    "#dc2626",
]

_HASH_COLORS = [
    "#2563eb",
    "#16a34a",
    "#f97316",
    "#db2777",
    "#0891b2",
    "#7c3aed",
    "#ca8a04",
    "#dc2626",
    "#475569",
]


def _uses_slimnoc_group_layout(graph: TopologyGraph) -> bool:
    layout = str(graph.metadata.get("layout", "group"))
    return layout in {"group", "figure7b", "paper_figure7b", "sn_l"}


def _square_side(value: int) -> int | None:
    side = int(sqrt(value))
    if side * side == value:
        return side
    return None


def _coord(node: Node) -> tuple[int, ...]:
    value = node.metadata.get("coord")
    if isinstance(value, (list, tuple)):
        try:
            return tuple(int(item) for item in value)
        except (TypeError, ValueError):
            return ()
    return ()


def _coord3(node: Node) -> tuple[int, int, int]:
    coord = list(_coord(node)) + [0, 0, 0]
    return coord[0], coord[1], coord[2]


def _fattree_coord_index(coord: tuple[int, ...], graph: TopologyGraph) -> int:
    split = int(graph.metadata.get("split", 1))
    index = 0
    for value in coord:
        index = index * split + int(value)
    return index


def _coord_position(coord: tuple[int, ...]) -> Vector3:
    values = list(coord) + [0, 0, 0]
    return (float(values[0]), float(values[2]), float(values[1]))


def _dimensions_list(graph: TopologyGraph) -> list[int]:
    dims = graph.metadata.get("dimensions")
    if isinstance(dims, list):
        return [int(value) for value in dims]
    if isinstance(dims, dict):
        return [int(value) for value in dims.values()]
    return []


def _color_for_key(value: str) -> str:
    total = sum((idx + 1) * ord(char) for idx, char in enumerate(value))
    return _HASH_COLORS[total % len(_HASH_COLORS)]


def _default_cameras() -> list[CameraPreset]:
    return [
        CameraPreset("front", (0.0, 4.0, 10.0), (0.0, 0.0, 0.0)),
        CameraPreset("top", (0.0, 12.0, 0.001), (0.0, 0.0, 0.0)),
        CameraPreset("orbit", (8.0, 6.0, 8.0), (0.0, 0.0, 0.0)),
    ]

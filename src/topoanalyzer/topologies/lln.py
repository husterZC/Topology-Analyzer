from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import ceil, sqrt
from typing import Any

from topoanalyzer.model.graph import Node, TopologyGraph
from topoanalyzer.model.links import LinkParameters, LinkSpec
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.topologies.base import TopologyBuilder

Coordinate2D = tuple[int, int]
Coordinate3D = tuple[int, int, int]


@dataclass(frozen=True)
class LLNParams:
    x: int
    y: int
    layers: int
    concentration: int = 1
    horizontal_ports: int = 4
    vertical_pillars: int = 4
    min_long_hops: int = 2
    coverage: str = "full_clique"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LLNParams":
        if "layers" in data:
            layers = int(data["layers"])
        elif "z" in data:
            layers = int(data["z"])
        elif "cache_layers" in data:
            layers = int(data["cache_layers"]) + 1
        else:
            raise KeyError("lln params require `layers`, `z`, or `cache_layers`")
        return cls(
            x=int(data["x"]),
            y=int(data["y"]),
            layers=layers,
            concentration=int(data.get("concentration", 1)),
            horizontal_ports=int(data.get("horizontal_ports", 4)),
            vertical_pillars=int(data.get("vertical_pillars", 4)),
            min_long_hops=int(data.get("min_long_hops", 2)),
            coverage=str(data.get("coverage", "full_clique")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "layers": self.layers,
            "cache_layers": self.cache_layers,
            "concentration": self.concentration,
            "horizontal_ports": self.horizontal_ports,
            "vertical_pillars": self.vertical_pillars,
            "min_long_hops": self.min_long_hops,
            "coverage": self.coverage,
        }

    @property
    def cache_layers(self) -> int:
        return self.layers - 1

    @property
    def routers_per_layer(self) -> int:
        return self.x * self.y

    @property
    def mesh_edges_per_layer(self) -> int:
        return (self.x - 1) * self.y + self.x * (self.y - 1)

    @property
    def projected_clique_edges(self) -> int:
        n = self.routers_per_layer
        return n * (n - 1) // 2

    @property
    def required_long_edges(self) -> int:
        return len(_projected_long_edges(self))

    def full_coverage_cache_layer_lower_bound(self) -> int:
        if self.mesh_edges_per_layer <= 0:
            return 0
        return ceil(self.required_long_edges / self.mesh_edges_per_layer)


class LLNTopologyBuilder(TopologyBuilder):
    name = "lln"
    link_classes = {"core_x", "core_y", "x", "y", "long", "vertical", "z"}
    coverage_modes = {"full_clique", "partial_greedy"}

    def validate(self, params: LLNParams, links: LinkParameters) -> ValidationReport:
        report = ValidationReport()
        if params.x <= 1 or params.y <= 1:
            report.add_error(
                "lln dimensions must be at least 2 in both X and Y",
                x=params.x,
                y=params.y,
            )
        if params.layers <= 1:
            report.add_error("lln requires at least one core layer and one cache layer")
        if params.concentration <= 0:
            report.add_error(
                "lln concentration must be positive",
                concentration=params.concentration,
            )
        if params.horizontal_ports <= 0:
            report.add_error(
                "lln horizontal_ports must be positive",
                horizontal_ports=params.horizontal_ports,
            )
        if params.vertical_pillars <= 0:
            report.add_error(
                "lln vertical_pillars must be positive",
                vertical_pillars=params.vertical_pillars,
            )
        if params.min_long_hops < 2:
            report.add_error(
                "lln min_long_hops must be at least 2",
                min_long_hops=params.min_long_hops,
            )
        if params.coverage not in self.coverage_modes:
            report.add_error(
                "unsupported lln coverage mode",
                coverage=params.coverage,
                supported=sorted(self.coverage_modes),
            )
        report.merge(links.validate(allowed_classes=self.link_classes))
        for idx, override in enumerate(links.overrides):
            for endpoint_name, endpoint in (("src", override.src), ("dst", override.dst)):
                if not isinstance(endpoint, tuple) or len(endpoint) != 3:
                    report.add_error(
                        "lln link overrides must use 3D coordinate endpoints",
                        override_index=idx,
                        endpoint=endpoint_name,
                        value=endpoint,
                    )
                    continue
                x, y, z = endpoint
                if not (
                    0 <= x < params.x
                    and 0 <= y < params.y
                    and 0 <= z < params.layers
                ):
                    report.add_error(
                        "lln link override endpoint is out of bounds",
                        override_index=idx,
                        endpoint=endpoint_name,
                        value=endpoint,
                    )

        if not report.errors and params.coverage == "full_clique":
            placement = place_long_links(params)
            if placement.missing_edges:
                report.add_error(
                    "lln full_clique coverage could not place every non-mesh projected edge",
                    missing_edges=len(placement.missing_edges),
                    required_long_edges=params.required_long_edges,
                    cache_layers=params.cache_layers,
                    mesh_edges_per_layer=params.mesh_edges_per_layer,
                    horizontal_ports=params.horizontal_ports,
                )
        return report

    def build(self, params: LLNParams, links: LinkParameters) -> TopologyGraph:
        report = self.validate(params, links)
        report.raise_if_errors()

        placement = place_long_links(params)
        long_lookup = _long_lookup(placement.placed_edges)
        graph = TopologyGraph(
            name=f"lln_{params.x}x{params.y}x{params.layers}",
            topology_type=self.name,
            metadata={
                "dimensions": {"x": params.x, "y": params.y, "layers": params.layers},
                "router_grid": [params.x, params.y],
                "layers": params.layers,
                "core_layer": 0,
                "cache_layers": params.cache_layers,
                "concentration": params.concentration,
                "router_count": params.routers_per_layer * params.layers,
                "routers_per_layer": params.routers_per_layer,
                "terminal_count": (
                    params.routers_per_layer * params.layers * params.concentration
                ),
                "horizontal_ports": params.horizontal_ports,
                "vertical_pillars": params.vertical_pillars,
                "min_long_hops": params.min_long_hops,
                "coverage": params.coverage,
                "full_coverage": not placement.missing_edges,
                "mesh_edges_per_layer": params.mesh_edges_per_layer,
                "projected_clique_edges": params.projected_clique_edges,
                "required_long_edges": params.required_long_edges,
                "placed_long_edges": len(placement.placed_edges),
                "missing_long_edges": len(placement.missing_edges),
                "full_coverage_cache_layers_lower_bound": (
                    params.full_coverage_cache_layer_lower_bound()
                ),
                "diameter": 3 if not placement.missing_edges else None,
                "long_link_lookup": long_lookup,
                "long_links": [
                    {
                        "layer": edge.layer,
                        "src_coord": list(edge.src),
                        "dst_coord": list(edge.dst),
                        "mesh_hops": manhattan(edge.src, edge.dst),
                    }
                    for edge in placement.placed_edges
                ],
            },
        )

        order = 0
        for z in range(params.layers):
            for y in range(params.y):
                for x in range(params.x):
                    graph.add_node(
                        Node(
                            id=router_id(x, y, z),
                            kind="router",
                            metadata={
                                "coord": [x, y, z],
                                "booksim_order": order,
                                "layer_role": "core" if z == 0 else "cache",
                            },
                        )
                    )
                    order += 1

        _add_core_mesh_links(graph, links, params)
        _add_vertical_links(graph, links, params)
        for edge in placement.placed_edges:
            _add_long_link(graph, links, edge)
        return graph


@dataclass(frozen=True)
class PlacedLongEdge:
    layer: int
    src: Coordinate2D
    dst: Coordinate2D


@dataclass(frozen=True)
class LongLinkPlacement:
    placed_edges: tuple[PlacedLongEdge, ...]
    missing_edges: tuple[tuple[Coordinate2D, Coordinate2D], ...]


def place_long_links(params: LLNParams) -> LongLinkPlacement:
    edges = _projected_long_edges(params)
    layer_count = params.cache_layers
    capacities = [params.mesh_edges_per_layer for _ in range(layer_count)]
    degrees = [
        {(x, y): 0 for y in range(params.y) for x in range(params.x)}
        for _ in range(layer_count)
    ]
    placed: list[PlacedLongEdge] = []
    missing: list[tuple[Coordinate2D, Coordinate2D]] = []

    for src, dst in edges:
        candidates: list[tuple[int, int, int, int]] = []
        for layer_index in range(layer_count):
            if capacities[layer_index] <= 0:
                continue
            if (
                degrees[layer_index][src] >= params.horizontal_ports
                or degrees[layer_index][dst] >= params.horizontal_ports
            ):
                continue
            candidates.append(
                (
                    max(degrees[layer_index][src], degrees[layer_index][dst]),
                    degrees[layer_index][src] + degrees[layer_index][dst],
                    -capacities[layer_index],
                    layer_index,
                )
            )
        if not candidates:
            missing.append((src, dst))
            continue
        _, _, _, layer_index = min(candidates)
        capacities[layer_index] -= 1
        degrees[layer_index][src] += 1
        degrees[layer_index][dst] += 1
        placed.append(PlacedLongEdge(layer=layer_index + 1, src=src, dst=dst))

    return LongLinkPlacement(tuple(placed), tuple(missing))


def router_id(x: int, y: int, z: int) -> str:
    return f"lln.{x}.{y}.{z}"


def parse_router_id(value: str) -> Coordinate3D | None:
    parts = value.split(".")
    if len(parts) != 4 or parts[0] != "lln":
        return None
    return int(parts[1]), int(parts[2]), int(parts[3])


def projected_pair_key(src: Coordinate2D, dst: Coordinate2D) -> str:
    a, b = sorted((src, dst))
    return f"{a[0]}.{a[1]}--{b[0]}.{b[1]}"


def manhattan(src: Coordinate2D, dst: Coordinate2D) -> int:
    return abs(src[0] - dst[0]) + abs(src[1] - dst[1])


def _projected_long_edges(params: LLNParams) -> list[tuple[Coordinate2D, Coordinate2D]]:
    coords = [(x, y) for y in range(params.y) for x in range(params.x)]
    edges = [
        (src, dst)
        for src, dst in combinations(coords, 2)
        if manhattan(src, dst) >= params.min_long_hops
    ]
    return sorted(
        edges,
        key=lambda edge: (
            -manhattan(edge[0], edge[1]),
            edge[0][1],
            edge[0][0],
            edge[1][1],
            edge[1][0],
        ),
    )


def _long_lookup(edges: tuple[PlacedLongEdge, ...]) -> dict[str, int]:
    return {projected_pair_key(edge.src, edge.dst): edge.layer for edge in edges}


def _add_core_mesh_links(
    graph: TopologyGraph,
    links: LinkParameters,
    params: LLNParams,
) -> None:
    z = 0
    for y in range(params.y):
        for x in range(params.x):
            if x + 1 < params.x:
                _add_link(
                    graph,
                    links,
                    (x, y, z),
                    (x + 1, y, z),
                    ("core_x", "x"),
                    "core_x",
                    {"kind": "core_mesh", "mesh_hops": 1},
                )
            if y + 1 < params.y:
                _add_link(
                    graph,
                    links,
                    (x, y, z),
                    (x, y + 1, z),
                    ("core_y", "y"),
                    "core_y",
                    {"kind": "core_mesh", "mesh_hops": 1},
                )


def _add_vertical_links(
    graph: TopologyGraph,
    links: LinkParameters,
    params: LLNParams,
) -> None:
    for y in range(params.y):
        for x in range(params.x):
            for z0, z1 in combinations(range(params.layers), 2):
                _add_link(
                    graph,
                    links,
                    (x, y, z0),
                    (x, y, z1),
                    ("vertical", "z"),
                    "vertical",
                    {"kind": "vertical_pillar", "src_layer": z0, "dst_layer": z1},
                )


def _add_long_link(
    graph: TopologyGraph,
    links: LinkParameters,
    edge: PlacedLongEdge,
) -> None:
    src = (edge.src[0], edge.src[1], edge.layer)
    dst = (edge.dst[0], edge.dst[1], edge.layer)
    _add_link(
        graph,
        links,
        src,
        dst,
        ("long",),
        "long",
        {
            "kind": "long",
            "layer": edge.layer,
            "src_coord_2d": list(edge.src),
            "dst_coord_2d": list(edge.dst),
            "mesh_hops": manhattan(edge.src, edge.dst),
        },
    )


def _add_link(
    graph: TopologyGraph,
    links: LinkParameters,
    src: Coordinate3D,
    dst: Coordinate3D,
    class_candidates: tuple[str, ...],
    default_class: str,
    metadata: dict[str, Any],
) -> None:
    link_class = _selected_link_class(links, class_candidates, default_class)
    spec_ab = _resolve_link(links, src, dst, class_candidates, default_class)
    spec_ba = _resolve_link(links, dst, src, class_candidates, default_class)
    graph.add_bidirectional_link(
        router_id(*src),
        router_id(*dst),
        spec_ab,
        spec_ba,
        metadata={
            "class": link_class,
            "orientation": link_class,
            "src_coord": list(src),
            "dst_coord": list(dst),
            **metadata,
        },
    )


def _selected_link_class(
    links: LinkParameters,
    class_candidates: tuple[str, ...],
    default_class: str,
) -> str:
    for link_class in class_candidates:
        if link_class in links.classes:
            return link_class
    return default_class


def _resolve_link(
    links: LinkParameters,
    src: Coordinate3D,
    dst: Coordinate3D,
    class_candidates: tuple[str, ...],
    default_class: str,
) -> LinkSpec:
    for link_class in class_candidates:
        spec = links.resolve(src, dst, link_class=link_class)
        if link_class in links.classes or spec != links.default:
            return spec
    return links.resolve(src, dst, link_class=default_class)


def square_full_coverage_total_layers(side: int) -> int:
    if side <= 1:
        raise ValueError(f"side must be greater than 1, got {side}")
    cache_layers = ceil(side * (side + 1) / 4 - 1)
    return cache_layers + 1


def square_max_side_for_cache_layers(cache_layers: int) -> int:
    if cache_layers < 0:
        raise ValueError(f"cache_layers must be non-negative, got {cache_layers}")
    return int((sqrt(16 * cache_layers + 17) - 1) // 2)

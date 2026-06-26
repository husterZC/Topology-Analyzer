from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from itertools import combinations
from math import ceil, floor, prod
from typing import Callable

from topoanalyzer.model.graph import Link, TopologyGraph
from topoanalyzer.model.system import System


_BANDWIDTH_RE = re.compile(
    r"^\s*(?P<value>[+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(?P<unit>[A-Za-z0-9_./-]+)\s*$"
)
_EXACT_BISECTION_ROUTER_LIMIT = 18


@dataclass(frozen=True)
class NetworkMetrics:
    system: str
    topology: str
    routing: str
    nodes: int
    routers: int
    graph_nodes: int
    links: int
    max_router_radix: int | None
    diameter: int | None
    bisection_bandwidth: str
    bisection_method: str
    bisection_partition_sizes: tuple[int, int] | None = None
    bisection_note: str | None = None


@dataclass(frozen=True)
class _BisectionResult:
    value: Decimal | None
    unit: str | None
    method: str
    partition_sizes: tuple[int, int] | None = None
    note: str | None = None

    @property
    def formatted(self) -> str:
        if self.value is None or self.unit is None:
            return "unavailable"
        return f"{_format_decimal(self.value)}{self.unit}"


@dataclass(frozen=True)
class _FormulaCandidate:
    value: Decimal
    unit: str
    note: str


def write_metrics_text(systems: list[System], path) -> None:
    path.write_text(metrics_text(systems), encoding="utf-8")


def metrics_text(systems: list[System]) -> str:
    unique_systems = _unique_systems(systems)
    lines = [
        "# Topology Analyzer Network Metrics",
        "",
        "benchmark_type: latency_vs_injection_rate",
        "notes:",
        "  nodes: terminal/injection nodes. If terminals are implicit, this uses terminal_count or concentration metadata.",
        "  routers: router nodes in the topology graph.",
        "  graph_nodes: explicit nodes stored in the topology graph.",
        "  links: directed router-router links stored in the topology graph.",
        "  max_router_radix: maximum router output radix, counted as outgoing "
        "router-router links plus locally attached terminal/injection ports.",
        "  diameter: exact directed router-hop diameter over router nodes.",
        "  bisection_bandwidth: one-way aggregate bisection bandwidth. Small graphs use exact balanced router cuts; larger graphs use topology-level formulas or documented estimates.",
        "",
    ]
    for system in unique_systems:
        metrics = summarize_system(system)
        lines.extend(_format_system_metrics(metrics))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def summarize_system(system: System) -> NetworkMetrics:
    graph = system.graph
    bisection = _bisection_bandwidth(system)
    return NetworkMetrics(
        system=system.name,
        topology=system.topology_type,
        routing=system.routing_table.name,
        nodes=_terminal_node_count(graph),
        routers=len(graph.routers()),
        graph_nodes=len(graph.nodes),
        links=len(graph.links),
        max_router_radix=_max_router_radix(graph),
        diameter=_router_diameter(graph),
        bisection_bandwidth=bisection.formatted,
        bisection_method=bisection.method,
        bisection_partition_sizes=bisection.partition_sizes,
        bisection_note=bisection.note,
    )


def _format_system_metrics(metrics: NetworkMetrics) -> list[str]:
    lines = [
        f"[{metrics.system}]",
        f"topology: {metrics.topology}",
        f"routing: {metrics.routing}",
        f"nodes: {metrics.nodes}",
        f"routers: {metrics.routers}",
        f"graph_nodes: {metrics.graph_nodes}",
        f"links: {metrics.links}",
        f"max_router_radix: {_format_optional_int(metrics.max_router_radix)}",
        f"diameter: {_format_optional_int(metrics.diameter)}",
        f"bisection_bandwidth: {metrics.bisection_bandwidth}",
        f"bisection_method: {metrics.bisection_method}",
    ]
    if metrics.bisection_partition_sizes is not None:
        left, right = metrics.bisection_partition_sizes
        lines.append(f"bisection_partition_sizes: {left},{right}")
    if metrics.bisection_note:
        lines.append(f"bisection_note: {metrics.bisection_note}")
    return lines


def _unique_systems(systems: list[System]) -> list[System]:
    unique: list[System] = []
    seen: set[str] = set()
    for system in systems:
        if system.name in seen:
            continue
        seen.add(system.name)
        unique.append(system)
    return unique


def _terminal_node_count(graph: TopologyGraph) -> int:
    explicit_terminals = sum(1 for node in graph.nodes.values() if node.kind == "terminal")
    if explicit_terminals:
        return explicit_terminals

    terminal_count = graph.metadata.get("terminal_count")
    if terminal_count is not None:
        return int(terminal_count)

    attachments = graph.metadata.get("terminal_attachments")
    if isinstance(attachments, list) and attachments:
        return sum(int(item.get("count", 0)) for item in attachments if isinstance(item, dict))

    return len(graph.routers()) * int(graph.metadata.get("concentration", 1))


def _max_router_radix(graph: TopologyGraph) -> int | None:
    router_ids = {node.id for node in graph.routers()}
    if not router_ids:
        return None

    router_outputs = {router_id: 0 for router_id in router_ids}
    terminal_neighbors: dict[str, set[str]] = {
        router_id: set() for router_id in router_ids
    }
    terminal_ids = {
        node.id for node in graph.nodes.values() if node.kind == "terminal"
    }
    for link in graph.links:
        if link.src in router_ids and link.dst in router_ids:
            router_outputs[link.src] += 1
        elif link.src in router_ids and link.dst in terminal_ids:
            terminal_neighbors[link.src].add(link.dst)
        elif link.dst in router_ids and link.src in terminal_ids:
            terminal_neighbors[link.dst].add(link.src)

    if any(terminal_neighbors.values()):
        local_ports = {
            router_id: len(neighbors)
            for router_id, neighbors in terminal_neighbors.items()
        }
    else:
        local_ports = _implicit_terminal_ports(graph, router_ids)

    return max(
        router_outputs[router_id] + local_ports.get(router_id, 0)
        for router_id in router_ids
    )


def _implicit_terminal_ports(
    graph: TopologyGraph,
    router_ids: set[str],
) -> dict[str, int]:
    attachments = graph.metadata.get("terminal_attachments")
    if isinstance(attachments, list) and attachments:
        counts = {router_id: 0 for router_id in router_ids}
        for item in attachments:
            if not isinstance(item, dict):
                continue
            router_id = item.get("router_id")
            if router_id in router_ids:
                counts[router_id] += int(item.get("count", 0))
        return counts

    concentration = graph.metadata.get("concentration")
    if concentration is None:
        return {router_id: 0 for router_id in router_ids}
    return {router_id: int(concentration) for router_id in router_ids}


def _router_diameter(graph: TopologyGraph) -> int | None:
    routers = sorted(node.id for node in graph.routers())
    if not routers:
        return None
    adjacency = _router_adjacency(graph)
    diameter = 0
    for source in routers:
        distances = _bfs_distances(source, adjacency)
        if len(distances) != len(routers):
            return None
        diameter = max(diameter, max(distances.values(), default=0))
    return diameter


def _router_adjacency(graph: TopologyGraph) -> dict[str, list[str]]:
    router_ids = {node.id for node in graph.routers()}
    adjacency = {router_id: [] for router_id in router_ids}
    for link in graph.links:
        if link.src in router_ids and link.dst in router_ids:
            adjacency[link.src].append(link.dst)
    return adjacency


def _bfs_distances(source: str, adjacency: dict[str, list[str]]) -> dict[str, int]:
    distances = {source: 0}
    queue = deque([source])
    while queue:
        current = queue.popleft()
        for neighbor in adjacency[current]:
            if neighbor in distances:
                continue
            distances[neighbor] = distances[current] + 1
            queue.append(neighbor)
    return distances


def _bisection_bandwidth(system: System) -> _BisectionResult:
    routers = sorted(node.id for node in system.graph.routers())
    if len(routers) <= 1:
        unit = _first_bandwidth_unit(system.graph)
        return _BisectionResult(Decimal(0), unit or "", "trivial_single_router", (len(routers), 0))

    if len(routers) <= _EXACT_BISECTION_ROUTER_LIMIT:
        exact = _exact_bisection(system.graph, routers)
        if exact.value is not None:
            return exact

    formula = _formula_bisection(system)
    if formula.value is not None:
        return formula

    return _BisectionResult(
        None,
        None,
        "bisection_formula_unavailable",
        None,
        (
            "exact balanced cut enumeration is disabled above "
            f"{_EXACT_BISECTION_ROUTER_LIMIT} routers and no formula "
            f"is implemented for topology {system.topology_type}"
        ),
    )


def _exact_bisection(graph: TopologyGraph, routers: list[str]) -> _BisectionResult:
    left_size = len(routers) // 2
    if left_size == 0:
        unit = _first_bandwidth_unit(graph)
        return _BisectionResult(Decimal(0), unit or "", "exact_balanced_router_cut", (0, len(routers)))

    best: tuple[Decimal, str, tuple[int, int]] | None = None
    first_router = routers[0]
    for subset_items in combinations(routers, left_size):
        if len(routers) % 2 == 0 and first_router not in subset_items:
            continue
        result = _partition_bandwidth(graph, set(subset_items))
        if result.value is None or result.unit is None:
            return _BisectionResult(
                None,
                None,
                "exact_balanced_router_cut",
                result.partition_sizes,
                result.note,
            )
        if best is None or result.value < best[0]:
            best = (result.value, result.unit, result.partition_sizes or (left_size, len(routers) - left_size))

    if best is None:
        return _BisectionResult(None, None, "exact_balanced_router_cut", None, "no partitions generated")
    return _BisectionResult(best[0], best[1], "exact_balanced_router_cut", best[2])


def _formula_bisection(system: System) -> _BisectionResult:
    graph = system.graph
    partition_sizes = _balanced_router_partition_sizes(graph)
    if system.topology_type in {"mesh2d", "mesh3d"}:
        return _mesh_bisection(graph, partition_sizes)
    if system.topology_type in {"torus2d", "torus3d"}:
        return _torus_bisection(graph, partition_sizes)
    if system.topology_type == "ruche3d":
        return _ruche_bisection(graph, partition_sizes)
    if system.topology_type == "hypercube":
        return _hypercube_bisection(graph, partition_sizes)
    if system.topology_type == "ubmesh":
        return _ubmesh_bisection(graph, partition_sizes)
    if system.topology_type == "dragonfly":
        return _dragonfly_bisection_estimate(graph)
    if system.topology_type == "slimnoc":
        return _slimnoc_bisection_estimate(graph)
    if system.topology_type == "lln":
        return _lln_bisection_estimate(graph)
    if system.topology_type == "fattree":
        return _fattree_bisection_estimate(graph)
    return _BisectionResult(None, None, "bisection_formula_unavailable", None)


def _mesh_bisection(
    graph: TopologyGraph,
    partition_sizes: tuple[int, int],
) -> _BisectionResult:
    dimensions = _ordered_dimensions(graph)
    candidates: list[_FormulaCandidate] = []
    for axis, length in dimensions:
        if length <= 1:
            continue
        bandwidth = _uniform_bandwidth_for_class(graph, {axis})
        if bandwidth is None:
            return _unavailable_formula(
                "mesh_axis_bisection_formula",
                f"axis {axis} has mixed or unparseable link bandwidths",
            )
        value, unit = bandwidth
        crossing_links = prod(
            other_length
            for other_axis, other_length in dimensions
            if other_axis != axis
        )
        candidates.append(
            _FormulaCandidate(
                Decimal(crossing_links) * value,
                unit,
                f"axis={axis}, crossing_links={crossing_links}",
            )
        )
    return _select_formula_candidate(
        candidates,
        "mesh_axis_bisection_formula",
        partition_sizes,
    )


def _torus_bisection(
    graph: TopologyGraph,
    partition_sizes: tuple[int, int],
) -> _BisectionResult:
    dimensions = _ordered_dimensions(graph)
    candidates: list[_FormulaCandidate] = []
    for axis, length in dimensions:
        if length <= 1:
            continue
        bandwidth = _uniform_bandwidth_for_class(graph, {axis, f"{axis}_wrap"})
        if bandwidth is None:
            return _unavailable_formula(
                "torus_axis_bisection_formula",
                f"axis {axis} has mixed or unparseable link bandwidths",
            )
        value, unit = bandwidth
        crossing_links = 2 * prod(
            other_length
            for other_axis, other_length in dimensions
            if other_axis != axis
        )
        candidates.append(
            _FormulaCandidate(
                Decimal(crossing_links) * value,
                unit,
                f"axis={axis}, crossing_links={crossing_links}",
            )
        )
    return _select_formula_candidate(
        candidates,
        "torus_axis_bisection_formula",
        partition_sizes,
    )


def _ruche_bisection(
    graph: TopologyGraph,
    partition_sizes: tuple[int, int],
) -> _BisectionResult:
    if bool(graph.metadata.get("wrap", False)):
        return _unavailable_formula(
            "ruche_nonwrap_axis_bisection_formula",
            "wrap ruche bisection formula is not implemented",
        )
    dimensions = _ordered_dimensions(graph)
    strides_data = graph.metadata.get("strides", {})
    if not isinstance(strides_data, dict):
        return _unavailable_formula(
            "ruche_nonwrap_axis_bisection_formula",
            "ruche stride metadata is unavailable",
        )

    candidates: list[_FormulaCandidate] = []
    for axis, length in dimensions:
        if length <= 1:
            continue
        local_bandwidth = _uniform_bandwidth_for_class(graph, {axis})
        if local_bandwidth is None:
            return _unavailable_formula(
                "ruche_nonwrap_axis_bisection_formula",
                f"axis {axis} has mixed or unparseable local-link bandwidths",
            )
        local_value, unit = local_bandwidth
        stride = int(strides_data.get(axis, 0))
        cut_position = length // 2
        local_crossings_per_line = 1
        ruche_crossings_per_line = _ruche_crossing_count(
            length,
            stride,
            cut_position,
        )
        parallel_lines = prod(
            other_length
            for other_axis, other_length in dimensions
            if other_axis != axis
        )
        value = Decimal(parallel_lines * local_crossings_per_line) * local_value
        if ruche_crossings_per_line:
            ruche_bandwidth = _uniform_bandwidth_for_class(graph, {f"ruche_{axis}"})
            if ruche_bandwidth is None:
                return _unavailable_formula(
                    "ruche_nonwrap_axis_bisection_formula",
                    f"axis {axis} has mixed or unparseable ruche-link bandwidths",
                )
            ruche_value, ruche_unit = ruche_bandwidth
            if ruche_unit != unit:
                return _unavailable_formula(
                    "ruche_nonwrap_axis_bisection_formula",
                    f"axis {axis} local and ruche bandwidth units differ",
                )
            value += Decimal(parallel_lines * ruche_crossings_per_line) * ruche_value
        crossing_links = parallel_lines * (
            local_crossings_per_line + ruche_crossings_per_line
        )
        candidates.append(
            _FormulaCandidate(
                value,
                unit,
                (
                    f"axis={axis}, cut_position={cut_position}, "
                    f"crossing_links={crossing_links}"
                ),
            )
        )
    return _select_formula_candidate(
        candidates,
        "ruche_nonwrap_axis_bisection_formula",
        partition_sizes,
    )


def _hypercube_bisection(
    graph: TopologyGraph,
    partition_sizes: tuple[int, int],
) -> _BisectionResult:
    dimension = int(graph.metadata.get("dimension", 0))
    if dimension <= 0:
        return _unavailable_formula(
            "hypercube_dimension_bisection_formula",
            "hypercube dimension metadata is unavailable",
        )
    crossing_links = 1 << (dimension - 1)
    candidates: list[_FormulaCandidate] = []
    for bit in range(dimension):
        bandwidth = _uniform_bandwidth_for_links(
            graph,
            lambda link, bit=bit: int(link.metadata.get("dimension", -1)) == bit,
        )
        if bandwidth is None:
            return _unavailable_formula(
                "hypercube_dimension_bisection_formula",
                f"dimension {bit} has mixed or unparseable link bandwidths",
            )
        value, unit = bandwidth
        candidates.append(
            _FormulaCandidate(
                Decimal(crossing_links) * value,
                unit,
                f"dimension={bit}, crossing_links={crossing_links}",
            )
        )
    return _select_formula_candidate(
        candidates,
        "hypercube_dimension_bisection_formula",
        partition_sizes,
    )


def _ubmesh_bisection(
    graph: TopologyGraph,
    partition_sizes: tuple[int, int],
) -> _BisectionResult:
    raw_dimensions = graph.metadata.get("dimensions")
    if not isinstance(raw_dimensions, list) or not raw_dimensions:
        return _unavailable_formula(
            "ubmesh_nd_fullmesh_bisection_formula",
            "ubmesh dimensions metadata is unavailable",
        )
    dimensions = [int(value) for value in raw_dimensions]
    router_count = prod(dimensions)
    candidates: list[_FormulaCandidate] = []
    for axis, length in enumerate(dimensions):
        if length <= 1:
            continue
        bandwidth = _uniform_bandwidth_for_links(
            graph,
            lambda link, axis=axis: int(link.metadata.get("dimension", -1)) == axis,
        )
        if bandwidth is None:
            return _unavailable_formula(
                "ubmesh_nd_fullmesh_bisection_formula",
                f"dimension {axis} has mixed or unparseable link bandwidths",
            )
        value, unit = bandwidth
        crossing_links = (
            router_count
            // length
            * floor(length / 2)
            * ceil(length / 2)
        )
        candidates.append(
            _FormulaCandidate(
                Decimal(crossing_links) * value,
                unit,
                f"dimension={axis}, crossing_links={crossing_links}",
            )
        )
    return _select_formula_candidate(
        candidates,
        "ubmesh_nd_fullmesh_bisection_formula",
        partition_sizes,
    )


def _dragonfly_bisection_estimate(graph: TopologyGraph) -> _BisectionResult:
    groups = int(graph.metadata.get("groups", 0))
    routers_per_group = int(graph.metadata.get("a", 0))
    if groups <= 1 or routers_per_group <= 0:
        return _unavailable_formula(
            "dragonfly_group_bisection_estimate",
            "dragonfly group metadata is unavailable",
        )
    bandwidth = _uniform_bandwidth_for_class(graph, {"global"})
    if bandwidth is None:
        return _unavailable_formula(
            "dragonfly_group_bisection_estimate",
            "global links have mixed or unparseable bandwidths",
        )
    value, unit = bandwidth
    left_groups = groups // 2
    right_groups = groups - left_groups
    crossing_links = left_groups * right_groups
    return _BisectionResult(
        Decimal(crossing_links) * value,
        unit,
        "dragonfly_group_bisection_estimate",
        (left_groups * routers_per_group, right_groups * routers_per_group),
        (
            f"group_partition_sizes={left_groups},{right_groups}, "
            f"crossing_global_links={crossing_links}"
        ),
    )


def _slimnoc_bisection_estimate(graph: TopologyGraph) -> _BisectionResult:
    q = int(graph.metadata.get("q", 0))
    if q <= 1:
        return _unavailable_formula(
            "slimnoc_group_bisection_estimate",
            "slimnoc q metadata is unavailable",
        )
    bandwidth = _uniform_bandwidth_for_class(graph, {"cross"})
    if bandwidth is None:
        return _unavailable_formula(
            "slimnoc_group_bisection_estimate",
            "cross links have mixed or unparseable bandwidths",
        )
    value, unit = bandwidth
    left_groups = q // 2
    right_groups = q - left_groups
    routers_per_group = 2 * q
    crossing_links = 2 * (q - 1) * left_groups * right_groups
    return _BisectionResult(
        Decimal(crossing_links) * value,
        unit,
        "slimnoc_group_bisection_estimate",
        (left_groups * routers_per_group, right_groups * routers_per_group),
        (
            f"group_partition_sizes={left_groups},{right_groups}, "
            f"crossing_cross_links={crossing_links}"
        ),
    )


def _lln_bisection_estimate(graph: TopologyGraph) -> _BisectionResult:
    routers_per_layer = int(graph.metadata.get("routers_per_layer", 0))
    vertical_pillars = int(graph.metadata.get("vertical_pillars", 0))
    if routers_per_layer <= 0 or vertical_pillars <= 0:
        return _unavailable_formula(
            "lln_projected_bisection_estimate",
            "lln projected-grid metadata is unavailable",
        )
    long_bandwidth = _uniform_bandwidth_for_class(graph, {"long"})
    vertical_bandwidth = _uniform_bandwidth_for_class(graph, {"vertical"})
    if long_bandwidth is None or vertical_bandwidth is None:
        return _unavailable_formula(
            "lln_projected_bisection_estimate",
            "long or vertical links have mixed or unparseable bandwidths",
        )
    long_value, long_unit = long_bandwidth
    vertical_value, vertical_unit = vertical_bandwidth
    if long_unit != vertical_unit:
        return _unavailable_formula(
            "lln_projected_bisection_estimate",
            "long and vertical link bandwidth units differ",
        )
    left = routers_per_layer // 2
    right = routers_per_layer - left
    long_crossing_links = left * right
    vertical_crossing_links = routers_per_layer * vertical_pillars
    candidates = [
        _FormulaCandidate(
            Decimal(long_crossing_links) * long_value,
            long_unit,
            f"projected_long_crossing_links={long_crossing_links}",
        ),
        _FormulaCandidate(
            Decimal(vertical_crossing_links) * vertical_value,
            vertical_unit,
            f"vertical_crossing_links={vertical_crossing_links}",
        ),
    ]
    return _select_formula_candidate(
        candidates,
        "lln_projected_bisection_estimate",
        _balanced_router_partition_sizes(graph),
    )


def _fattree_bisection_estimate(graph: TopologyGraph) -> _BisectionResult:
    bandwidth = _minimum_link_bandwidth(graph)
    if bandwidth is None:
        return _unavailable_formula(
            "fattree_terminal_bisection_estimate",
            "link bandwidths use mixed or unparseable units",
        )
    value, unit = bandwidth
    terminal_count = _terminal_node_count(graph)
    left = terminal_count // 2
    right = terminal_count - left
    return _BisectionResult(
        Decimal(left) * value,
        unit,
        "fattree_terminal_bisection_estimate",
        (left, right),
        "terminal_partition_sizes",
    )


def _balanced_router_partition_sizes(graph: TopologyGraph) -> tuple[int, int]:
    router_count = len(graph.routers())
    left = router_count // 2
    return left, router_count - left


def _ordered_dimensions(graph: TopologyGraph) -> list[tuple[str, int]]:
    raw = graph.metadata.get("dimensions")
    if not isinstance(raw, dict):
        return []
    return [
        (axis, int(raw[axis]))
        for axis in ("x", "y", "z")
        if axis in raw
    ]


def _ruche_crossing_count(length: int, stride: int, cut_position: int) -> int:
    if stride <= 0:
        return 0
    first = max(0, cut_position - stride)
    last = min(cut_position - 1, length - stride - 1)
    if last < first:
        return 0
    return last - first + 1


def _select_formula_candidate(
    candidates: list[_FormulaCandidate],
    method: str,
    partition_sizes: tuple[int, int],
) -> _BisectionResult:
    if not candidates:
        return _unavailable_formula(method, "no valid formula candidates")
    units = {candidate.unit for candidate in candidates}
    if len(units) != 1:
        return _unavailable_formula(
            method,
            "formula candidates use different bandwidth units",
        )
    best = min(candidates, key=lambda candidate: candidate.value)
    return _BisectionResult(
        best.value,
        best.unit,
        method,
        partition_sizes,
        best.note,
    )


def _unavailable_formula(method: str, note: str) -> _BisectionResult:
    return _BisectionResult(None, None, method, None, note)


def _uniform_bandwidth_for_class(
    graph: TopologyGraph,
    classes: set[str],
) -> tuple[Decimal, str] | None:
    return _uniform_bandwidth_for_links(
        graph,
        lambda link: str(link.metadata.get("class", "default")) in classes,
    )


def _uniform_bandwidth_for_links(
    graph: TopologyGraph,
    predicate: Callable[[Link], bool],
) -> tuple[Decimal, str] | None:
    parsed_values: set[tuple[Decimal, str]] = set()
    matched = False
    for link in graph.links:
        if not predicate(link):
            continue
        matched = True
        parsed = _parse_bandwidth(link.bandwidth)
        if parsed is None:
            return None
        parsed_values.add(parsed)
    if not matched or len(parsed_values) != 1:
        return None
    return next(iter(parsed_values))


def _partition_bandwidth(graph: TopologyGraph, left: set[str]) -> _BisectionResult:
    router_ids = {node.id for node in graph.routers()}
    right = router_ids - left
    left_to_right = _directed_cut_bandwidth(graph, left, right)
    right_to_left = _directed_cut_bandwidth(graph, right, left)
    if left_to_right.value is None:
        return left_to_right
    if right_to_left.value is None:
        return right_to_left
    if left_to_right.unit != right_to_left.unit:
        return _BisectionResult(
            None,
            None,
            "partition_bandwidth",
            (len(left), len(right)),
            f"opposite cut directions use different units: {left_to_right.unit}, {right_to_left.unit}",
        )
    return _BisectionResult(
        min(left_to_right.value, right_to_left.value),
        left_to_right.unit,
        "partition_bandwidth",
        (len(left), len(right)),
    )


def _directed_cut_bandwidth(
    graph: TopologyGraph,
    sources: set[str],
    destinations: set[str],
) -> _BisectionResult:
    total = Decimal(0)
    unit: str | None = None
    crossing_links = 0
    for link in graph.links:
        if link.src not in sources or link.dst not in destinations:
            continue
        parsed = _parse_bandwidth(link.bandwidth)
        if parsed is None:
            return _BisectionResult(
                None,
                None,
                "directed_cut_bandwidth",
                None,
                f"unparseable link bandwidth: {link.bandwidth}",
            )
        value, parsed_unit = parsed
        if unit is None:
            unit = parsed_unit
        elif parsed_unit != unit:
            return _BisectionResult(
                None,
                None,
                "directed_cut_bandwidth",
                None,
                f"mixed link bandwidth units: {unit}, {parsed_unit}",
            )
        total += value
        crossing_links += 1

    if unit is None:
        unit = _first_bandwidth_unit(graph)
    return _BisectionResult(
        total,
        unit or "",
        "directed_cut_bandwidth",
        None,
        "no crossing links" if crossing_links == 0 else None,
    )


def _minimum_link_bandwidth(graph: TopologyGraph) -> tuple[Decimal, str] | None:
    best: tuple[Decimal, str] | None = None
    for link in graph.links:
        parsed = _parse_bandwidth(link.bandwidth)
        if parsed is None:
            return None
        if best is None:
            best = parsed
            continue
        value, unit = parsed
        if unit != best[1]:
            return None
        if value < best[0]:
            best = parsed
    return best


def _first_bandwidth_unit(graph: TopologyGraph) -> str | None:
    for link in graph.links:
        parsed = _parse_bandwidth(link.bandwidth)
        if parsed is not None:
            return parsed[1]
    return None


def _parse_bandwidth(value: str) -> tuple[Decimal, str] | None:
    match = _BANDWIDTH_RE.fullmatch(value)
    if not match:
        return None
    try:
        numeric = Decimal(match.group("value"))
    except InvalidOperation:
        return None
    return numeric, match.group("unit")


def _format_decimal(value: Decimal) -> str:
    if value == value.to_integral_value():
        return str(int(value))
    return format(value.normalize(), "f")


def _format_optional_int(value: int | None) -> str:
    return "unavailable" if value is None else str(value)

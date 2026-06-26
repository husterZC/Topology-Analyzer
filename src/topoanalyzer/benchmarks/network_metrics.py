from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from itertools import combinations

from topoanalyzer.model.graph import TopologyGraph
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
        "  bisection_bandwidth: one-way aggregate bandwidth across a balanced router bisection when exact, or the documented method otherwise.",
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

    if system.topology_type == "fattree":
        formula = _fattree_bisection(system)
        if formula.value is not None:
            return formula

    axis_cut = _axis_aligned_bisection(system.graph, routers)
    if axis_cut.value is not None:
        return axis_cut

    return _BisectionResult(
        None,
        None,
        "unavailable",
        None,
        "no exact cut was attempted for this router count and no coordinate cut was available",
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


def _fattree_bisection(system: System) -> _BisectionResult:
    bandwidth = _minimum_link_bandwidth(system.graph)
    if bandwidth is None:
        return _BisectionResult(
            None,
            None,
            "fattree_terminal_bisection_formula",
            None,
            "link bandwidths use mixed or unparseable units",
        )
    value, unit = bandwidth
    terminal_count = _terminal_node_count(system.graph)
    return _BisectionResult(
        Decimal(terminal_count // 2) * value,
        unit,
        "fattree_terminal_bisection_formula",
        (terminal_count // 2, terminal_count - terminal_count // 2),
    )


def _axis_aligned_bisection(graph: TopologyGraph, routers: list[str]) -> _BisectionResult:
    coords = _router_coords(graph, routers)
    if not coords:
        return _BisectionResult(None, None, "axis_aligned_router_cut", None, "router coordinates unavailable")

    dimension_count = len(next(iter(coords.values())))
    best: tuple[int, Decimal, str, tuple[int, int], int] | None = None
    for axis in range(dimension_count):
        values = sorted({coord[axis] for coord in coords.values()})
        for threshold in values[:-1]:
            left = {
                router
                for router, coord in coords.items()
                if coord[axis] <= threshold
            }
            if not left or len(left) == len(routers):
                continue
            result = _partition_bandwidth(graph, left)
            if result.value is None or result.unit is None:
                continue
            partition_sizes = result.partition_sizes or (len(left), len(routers) - len(left))
            imbalance = abs(partition_sizes[0] - partition_sizes[1])
            candidate = (imbalance, result.value, result.unit, partition_sizes, axis)
            if best is None or candidate[:2] < best[:2]:
                best = candidate

    if best is None:
        return _BisectionResult(
            None,
            None,
            "axis_aligned_router_cut",
            None,
            "no coordinate axis produced a valid cut",
        )
    imbalance, value, unit, partition_sizes, axis = best
    method = "axis_aligned_balanced_router_cut" if imbalance <= 1 else "axis_aligned_nearest_router_cut"
    note = f"axis={axis}, imbalance={imbalance}"
    return _BisectionResult(value, unit, method, partition_sizes, note)


def _router_coords(graph: TopologyGraph, routers: list[str]) -> dict[str, tuple[int, ...]]:
    coords: dict[str, tuple[int, ...]] = {}
    dimension_count: int | None = None
    for router in routers:
        value = graph.nodes[router].metadata.get("coord")
        if not isinstance(value, (list, tuple)):
            return {}
        try:
            coord = tuple(int(item) for item in value)
        except (TypeError, ValueError):
            return {}
        if dimension_count is None:
            dimension_count = len(coord)
        elif len(coord) != dimension_count:
            return {}
        coords[router] = coord
    return coords


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

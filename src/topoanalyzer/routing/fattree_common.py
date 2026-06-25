from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from topoanalyzer.model.graph import TopologyGraph
from topoanalyzer.model.routing import RoutingTable
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.routing.deadlock import channel_dependency_has_cycle


@dataclass(frozen=True)
class TerminalDestination:
    terminal_id: int
    router_id: str
    local_index: int
    leaf_coord: tuple[int, ...]


UpSelector = Callable[
    [
        TopologyGraph,
        str,
        TerminalDestination,
        dict[str, list[str]],
        dict[str, list[str]],
    ],
    str,
]


def validate_fattree_terminal_routing(
    graph: TopologyGraph,
    *,
    routing_name: str,
) -> ValidationReport:
    report = ValidationReport()
    if graph.topology_type != "fattree":
        report.add_error(
            f"{routing_name} routing requires a fattree topology",
            topology_type=graph.topology_type,
        )
    if not graph.routers():
        report.add_error(f"{routing_name} routing requires at least one router")
    if not graph.is_connected():
        report.add_error(f"{routing_name} routing requires a connected router graph")
    if not terminal_destinations(graph):
        report.add_error(f"{routing_name} routing requires terminal-attached routers")
    return report


def generate_terminal_aware_nca_table(
    graph: TopologyGraph,
    *,
    routing_name: str,
    metadata: dict[str, object],
    up_selector: UpSelector,
    disabled_links: set[tuple[str, str]] | None = None,
) -> RoutingTable:
    disabled = set() if disabled_links is None else set(disabled_links)
    routers = router_ids(graph)
    terminals = terminal_destinations(graph)
    up_adjacency, down_adjacency = up_down_adjacency(graph, disabled_links=disabled)
    terminal_next_hops: dict[str, dict[str, dict[str, int | str]]] = {
        router: {} for router in routers
    }

    table = RoutingTable(
        name=routing_name,
        metadata={
            **metadata,
            "topology": "fattree",
            "destination_routers": destination_router_ids(terminals, routers),
            "terminal_routes": "metadata.terminal_next_hops[current][terminal_id]",
        },
    )

    first_terminal_by_leaf = first_terminal_by_leaf_router(terminals)
    for source in routers:
        for destination, terminal in first_terminal_by_leaf.items():
            if source == destination:
                continue
            table.add_path(
                source,
                destination,
                path_to_terminal(
                    graph,
                    source,
                    terminal,
                    up_adjacency,
                    down_adjacency,
                    up_selector,
                    routing_name=routing_name,
                ),
            )

    for current in routers:
        for terminal in terminals:
            if current == terminal.router_id:
                continue
            path = path_to_terminal(
                graph,
                current,
                terminal,
                up_adjacency,
                down_adjacency,
                up_selector,
                routing_name=routing_name,
            )
            terminal_next_hops[current][str(terminal.terminal_id)] = {
                "next_hop": path[1],
                "vc": 0,
            }

    has_cycle, cycle = channel_dependency_has_cycle(table)
    if has_cycle:
        raise ValueError(f"{routing_name} generated cyclic channel dependencies: {cycle}")
    table.metadata["terminal_next_hops"] = terminal_next_hops
    table.metadata["terminal_count"] = len(terminals)
    table.metadata["used_vcs"] = 1
    if disabled:
        table.metadata["disabled_links"] = [
            {"src": src, "dst": dst} for src, dst in sorted(disabled)
        ]
    return table


def router_ids(graph: TopologyGraph) -> list[str]:
    return [
        node.id
        for node in sorted(
            graph.routers(),
            key=lambda node: (int(node.metadata.get("booksim_order", 0)), node.id),
        )
    ]


def terminal_destinations(graph: TopologyGraph) -> list[TerminalDestination]:
    attachments = graph.metadata.get("terminal_attachments")
    if not isinstance(attachments, list):
        return []

    terminals: list[TerminalDestination] = []
    next_terminal = 0
    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        router_id = str(attachment["router_id"])
        count = int(attachment.get("count", 0))
        if count <= 0 or router_id not in graph.nodes:
            continue
        leaf_coord = tuple(int(value) for value in graph.nodes[router_id].metadata["coord"])
        for local_index in range(count):
            terminals.append(
                TerminalDestination(
                    terminal_id=next_terminal,
                    router_id=router_id,
                    local_index=local_index,
                    leaf_coord=leaf_coord,
                )
            )
            next_terminal += 1
    return terminals


def destination_router_ids(
    terminals: list[TerminalDestination],
    routers: list[str],
) -> list[str]:
    order = {router_id: index for index, router_id in enumerate(routers)}
    return sorted({terminal.router_id for terminal in terminals}, key=lambda item: order[item])


def first_terminal_by_leaf_router(
    terminals: list[TerminalDestination],
) -> dict[str, TerminalDestination]:
    first: dict[str, TerminalDestination] = {}
    for terminal in terminals:
        first.setdefault(terminal.router_id, terminal)
    return first


def up_down_adjacency(
    graph: TopologyGraph,
    *,
    disabled_links: set[tuple[str, str]] | None = None,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    disabled = set() if disabled_links is None else disabled_links
    routers = router_ids(graph)
    order = {router_id: index for index, router_id in enumerate(routers)}
    up: dict[str, set[str]] = {router_id: set() for router_id in routers}
    down: dict[str, set[str]] = {router_id: set() for router_id in routers}
    for link in graph.links:
        if (link.src, link.dst) in disabled:
            continue
        direction = link.metadata.get("direction")
        if direction == "up":
            up[link.src].add(link.dst)
        elif direction == "down":
            down[link.src].add(link.dst)
    return (
        {router: sorted(neighbors, key=lambda item: order[item]) for router, neighbors in up.items()},
        {router: sorted(neighbors, key=lambda item: order[item]) for router, neighbors in down.items()},
    )


def path_to_terminal(
    graph: TopologyGraph,
    source: str,
    terminal: TerminalDestination,
    up_adjacency: dict[str, list[str]],
    down_adjacency: dict[str, list[str]],
    up_selector: UpSelector,
    *,
    routing_name: str,
) -> list[str]:
    current = source
    path = [current]
    seen = {current}
    while current != terminal.router_id:
        next_hop = None
        if covers_leaf(graph, current, terminal.leaf_coord):
            next_hop = down_neighbor(graph, current, terminal, down_adjacency)
        if next_hop is None:
            next_hop = up_selector(
                graph,
                current,
                terminal,
                up_adjacency,
                down_adjacency,
            )
        if next_hop in seen:
            raise ValueError(
                f"{routing_name} generated a loop while tracing "
                f"{source} -> terminal {terminal.terminal_id}: {path} -> {next_hop}"
            )
        path.append(next_hop)
        seen.add(next_hop)
        current = next_hop
    return path


def covers_leaf(
    graph: TopologyGraph,
    router_id: str,
    leaf_coord: tuple[int, ...],
) -> bool:
    node = graph.nodes[router_id]
    level = int(node.metadata["level"])
    levels = int(graph.metadata["levels"])
    fixed_digits = {
        int(key): int(value) for key, value in node.metadata["fixed_digits"].items()
    }
    for digit_position in range(level + 1, levels):
        if fixed_digits[digit_position] != leaf_coord[digit_position - 1]:
            return False
    return True


def down_neighbor(
    graph: TopologyGraph,
    current: str,
    terminal: TerminalDestination,
    down_adjacency: dict[str, list[str]],
) -> str | None:
    candidates = [
        neighbor
        for neighbor in down_adjacency[current]
        if covers_leaf(graph, neighbor, terminal.leaf_coord)
    ]
    if not candidates:
        return None
    return candidates[0]


def has_down_path(
    graph: TopologyGraph,
    current: str,
    terminal: TerminalDestination,
    down_adjacency: dict[str, list[str]],
) -> bool:
    node = current
    seen = {node}
    while node != terminal.router_id:
        next_hop = down_neighbor(graph, node, terminal, down_adjacency)
        if next_hop is None or next_hop in seen:
            return False
        seen.add(next_hop)
        node = next_hop
    return True


def terminal_rank_from_current(
    graph: TopologyGraph,
    current: str,
    terminal: TerminalDestination,
) -> int:
    node = graph.nodes[current]
    level = int(node.metadata["level"])
    levels = int(graph.metadata["levels"])
    split = int(graph.metadata["split"])
    fixed_digits = {
        int(key): int(value) for key, value in node.metadata["fixed_digits"].items()
    }
    rank = terminal.local_index
    multiplier = split
    for digit_position in range(level + 1):
        if digit_position not in fixed_digits:
            digit = terminal.leaf_coord[digit_position - 1] if digit_position > 0 else 0
            rank += digit * multiplier
            multiplier *= split
    for digit_position in range(level + 1, levels):
        rank += terminal.leaf_coord[digit_position - 1] * multiplier
        multiplier *= split
    return rank


def parse_disabled_links(raw_links: object) -> set[tuple[str, str]]:
    if raw_links is None:
        return set()
    if not isinstance(raw_links, list):
        raise ValueError("disabled_links must be a list")
    disabled: set[tuple[str, str]] = set()
    for item in raw_links:
        if isinstance(item, str):
            if "->" not in item:
                raise ValueError(
                    "disabled link strings must use 'src->dst' format: "
                    f"{item!r}"
                )
            src, dst = item.split("->", 1)
            disabled.add((src.strip(), dst.strip()))
        elif isinstance(item, dict):
            disabled.add((str(item["src"]), str(item["dst"])))
        else:
            raise ValueError(
                "disabled_links entries must be strings or mappings with src/dst"
            )
    return disabled

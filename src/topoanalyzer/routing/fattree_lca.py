from __future__ import annotations

from collections import deque

from topoanalyzer.model.graph import TopologyGraph
from topoanalyzer.model.routing import RoutingTable
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.routing.base import RoutingGenerator
from topoanalyzer.routing.deadlock import channel_dependency_has_cycle


class FatTreeLCARoutingGenerator(RoutingGenerator):
    name = "fattree_lca"

    def validate(self, graph: TopologyGraph) -> ValidationReport:
        report = ValidationReport()
        if graph.topology_type != "fattree":
            report.add_error(
                "fattree_lca routing requires a fattree topology",
                topology_type=graph.topology_type,
            )
        if not graph.routers():
            report.add_error("fattree_lca routing requires at least one router")
        if not graph.is_connected():
            report.add_error("fattree_lca routing requires a connected router graph")
        if not _destination_router_ids(graph):
            report.add_error("fattree_lca routing requires terminal-attached routers")
        return report

    def generate(self, graph: TopologyGraph) -> RoutingTable:
        report = self.validate(graph)
        report.raise_if_errors()

        routers = _router_ids(graph)
        destination_routers = _destination_router_ids(graph)
        up_adjacency, down_adjacency = _up_down_adjacency(graph)
        table = RoutingTable(
            name=self.name,
            metadata={
                "algorithm": "least_common_ancestor_up_down",
                "topology": "fattree",
                "description": (
                    "Routes upward to a nearest common ancestor, then downward to "
                    "the destination leaf router. All routes use VC 0."
                ),
                "destination_routers": destination_routers,
            },
        )

        for source in routers:
            for destination in destination_routers:
                if source == destination:
                    continue
                table.add_path(
                    source,
                    destination,
                    _up_down_path(source, destination, up_adjacency, down_adjacency),
                )

        has_cycle, cycle = channel_dependency_has_cycle(table)
        if has_cycle:
            raise ValueError(f"fattree_lca generated cyclic channel dependencies: {cycle}")
        table.metadata["used_vcs"] = 1
        return table


def _router_ids(graph: TopologyGraph) -> list[str]:
    return [
        node.id
        for node in sorted(
            graph.routers(),
            key=lambda node: (int(node.metadata.get("booksim_order", 0)), node.id),
        )
    ]


def _destination_router_ids(graph: TopologyGraph) -> list[str]:
    attachments = graph.metadata.get("terminal_attachments")
    if not isinstance(attachments, list):
        return _router_ids(graph)
    routers = [
        str(attachment["router_id"])
        for attachment in attachments
        if isinstance(attachment, dict) and int(attachment.get("count", 0)) > 0
    ]
    order = {router_id: index for index, router_id in enumerate(_router_ids(graph))}
    return sorted(set(routers), key=lambda router_id: order[router_id])


def _up_down_adjacency(
    graph: TopologyGraph,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    routers = _router_ids(graph)
    order = {router_id: index for index, router_id in enumerate(routers)}
    up: dict[str, set[str]] = {router_id: set() for router_id in routers}
    down: dict[str, set[str]] = {router_id: set() for router_id in routers}
    for link in graph.links:
        direction = link.metadata.get("direction")
        if direction == "up":
            up[link.src].add(link.dst)
        elif direction == "down":
            down[link.src].add(link.dst)
    return (
        {router: sorted(neighbors, key=lambda item: order[item]) for router, neighbors in up.items()},
        {router: sorted(neighbors, key=lambda item: order[item]) for router, neighbors in down.items()},
    )


def _up_down_path(
    source: str,
    destination: str,
    up_adjacency: dict[str, list[str]],
    down_adjacency: dict[str, list[str]],
) -> list[str]:
    queue: deque[tuple[str, int, list[str]]] = deque([(source, 0, [source])])
    seen = {(source, 0)}
    while queue:
        current, phase, path = queue.popleft()
        if current == destination:
            return path

        transitions: list[tuple[str, int]] = []
        if phase == 0:
            transitions.extend((neighbor, 0) for neighbor in up_adjacency[current])
            transitions.extend((neighbor, 1) for neighbor in down_adjacency[current])
        else:
            transitions.extend((neighbor, 1) for neighbor in down_adjacency[current])

        for neighbor, next_phase in transitions:
            state = (neighbor, next_phase)
            if state in seen or neighbor in path:
                continue
            seen.add(state)
            queue.append((neighbor, next_phase, [*path, neighbor]))
    raise ValueError(f"no fattree_lca up/down route from {source} to {destination}")

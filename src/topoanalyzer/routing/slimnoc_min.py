from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Iterable

from topoanalyzer.model.graph import TopologyGraph
from topoanalyzer.model.routing import RoutingTable
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.routing.base import RoutingGenerator
from topoanalyzer.routing.deadlock import channel_dependency_has_cycle


@dataclass(frozen=True)
class SlimNoCMinimalRoutingGenerator(RoutingGenerator):
    name = "slimnoc_min"

    def validate(self, graph: TopologyGraph) -> ValidationReport:
        report = ValidationReport()
        if graph.topology_type != "slimnoc":
            report.add_error(
                "slimnoc_min routing requires a slimnoc topology",
                topology_type=graph.topology_type,
            )
        for key in ("q", "network_radix", "concentration"):
            if key not in graph.metadata:
                report.add_error("slimnoc graph is missing metadata", key=key)
        if not graph.is_connected():
            report.add_error("slimnoc_min routing requires a connected graph")
        return report

    def generate(self, graph: TopologyGraph) -> RoutingTable:
        report = self.validate(graph)
        report.raise_if_errors()

        routers = sorted(node.id for node in graph.routers())
        adjacency = directed_router_adjacency(graph)
        table = RoutingTable(
            name=self.name,
            metadata={
                "algorithm": "slimnoc_static_min_dijkstra",
                "required_vcs": 2,
                "vc_policy": {
                    "0": "first hop of two-hop minimum routes",
                    "1": "direct routes and final hop of two-hop minimum routes",
                },
            },
        )
        max_hops = 0
        for source in routers:
            for destination in routers:
                if source == destination:
                    continue
                path = shortest_path(adjacency, source, destination)
                max_hops = max(max_hops, len(path) - 1)
                table.add_path(source, destination, path, hop_vcs=minimal_hop_vcs(path))
        table.metadata["max_hops"] = max_hops

        has_cycle, cycle = channel_dependency_has_cycle(table)
        if has_cycle:
            raise ValueError(f"slimnoc_min generated cyclic CDG: {cycle}")
        return table


def directed_router_adjacency(graph: TopologyGraph) -> dict[str, list[str]]:
    routers = {node.id for node in graph.routers()}
    adjacency: dict[str, set[str]] = {router: set() for router in routers}
    for link in graph.links:
        if link.src in routers and link.dst in routers:
            adjacency[link.src].add(link.dst)
    return {router: sorted(neighbors) for router, neighbors in adjacency.items()}


def shortest_path(
    adjacency: dict[str, list[str]],
    source: str,
    destination: str,
    *,
    forbidden_internal: Iterable[str] = (),
) -> list[str]:
    forbidden = set(forbidden_internal)
    queue: deque[list[str]] = deque([[source]])
    seen = {source}
    while queue:
        path = queue.popleft()
        current = path[-1]
        for neighbor in adjacency[current]:
            if neighbor in seen:
                continue
            next_path = [*path, neighbor]
            if neighbor == destination:
                return next_path
            if neighbor in forbidden:
                continue
            seen.add(neighbor)
            queue.append(next_path)
    raise ValueError(f"no path from {source} to {destination}")


def minimal_hop_vcs(path: list[str]) -> list[int]:
    hops = len(path) - 1
    if hops <= 0:
        return []
    if hops == 1:
        return [1]
    return [0] * (hops - 1) + [1]

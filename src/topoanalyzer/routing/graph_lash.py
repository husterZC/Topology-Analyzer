from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from topoanalyzer.model.graph import TopologyGraph
from topoanalyzer.model.routing import RoutingTable
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.routing.base import RoutingGenerator
from topoanalyzer.routing.deadlock import channel_dependency_has_cycle


@dataclass(frozen=True)
class GraphLashRoutingGenerator(RoutingGenerator):
    """LASH-style shortest-path routing with VC layers to break CDG cycles."""

    max_vcs: int = 4
    candidate_paths: int = 8

    name = "graph_lash"

    def validate(self, graph: TopologyGraph) -> ValidationReport:
        report = ValidationReport()
        if self.max_vcs <= 0:
            report.add_error("graph_lash max_vcs must be positive", max_vcs=self.max_vcs)
        if self.candidate_paths <= 0:
            report.add_error(
                "graph_lash candidate_paths must be positive",
                candidate_paths=self.candidate_paths,
            )
        if not graph.routers():
            report.add_error("graph_lash routing requires at least one router")
        if not graph.is_connected():
            report.add_error("graph_lash routing requires a connected router graph")
        return report

    def generate(self, graph: TopologyGraph) -> RoutingTable:
        report = self.validate(graph)
        report.raise_if_errors()

        routers = sorted(node.id for node in graph.routers())
        adjacency = _directed_router_adjacency(graph)
        table = RoutingTable(
            name=self.name,
            metadata={
                "algorithm": "lash",
                "candidate_paths": self.candidate_paths,
                "max_vcs": self.max_vcs,
                "description": (
                    "First-fit assignment of candidate shortest/simple paths to "
                    "VC layers whose channel dependency graph remains acyclic."
                ),
            },
        )

        for source in routers:
            for destination in routers:
                if source == destination:
                    continue
                candidates = _candidate_simple_paths(
                    adjacency,
                    source,
                    destination,
                    limit=self.candidate_paths,
                )
                if not candidates:
                    raise ValueError(f"no route candidates from {source} to {destination}")
                _assign_first_acyclic_candidate(table, source, destination, candidates, self.max_vcs)

        has_cycle, cycle = channel_dependency_has_cycle(table)
        if has_cycle:
            raise ValueError(f"graph_lash generated cyclic channel dependencies: {cycle}")
        table.metadata["used_vcs"] = 1 + max(table.route_vcs.values(), default=0)
        return table


def _assign_first_acyclic_candidate(
    table: RoutingTable,
    source: str,
    destination: str,
    candidates: list[list[str]],
    max_vcs: int,
) -> None:
    for vc in range(max_vcs):
        for path in candidates:
            trial = _copy_table(table)
            trial.add_path(source, destination, path, vc=vc)
            has_cycle, _ = channel_dependency_has_cycle(trial)
            if not has_cycle:
                table.add_path(source, destination, path, vc=vc)
                return
    raise ValueError(
        f"unable to assign deadlock-free route from {source} to {destination} "
        f"with {max_vcs} VCs and {len(candidates)} candidate paths"
    )


def _copy_table(table: RoutingTable) -> RoutingTable:
    copied = RoutingTable(
        name=table.name,
        metadata=dict(table.metadata),
    )
    for (source, destination), path in table.paths.items():
        copied.add_path(source, destination, list(path), vc=table.route_vcs.get((source, destination), 0))
    return copied


def _directed_router_adjacency(graph: TopologyGraph) -> dict[str, list[str]]:
    routers = {node.id for node in graph.routers()}
    adjacency: dict[str, set[str]] = {router: set() for router in routers}
    for link in graph.links:
        if link.src in routers and link.dst in routers:
            adjacency[link.src].add(link.dst)
    return {router: sorted(neighbors) for router, neighbors in adjacency.items()}


def _candidate_simple_paths(
    adjacency: dict[str, list[str]],
    source: str,
    destination: str,
    *,
    limit: int,
) -> list[list[str]]:
    # Uniform-cost BFS enumerates simple paths in nondecreasing hop count.
    queue: deque[list[str]] = deque([[source]])
    candidates: list[list[str]] = []
    best_len: int | None = None
    max_extra_hops = 2
    while queue and len(candidates) < limit:
        path = queue.popleft()
        if best_len is not None and len(path) > best_len + max_extra_hops:
            continue
        current = path[-1]
        for neighbor in adjacency[current]:
            if neighbor in path:
                continue
            next_path = [*path, neighbor]
            if neighbor == destination:
                if best_len is None:
                    best_len = len(next_path)
                candidates.append(next_path)
                if len(candidates) >= limit:
                    break
            else:
                queue.append(next_path)
    return candidates

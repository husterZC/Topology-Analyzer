from __future__ import annotations

from collections import deque

from topoanalyzer.model.graph import TopologyGraph
from topoanalyzer.model.routing import RoutingTable
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.routing.base import RoutingGenerator
from topoanalyzer.routing.deadlock import channel_dependency_has_cycle


class GraphUpDownRoutingGenerator(RoutingGenerator):
    """Generate deadlock-free routes from a graph using up*/down* tree routing."""

    name = "graph_updown"

    def __init__(self, root: str | None = None) -> None:
        self.root = root

    def validate(self, graph: TopologyGraph) -> ValidationReport:
        report = ValidationReport()
        routers = [node.id for node in graph.routers()]
        if not routers:
            report.add_error("graph_updown routing requires at least one router")
            return report
        if self.root is not None and self.root not in routers:
            report.add_error("graph_updown root is not a router", root=self.root)
        if not graph.is_connected():
            report.add_error("graph_updown routing requires a connected router graph")
        return report

    def generate(self, graph: TopologyGraph) -> RoutingTable:
        report = self.validate(graph)
        report.raise_if_errors()

        root = self.root or sorted(node.id for node in graph.routers())[0]
        tree = _build_bfs_tree(graph, root)
        table = RoutingTable(
            name=self.name,
            metadata={
                "algorithm": "up_down",
                "root": root,
                "parent": tree.parent,
                "depth": tree.depth,
                "note": "Routes use the BFS spanning tree; non-tree links are not used.",
            },
        )
        routers = sorted(node.id for node in graph.routers())
        for src in routers:
            for dst in routers:
                if src == dst:
                    continue
                table.add_path(src, dst, _tree_path(src, dst, tree.parent, tree.depth))

        has_cycle, cycle = channel_dependency_has_cycle(table)
        if has_cycle:
            raise ValueError(f"graph_updown generated cyclic channel dependencies: {cycle}")
        return table


class _Tree:
    def __init__(self, parent: dict[str, str | None], depth: dict[str, int]) -> None:
        self.parent = parent
        self.depth = depth


def _build_bfs_tree(graph: TopologyGraph, root: str) -> _Tree:
    adjacency = _undirected_router_adjacency(graph)
    parent: dict[str, str | None] = {root: None}
    depth: dict[str, int] = {root: 0}
    queue: deque[str] = deque([root])

    while queue:
        current = queue.popleft()
        for neighbor in adjacency[current]:
            if neighbor in parent:
                continue
            parent[neighbor] = current
            depth[neighbor] = depth[current] + 1
            queue.append(neighbor)

    missing = set(adjacency) - set(parent)
    if missing:
        raise ValueError(f"router graph is disconnected; missing routers: {sorted(missing)}")
    return _Tree(parent=parent, depth=depth)


def _undirected_router_adjacency(graph: TopologyGraph) -> dict[str, list[str]]:
    routers = {node.id for node in graph.routers()}
    adjacency: dict[str, set[str]] = {router: set() for router in routers}
    for link in graph.links:
        if link.src in routers and link.dst in routers:
            adjacency[link.src].add(link.dst)
            adjacency[link.dst].add(link.src)
    return {router: sorted(neighbors) for router, neighbors in adjacency.items()}


def _tree_path(
    src: str,
    dst: str,
    parent: dict[str, str | None],
    depth: dict[str, int],
) -> list[str]:
    src_chain = _ancestor_chain(src, parent)
    dst_chain = _ancestor_chain(dst, parent)
    dst_index = {node: index for index, node in enumerate(dst_chain)}
    for src_index, node in enumerate(src_chain):
        if node not in dst_index:
            continue
        dst_lca_index = dst_index[node]
        return src_chain[: src_index + 1] + list(reversed(dst_chain[:dst_lca_index]))
    raise ValueError(f"failed to find common ancestor from {src} to {dst}")


def _ancestor_chain(node: str, parent: dict[str, str | None]) -> list[str]:
    chain = [node]
    current = node
    while parent[current] is not None:
        current = parent[current]
        chain.append(current)
    return chain

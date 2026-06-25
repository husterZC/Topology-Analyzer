from __future__ import annotations

from dataclasses import dataclass

from topoanalyzer.model.graph import TopologyGraph
from topoanalyzer.model.routing import RoutingTable
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.routing.base import RoutingGenerator
from topoanalyzer.routing.deadlock import channel_dependency_has_cycle


@dataclass(frozen=True)
class DragonflyMinimalRoutingGenerator(RoutingGenerator):
    name = "dragonfly_min"

    def validate(self, graph: TopologyGraph) -> ValidationReport:
        report = ValidationReport()
        if graph.topology_type != "dragonfly":
            report.add_error(
                "dragonfly_min routing requires a dragonfly topology",
                topology_type=graph.topology_type,
            )
        for key in ("p", "a", "h", "groups"):
            if key not in graph.metadata:
                report.add_error("dragonfly graph is missing metadata", key=key)
        if not graph.is_connected():
            report.add_error("dragonfly_min routing requires a connected graph")
        return report

    def generate(self, graph: TopologyGraph) -> RoutingTable:
        report = self.validate(graph)
        report.raise_if_errors()

        global_links = _global_links_by_group_pair(graph)
        table = RoutingTable(
            name=self.name,
            metadata={
                "algorithm": "dragonfly_minimal",
                "vc_policy": {
                    "0": "source-group local hop and global hop",
                    "1": "destination-group local hop",
                },
                "required_vcs": 2,
            },
        )
        routers = sorted(node.id for node in graph.routers())
        for src in routers:
            for dst in routers:
                if src == dst:
                    continue
                path, hop_vcs = _minimal_path(graph, global_links, src, dst)
                table.add_path(src, dst, path, hop_vcs=hop_vcs)

        has_cycle, cycle = channel_dependency_has_cycle(table)
        if has_cycle:
            raise ValueError(
                f"dragonfly_min generated cyclic channel dependencies: {cycle}"
            )
        return table


def _minimal_path(
    graph: TopologyGraph,
    global_links: dict[tuple[int, int], tuple[str, str]],
    src: str,
    dst: str,
) -> tuple[list[str], list[int]]:
    src_group = int(graph.nodes[src].metadata["group"])
    dst_group = int(graph.nodes[dst].metadata["group"])
    if src_group == dst_group:
        return [src, dst], [1]

    try:
        global_src, global_dst = global_links[(src_group, dst_group)]
    except KeyError as exc:
        raise ValueError(
            f"dragonfly graph has no global link from group {src_group} "
            f"to group {dst_group}"
        ) from exc

    path = [src]
    hop_vcs: list[int] = []
    if src != global_src:
        path.append(global_src)
        hop_vcs.append(0)
    path.append(global_dst)
    hop_vcs.append(0)
    if global_dst != dst:
        path.append(dst)
        hop_vcs.append(1)
    return path, hop_vcs


def _global_links_by_group_pair(
    graph: TopologyGraph,
) -> dict[tuple[int, int], tuple[str, str]]:
    global_links: dict[tuple[int, int], tuple[str, str]] = {}
    for link in graph.links:
        if link.metadata.get("class") != "global":
            continue
        src_group = int(graph.nodes[link.src].metadata["group"])
        dst_group = int(graph.nodes[link.dst].metadata["group"])
        global_links[(src_group, dst_group)] = (link.src, link.dst)
    return global_links

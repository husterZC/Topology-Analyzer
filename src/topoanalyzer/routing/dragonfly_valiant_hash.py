from __future__ import annotations

from dataclasses import dataclass

from topoanalyzer.model.graph import TopologyGraph
from topoanalyzer.model.routing import RoutingTable
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.routing.base import RoutingGenerator
from topoanalyzer.routing.deadlock import channel_dependency_has_cycle
from topoanalyzer.routing.dragonfly_min import _global_links_by_group_pair, _minimal_path
from topoanalyzer.routing.static import stable_hash_int


@dataclass(frozen=True)
class DragonflyValiantHashRoutingGenerator(RoutingGenerator):
    seed: int = 0
    nonminimal_same_group: bool = False

    name = "dragonfly_valiant_hash"

    def validate(self, graph: TopologyGraph) -> ValidationReport:
        report = ValidationReport()
        if graph.topology_type != "dragonfly":
            report.add_error(
                "dragonfly_valiant_hash routing requires a dragonfly topology",
                topology_type=graph.topology_type,
            )
        for key in ("p", "a", "h", "groups"):
            if key not in graph.metadata:
                report.add_error("dragonfly graph is missing metadata", key=key)
        if not graph.is_connected():
            report.add_error("dragonfly_valiant_hash routing requires a connected graph")
        return report

    def generate(self, graph: TopologyGraph) -> RoutingTable:
        report = self.validate(graph)
        report.raise_if_errors()

        global_links = _global_links_by_group_pair(graph)
        groups = int(graph.metadata["groups"])
        table = RoutingTable(
            name=self.name,
            metadata={
                "algorithm": "dragonfly_valiant_hash",
                "seed": self.seed,
                "nonminimal_same_group": self.nonminimal_same_group,
                "vc_policy": {
                    "0": "source-group local hop and first global hop",
                    "1": "intermediate-group local hop",
                    "2": "second global hop",
                    "3": "destination-group local hop",
                },
                "required_vcs": 4,
            },
        )
        routers = sorted(node.id for node in graph.routers())
        for src in routers:
            for dst in routers:
                if src == dst:
                    continue
                path, hop_vcs = _valiant_path(
                    graph,
                    global_links,
                    groups,
                    src,
                    dst,
                    seed=self.seed,
                    nonminimal_same_group=self.nonminimal_same_group,
                )
                table.add_path(src, dst, path, hop_vcs=hop_vcs)

        has_cycle, cycle = channel_dependency_has_cycle(table)
        if has_cycle:
            raise ValueError(
                f"dragonfly_valiant_hash generated cyclic CDG: {cycle}"
            )
        return table


def _valiant_path(
    graph: TopologyGraph,
    global_links: dict[tuple[int, int], tuple[str, str]],
    groups: int,
    src: str,
    dst: str,
    *,
    seed: int,
    nonminimal_same_group: bool,
) -> tuple[list[str], list[int]]:
    src_group = int(graph.nodes[src].metadata["group"])
    dst_group = int(graph.nodes[dst].metadata["group"])
    if src_group == dst_group and not nonminimal_same_group:
        return [src, dst], [3]

    candidates = [
        group
        for group in range(groups)
        if group != src_group and group != dst_group
    ]
    if not candidates:
        return _minimal_path(graph, global_links, src, dst)

    intermediate_group = min(
        candidates,
        key=lambda group: stable_hash_int(src, dst, group, seed=seed),
    )
    path = [src]
    hop_vcs: list[int] = []

    current = _append_group_hop(
        graph,
        global_links,
        path,
        hop_vcs,
        current=src,
        current_group=src_group,
        target_group=intermediate_group,
        local_vc=0,
        global_vc=0,
    )
    current = _append_group_hop(
        graph,
        global_links,
        path,
        hop_vcs,
        current=current,
        current_group=intermediate_group,
        target_group=dst_group,
        local_vc=1,
        global_vc=2,
    )
    if current != dst:
        path.append(dst)
        hop_vcs.append(3)
    return path, hop_vcs


def _append_group_hop(
    graph: TopologyGraph,
    global_links: dict[tuple[int, int], tuple[str, str]],
    path: list[str],
    hop_vcs: list[int],
    *,
    current: str,
    current_group: int,
    target_group: int,
    local_vc: int,
    global_vc: int,
) -> str:
    try:
        global_src, global_dst = global_links[(current_group, target_group)]
    except KeyError as exc:
        raise ValueError(
            f"dragonfly graph has no global link from group {current_group} "
            f"to group {target_group}"
        ) from exc
    if current != global_src:
        if int(graph.nodes[current].metadata["group"]) != current_group:
            raise ValueError(f"router {current} is not in group {current_group}")
        path.append(global_src)
        hop_vcs.append(local_vc)
    path.append(global_dst)
    hop_vcs.append(global_vc)
    return global_dst

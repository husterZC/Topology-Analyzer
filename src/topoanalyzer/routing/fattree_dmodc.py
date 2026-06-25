from __future__ import annotations

from topoanalyzer.model.graph import TopologyGraph
from topoanalyzer.model.routing import RoutingTable
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.routing.base import RoutingGenerator
from topoanalyzer.routing.fattree_common import (
    TerminalDestination,
    generate_terminal_aware_nca_table,
    has_down_path,
    validate_fattree_terminal_routing,
)


class FatTreeDmodcRoutingGenerator(RoutingGenerator):
    name = "fattree_dmodc"

    def __init__(self, disabled_links: set[tuple[str, str]] | None = None):
        self.disabled_links = set() if disabled_links is None else set(disabled_links)

    def validate(self, graph: TopologyGraph) -> ValidationReport:
        report = validate_fattree_terminal_routing(graph, routing_name=self.name)
        routers = {node.id for node in graph.routers()}
        graph_links = {(link.src, link.dst) for link in graph.links}
        for src, dst in sorted(self.disabled_links):
            if src not in routers or dst not in routers:
                report.add_error(
                    "fattree_dmodc disabled link references unknown router",
                    src=src,
                    dst=dst,
                )
            elif (src, dst) not in graph_links:
                report.add_error(
                    "fattree_dmodc disabled link is not a graph link",
                    src=src,
                    dst=dst,
                )
        return report

    def generate(self, graph: TopologyGraph) -> RoutingTable:
        report = self.validate(graph)
        report.raise_if_errors()
        return generate_terminal_aware_nca_table(
            graph,
            routing_name=self.name,
            metadata={
                "algorithm": "nearest_common_ancestor_dmodc_style",
                "description": (
                    "Routes upward until a viable downward path to the destination "
                    "leaf exists. Upward equal-cost choices use a compressed "
                    "destination modulo rule over currently viable parents."
                ),
                "fault_model": "disabled_links_are_avoided_by_the_route_table",
            },
            up_selector=self._select_up_neighbor,
            disabled_links=self.disabled_links,
        )

    def _select_up_neighbor(
        self,
        graph: TopologyGraph,
        current: str,
        terminal: TerminalDestination,
        up_adjacency: dict[str, list[str]],
        down_adjacency: dict[str, list[str]],
    ) -> str:
        candidates = [
            candidate
            for candidate in up_adjacency[current]
            if has_down_path(graph, candidate, terminal, down_adjacency)
            or up_adjacency[candidate]
        ]
        if not candidates:
            raise ValueError(
                "no fattree_dmodc viable upward route from "
                f"{current} to terminal {terminal.terminal_id}"
            )
        rank = _level_modulo_rank(graph, current, terminal)
        return candidates[rank % len(candidates)]


def _level_modulo_rank(
    graph: TopologyGraph,
    current: str,
    terminal: TerminalDestination,
) -> int:
    split = int(graph.metadata["split"])
    level = int(graph.nodes[current].metadata["level"])
    return terminal.terminal_id // (split**level)

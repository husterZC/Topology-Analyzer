from __future__ import annotations

from topoanalyzer.model.graph import TopologyGraph
from topoanalyzer.model.routing import RoutingTable
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.routing.base import RoutingGenerator
from topoanalyzer.routing.fattree_common import (
    TerminalDestination,
    generate_terminal_aware_nca_table,
    validate_fattree_terminal_routing,
)


class FatTreeDmodKRoutingGenerator(RoutingGenerator):
    name = "fattree_dmodk"

    def validate(self, graph: TopologyGraph) -> ValidationReport:
        return validate_fattree_terminal_routing(graph, routing_name=self.name)

    def generate(self, graph: TopologyGraph) -> RoutingTable:
        report = self.validate(graph)
        report.raise_if_errors()
        return generate_terminal_aware_nca_table(
            graph,
            routing_name=self.name,
            metadata={
                "algorithm": "nearest_common_ancestor_d_mod_k",
                "description": (
                    "Routes upward until the destination leaf can be reached by "
                    "downward hops. Upward equal-cost choices use a deterministic "
                    "destination modulo rule."
                ),
            },
            up_selector=self._select_up_neighbor,
        )

    def _select_up_neighbor(
        self,
        graph: TopologyGraph,
        current: str,
        terminal: TerminalDestination,
        up_adjacency: dict[str, list[str]],
        down_adjacency: dict[str, list[str]],
    ) -> str:
        candidates = up_adjacency[current]
        if not candidates:
            raise ValueError(
                "no fattree_dmodk upward route from "
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

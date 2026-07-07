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


class FatTreeANCARoutingGenerator(RoutingGenerator):
    name = "fattree_anca"

    def validate(self, graph: TopologyGraph) -> ValidationReport:
        return validate_fattree_terminal_routing(graph, routing_name=self.name)

    def generate(self, graph: TopologyGraph) -> RoutingTable:
        report = self.validate(graph)
        report.raise_if_errors()
        metadata = {
            "algorithm": "booksim_runtime_anca",
            "description": (
                "Marker routing table for BookSim native adaptive nearest "
                "common ancestor Fat-tree routing. The static paths validate "
                "the topology but are not used by the stock_fattree backend."
            ),
        }
        if graph.metadata.get("root_mode") == "full":
            metadata = {
                "algorithm": "nearest_common_ancestor_anca_representative",
                "description": (
                    "Full-root Fat-tree representative ANCA/NCA routes. "
                    "BookSim's native Fat-tree backend models the half-root "
                    "shape, so full-root systems use the table-driven anynet "
                    "backend."
                ),
                "booksim_backend": "anynet_table",
            }
        else:
            metadata["booksim_runtime_routing"] = {
                "backend": "stock_fattree",
                "topology": "fattree",
                "routing_function": "anca",
            }
        table = generate_terminal_aware_nca_table(
            graph,
            routing_name=self.name,
            metadata=metadata,
            up_selector=self._select_up_neighbor,
        )
        return table

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
                "no fattree_anca representative upward route from "
                f"{current} to terminal {terminal.terminal_id}"
            )
        return candidates[terminal.terminal_id % len(candidates)]

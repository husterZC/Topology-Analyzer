from __future__ import annotations

import hashlib

from topoanalyzer.model.graph import TopologyGraph
from topoanalyzer.model.routing import RoutingTable
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.routing.base import RoutingGenerator
from topoanalyzer.routing.fattree_common import (
    TerminalDestination,
    generate_terminal_aware_nca_table,
    validate_fattree_terminal_routing,
)


class FatTreeNCAHashRoutingGenerator(RoutingGenerator):
    name = "fattree_nca_hash"

    def __init__(self, seed: int = 0):
        self.seed = seed

    def validate(self, graph: TopologyGraph) -> ValidationReport:
        return validate_fattree_terminal_routing(graph, routing_name=self.name)

    def generate(self, graph: TopologyGraph) -> RoutingTable:
        report = self.validate(graph)
        report.raise_if_errors()

        return generate_terminal_aware_nca_table(
            graph,
            routing_name=self.name,
            metadata={
                "algorithm": "nearest_common_ancestor_destination_hash",
                "hash_seed": self.seed,
                "description": (
                    "Routes upward until the destination leaf can be reached by "
                    "downward hops. Upward equal-cost choices are selected by a "
                    "stable hash of the current router and destination terminal."
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
                "no fattree_nca_hash upward route from "
                f"{current} to terminal {terminal.terminal_id}"
            )
        digest = hashlib.blake2s(
            f"{self.seed}:{current}:{terminal.terminal_id}".encode("ascii"),
            digest_size=8,
        ).digest()
        index = int.from_bytes(digest, "big") % len(candidates)
        return candidates[index]

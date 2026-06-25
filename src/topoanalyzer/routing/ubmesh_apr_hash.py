from __future__ import annotations

from dataclasses import dataclass

from topoanalyzer.model.graph import TopologyGraph
from topoanalyzer.model.routing import RoutingTable
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.routing.base import RoutingGenerator
from topoanalyzer.routing.deadlock import channel_dependency_has_cycle
from topoanalyzer.routing.ubmesh_common import (
    generate_apr_hash_table,
    validate_ubmesh_graph,
)


@dataclass(frozen=True)
class UBMeshAPRHashRoutingGenerator(RoutingGenerator):
    seed: int = 0

    name = "ubmesh_apr_hash"

    def validate(self, graph: TopologyGraph) -> ValidationReport:
        return validate_ubmesh_graph(graph, routing_name=self.name)

    def generate(self, graph: TopologyGraph) -> RoutingTable:
        report = self.validate(graph)
        report.raise_if_errors()

        table = generate_apr_hash_table(
            graph,
            routing_name=self.name,
            algorithm="ubmesh_static_apr_hash",
            seed=self.seed,
            description=(
                "Static APR-style UBMesh baseline. A stable hash chooses a "
                "detour router, then each segment uses deterministic DOR. This "
                "spreads traffic over non-minimal all-path candidates while "
                "remaining exportable as a static BookSim anynet route table."
            ),
        )

        has_cycle, cycle = channel_dependency_has_cycle(table)
        if has_cycle:
            raise ValueError(f"ubmesh_apr_hash generated cyclic CDG: {cycle}")
        return table

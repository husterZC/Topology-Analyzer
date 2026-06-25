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
class UBMeshTFCRoutingGenerator(RoutingGenerator):
    seed: int = 0

    name = "ubmesh_tfc"

    def validate(self, graph: TopologyGraph) -> ValidationReport:
        return validate_ubmesh_graph(graph, routing_name=self.name)

    def generate(self, graph: TopologyGraph) -> RoutingTable:
        report = self.validate(graph)
        report.raise_if_errors()

        table = generate_apr_hash_table(
            graph,
            routing_name=self.name,
            algorithm="ubmesh_tfc_static_approximation",
            seed=self.seed,
            description=(
                "Static approximation of the paper's TFC virtual-lane policy. "
                "The route path is APR-hash style; VC 0 carries the first DOR "
                "segment and VC 1 carries the post-detour DOR segment."
            ),
            extra_metadata={
                "tfc_model": "two_virtual_lanes_segment_phase_split",
                "paper_note": (
                    "The UBMesh paper states that TFC uses two VLs but omits "
                    "the full algorithmic detail; this generator is a "
                    "conservative static approximation for table-driven BookSim."
                ),
            },
        )

        has_cycle, cycle = channel_dependency_has_cycle(table)
        if has_cycle:
            raise ValueError(f"ubmesh_tfc generated cyclic CDG: {cycle}")
        return table

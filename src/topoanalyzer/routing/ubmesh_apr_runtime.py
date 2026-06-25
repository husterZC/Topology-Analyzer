from __future__ import annotations

from dataclasses import dataclass

from topoanalyzer.model.graph import TopologyGraph
from topoanalyzer.model.routing import RoutingTable
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.routing.base import RoutingGenerator
from topoanalyzer.routing.deadlock import channel_dependency_has_cycle
from topoanalyzer.routing.ubmesh_common import (
    dor_path,
    router_coords,
    validate_ubmesh_graph,
)


@dataclass(frozen=True)
class UBMeshAPRRuntimeRoutingGenerator(RoutingGenerator):
    seed: int = 0

    name = "ubmesh_apr_runtime"

    def validate(self, graph: TopologyGraph) -> ValidationReport:
        return validate_ubmesh_graph(graph, routing_name=self.name)

    def generate(self, graph: TopologyGraph) -> RoutingTable:
        report = self.validate(graph)
        report.raise_if_errors()

        coords_by_router = router_coords(graph)
        routers = sorted(coords_by_router)
        table = RoutingTable(
            name=self.name,
            metadata={
                "algorithm": "booksim_runtime_ubmesh_apr",
                "description": (
                    "Marker routing table for BookSim runtime UBMesh APR. The "
                    "static DOR paths validate graph reachability; benchmarks "
                    "must use booksim.backend: auto or ubmesh_apr_runtime so "
                    "BookSim chooses output ports adaptively at runtime."
                ),
                "booksim_runtime_routing": {
                    "backend": "ubmesh_apr_runtime",
                    "topology": "anynet",
                    "routing_function": "ubmesh_apr",
                    "seed": self.seed,
                    "vc_policy": "tfc_two_virtual_lanes",
                },
                "required_vcs": 2,
            },
        )
        max_hops = 0
        for source in routers:
            for destination in routers:
                if source == destination:
                    continue
                path = dor_path(coords_by_router[source], coords_by_router[destination])
                max_hops = max(max_hops, len(path) - 1)
                table.add_path(source, destination, path, vc=0)
        table.metadata["max_hops"] = max_hops

        has_cycle, cycle = channel_dependency_has_cycle(table)
        if has_cycle:
            raise ValueError(f"ubmesh_apr_runtime representative table has cyclic CDG: {cycle}")
        return table

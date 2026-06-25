from __future__ import annotations

from topoanalyzer.model.graph import TopologyGraph
from topoanalyzer.model.routing import RoutingTable
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.routing.base import RoutingGenerator
from topoanalyzer.routing.deadlock import channel_dependency_has_cycle
from topoanalyzer.routing.ubmesh_common import (
    minimal_phase_vcs,
    router_coords,
    shortest_latency_path,
    validate_ubmesh_graph,
)


class UBMeshShortestRoutingGenerator(RoutingGenerator):
    name = "ubmesh_shortest"

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
                "algorithm": "ubmesh_latency_ordered_shortest",
                "description": (
                    "Minimum-hop nD-FullMesh routing. At each hop it fixes the "
                    "remaining destination dimension with the lowest direct-link "
                    "latency, then uses monotonic VC phases to keep the static "
                    "table deadlock-free when heterogeneous links change the "
                    "dimension order."
                ),
                "required_vcs": max(1, int(graph.metadata["diameter"])),
            },
        )
        max_hops = 0
        for source in routers:
            for destination in routers:
                if source == destination:
                    continue
                path = shortest_latency_path(
                    graph,
                    coords_by_router[source],
                    coords_by_router[destination],
                )
                max_hops = max(max_hops, len(path) - 1)
                table.add_path(source, destination, path, hop_vcs=minimal_phase_vcs(path))
        table.metadata["max_hops"] = max_hops

        has_cycle, cycle = channel_dependency_has_cycle(table)
        if has_cycle:
            raise ValueError(f"ubmesh_shortest generated cyclic CDG: {cycle}")
        return table

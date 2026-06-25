from __future__ import annotations

from dataclasses import dataclass

from topoanalyzer.model.graph import TopologyGraph
from topoanalyzer.model.routing import RoutingTable
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.routing.base import RoutingGenerator
from topoanalyzer.routing.deadlock import channel_dependency_has_cycle
from topoanalyzer.routing.ubmesh_common import (
    dimension_count,
    dor_path,
    router_coords,
    validate_ubmesh_graph,
)


@dataclass(frozen=True)
class UBMeshDORRoutingGenerator(RoutingGenerator):
    dimension_order: tuple[int, ...] | None = None

    name = "ubmesh_dor"

    def validate(self, graph: TopologyGraph) -> ValidationReport:
        report = validate_ubmesh_graph(graph, routing_name=self.name)
        if self.dimension_order is not None:
            expected = list(range(dimension_count(graph)))
            if sorted(self.dimension_order) != expected:
                report.add_error(
                    "ubmesh_dor dimension_order must contain every dimension exactly once",
                    dimension_order=list(self.dimension_order),
                    expected=expected,
                )
        return report

    def generate(self, graph: TopologyGraph) -> RoutingTable:
        report = self.validate(graph)
        report.raise_if_errors()

        coords_by_router = router_coords(graph)
        routers = sorted(coords_by_router)
        order = self.dimension_order or tuple(range(dimension_count(graph)))
        table = RoutingTable(
            name=self.name,
            metadata={
                "algorithm": "ubmesh_dimension_order",
                "dimension_order": list(order),
                "description": (
                    "Deterministic dimension-order routing over the nD-FullMesh "
                    "graph. Each differing coordinate is fixed with one direct "
                    "full-mesh hop."
                ),
                "required_vcs": 1,
            },
        )
        max_hops = 0
        for source in routers:
            for destination in routers:
                if source == destination:
                    continue
                path = dor_path(
                    coords_by_router[source],
                    coords_by_router[destination],
                    dimension_order=order,
                )
                max_hops = max(max_hops, len(path) - 1)
                table.add_path(source, destination, path, vc=0)
        table.metadata["max_hops"] = max_hops

        has_cycle, cycle = channel_dependency_has_cycle(table)
        if has_cycle:
            raise ValueError(f"ubmesh_dor generated cyclic CDG: {cycle}")
        return table

from __future__ import annotations

from topoanalyzer.model.graph import TopologyGraph
from topoanalyzer.model.routing import RoutingTable
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.routing.base import RoutingGenerator
from topoanalyzer.topologies.hypercube import router_id


class HypercubeECubeRoutingGenerator(RoutingGenerator):
    name = "hypercube_ecube"

    def validate(self, graph: TopologyGraph) -> ValidationReport:
        report = ValidationReport()
        if graph.topology_type != "hypercube":
            report.add_error(
                "hypercube_ecube routing requires a hypercube topology",
                topology_type=graph.topology_type,
            )
        if "dimension" not in graph.metadata:
            report.add_error("hypercube graph is missing dimension metadata")
        return report

    def generate(self, graph: TopologyGraph) -> RoutingTable:
        report = self.validate(graph)
        report.raise_if_errors()

        dimension = int(graph.metadata["dimension"])
        table = RoutingTable(
            name=self.name,
            metadata={
                "algorithm": "e_cube",
                "dimension_order": list(range(dimension)),
                "bit_order": "least_significant_first",
            },
        )
        routers = [
            (node.id, int(node.metadata["value"]))
            for node in graph.routers()
        ]
        for src_id, src_value in routers:
            for dst_id, dst_value in routers:
                if src_id == dst_id:
                    continue
                table.add_path(src_id, dst_id, _ecube_path(src_value, dst_value, dimension))
        return table


def _ecube_path(src: int, dst: int, dimension: int) -> list[str]:
    current = src
    path = [router_id(current)]
    diff = src ^ dst
    for bit in range(dimension):
        if diff & (1 << bit):
            current ^= 1 << bit
            path.append(router_id(current))
    return path

from __future__ import annotations

from dataclasses import dataclass

from topoanalyzer.model.graph import TopologyGraph
from topoanalyzer.model.routing import RoutingTable
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.routing.base import RoutingGenerator
from topoanalyzer.routing.graph_lash import GraphLashRoutingGenerator


@dataclass(frozen=True)
class Ruche3DLashRoutingGenerator(RoutingGenerator):
    max_vcs: int = 8
    candidate_paths: int = 8

    name = "ruche_lash"

    def validate(self, graph: TopologyGraph) -> ValidationReport:
        report = ValidationReport()
        if graph.topology_type != "ruche3d":
            report.add_error(
                "ruche_lash routing requires a ruche3d topology",
                topology_type=graph.topology_type,
            )
        report.merge(
            GraphLashRoutingGenerator(
                max_vcs=self.max_vcs,
                candidate_paths=self.candidate_paths,
            ).validate(graph)
        )
        return report

    def generate(self, graph: TopologyGraph) -> RoutingTable:
        report = self.validate(graph)
        report.raise_if_errors()

        table = GraphLashRoutingGenerator(
            max_vcs=self.max_vcs,
            candidate_paths=self.candidate_paths,
        ).generate(graph)
        table.name = self.name
        table.metadata.update(
            {
                "algorithm": "ruche_lash",
                "base_algorithm": "lash",
                "description": (
                    "Ruche-specialized wrapper around LASH shortest-path "
                    "routing. Express links are considered normal graph "
                    "edges and VC layers are assigned to keep the CDG acyclic."
                ),
            }
        )
        return table

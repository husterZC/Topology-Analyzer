from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from topoanalyzer.model.graph import TopologyGraph
from topoanalyzer.model.links import LinkParameters
from topoanalyzer.model.routing import RoutingTable
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.routing.deadlock import channel_dependency_has_cycle


@dataclass
class System:
    name: str
    topology_type: str
    topology_params: dict[str, Any]
    link_params: LinkParameters
    graph: TopologyGraph
    routing_table: RoutingTable
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> ValidationReport:
        report = ValidationReport()
        if not self.graph.nodes:
            report.add_error("system graph has no nodes")
        if not self.graph.is_connected():
            report.add_error("router graph is not connected")

        routers = [node.id for node in self.graph.routers()]
        for src in routers:
            for dst in routers:
                if src == dst:
                    continue
                path = self.routing_table.paths.get((src, dst))
                if not path:
                    report.add_error("missing route", source=src, destination=dst)
                    continue
                if path[0] != src or path[-1] != dst:
                    report.add_error(
                        "route path endpoints do not match route key",
                        source=src,
                        destination=dst,
                        path=path,
                    )
                for current, next_hop in zip(path[:-1], path[1:]):
                    if self.graph.link_between(current, next_hop) is None:
                        report.add_error(
                            "route uses non-adjacent hop",
                            source=src,
                            destination=dst,
                            current=current,
                            next_hop=next_hop,
                        )

        has_cycle, cycle = channel_dependency_has_cycle(self.routing_table)
        if has_cycle:
            report.add_error("routing channel dependency graph has a cycle", cycle=cycle)
        return report

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "topology_type": self.topology_type,
            "topology_params": dict(self.topology_params),
            "link_params": self.link_params.to_dict(),
            "graph": self.graph.to_dict(),
            "routing_table": self.routing_table.to_dict(),
            "metadata": dict(self.metadata),
        }

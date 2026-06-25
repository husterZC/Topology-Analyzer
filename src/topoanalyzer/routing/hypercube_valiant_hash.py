from __future__ import annotations

from dataclasses import dataclass

from topoanalyzer.model.graph import TopologyGraph
from topoanalyzer.model.routing import RoutingTable
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.routing.base import RoutingGenerator
from topoanalyzer.routing.deadlock import channel_dependency_has_cycle
from topoanalyzer.routing.hypercube_ecube import _ecube_path
from topoanalyzer.routing.static import stable_hash_int


@dataclass(frozen=True)
class HypercubeValiantHashRoutingGenerator(RoutingGenerator):
    seed: int = 0

    name = "hypercube_valiant_hash"

    def validate(self, graph: TopologyGraph) -> ValidationReport:
        report = ValidationReport()
        if graph.topology_type != "hypercube":
            report.add_error(
                "hypercube_valiant_hash routing requires a hypercube topology",
                topology_type=graph.topology_type,
            )
        if "dimension" not in graph.metadata:
            report.add_error("hypercube graph is missing dimension metadata")
        return report

    def generate(self, graph: TopologyGraph) -> RoutingTable:
        report = self.validate(graph)
        report.raise_if_errors()

        dimension = int(graph.metadata["dimension"])
        values = [int(node.metadata["value"]) for node in graph.routers()]
        table = RoutingTable(
            name=self.name,
            metadata={
                "algorithm": "hypercube_valiant_hash",
                "seed": self.seed,
                "vc_policy": {
                    "0": "source to hashed intermediate",
                    "1": "intermediate to destination",
                },
                "required_vcs": 2,
            },
        )
        for src in values:
            for dst in values:
                if src == dst:
                    continue
                path, hop_vcs = _valiant_path(
                    src,
                    dst,
                    values,
                    dimension,
                    seed=self.seed,
                )
                table.add_path(path[0], path[-1], path, hop_vcs=hop_vcs)

        has_cycle, cycle = channel_dependency_has_cycle(table)
        if has_cycle:
            raise ValueError(
                f"hypercube_valiant_hash generated cyclic CDG: {cycle}"
            )
        return table


def _valiant_path(
    src: int,
    dst: int,
    values: list[int],
    dimension: int,
    *,
    seed: int,
) -> tuple[list[str], list[int]]:
    candidates = [value for value in values if value not in {src, dst}]
    candidates.sort(key=lambda value: stable_hash_int(src, dst, value, seed=seed))
    dst_id = _ecube_path(dst, dst, dimension)[0]
    for intermediate in candidates:
        first = _ecube_path(src, intermediate, dimension)
        second = _ecube_path(intermediate, dst, dimension)
        path = first + second[1:]
        if path[-1] != dst_id:
            continue
        if path.count(dst_id) != 1:
            continue
        if len(set(path)) != len(path):
            continue
        hop_vcs = [0] * (len(first) - 1) + [1] * (len(second) - 1)
        return path, hop_vcs

    direct = _ecube_path(src, dst, dimension)
    return direct, [0] * (len(direct) - 1)

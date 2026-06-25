from __future__ import annotations

from dataclasses import dataclass

from topoanalyzer.model.graph import TopologyGraph
from topoanalyzer.model.routing import RoutingTable
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.routing.base import RoutingGenerator
from topoanalyzer.routing.deadlock import channel_dependency_has_cycle
from topoanalyzer.routing.ruche_xyz import _ruche_xyz_path
from topoanalyzer.routing.static import stable_hash_int


@dataclass(frozen=True)
class Ruche3DValiantHashRoutingGenerator(RoutingGenerator):
    seed: int = 0

    name = "ruche_valiant_hash"

    def validate(self, graph: TopologyGraph) -> ValidationReport:
        report = ValidationReport()
        if graph.topology_type != "ruche3d":
            report.add_error(
                "ruche_valiant_hash routing requires a ruche3d topology",
                topology_type=graph.topology_type,
            )
        dimensions = graph.metadata.get("dimensions", {})
        strides = graph.metadata.get("strides", {})
        for axis in ("x", "y", "z"):
            if axis not in dimensions:
                report.add_error("ruche3d graph is missing dimension metadata", axis=axis)
            if axis not in strides:
                report.add_error("ruche3d graph is missing stride metadata", axis=axis)
        if bool(graph.metadata.get("wrap", False)):
            report.add_error(
                "ruche_valiant_hash currently supports non-wrap ruche3d only"
            )
        return report

    def generate(self, graph: TopologyGraph) -> RoutingTable:
        report = self.validate(graph)
        report.raise_if_errors()

        dims = graph.metadata["dimensions"]
        strides = graph.metadata["strides"]
        routers = [
            (node.id, tuple(int(value) for value in node.metadata["coord"]))
            for node in graph.routers()
        ]
        router_by_coord = {coord: router_id for router_id, coord in routers}
        table = RoutingTable(
            name=self.name,
            metadata={
                "algorithm": "ruche_valiant_hash",
                "seed": self.seed,
                "vc_policy": {
                    "0": "source to hashed intermediate",
                    "1": "intermediate to destination",
                },
                "required_vcs": 2,
                "wrap_links_used": False,
            },
        )

        for src_id, src_coord in routers:
            for dst_id, dst_coord in routers:
                if src_id == dst_id:
                    continue
                path, hop_vcs = _valiant_path(
                    src_id,
                    src_coord,
                    dst_id,
                    dst_coord,
                    router_by_coord,
                    dims,
                    strides,
                    seed=self.seed,
                )
                table.add_path(src_id, dst_id, path, hop_vcs=hop_vcs)

        has_cycle, cycle = channel_dependency_has_cycle(table)
        if has_cycle:
            raise ValueError(
                f"ruche_valiant_hash generated cyclic channel dependencies: {cycle}"
            )
        return table


def _valiant_path(
    src_id: str,
    src_coord: tuple[int, int, int],
    dst_id: str,
    dst_coord: tuple[int, int, int],
    router_by_coord: dict[tuple[int, int, int], str],
    dims: dict[str, int],
    strides: dict[str, int],
    *,
    seed: int,
) -> tuple[list[str], list[int]]:
    candidates = [
        coord
        for coord in router_by_coord
        if coord != src_coord and coord != dst_coord
    ]
    candidates.sort(
        key=lambda coord: stable_hash_int(src_id, dst_id, coord, seed=seed)
    )
    for intermediate_coord in candidates:
        first = _ruche_xyz_path(src_coord, intermediate_coord, dims, strides)
        second = _ruche_xyz_path(intermediate_coord, dst_coord, dims, strides)
        path = first + second[1:]
        if path[-1] != dst_id:
            continue
        if path.count(dst_id) != 1:
            continue
        if len(set(path)) != len(path):
            continue
        hop_vcs = [0] * (len(first) - 1) + [1] * (len(second) - 1)
        return path, hop_vcs

    direct = _ruche_xyz_path(src_coord, dst_coord, dims, strides)
    return direct, [0] * (len(direct) - 1)

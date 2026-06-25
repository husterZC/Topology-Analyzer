from __future__ import annotations

from topoanalyzer.model.graph import TopologyGraph
from topoanalyzer.model.routing import RoutingTable
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.routing.base import RoutingGenerator
from topoanalyzer.topologies.mesh3d import router_id


class Mesh3DXYZRoutingGenerator(RoutingGenerator):
    name = "mesh_xyz"

    def validate(self, graph: TopologyGraph) -> ValidationReport:
        report = ValidationReport()
        if graph.topology_type != "mesh3d":
            report.add_error(
                "mesh_xyz routing requires a mesh3d topology",
                topology_type=graph.topology_type,
            )
        dimensions = graph.metadata.get("dimensions", {})
        for axis in ("x", "y", "z"):
            if axis not in dimensions:
                report.add_error("mesh3d graph is missing dimension metadata", axis=axis)
        return report

    def generate(self, graph: TopologyGraph) -> RoutingTable:
        report = self.validate(graph)
        report.raise_if_errors()

        dims = graph.metadata["dimensions"]
        table = RoutingTable(
            name=self.name,
            metadata={
                "algorithm": "dimension_order",
                "dimension_order": ["x", "y", "z"],
            },
        )
        routers = [
            (node.id, tuple(int(value) for value in node.metadata["coord"]))
            for node in graph.routers()
        ]
        for src_id, src_coord in routers:
            for dst_id, dst_coord in routers:
                if src_id == dst_id:
                    continue
                table.add_path(src_id, dst_id, _xyz_path(src_coord, dst_coord, dims))
        return table


def _xyz_path(
    src: tuple[int, int, int],
    dst: tuple[int, int, int],
    dims: dict[str, int],
) -> list[str]:
    sx, sy, sz = src
    dx, dy, dz = dst
    if not (
        0 <= sx < dims["x"]
        and 0 <= dx < dims["x"]
        and 0 <= sy < dims["y"]
        and 0 <= dy < dims["y"]
        and 0 <= sz < dims["z"]
        and 0 <= dz < dims["z"]
    ):
        raise ValueError(f"route endpoint out of bounds: {src} -> {dst}")

    path = [router_id(sx, sy, sz)]
    x, y, z = sx, sy, sz
    while x != dx:
        x += 1 if dx > x else -1
        path.append(router_id(x, y, z))
    while y != dy:
        y += 1 if dy > y else -1
        path.append(router_id(x, y, z))
    while z != dz:
        z += 1 if dz > z else -1
        path.append(router_id(x, y, z))
    return path

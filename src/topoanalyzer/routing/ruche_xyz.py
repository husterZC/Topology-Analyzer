from __future__ import annotations

from topoanalyzer.model.graph import TopologyGraph
from topoanalyzer.model.routing import RoutingTable
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.routing.base import RoutingGenerator
from topoanalyzer.topologies.ruche3d import router_id


class Ruche3DXYZRoutingGenerator(RoutingGenerator):
    name = "ruche_xyz"

    def validate(self, graph: TopologyGraph) -> ValidationReport:
        report = ValidationReport()
        if graph.topology_type != "ruche3d":
            report.add_error(
                "ruche_xyz routing requires a ruche3d topology",
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
                "ruche_xyz currently supports non-wrap ruche3d routing only"
            )
        return report

    def generate(self, graph: TopologyGraph) -> RoutingTable:
        report = self.validate(graph)
        report.raise_if_errors()

        dims = graph.metadata["dimensions"]
        strides = graph.metadata["strides"]
        table = RoutingTable(
            name=self.name,
            metadata={
                "algorithm": "ruche_dimension_order",
                "dimension_order": ["x", "y", "z"],
                "strides": dict(strides),
                "wrap_links_used": False,
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
                table.add_path(
                    src_id,
                    dst_id,
                    _ruche_xyz_path(src_coord, dst_coord, dims, strides),
                )
        return table


def _ruche_xyz_path(
    src: tuple[int, int, int],
    dst: tuple[int, int, int],
    dims: dict[str, int],
    strides: dict[str, int],
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
    coord = [sx, sy, sz]
    targets = [dx, dy, dz]
    axis_names = ["x", "y", "z"]
    for axis, axis_name in enumerate(axis_names):
        stride = int(strides[axis_name])
        while coord[axis] != targets[axis]:
            delta = targets[axis] - coord[axis]
            direction = 1 if delta > 0 else -1
            step = stride if abs(delta) >= stride else 1
            coord[axis] += direction * step
            path.append(router_id(coord[0], coord[1], coord[2]))
    return path

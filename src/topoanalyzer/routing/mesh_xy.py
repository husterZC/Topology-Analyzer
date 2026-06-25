from __future__ import annotations

from topoanalyzer.model.graph import TopologyGraph
from topoanalyzer.model.routing import RoutingTable
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.routing.base import RoutingGenerator
from topoanalyzer.topologies.mesh2d import router_id


class Mesh2DXYRoutingGenerator(RoutingGenerator):
    name = "mesh_xy"

    def validate(self, graph: TopologyGraph) -> ValidationReport:
        report = ValidationReport()
        if graph.topology_type != "mesh2d":
            report.add_error(
                "mesh_xy routing requires a mesh2d topology",
                topology_type=graph.topology_type,
            )
        dimensions = graph.metadata.get("dimensions", {})
        if "x" not in dimensions or "y" not in dimensions:
            report.add_error("mesh2d graph is missing dimensions metadata")
        return report

    def generate(self, graph: TopologyGraph) -> RoutingTable:
        report = self.validate(graph)
        report.raise_if_errors()

        dims = graph.metadata["dimensions"]
        table = RoutingTable(
            name=self.name,
            metadata={
                "algorithm": "dimension_order",
                "dimension_order": ["x", "y"],
            },
        )
        routers = [
            (node.id, tuple(node.metadata["coord"]))
            for node in graph.routers()
        ]
        for src_id, src_coord in routers:
            for dst_id, dst_coord in routers:
                if src_id == dst_id:
                    continue
                path = _xy_path(src_coord, dst_coord, dims["x"], dims["y"])
                table.add_path(src_id, dst_id, path)
        return table


def _xy_path(
    src: tuple[int, int],
    dst: tuple[int, int],
    x_dim: int,
    y_dim: int,
) -> list[str]:
    sx, sy = src
    dx, dy = dst
    if not (0 <= sx < x_dim and 0 <= dx < x_dim and 0 <= sy < y_dim and 0 <= dy < y_dim):
        raise ValueError(f"route endpoint out of bounds: {src} -> {dst}")

    path = [router_id(sx, sy)]
    x = sx
    y = sy
    while x != dx:
        x += 1 if dx > x else -1
        path.append(router_id(x, y))
    while y != dy:
        y += 1 if dy > y else -1
        path.append(router_id(x, y))
    return path

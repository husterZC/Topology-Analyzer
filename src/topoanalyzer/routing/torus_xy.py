from __future__ import annotations

from topoanalyzer.model.graph import TopologyGraph
from topoanalyzer.model.routing import RoutingTable
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.routing.base import RoutingGenerator
from topoanalyzer.topologies.torus2d import router_id


class Torus2DXYRoutingGenerator(RoutingGenerator):
    name = "torus_xy"

    def validate(self, graph: TopologyGraph) -> ValidationReport:
        report = ValidationReport()
        if graph.topology_type != "torus2d":
            report.add_error(
                "torus_xy routing requires a torus2d topology",
                topology_type=graph.topology_type,
            )
        dimensions = graph.metadata.get("dimensions", {})
        for axis in ("x", "y"):
            if axis not in dimensions:
                report.add_error("torus2d graph is missing dimension metadata", axis=axis)
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
                "wrap_links_used": False,
                "note": (
                    "This table-compatible baseline uses the torus topology but "
                    "routes without wrap links. Dateline/adaptive torus routing "
                    "needs runtime VC state."
                ),
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
                table.add_path(src_id, dst_id, _xy_path(src_coord, dst_coord, dims))
        return table


def _xy_path(
    src: tuple[int, int],
    dst: tuple[int, int],
    dims: dict[str, int],
) -> list[str]:
    sx, sy = src
    dx, dy = dst
    if not (
        0 <= sx < dims["x"]
        and 0 <= dx < dims["x"]
        and 0 <= sy < dims["y"]
        and 0 <= dy < dims["y"]
    ):
        raise ValueError(f"route endpoint out of bounds: {src} -> {dst}")

    path = [router_id(sx, sy)]
    x, y = sx, sy
    while x != dx:
        x += 1 if dx > x else -1
        path.append(router_id(x, y))
    while y != dy:
        y += 1 if dy > y else -1
        path.append(router_id(x, y))
    return path

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from topoanalyzer.model.graph import Node, TopologyGraph
from topoanalyzer.model.links import LinkParameters
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.topologies.base import TopologyBuilder


@dataclass(frozen=True)
class Mesh3DParams:
    x: int
    y: int
    z: int
    concentration: int = 1

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Mesh3DParams":
        return cls(
            x=int(data["x"]),
            y=int(data["y"]),
            z=int(data["z"]),
            concentration=int(data.get("concentration", 1)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "concentration": self.concentration,
        }


class Mesh3DTopologyBuilder(TopologyBuilder):
    name = "mesh3d"
    link_classes = {"x", "y", "z"}

    def validate(self, params: Mesh3DParams, links: LinkParameters) -> ValidationReport:
        report = ValidationReport()
        for axis in ("x", "y", "z"):
            value = getattr(params, axis)
            if value <= 0:
                report.add_error(
                    "mesh3d dimension must be positive",
                    dimension=axis,
                    value=value,
                )
        if params.concentration <= 0:
            report.add_error(
                "mesh3d concentration must be positive",
                concentration=params.concentration,
            )
        report.merge(links.validate(allowed_classes=self.link_classes))
        for idx, override in enumerate(links.overrides):
            for endpoint_name, endpoint in (("src", override.src), ("dst", override.dst)):
                if not isinstance(endpoint, tuple) or len(endpoint) != 3:
                    report.add_error(
                        "mesh3d link overrides must use 3D coordinate endpoints",
                        override_index=idx,
                        endpoint=endpoint_name,
                        value=endpoint,
                    )
                    continue
                x, y, z = endpoint
                if not (0 <= x < params.x and 0 <= y < params.y and 0 <= z < params.z):
                    report.add_error(
                        "mesh3d link override endpoint is out of bounds",
                        override_index=idx,
                        endpoint=endpoint_name,
                        value=endpoint,
                    )
        return report

    def build(self, params: Mesh3DParams, links: LinkParameters) -> TopologyGraph:
        report = self.validate(params, links)
        report.raise_if_errors()

        graph = TopologyGraph(
            name=f"mesh3d_{params.x}x{params.y}x{params.z}",
            topology_type=self.name,
            metadata={
                "dimensions": {"x": params.x, "y": params.y, "z": params.z},
                "concentration": params.concentration,
                "terminal_count": params.x * params.y * params.z * params.concentration,
            },
        )
        order = 0
        for z in range(params.z):
            for y in range(params.y):
                for x in range(params.x):
                    graph.add_node(
                        Node(
                            id=router_id(x, y, z),
                            kind="router",
                            metadata={"coord": [x, y, z], "booksim_order": order},
                        )
                    )
                    order += 1

        for z in range(params.z):
            for y in range(params.y):
                for x in range(params.x):
                    if x + 1 < params.x:
                        _add_link(graph, links, (x, y, z), (x + 1, y, z), "x")
                    if y + 1 < params.y:
                        _add_link(graph, links, (x, y, z), (x, y + 1, z), "y")
                    if z + 1 < params.z:
                        _add_link(graph, links, (x, y, z), (x, y, z + 1), "z")
        return graph


def _add_link(
    graph: TopologyGraph,
    links: LinkParameters,
    src: tuple[int, int, int],
    dst: tuple[int, int, int],
    link_class: str,
) -> None:
    spec_ab = links.resolve(src, dst, link_class=link_class)
    spec_ba = links.resolve(dst, src, link_class=link_class)
    graph.add_bidirectional_link(
        router_id(*src),
        router_id(*dst),
        spec_ab,
        spec_ba,
        metadata={
            "class": link_class,
            "orientation": link_class,
            "src_coord": list(src),
            "dst_coord": list(dst),
        },
    )


def router_id(x: int, y: int, z: int) -> str:
    return f"r3.{x}.{y}.{z}"

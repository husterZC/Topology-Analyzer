from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from topoanalyzer.model.graph import Node, TopologyGraph
from topoanalyzer.model.links import LinkParameters
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.topologies.base import TopologyBuilder


@dataclass(frozen=True)
class Mesh2DParams:
    x: int
    y: int
    concentration: int = 1

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Mesh2DParams":
        return cls(
            x=int(data["x"]),
            y=int(data["y"]),
            concentration=int(data.get("concentration", 1)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "concentration": self.concentration,
        }


class Mesh2DTopologyBuilder(TopologyBuilder):
    name = "mesh2d"
    link_classes = {"x", "y"}

    def validate(self, params: Mesh2DParams, links: LinkParameters) -> ValidationReport:
        report = ValidationReport()
        if params.x <= 0:
            report.add_error("mesh x dimension must be positive", x=params.x)
        if params.y <= 0:
            report.add_error("mesh y dimension must be positive", y=params.y)
        if params.concentration <= 0:
            report.add_error(
                "mesh concentration must be positive",
                concentration=params.concentration,
            )
        report.merge(links.validate(allowed_classes=self.link_classes))
        for idx, override in enumerate(links.overrides):
            for endpoint_name, endpoint in (("src", override.src), ("dst", override.dst)):
                if isinstance(endpoint, tuple) and len(endpoint) == 2:
                    ex, ey = endpoint
                    if ex < 0 or ex >= params.x or ey < 0 or ey >= params.y:
                        report.add_error(
                            "mesh link override endpoint is out of bounds",
                            override_index=idx,
                            endpoint=endpoint_name,
                            value=endpoint,
                        )
                else:
                    report.add_error(
                        "mesh2d link overrides must use coordinate endpoints",
                        override_index=idx,
                        endpoint=endpoint_name,
                        value=endpoint,
                    )
        return report

    def build(self, params: Mesh2DParams, links: LinkParameters) -> TopologyGraph:
        report = self.validate(params, links)
        report.raise_if_errors()

        graph = TopologyGraph(
            name=f"mesh2d_{params.x}x{params.y}",
            topology_type=self.name,
            metadata={
                "dimensions": {"x": params.x, "y": params.y},
                "concentration": params.concentration,
                "terminal_count": params.x * params.y * params.concentration,
            },
        )
        for y in range(params.y):
            for x in range(params.x):
                graph.add_node(
                    Node(
                        id=router_id(x, y),
                        kind="router",
                        metadata={"coord": [x, y]},
                    )
                )

        for y in range(params.y):
            for x in range(params.x):
                if x + 1 < params.x:
                    self._add_mesh_link(graph, links, (x, y), (x + 1, y), "x")
                if y + 1 < params.y:
                    self._add_mesh_link(graph, links, (x, y), (x, y + 1), "y")
        return graph

    @staticmethod
    def _add_mesh_link(
        graph: TopologyGraph,
        links: LinkParameters,
        src: tuple[int, int],
        dst: tuple[int, int],
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


def router_id(x: int, y: int) -> str:
    return f"r.{x}.{y}"

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from topoanalyzer.model.graph import Node, TopologyGraph
from topoanalyzer.model.links import LinkParameters
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.topologies.base import TopologyBuilder


@dataclass(frozen=True)
class Torus2DParams:
    x: int
    y: int
    concentration: int = 1

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Torus2DParams":
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


class Torus2DTopologyBuilder(TopologyBuilder):
    name = "torus2d"
    link_classes = {"x", "y", "x_wrap", "y_wrap"}

    def validate(self, params: Torus2DParams, links: LinkParameters) -> ValidationReport:
        report = ValidationReport()
        for axis in ("x", "y"):
            value = getattr(params, axis)
            if value < 3:
                report.add_error(
                    "torus2d dimensions must be at least 3 to avoid parallel wrap links",
                    dimension=axis,
                    value=value,
                )
        if params.concentration <= 0:
            report.add_error(
                "torus2d concentration must be positive",
                concentration=params.concentration,
            )
        report.merge(links.validate(allowed_classes=self.link_classes))
        for idx, override in enumerate(links.overrides):
            for endpoint_name, endpoint in (("src", override.src), ("dst", override.dst)):
                if not isinstance(endpoint, tuple) or len(endpoint) != 2:
                    report.add_error(
                        "torus2d link overrides must use 2D coordinate endpoints",
                        override_index=idx,
                        endpoint=endpoint_name,
                        value=endpoint,
                    )
                    continue
                x, y = endpoint
                if not (0 <= x < params.x and 0 <= y < params.y):
                    report.add_error(
                        "torus2d link override endpoint is out of bounds",
                        override_index=idx,
                        endpoint=endpoint_name,
                        value=endpoint,
                    )
        return report

    def build(self, params: Torus2DParams, links: LinkParameters) -> TopologyGraph:
        report = self.validate(params, links)
        report.raise_if_errors()

        graph = TopologyGraph(
            name=f"torus2d_{params.x}x{params.y}",
            topology_type=self.name,
            metadata={
                "dimensions": {"x": params.x, "y": params.y},
                "concentration": params.concentration,
                "terminal_count": params.x * params.y * params.concentration,
            },
        )
        order = 0
        for y in range(params.y):
            for x in range(params.x):
                graph.add_node(
                    Node(
                        id=router_id(x, y),
                        kind="router",
                        metadata={"coord": [x, y], "booksim_order": order},
                    )
                )
                order += 1

        for y in range(params.y):
            for x in range(params.x):
                _add_torus_link(
                    graph,
                    links,
                    (x, y),
                    ((x + 1) % params.x, y),
                    "x_wrap" if x + 1 == params.x else "x",
                )
                _add_torus_link(
                    graph,
                    links,
                    (x, y),
                    (x, (y + 1) % params.y),
                    "y_wrap" if y + 1 == params.y else "y",
                )
        return graph


def _add_torus_link(
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
            "orientation": link_class.removesuffix("_wrap"),
            "wrap": link_class.endswith("_wrap"),
            "src_coord": list(src),
            "dst_coord": list(dst),
        },
    )


def router_id(x: int, y: int) -> str:
    return f"t2.{x}.{y}"

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from topoanalyzer.model.graph import Node, TopologyGraph
from topoanalyzer.model.links import LinkParameters
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.topologies.base import TopologyBuilder


@dataclass(frozen=True)
class Ruche3DParams:
    x: int
    y: int
    z: int
    stride_x: int = 2
    stride_y: int = 2
    stride_z: int = 2
    wrap: bool = False
    concentration: int = 1

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Ruche3DParams":
        stride = data.get("stride")
        return cls(
            x=int(data["x"]),
            y=int(data["y"]),
            z=int(data["z"]),
            stride_x=int(data.get("stride_x", stride or 2)),
            stride_y=int(data.get("stride_y", stride or 2)),
            stride_z=int(data.get("stride_z", stride or 2)),
            wrap=bool(data.get("wrap", False)),
            concentration=int(data.get("concentration", 1)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "stride_x": self.stride_x,
            "stride_y": self.stride_y,
            "stride_z": self.stride_z,
            "wrap": self.wrap,
            "concentration": self.concentration,
        }


class Ruche3DTopologyBuilder(TopologyBuilder):
    name = "ruche3d"
    link_classes = {"x", "y", "z", "ruche_x", "ruche_y", "ruche_z"}

    def validate(self, params: Ruche3DParams, links: LinkParameters) -> ValidationReport:
        report = ValidationReport()
        dims = {"x": params.x, "y": params.y, "z": params.z}
        strides = {
            "x": params.stride_x,
            "y": params.stride_y,
            "z": params.stride_z,
        }
        for axis, value in dims.items():
            if value <= 0:
                report.add_error(
                    "ruche3d dimension must be positive",
                    dimension=axis,
                    value=value,
                )
        for axis, stride in strides.items():
            dim = dims[axis]
            if stride <= 1:
                report.add_error(
                    "ruche3d stride must be greater than 1",
                    dimension=axis,
                    stride=stride,
                )
            if not params.wrap and stride >= dim:
                report.add_error(
                    "non-wrap ruche3d stride must be smaller than its dimension",
                    dimension=axis,
                    stride=stride,
                    size=dim,
                )
            if params.wrap and dim > 0 and stride % dim == 0:
                report.add_error(
                    "wrap ruche3d stride must not be a multiple of its dimension",
                    dimension=axis,
                    stride=stride,
                    size=dim,
                )
        if params.concentration <= 0:
            report.add_error(
                "ruche3d concentration must be positive",
                concentration=params.concentration,
            )
        report.merge(links.validate(allowed_classes=self.link_classes))
        for idx, override in enumerate(links.overrides):
            for endpoint_name, endpoint in (("src", override.src), ("dst", override.dst)):
                if not isinstance(endpoint, tuple) or len(endpoint) != 3:
                    report.add_error(
                        "ruche3d link overrides must use 3D coordinate endpoints",
                        override_index=idx,
                        endpoint=endpoint_name,
                        value=endpoint,
                    )
                    continue
                x, y, z = endpoint
                if not (0 <= x < params.x and 0 <= y < params.y and 0 <= z < params.z):
                    report.add_error(
                        "ruche3d link override endpoint is out of bounds",
                        override_index=idx,
                        endpoint=endpoint_name,
                        value=endpoint,
                    )
        return report

    def build(self, params: Ruche3DParams, links: LinkParameters) -> TopologyGraph:
        report = self.validate(params, links)
        report.raise_if_errors()

        graph = TopologyGraph(
            name=f"ruche3d_{params.x}x{params.y}x{params.z}",
            topology_type=self.name,
            metadata={
                "dimensions": {"x": params.x, "y": params.y, "z": params.z},
                "strides": {
                    "x": params.stride_x,
                    "y": params.stride_y,
                    "z": params.stride_z,
                },
                "wrap": params.wrap,
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
                        _add_link(graph, links, (x, y, z), (x + 1, y, z), "x", False)
                    if y + 1 < params.y:
                        _add_link(graph, links, (x, y, z), (x, y + 1, z), "y", False)
                    if z + 1 < params.z:
                        _add_link(graph, links, (x, y, z), (x, y, z + 1), "z", False)

                    _maybe_add_ruche_link(
                        graph,
                        links,
                        (x, y, z),
                        axis=0,
                        size=params.x,
                        stride=params.stride_x,
                        wrap=params.wrap,
                        link_class="ruche_x",
                    )
                    _maybe_add_ruche_link(
                        graph,
                        links,
                        (x, y, z),
                        axis=1,
                        size=params.y,
                        stride=params.stride_y,
                        wrap=params.wrap,
                        link_class="ruche_y",
                    )
                    _maybe_add_ruche_link(
                        graph,
                        links,
                        (x, y, z),
                        axis=2,
                        size=params.z,
                        stride=params.stride_z,
                        wrap=params.wrap,
                        link_class="ruche_z",
                    )
        return graph


def _maybe_add_ruche_link(
    graph: TopologyGraph,
    links: LinkParameters,
    src: tuple[int, int, int],
    *,
    axis: int,
    size: int,
    stride: int,
    wrap: bool,
    link_class: str,
) -> None:
    dst = list(src)
    next_value = src[axis] + stride
    if wrap:
        dst[axis] = next_value % size
        if tuple(dst) <= src:
            return
    else:
        if next_value >= size:
            return
        dst[axis] = next_value
    _add_link(graph, links, src, tuple(dst), link_class, True)


def _add_link(
    graph: TopologyGraph,
    links: LinkParameters,
    src: tuple[int, int, int],
    dst: tuple[int, int, int],
    link_class: str,
    ruche: bool,
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
            "orientation": link_class.removeprefix("ruche_"),
            "ruche": ruche,
            "src_coord": list(src),
            "dst_coord": list(dst),
        },
    )


def router_id(x: int, y: int, z: int) -> str:
    return f"ru3.{x}.{y}.{z}"

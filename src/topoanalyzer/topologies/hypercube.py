from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from topoanalyzer.model.graph import Node, TopologyGraph
from topoanalyzer.model.links import LinkParameters
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.topologies.base import TopologyBuilder


@dataclass(frozen=True)
class HypercubeParams:
    dimension: int
    concentration: int = 1

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HypercubeParams":
        return cls(
            dimension=int(data["dimension"]),
            concentration=int(data.get("concentration", 1)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "concentration": self.concentration,
        }


class HypercubeTopologyBuilder(TopologyBuilder):
    name = "hypercube"

    def validate(
        self,
        params: HypercubeParams,
        links: LinkParameters,
    ) -> ValidationReport:
        report = ValidationReport()
        if params.dimension <= 0:
            report.add_error(
                "hypercube dimension must be positive",
                dimension=params.dimension,
            )
        if params.concentration <= 0:
            report.add_error(
                "hypercube concentration must be positive",
                concentration=params.concentration,
            )
        allowed_classes = {"cube"} | {
            f"dim_{bit}" for bit in range(max(params.dimension, 0))
        }
        report.merge(links.validate(allowed_classes=allowed_classes))
        for idx, override in enumerate(links.overrides):
            if not isinstance(override.src, str) or not isinstance(override.dst, str):
                report.add_error(
                    "hypercube link overrides must use router ID string endpoints",
                    override_index=idx,
                    src=override.src,
                    dst=override.dst,
                )
        return report

    def build(self, params: HypercubeParams, links: LinkParameters) -> TopologyGraph:
        report = self.validate(params, links)
        report.raise_if_errors()

        node_count = 1 << params.dimension
        graph = TopologyGraph(
            name=f"hypercube_d{params.dimension}",
            topology_type=self.name,
            metadata={
                "dimension": params.dimension,
                "node_count": node_count,
                "concentration": params.concentration,
                "terminal_count": node_count * params.concentration,
            },
        )
        for value in range(node_count):
            graph.add_node(
                Node(
                    id=router_id(value),
                    kind="router",
                    metadata={
                        "value": value,
                        "bits": _bits(value, params.dimension),
                        "coord": [value],
                        "booksim_order": value,
                    },
                )
            )

        for value in range(node_count):
            for bit in range(params.dimension):
                neighbor = value ^ (1 << bit)
                if neighbor < value:
                    continue
                link_class = _link_class(links, bit)
                spec_ab = links.resolve(router_id(value), router_id(neighbor), link_class)
                spec_ba = links.resolve(router_id(neighbor), router_id(value), link_class)
                graph.add_bidirectional_link(
                    router_id(value),
                    router_id(neighbor),
                    spec_ab,
                    spec_ba,
                    metadata={
                        "class": link_class or "default",
                        "dimension": bit,
                        "src_value": value,
                        "dst_value": neighbor,
                    },
                )
        return graph


def router_id(value: int) -> str:
    return f"hc.{value}"


def _bits(value: int, dimension: int) -> list[int]:
    return [(value >> bit) & 1 for bit in range(dimension)]


def _link_class(links: LinkParameters, bit: int) -> str | None:
    dim_class = f"dim_{bit}"
    if dim_class in links.classes:
        return dim_class
    if "cube" in links.classes:
        return "cube"
    return None

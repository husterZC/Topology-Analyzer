from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from math import prod
from typing import Any

from topoanalyzer.model.graph import Node, TopologyGraph
from topoanalyzer.model.links import LinkParameters, LinkSpec
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.topologies.base import TopologyBuilder


Coordinate = tuple[int, ...]


@dataclass(frozen=True)
class UBMeshParams:
    dimensions: tuple[int, ...]
    concentration: int = 1
    dimension_names: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UBMeshParams":
        dimensions_data = data.get("dimensions", data.get("dims"))
        if dimensions_data is None:
            raise KeyError("ubmesh params require `dimensions`")
        dimensions = tuple(int(value) for value in dimensions_data)
        dimension_names_data = data.get("dimension_names", data.get("names", ()))
        return cls(
            dimensions=dimensions,
            concentration=int(data.get("concentration", 1)),
            dimension_names=tuple(str(value) for value in dimension_names_data),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "dimensions": list(self.dimensions),
            "concentration": self.concentration,
        }
        if self.dimension_names:
            data["dimension_names"] = list(self.dimension_names)
        return data

    @property
    def resolved_dimension_names(self) -> tuple[str, ...]:
        if self.dimension_names:
            return self.dimension_names
        return tuple(f"dim_{idx}" for idx in range(len(self.dimensions)))


class UBMeshTopologyBuilder(TopologyBuilder):
    name = "ubmesh"

    def validate(
        self,
        params: UBMeshParams,
        links: LinkParameters,
    ) -> ValidationReport:
        report = ValidationReport()
        if not params.dimensions:
            report.add_error("ubmesh dimensions must be non-empty")
        for idx, value in enumerate(params.dimensions):
            if value <= 0:
                report.add_error(
                    "ubmesh dimension must be positive",
                    dimension=idx,
                    value=value,
                )
        if params.concentration <= 0:
            report.add_error(
                "ubmesh concentration must be positive",
                concentration=params.concentration,
            )
        if params.dimension_names and len(params.dimension_names) != len(params.dimensions):
            report.add_error(
                "ubmesh dimension_names length must match dimensions length",
                dimension_count=len(params.dimensions),
                dimension_names=list(params.dimension_names),
            )
        if len(set(params.resolved_dimension_names)) != len(params.resolved_dimension_names):
            report.add_error(
                "ubmesh dimension names must be unique",
                dimension_names=list(params.resolved_dimension_names),
            )

        report.merge(links.validate(allowed_classes=self._allowed_link_classes(params)))
        for idx, override in enumerate(links.overrides):
            for endpoint_name, endpoint in (("src", override.src), ("dst", override.dst)):
                self._validate_override_endpoint(
                    report,
                    params,
                    override_index=idx,
                    endpoint_name=endpoint_name,
                    endpoint=endpoint,
                )
        return report

    def build(self, params: UBMeshParams, links: LinkParameters) -> TopologyGraph:
        report = self.validate(params, links)
        report.raise_if_errors()

        router_count = prod(params.dimensions)
        dimension_count = len(params.dimensions)
        network_radix = sum(length - 1 for length in params.dimensions)
        graph = TopologyGraph(
            name=f"ubmesh_{'x'.join(str(value) for value in params.dimensions)}",
            topology_type=self.name,
            metadata={
                "dimensions": list(params.dimensions),
                "dimension_names": list(params.resolved_dimension_names),
                "dimension_count": dimension_count,
                "network_radix": network_radix,
                "radix": network_radix + params.concentration,
                "concentration": params.concentration,
                "terminal_count": router_count * params.concentration,
                "router_count": router_count,
                "diameter": sum(1 for length in params.dimensions if length > 1),
                "topology_family": "nd_fullmesh",
            },
        )

        coords = _all_coordinates(params.dimensions)
        for order, coord in enumerate(coords):
            graph.add_node(
                Node(
                    id=router_id(*coord),
                    kind="router",
                    metadata={
                        "coord": list(coord),
                        "booksim_order": order,
                    },
                )
            )

        for coord in coords:
            for dimension, length in enumerate(params.dimensions):
                for next_value in range(coord[dimension] + 1, length):
                    dst = list(coord)
                    dst[dimension] = next_value
                    _add_fullmesh_link(
                        graph,
                        links,
                        params,
                        coord,
                        tuple(dst),
                        dimension,
                    )
        return graph

    @staticmethod
    def _allowed_link_classes(params: UBMeshParams) -> set[str]:
        classes = {f"dim_{idx}" for idx in range(len(params.dimensions))}
        classes.update(params.resolved_dimension_names)
        return classes

    @staticmethod
    def _validate_override_endpoint(
        report: ValidationReport,
        params: UBMeshParams,
        *,
        override_index: int,
        endpoint_name: str,
        endpoint: Coordinate | str,
    ) -> None:
        coord: Coordinate | None
        if isinstance(endpoint, tuple):
            coord = endpoint
        else:
            coord = parse_router_id(endpoint)
            if coord is None:
                report.add_error(
                    "ubmesh link overrides must use coordinate endpoints or ubmesh router IDs",
                    override_index=override_index,
                    endpoint=endpoint_name,
                    value=endpoint,
                )
                return
        if len(coord) != len(params.dimensions):
            report.add_error(
                "ubmesh link override endpoint has wrong dimensionality",
                override_index=override_index,
                endpoint=endpoint_name,
                value=coord,
                dimension_count=len(params.dimensions),
            )
            return
        for axis, (value, length) in enumerate(zip(coord, params.dimensions)):
            if not (0 <= value < length):
                report.add_error(
                    "ubmesh link override endpoint is out of bounds",
                    override_index=override_index,
                    endpoint=endpoint_name,
                    value=coord,
                    axis=axis,
                )


def _all_coordinates(dimensions: tuple[int, ...]) -> list[Coordinate]:
    return [
        tuple(int(value) for value in coord)
        for coord in product(*(range(length) for length in dimensions))
    ]


def _add_fullmesh_link(
    graph: TopologyGraph,
    links: LinkParameters,
    params: UBMeshParams,
    src: Coordinate,
    dst: Coordinate,
    dimension: int,
) -> None:
    class_candidates = _link_class_candidates(params, dimension)
    link_class = _selected_link_class(links, class_candidates)
    src_id = router_id(*src)
    dst_id = router_id(*dst)
    spec_ab = _resolve_link(links, src, dst, src_id, dst_id, class_candidates)
    spec_ba = _resolve_link(links, dst, src, dst_id, src_id, class_candidates)
    graph.add_bidirectional_link(
        src_id,
        dst_id,
        spec_ab,
        spec_ba,
        metadata={
            "class": link_class,
            "orientation": link_class,
            "dimension": dimension,
            "dimension_name": params.resolved_dimension_names[dimension],
            "src_coord": list(src),
            "dst_coord": list(dst),
        },
    )


def _link_class_candidates(params: UBMeshParams, dimension: int) -> tuple[str, ...]:
    dim_class = f"dim_{dimension}"
    dim_name = params.resolved_dimension_names[dimension]
    if dim_name == dim_class:
        return (dim_class,)
    return (dim_class, dim_name)


def _selected_link_class(
    links: LinkParameters,
    class_candidates: tuple[str, ...],
) -> str:
    for link_class in class_candidates:
        if link_class in links.classes:
            return link_class
    return class_candidates[0]


def _resolve_link(
    links: LinkParameters,
    src_coord: Coordinate,
    dst_coord: Coordinate,
    src_id: str,
    dst_id: str,
    class_candidates: tuple[str, ...],
) -> LinkSpec:
    for override in links.overrides:
        if override.matches(src_coord, dst_coord) or override.matches(src_id, dst_id):
            return override.spec
    for link_class in class_candidates:
        if link_class in links.classes:
            return links.classes[link_class]
    return links.default


def router_id(*coord: int) -> str:
    return "ub." + ".".join(str(value) for value in coord)


def parse_router_id(value: str) -> Coordinate | None:
    parts = value.split(".")
    if len(parts) < 2 or parts[0] != "ub":
        return None
    try:
        return tuple(int(part) for part in parts[1:])
    except ValueError:
        return None

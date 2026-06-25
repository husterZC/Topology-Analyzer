from __future__ import annotations

from typing import Iterable

from topoanalyzer.model.graph import TopologyGraph
from topoanalyzer.model.routing import RoutingTable
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.routing.static import stable_hash_int
from topoanalyzer.topologies.ubmesh import Coordinate, router_id


def validate_ubmesh_graph(
    graph: TopologyGraph,
    *,
    routing_name: str,
) -> ValidationReport:
    report = ValidationReport()
    if graph.topology_type != "ubmesh":
        report.add_error(
            f"{routing_name} routing requires a ubmesh topology",
            topology_type=graph.topology_type,
        )
    for key in ("dimensions", "dimension_count", "network_radix", "concentration"):
        if key not in graph.metadata:
            report.add_error("ubmesh graph is missing metadata", key=key)
    if not graph.is_connected():
        report.add_error(f"{routing_name} routing requires a connected graph")
    return report


def router_coords(graph: TopologyGraph) -> dict[str, Coordinate]:
    return {
        node.id: tuple(int(value) for value in node.metadata["coord"])
        for node in graph.routers()
    }


def dimension_count(graph: TopologyGraph) -> int:
    return int(graph.metadata["dimension_count"])


def dor_path(
    src_coord: Coordinate,
    dst_coord: Coordinate,
    *,
    dimension_order: Iterable[int] | None = None,
) -> list[str]:
    if len(src_coord) != len(dst_coord):
        raise ValueError(f"route dimensionality mismatch: {src_coord} -> {dst_coord}")
    order = (
        tuple(range(len(src_coord)))
        if dimension_order is None
        else tuple(int(value) for value in dimension_order)
    )
    if sorted(order) != list(range(len(src_coord))):
        raise ValueError(
            "dimension_order must contain every dimension exactly once: "
            f"{dimension_order}"
        )

    current = list(src_coord)
    path = [router_id(*current)]
    for dimension in order:
        if current[dimension] == dst_coord[dimension]:
            continue
        current[dimension] = dst_coord[dimension]
        path.append(router_id(*current))
    return path


def shortest_latency_path(
    graph: TopologyGraph,
    src_coord: Coordinate,
    dst_coord: Coordinate,
) -> list[str]:
    current = list(src_coord)
    path = [router_id(*current)]
    remaining = {
        dimension
        for dimension, (left, right) in enumerate(zip(src_coord, dst_coord))
        if left != right
    }
    while remaining:
        dimension = min(
            remaining,
            key=lambda item: (
                _direct_hop_latency(graph, tuple(current), dst_coord, item),
                item,
            ),
        )
        current[dimension] = dst_coord[dimension]
        path.append(router_id(*current))
        remaining.remove(dimension)
    return path


def minimal_phase_vcs(path: list[str]) -> list[int]:
    return list(range(max(len(path) - 1, 0)))


def apr_hash_path(
    graph: TopologyGraph,
    coords_by_router: dict[str, Coordinate],
    routers: list[str],
    source: str,
    destination: str,
    *,
    seed: int,
) -> tuple[list[str], list[int], str | None]:
    src_coord = coords_by_router[source]
    dst_coord = coords_by_router[destination]
    candidates = [
        router
        for router in routers
        if router != source and router != destination
    ]
    ordered = sorted(
        candidates,
        key=lambda router: stable_hash_int(source, destination, router, seed=seed),
    )
    for intermediate in ordered:
        intermediate_coord = coords_by_router[intermediate]
        first = dor_path(src_coord, intermediate_coord)
        second = dor_path(intermediate_coord, dst_coord)
        path = [*first, *second[1:]]
        if destination in first[:-1]:
            continue
        if source in second[1:]:
            continue
        if len(set(path)) != len(path):
            continue
        return path, [0] * (len(first) - 1) + [1] * (len(second) - 1), intermediate

    fallback = dor_path(src_coord, dst_coord)
    return fallback, [0] * (len(fallback) - 1), None


def generate_apr_hash_table(
    graph: TopologyGraph,
    *,
    routing_name: str,
    algorithm: str,
    seed: int,
    description: str,
    extra_metadata: dict[str, object] | None = None,
) -> RoutingTable:
    coords_by_router = router_coords(graph)
    routers = sorted(coords_by_router)
    table = RoutingTable(
        name=routing_name,
        metadata={
            "algorithm": algorithm,
            "seed": seed,
            "required_vcs": 2,
            "vc_policy": {
                "0": "source-to-detour DOR segment",
                "1": "detour-to-destination DOR segment",
            },
            "description": description,
            **({} if extra_metadata is None else extra_metadata),
        },
    )
    detour_count = 0
    max_hops = 0
    for source in routers:
        for destination in routers:
            if source == destination:
                continue
            path, hop_vcs, intermediate = apr_hash_path(
                graph,
                coords_by_router,
                routers,
                source,
                destination,
                seed=seed,
            )
            if intermediate is not None:
                detour_count += 1
            max_hops = max(max_hops, len(path) - 1)
            table.add_path(source, destination, path, hop_vcs=hop_vcs)
    table.metadata["detour_routes"] = detour_count
    table.metadata["max_hops"] = max_hops
    return table


def _direct_hop_latency(
    graph: TopologyGraph,
    current: Coordinate,
    destination: Coordinate,
    dimension: int,
) -> int:
    next_coord = list(current)
    next_coord[dimension] = destination[dimension]
    link = graph.link_between(router_id(*current), router_id(*next_coord))
    if link is None:
        raise ValueError(
            "ubmesh graph is missing direct dimension link: "
            f"{current} -> {tuple(next_coord)}"
        )
    return link.latency_cycles

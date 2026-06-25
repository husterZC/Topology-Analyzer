from __future__ import annotations

from dataclasses import dataclass

from topoanalyzer.model.graph import TopologyGraph
from topoanalyzer.model.routing import RoutingTable
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.routing.base import RoutingGenerator
from topoanalyzer.routing.deadlock import channel_dependency_has_cycle
from topoanalyzer.routing.slimnoc_min import (
    directed_router_adjacency,
    minimal_hop_vcs,
    shortest_path,
)
from topoanalyzer.routing.static import stable_hash_int


@dataclass(frozen=True)
class SlimNoCValiantHashRoutingGenerator(RoutingGenerator):
    seed: int = 0

    name = "slimnoc_valiant_hash"

    def validate(self, graph: TopologyGraph) -> ValidationReport:
        report = ValidationReport()
        if graph.topology_type != "slimnoc":
            report.add_error(
                "slimnoc_valiant_hash routing requires a slimnoc topology",
                topology_type=graph.topology_type,
            )
        for key in ("q", "network_radix", "concentration"):
            if key not in graph.metadata:
                report.add_error("slimnoc graph is missing metadata", key=key)
        if not graph.is_connected():
            report.add_error("slimnoc_valiant_hash routing requires a connected graph")
        return report

    def generate(self, graph: TopologyGraph) -> RoutingTable:
        report = self.validate(graph)
        report.raise_if_errors()

        routers = sorted(node.id for node in graph.routers())
        adjacency = directed_router_adjacency(graph)
        table = RoutingTable(
            name=self.name,
            metadata={
                "algorithm": "slimnoc_valiant_hash",
                "seed": self.seed,
                "required_vcs": 4,
                "vc_policy": {
                    "0": "first hop toward hashed intermediate",
                    "1": "final hop toward hashed intermediate",
                    "2": "first hop from intermediate to destination",
                    "3": "final hop from intermediate to destination",
                },
            },
        )

        max_hops = 0
        for source in routers:
            for destination in routers:
                if source == destination:
                    continue
                path, hop_vcs = _valiant_path(
                    adjacency,
                    routers,
                    source,
                    destination,
                    seed=self.seed,
                )
                max_hops = max(max_hops, len(path) - 1)
                table.add_path(source, destination, path, hop_vcs=hop_vcs)
        table.metadata["max_hops"] = max_hops

        has_cycle, cycle = channel_dependency_has_cycle(table)
        if has_cycle:
            raise ValueError(f"slimnoc_valiant_hash generated cyclic CDG: {cycle}")
        return table


def _valiant_path(
    adjacency: dict[str, list[str]],
    routers: list[str],
    source: str,
    destination: str,
    *,
    seed: int,
) -> tuple[list[str], list[int]]:
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
        first_candidates = _diameter_two_paths(
            adjacency,
            source,
            intermediate,
            forbidden_internal={destination},
        )
        for first in first_candidates:
            second_candidates = _diameter_two_paths(
                adjacency,
                intermediate,
                destination,
                forbidden_internal=set(first[:-1]),
            )
            for second in second_candidates:
                path = [*first, *second[1:]]
                if len(set(path)) != len(path):
                    continue
                return path, [
                    *_segment_hop_vcs(first, first_vc=0, final_vc=1),
                    *_segment_hop_vcs(second, first_vc=2, final_vc=3),
                ]

    path = shortest_path(adjacency, source, destination)
    return path, minimal_hop_vcs(path)


def _segment_hop_vcs(path: list[str], *, first_vc: int, final_vc: int) -> list[int]:
    hops = len(path) - 1
    if hops <= 0:
        return []
    if hops == 1:
        return [final_vc]
    return [first_vc] * (hops - 1) + [final_vc]


def _diameter_two_paths(
    adjacency: dict[str, list[str]],
    source: str,
    destination: str,
    *,
    forbidden_internal: set[str],
) -> list[list[str]]:
    candidates: list[list[str]] = []
    if destination in adjacency[source]:
        candidates.append([source, destination])
    for neighbor in adjacency[source]:
        if neighbor == destination or neighbor in forbidden_internal:
            continue
        if destination in adjacency[neighbor]:
            candidates.append([source, neighbor, destination])
    return candidates

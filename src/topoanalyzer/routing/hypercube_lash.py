from __future__ import annotations

from dataclasses import dataclass

from topoanalyzer.model.graph import TopologyGraph
from topoanalyzer.model.routing import RoutingTable
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.routing.base import RoutingGenerator
from topoanalyzer.routing.deadlock import channel_dependency_has_cycle
from topoanalyzer.routing.static import assign_first_acyclic_path, stable_hash_int
from topoanalyzer.topologies.hypercube import router_id


@dataclass(frozen=True)
class HypercubeLashRoutingGenerator(RoutingGenerator):
    max_vcs: int = 4
    candidate_paths: int = 8
    seed: int = 0

    name = "hypercube_lash"

    def validate(self, graph: TopologyGraph) -> ValidationReport:
        report = ValidationReport()
        if graph.topology_type != "hypercube":
            report.add_error(
                "hypercube_lash routing requires a hypercube topology",
                topology_type=graph.topology_type,
            )
        if "dimension" not in graph.metadata:
            report.add_error("hypercube graph is missing dimension metadata")
        if self.max_vcs <= 0:
            report.add_error("hypercube_lash max_vcs must be positive", max_vcs=self.max_vcs)
        if self.candidate_paths <= 0:
            report.add_error(
                "hypercube_lash candidate_paths must be positive",
                candidate_paths=self.candidate_paths,
            )
        return report

    def generate(self, graph: TopologyGraph) -> RoutingTable:
        report = self.validate(graph)
        report.raise_if_errors()

        dimension = int(graph.metadata["dimension"])
        table = RoutingTable(
            name=self.name,
            metadata={
                "algorithm": "hypercube_lash",
                "base_algorithm": "minimal_adaptive_bit_order",
                "candidate_paths": self.candidate_paths,
                "max_vcs": self.max_vcs,
                "seed": self.seed,
            },
        )
        routers = [(node.id, int(node.metadata["value"])) for node in graph.routers()]
        for src_id, src_value in routers:
            for dst_id, dst_value in routers:
                if src_id == dst_id:
                    continue
                candidates = _minimal_candidates(
                    src_value,
                    dst_value,
                    dimension,
                    limit=self.candidate_paths,
                    seed=self.seed,
                )
                assign_first_acyclic_path(
                    table,
                    src_id,
                    dst_id,
                    candidates,
                    max_vcs=self.max_vcs,
                )

        has_cycle, cycle = channel_dependency_has_cycle(table)
        if has_cycle:
            raise ValueError(f"hypercube_lash generated cyclic CDG: {cycle}")
        table.metadata["used_vcs"] = 1 + max(table.route_vcs.values(), default=0)
        return table


def _minimal_candidates(
    src: int,
    dst: int,
    dimension: int,
    *,
    limit: int,
    seed: int,
) -> list[list[str]]:
    diff_bits = [bit for bit in range(dimension) if (src ^ dst) & (1 << bit)]
    orders: list[list[int]] = []
    _append_order(orders, diff_bits)
    _append_order(orders, list(reversed(diff_bits)))
    hashed = sorted(
        diff_bits,
        key=lambda bit: stable_hash_int(src, dst, bit, seed=seed),
    )
    _append_order(orders, hashed)
    for offset in range(1, len(hashed)):
        _append_order(orders, hashed[offset:] + hashed[:offset])
    candidates = [_path_for_bit_order(src, order) for order in orders[:limit]]
    return candidates


def _append_order(orders: list[list[int]], order: list[int]) -> None:
    if order and order not in orders:
        orders.append(list(order))


def _path_for_bit_order(src: int, bit_order: list[int]) -> list[str]:
    current = src
    path = [router_id(current)]
    for bit in bit_order:
        current ^= 1 << bit
        path.append(router_id(current))
    return path

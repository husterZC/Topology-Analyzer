from __future__ import annotations

import hashlib
from typing import Iterable

from topoanalyzer.model.routing import RoutingTable
from topoanalyzer.routing.deadlock import channel_dependency_has_cycle


def stable_hash_int(*parts: object, seed: int = 0) -> int:
    data = "|".join([str(seed), *(str(part) for part in parts)]).encode("utf-8")
    return int.from_bytes(hashlib.blake2b(data, digest_size=8).digest(), "big")


def assign_first_acyclic_path(
    table: RoutingTable,
    source: str,
    destination: str,
    candidates: Iterable[list[str]],
    *,
    max_vcs: int,
) -> None:
    candidate_list = [candidate for candidate in candidates if len(candidate) >= 2]
    if not candidate_list:
        raise ValueError(f"no route candidates from {source} to {destination}")
    for vc in range(max_vcs):
        for path in candidate_list:
            trial = copy_routing_table(table)
            trial.add_path(source, destination, path, vc=vc)
            has_cycle, _ = channel_dependency_has_cycle(trial)
            if not has_cycle:
                table.add_path(source, destination, path, vc=vc)
                return
    raise ValueError(
        f"unable to assign deadlock-free route from {source} to {destination} "
        f"with {max_vcs} VCs and {len(candidate_list)} candidate paths"
    )


def copy_routing_table(table: RoutingTable) -> RoutingTable:
    copied = RoutingTable(
        name=table.name,
        metadata=dict(table.metadata),
    )
    for route, path in table.paths.items():
        copied.add_path(
            route[0],
            route[1],
            list(path),
            hop_vcs=table.path_vcs.get(
                route,
                [table.route_vcs.get(route, 0)] * max(len(path) - 1, 0),
            ),
        )
    return copied

from __future__ import annotations

from topoanalyzer.model.graph import TopologyGraph
from topoanalyzer.model.routing import RoutingTable
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.routing.base import RoutingGenerator
from topoanalyzer.routing.deadlock import channel_dependency_has_cycle
from topoanalyzer.topologies.lln import parse_router_id, projected_pair_key, router_id


class LLNTableRoutingGenerator(RoutingGenerator):
    """Paper-style deterministic LLN routing.

    Routes use the layer that owns a projected long link when available:
    vertical phase -> long-link phase -> vertical phase. If a projected pair is
    missing, the route falls back to deterministic XY routing through layer 0.
    """

    name = "lln_table"

    def validate(self, graph: TopologyGraph) -> ValidationReport:
        report = ValidationReport()
        if graph.topology_type != "lln":
            report.add_error(
                f"{self.name} routing requires an lln topology",
                topology_type=graph.topology_type,
            )
        dims = graph.metadata.get("dimensions", {})
        for axis in ("x", "y", "layers"):
            if axis not in dims:
                report.add_error("lln graph is missing dimension metadata", axis=axis)
        if not isinstance(graph.metadata.get("long_link_lookup"), dict):
            report.add_error("lln graph is missing long_link_lookup metadata")
        return report

    def generate(self, graph: TopologyGraph) -> RoutingTable:
        report = self.validate(graph)
        report.raise_if_errors()

        dims = graph.metadata["dimensions"]
        long_lookup = {
            str(key): int(value)
            for key, value in graph.metadata["long_link_lookup"].items()
        }
        table = RoutingTable(
            name=self.name,
            metadata={
                "algorithm": "lln_deterministic_table",
                "description": (
                    "Use a projected long link if one exists; otherwise route "
                    "through the preserved core-layer XY mesh."
                ),
                "vc_policy": {
                    "pre_horizontal_vertical": 0,
                    "horizontal": 1,
                    "post_horizontal_vertical": 2,
                },
                "requires_num_vcs": 3,
                "full_coverage": bool(graph.metadata.get("full_coverage")),
            },
        )

        routers = [
            (node.id, _coord(node.id))
            for node in graph.routers()
        ]
        for src_id, src_coord in routers:
            for dst_id, dst_coord in routers:
                if src_id == dst_id:
                    continue
                path, hop_vcs, used_fallback = _lln_path(
                    src_coord,
                    dst_coord,
                    dims,
                    long_lookup,
                )
                table.add_path(src_id, dst_id, path, hop_vcs=hop_vcs)
                if used_fallback:
                    table.metadata["fallback_routes"] = (
                        int(table.metadata.get("fallback_routes", 0)) + 1
                    )

        table.metadata.setdefault("fallback_routes", 0)
        has_cycle, cycle = channel_dependency_has_cycle(table)
        if has_cycle:
            raise ValueError(f"{self.name} generated cyclic channel dependencies: {cycle}")
        return table


class LLNDORFallbackRoutingGenerator(LLNTableRoutingGenerator):
    name = "lln_dor_fallback"


def _coord(router: str) -> tuple[int, int, int]:
    coord = parse_router_id(router)
    if coord is None:
        raise ValueError(f"invalid lln router id: {router}")
    return coord


def _lln_path(
    src: tuple[int, int, int],
    dst: tuple[int, int, int],
    dims: dict[str, int],
    long_lookup: dict[str, int],
) -> tuple[list[str], list[int], bool]:
    sx, sy, sz = src
    dx, dy, dz = dst
    _validate_coord(src, dims)
    _validate_coord(dst, dims)

    if (sx, sy) == (dx, dy):
        return _dedupe([router_id(sx, sy, sz), router_id(dx, dy, dz)]), [0], False

    key = projected_pair_key((sx, sy), (dx, dy))
    if key in long_lookup:
        layer = long_lookup[key]
        path = _dedupe(
            [
                router_id(sx, sy, sz),
                router_id(sx, sy, layer),
                router_id(dx, dy, layer),
                router_id(dx, dy, dz),
            ]
        )
        return path, _phase_vcs(path), False

    path = _fallback_core_xy_path(src, dst)
    return path, _phase_vcs(path), True


def _fallback_core_xy_path(
    src: tuple[int, int, int],
    dst: tuple[int, int, int],
) -> list[str]:
    sx, sy, sz = src
    dx, dy, dz = dst
    path = [router_id(sx, sy, sz)]
    x, y, z = sx, sy, sz
    if z != 0:
        z = 0
        path.append(router_id(x, y, z))
    while x != dx:
        x += 1 if dx > x else -1
        path.append(router_id(x, y, z))
    while y != dy:
        y += 1 if dy > y else -1
        path.append(router_id(x, y, z))
    if z != dz:
        z = dz
        path.append(router_id(x, y, z))
    return _dedupe(path)


def _phase_vcs(path: list[str]) -> list[int]:
    if len(path) < 2:
        return []
    horizontal_indices = [
        idx
        for idx, (current, next_hop) in enumerate(zip(path[:-1], path[1:]))
        if _is_horizontal(current, next_hop)
    ]
    if not horizontal_indices:
        return [0] * (len(path) - 1)
    first_horizontal = horizontal_indices[0]
    last_horizontal = horizontal_indices[-1]
    vcs: list[int] = []
    for idx in range(len(path) - 1):
        if idx < first_horizontal:
            vcs.append(0)
        elif idx <= last_horizontal:
            vcs.append(1)
        else:
            vcs.append(2)
    return vcs


def _is_horizontal(current: str, next_hop: str) -> bool:
    cx, cy, cz = _coord(current)
    nx, ny, nz = _coord(next_hop)
    return cz == nz and (cx, cy) != (nx, ny)


def _dedupe(path: list[str]) -> list[str]:
    deduped: list[str] = []
    for node in path:
        if not deduped or deduped[-1] != node:
            deduped.append(node)
    return deduped


def _validate_coord(coord: tuple[int, int, int], dims: dict[str, int]) -> None:
    x, y, z = coord
    if not (0 <= x < dims["x"] and 0 <= y < dims["y"] and 0 <= z < dims["layers"]):
        raise ValueError(f"lln route endpoint out of bounds: {coord}")

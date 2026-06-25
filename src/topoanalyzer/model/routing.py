from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RouteEntry:
    current: str
    destination: str
    next_hop: str
    output_port: str
    vc: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "current": self.current,
            "destination": self.destination,
            "next_hop": self.next_hop,
            "output_port": self.output_port,
            "vc": self.vc,
        }


@dataclass
class RoutingTable:
    name: str
    entries: list[RouteEntry] = field(default_factory=list)
    paths: dict[tuple[str, str], list[str]] = field(default_factory=dict)
    route_vcs: dict[tuple[str, str], int] = field(default_factory=dict)
    path_vcs: dict[tuple[str, str], list[int]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_path(
        self,
        source: str,
        destination: str,
        path: list[str],
        *,
        vc: int = 0,
        hop_vcs: list[int] | None = None,
    ) -> None:
        if len(path) < 2:
            return
        channel_count = len(path) - 1
        if hop_vcs is None:
            hop_vcs = [vc] * channel_count
        if len(hop_vcs) != channel_count:
            raise ValueError(
                "hop_vcs length must match route channel count: "
                f"{len(hop_vcs)} != {channel_count}"
            )
        self.paths[(source, destination)] = list(path)
        self.route_vcs[(source, destination)] = hop_vcs[0]
        self.path_vcs[(source, destination)] = list(hop_vcs)
        for (current, next_hop), hop_vc in zip(zip(path[:-1], path[1:]), hop_vcs):
            self.entries.append(
                RouteEntry(
                    current=current,
                    destination=destination,
                    next_hop=next_hop,
                    output_port=_infer_output_port(current, next_hop),
                    vc=hop_vc,
                )
            )

    def next_hop(self, current: str, destination: str) -> str | None:
        for entry in self.entries:
            if entry.current == current and entry.destination == destination:
                return entry.next_hop
        return None

    def next_hop_with_vc(
        self,
        current: str,
        destination: str,
    ) -> tuple[str, int] | None:
        for entry in self.entries:
            if entry.current == current and entry.destination == destination:
                return entry.next_hop, entry.vc
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "metadata": dict(self.metadata),
            "entries": [entry.to_dict() for entry in self.entries],
            "paths": [
                {
                    "source": src,
                    "destination": dst,
                    "path": path,
                    "vc": self.route_vcs.get((src, dst), 0),
                    "hop_vcs": self.path_vcs.get(
                        (src, dst),
                        [self.route_vcs.get((src, dst), 0)] * max(len(path) - 1, 0),
                    ),
                }
                for (src, dst), path in sorted(self.paths.items())
            ],
        }


def _infer_output_port(current: str, next_hop: str) -> str:
    c = _coord_from_router_id(current)
    n = _coord_from_router_id(next_hop)
    if c is None or n is None:
        return "unknown"
    if n[0] > c[0]:
        return "east"
    if n[0] < c[0]:
        return "west"
    if n[1] > c[1]:
        return "north"
    if n[1] < c[1]:
        return "south"
    return "local"


def _coord_from_router_id(router_id: str) -> tuple[int, int] | None:
    parts = router_id.split(".")
    if len(parts) != 3 or parts[0] != "r":
        return None
    return int(parts[1]), int(parts[2])

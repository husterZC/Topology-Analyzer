from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from topoanalyzer.model.graph import Link
from topoanalyzer.model.system import System


@dataclass(frozen=True)
class AnyNetArtifacts:
    network_file: Path
    route_table_file: Path
    mapping_file: Path


@dataclass(frozen=True)
class AnyNetNetworkArtifacts:
    network_file: Path
    mapping_file: Path


@dataclass(frozen=True)
class TerminalMapping:
    terminal_id: int
    router_id: str
    local_index: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "terminal_id": self.terminal_id,
            "router_id": self.router_id,
            "local_index": self.local_index,
        }


class AnyNetTableExporter:
    """Export a Topology-Analyzer system to BookSim anynet + route-table files."""

    def materialize(self, system: System, run_dir: Path) -> AnyNetArtifacts:
        run_dir.mkdir(parents=True, exist_ok=True)
        network_file = run_dir / "anynet.net"
        route_table_file = run_dir / "anynet.routes"
        mapping_file = run_dir / "anynet_mapping.json"

        router_ids = self.router_ids(system)
        router_index = {router_id: index for index, router_id in enumerate(router_ids)}
        terminals = self.terminal_mappings(system, router_ids)

        network_file.write_text(
            self.network_text(system, router_ids, router_index, terminals),
            encoding="utf-8",
        )
        route_table_file.write_text(
            self.route_table_text(system, router_ids, router_index, terminals),
            encoding="utf-8",
        )
        mapping_file.write_text(
            json.dumps(
                self.mapping(system, router_ids, router_index, terminals),
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return AnyNetArtifacts(network_file, route_table_file, mapping_file)

    def materialize_network(
        self,
        system: System,
        run_dir: Path,
    ) -> AnyNetNetworkArtifacts:
        run_dir.mkdir(parents=True, exist_ok=True)
        network_file = run_dir / "anynet.net"
        mapping_file = run_dir / "anynet_mapping.json"

        router_ids = self.router_ids(system)
        router_index = {router_id: index for index, router_id in enumerate(router_ids)}
        terminals = self.terminal_mappings(system, router_ids)

        network_file.write_text(
            self.network_text(system, router_ids, router_index, terminals),
            encoding="utf-8",
        )
        mapping_file.write_text(
            json.dumps(
                self.mapping(system, router_ids, router_index, terminals),
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return AnyNetNetworkArtifacts(network_file, mapping_file)

    def router_ids(self, system: System) -> list[str]:
        routers = [node for node in system.graph.routers()]
        return [
            node.id
            for node in sorted(
                routers,
                key=lambda node: (
                    int(node.metadata.get("booksim_order", 0)),
                    _coord_sort_key(node.metadata.get("coord")),
                    node.id,
                ),
            )
        ]

    def terminal_mappings(
        self,
        system: System,
        router_ids: list[str],
    ) -> list[TerminalMapping]:
        attachments = system.graph.metadata.get("terminal_attachments")
        if isinstance(attachments, list) and attachments:
            terminals: list[TerminalMapping] = []
            next_terminal = 0
            for attachment in attachments:
                router_id = str(attachment["router_id"])
                if router_id not in router_ids:
                    raise ValueError(
                        "terminal attachment references unknown router: "
                        f"{router_id}"
                    )
                for local_index in range(int(attachment.get("count", 0))):
                    terminals.append(
                        TerminalMapping(
                            terminal_id=next_terminal,
                            router_id=router_id,
                            local_index=local_index,
                        )
                    )
                    next_terminal += 1
            return terminals

        concentration = int(system.graph.metadata.get("concentration", 1))
        terminals: list[TerminalMapping] = []
        next_terminal = 0
        for router_id in router_ids:
            for local_index in range(concentration):
                terminals.append(
                    TerminalMapping(
                        terminal_id=next_terminal,
                        router_id=router_id,
                        local_index=local_index,
                    )
                )
                next_terminal += 1
        return terminals

    def network_text(
        self,
        system: System,
        router_ids: list[str],
        router_index: dict[str, int],
        terminals: list[TerminalMapping],
    ) -> str:
        terminal_by_router: dict[str, list[TerminalMapping]] = {
            router_id: [] for router_id in router_ids
        }
        for terminal in terminals:
            terminal_by_router[terminal.router_id].append(terminal)

        outgoing_links: dict[str, list[Link]] = {router_id: [] for router_id in router_ids}
        for link in system.graph.links:
            if link.src in outgoing_links:
                outgoing_links[link.src].append(link)

        lines: list[str] = []
        for router_id in router_ids:
            tokens = ["router", str(router_index[router_id])]
            for terminal in sorted(
                terminal_by_router[router_id],
                key=lambda terminal: terminal.terminal_id,
            ):
                # Weighted node entries can be misparsed as router self-links by BookSim anynet.
                tokens.extend(["node", str(terminal.terminal_id)])
            for link in sorted(
                outgoing_links[router_id],
                key=lambda link: router_index[link.dst],
            ):
                tokens.extend(
                    [
                        "router",
                        str(router_index[link.dst]),
                        str(link.latency_cycles),
                    ]
                )
            lines.append(" ".join(tokens))
        return "\n".join(lines) + "\n"

    def route_table_text(
        self,
        system: System,
        router_ids: list[str],
        router_index: dict[str, int],
        terminals: list[TerminalMapping],
    ) -> str:
        terminals_by_destination_router: dict[str, list[TerminalMapping]] = {
            router_id: [] for router_id in router_ids
        }
        for terminal in terminals:
            terminals_by_destination_router[terminal.router_id].append(terminal)

        output_ports = self.output_ports(system, router_ids, router_index, terminals)
        terminal_route_lookup = _terminal_route_lookup(system)
        route_lookup = _route_lookup(system)
        destination_routers = [
            router_id
            for router_id in router_ids
            if terminals_by_destination_router[router_id]
        ]
        lines = [
            "# Generated by Topology Analyzer.",
            f"# system = {system.name}",
            "# Format: <router> <destination_terminal> <output_port> <vc>",
        ]
        for current in router_ids:
            current_idx = router_index[current]
            for destination in destination_routers:
                if current == destination:
                    for terminal in terminals_by_destination_router[destination]:
                        lines.append(
                            f"{current_idx} {terminal.terminal_id} "
                            f"{output_ports[(current, terminal.terminal_id)]} 0"
                        )
                    continue

                for terminal in terminals_by_destination_router[destination]:
                    next_hop, route_vc = _route_for_terminal(
                        current,
                        destination,
                        terminal.terminal_id,
                        terminal_route_lookup,
                        route_lookup,
                    )
                    lines.append(
                        f"{current_idx} {terminal.terminal_id} "
                        f"{output_ports[(current, next_hop)]} {route_vc}"
                    )
        return "\n".join(lines) + "\n"

    def output_ports(
        self,
        system: System,
        router_ids: list[str],
        router_index: dict[str, int],
        terminals: list[TerminalMapping],
    ) -> dict[tuple[str, str | int], int]:
        ports: dict[tuple[str, str | int], int] = {}
        terminal_by_router: dict[str, list[TerminalMapping]] = {
            router_id: [] for router_id in router_ids
        }
        for terminal in terminals:
            terminal_by_router[terminal.router_id].append(terminal)

        for router_id in router_ids:
            next_port = 0
            for terminal in sorted(
                terminal_by_router[router_id],
                key=lambda terminal: terminal.terminal_id,
            ):
                ports[(router_id, terminal.terminal_id)] = next_port
                next_port += 1
            neighbors = sorted(
                system.graph.neighbors(router_id),
                key=lambda neighbor: router_index[neighbor],
            )
            for neighbor in neighbors:
                ports[(router_id, neighbor)] = next_port
                next_port += 1
        return ports

    def mapping(
        self,
        system: System,
        router_ids: list[str],
        router_index: dict[str, int],
        terminals: list[TerminalMapping],
    ) -> dict[str, Any]:
        return {
            "system": system.name,
            "topology_type": system.topology_type,
            "routing": system.routing_table.name,
            "routers": [
                {
                    "booksim_router": router_index[router_id],
                    "router_id": router_id,
                    "metadata": dict(system.graph.nodes[router_id].metadata),
                }
                for router_id in router_ids
            ],
            "terminals": [terminal.to_dict() for terminal in terminals],
            "links": [
                {
                    "src": link.src,
                    "dst": link.dst,
                    "booksim_src": router_index[link.src],
                    "booksim_dst": router_index[link.dst],
                    "latency_cycles": link.latency_cycles,
                    "bandwidth": link.bandwidth,
                    "metadata": dict(link.metadata),
                }
                for link in system.graph.links
            ],
            "notes": [
                "BookSim anynet consumes per-directed-link latency.",
                "Per-link bandwidth is preserved as metadata; this BookSim overlay does not yet model per-link bandwidth.",
            ],
        }


def _coord_sort_key(coord: object) -> tuple[int, ...]:
    if isinstance(coord, (list, tuple)):
        try:
            return tuple(int(value) for value in reversed(coord))
        except (TypeError, ValueError):
            return (0,)
    return (0,)


def _terminal_route_lookup(system: System) -> dict[tuple[str, int], tuple[str, int]]:
    terminal_routes = system.routing_table.metadata.get("terminal_next_hops")
    if not isinstance(terminal_routes, dict):
        return {}

    lookup: dict[tuple[str, int], tuple[str, int]] = {}
    for current, current_routes in terminal_routes.items():
        if not isinstance(current_routes, dict):
            continue
        for terminal_id, route in current_routes.items():
            if isinstance(route, dict):
                lookup[(str(current), int(terminal_id))] = (
                    str(route["next_hop"]),
                    int(route.get("vc", 0)),
                )
    return lookup


def _route_lookup(system: System) -> dict[tuple[str, str], tuple[str, int]]:
    return {
        (entry.current, entry.destination): (entry.next_hop, entry.vc)
        for entry in system.routing_table.entries
    }


def _route_for_terminal(
    current: str,
    destination_router: str,
    terminal_id: int,
    terminal_route_lookup: dict[tuple[str, int], tuple[str, int]],
    route_lookup: dict[tuple[str, str], tuple[str, int]],
) -> tuple[str, int]:
    terminal_route = terminal_route_lookup.get((current, terminal_id))
    if terminal_route is not None:
        return terminal_route

    route = route_lookup.get((current, destination_router))
    if route is None:
        raise ValueError(
            "missing next hop while exporting BookSim route table: "
            f"{current} -> {destination_router}"
        )
    return route

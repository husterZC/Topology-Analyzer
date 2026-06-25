from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from topoanalyzer.model.links import LinkSpec


@dataclass(frozen=True)
class Node:
    id: str
    kind: str = "router"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class Link:
    src: str
    dst: str
    latency_cycles: int
    bandwidth: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_spec(
        cls,
        src: str,
        dst: str,
        spec: LinkSpec,
        metadata: dict[str, Any] | None = None,
    ) -> "Link":
        return cls(
            src=src,
            dst=dst,
            latency_cycles=spec.latency_cycles,
            bandwidth=spec.bandwidth,
            metadata={} if metadata is None else dict(metadata),
        )

    @property
    def id(self) -> str:
        return f"{self.src}->{self.dst}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "src": self.src,
            "dst": self.dst,
            "latency_cycles": self.latency_cycles,
            "bandwidth": self.bandwidth,
            "metadata": dict(self.metadata),
        }


@dataclass
class TopologyGraph:
    name: str
    topology_type: str
    nodes: dict[str, Node] = field(default_factory=dict)
    links: list[Link] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_node(self, node: Node) -> None:
        if node.id in self.nodes:
            raise ValueError(f"duplicate node id: {node.id}")
        self.nodes[node.id] = node

    def add_link(self, link: Link) -> None:
        if link.src not in self.nodes:
            raise ValueError(f"unknown link source: {link.src}")
        if link.dst not in self.nodes:
            raise ValueError(f"unknown link destination: {link.dst}")
        self.links.append(link)

    def add_bidirectional_link(
        self,
        a: str,
        b: str,
        spec_ab: LinkSpec,
        spec_ba: LinkSpec | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        meta = {} if metadata is None else dict(metadata)
        self.add_link(Link.from_spec(a, b, spec_ab, meta))
        self.add_link(Link.from_spec(b, a, spec_ba or spec_ab, meta))

    def routers(self) -> list[Node]:
        return [node for node in self.nodes.values() if node.kind == "router"]

    def neighbors(self, node_id: str) -> list[str]:
        return [link.dst for link in self.links if link.src == node_id]

    def link_between(self, src: str, dst: str) -> Link | None:
        for link in self.links:
            if link.src == src and link.dst == dst:
                return link
        return None

    def is_connected(self) -> bool:
        routers = [node.id for node in self.routers()]
        if not routers:
            return False
        seen = {routers[0]}
        stack = [routers[0]]
        while stack:
            node = stack.pop()
            for neighbor in self.neighbors(node):
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        return all(router in seen for router in routers)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "topology_type": self.topology_type,
            "metadata": dict(self.metadata),
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "links": [link.to_dict() for link in self.links],
        }

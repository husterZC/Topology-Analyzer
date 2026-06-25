from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from topoanalyzer.model.graph import Node, TopologyGraph
from topoanalyzer.model.links import LinkParameters
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.topologies.base import TopologyBuilder


@dataclass(frozen=True)
class DragonflyParams:
    p: int
    a: int
    h: int
    groups: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DragonflyParams":
        return cls(
            p=int(data["p"]),
            a=int(data["a"]),
            h=int(data["h"]),
            groups=None if data.get("groups") is None else int(data["groups"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "p": self.p,
            "a": self.a,
            "h": self.h,
            "groups": self.resolved_groups,
        }

    @property
    def resolved_groups(self) -> int:
        return self.groups if self.groups is not None else self.a * self.h + 1


class DragonflyTopologyBuilder(TopologyBuilder):
    name = "dragonfly"
    link_classes = {"local", "global"}

    def validate(
        self,
        params: DragonflyParams,
        links: LinkParameters,
    ) -> ValidationReport:
        report = ValidationReport()
        if params.p <= 0:
            report.add_error("dragonfly p must be positive", p=params.p)
        if params.a <= 1:
            report.add_error("dragonfly a must be greater than 1", a=params.a)
        if params.h <= 0:
            report.add_error("dragonfly h must be positive", h=params.h)
        groups = params.resolved_groups
        if groups <= 1:
            report.add_error("dragonfly groups must be greater than 1", groups=groups)
        if groups - 1 > params.a * params.h:
            report.add_error(
                "dragonfly groups exceed available global ports",
                groups=groups,
                global_ports_per_group=params.a * params.h,
            )
        report.merge(links.validate(allowed_classes=self.link_classes))
        for idx, override in enumerate(links.overrides):
            if not isinstance(override.src, str) or not isinstance(override.dst, str):
                report.add_error(
                    "dragonfly link overrides must use router ID string endpoints",
                    override_index=idx,
                    src=override.src,
                    dst=override.dst,
                )
        return report

    def build(self, params: DragonflyParams, links: LinkParameters) -> TopologyGraph:
        report = self.validate(params, links)
        report.raise_if_errors()

        groups = params.resolved_groups
        router_count = groups * params.a
        graph = TopologyGraph(
            name=f"dragonfly_p{params.p}_a{params.a}_h{params.h}_g{groups}",
            topology_type=self.name,
            metadata={
                "p": params.p,
                "a": params.a,
                "h": params.h,
                "groups": groups,
                "radix": params.p + params.h + params.a - 1,
                "concentration": params.p,
                "terminal_count": router_count * params.p,
                "local_topology": "fully_connected",
                "global_link_arrangement": "absolute_group_index",
            },
        )

        order = 0
        for group in range(groups):
            for router in range(params.a):
                graph.add_node(
                    Node(
                        id=router_id(group, router),
                        kind="router",
                        metadata={
                            "group": group,
                            "router": router,
                            "coord": [group, router],
                            "booksim_order": order,
                        },
                    )
                )
                order += 1

        for group in range(groups):
            for left in range(params.a):
                for right in range(left + 1, params.a):
                    _add_link(
                        graph,
                        links,
                        router_id(group, left),
                        router_id(group, right),
                        "local",
                        {
                            "scope": "local",
                            "group": group,
                            "left_router": left,
                            "right_router": right,
                        },
                    )

        for left_group in range(groups):
            for right_group in range(left_group + 1, groups):
                left_router = _global_router_for_peer(left_group, right_group, params)
                right_router = _global_router_for_peer(right_group, left_group, params)
                _add_link(
                    graph,
                    links,
                    router_id(left_group, left_router),
                    router_id(right_group, right_router),
                    "global",
                    {
                        "scope": "global",
                        "left_group": left_group,
                        "right_group": right_group,
                        "left_router": left_router,
                        "right_router": right_router,
                    },
                )
        return graph


def router_id(group: int, router: int) -> str:
    return f"df.g{group}.r{router}"


def _add_link(
    graph: TopologyGraph,
    links: LinkParameters,
    src: str,
    dst: str,
    link_class: str,
    metadata: dict[str, int | str],
) -> None:
    spec_ab = links.resolve(src, dst, link_class=link_class)
    spec_ba = links.resolve(dst, src, link_class=link_class)
    graph.add_bidirectional_link(
        src,
        dst,
        spec_ab,
        spec_ba,
        metadata={"class": link_class, **metadata},
    )


def _global_router_for_peer(
    group: int,
    peer_group: int,
    params: DragonflyParams,
) -> int:
    index = peer_group if peer_group < group else peer_group - 1
    return index // params.h

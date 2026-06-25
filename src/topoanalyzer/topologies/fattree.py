from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any

from topoanalyzer.model.graph import Link, Node, TopologyGraph
from topoanalyzer.model.links import LinkParameters
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.topologies.base import TopologyBuilder


@dataclass(frozen=True)
class FatTreeParams:
    radix: int
    levels: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FatTreeParams":
        return cls(
            radix=int(data["radix"]),
            levels=int(data["levels"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "radix": self.radix,
            "levels": self.levels,
        }

    @property
    def split(self) -> int:
        return self.radix // 2


class FatTreeTopologyBuilder(TopologyBuilder):
    name = "fattree"

    def validate(self, params: FatTreeParams, links: LinkParameters) -> ValidationReport:
        report = ValidationReport()
        if params.radix <= 1:
            report.add_error("fattree radix must be greater than 1", radix=params.radix)
        if params.radix % 2 != 0:
            report.add_error("fattree radix must be even", radix=params.radix)
        if params.levels < 2:
            report.add_error("fattree levels must be at least 2", levels=params.levels)

        allowed_classes = {"up", "down"}
        for level in range(max(params.levels - 1, 0)):
            allowed_classes.add(f"level_{level}_up")
            allowed_classes.add(f"level_{level}_down")
        report.merge(links.validate(allowed_classes=allowed_classes))
        for idx, override in enumerate(links.overrides):
            if not isinstance(override.src, str) or not isinstance(override.dst, str):
                report.add_error(
                    "fattree link overrides must use router ID string endpoints",
                    override_index=idx,
                    src=override.src,
                    dst=override.dst,
                )
        return report

    def build(self, params: FatTreeParams, links: LinkParameters) -> TopologyGraph:
        report = self.validate(params, links)
        report.raise_if_errors()

        split = params.split
        routers_per_level = split ** (params.levels - 1)
        terminal_count = split ** params.levels
        graph = TopologyGraph(
            name=f"fattree_r{params.radix}_l{params.levels}",
            topology_type=self.name,
            metadata={
                "radix": params.radix,
                "levels": params.levels,
                "split": split,
                "routers_per_level": routers_per_level,
                "terminal_count": terminal_count,
                "terminal_attachments": [],
            },
        )

        order = 0
        for level in range(params.levels):
            for coord in _coords(split, params.levels - 1):
                router = router_id(level, coord)
                graph.add_node(
                    Node(
                        id=router,
                        kind="router",
                        metadata={
                            "level": level,
                            "coord": list(coord),
                            "fixed_digits": _fixed_digits(level, coord, params.levels),
                            "role": _role(level, params.levels),
                            "booksim_order": order,
                        },
                    )
                )
                order += 1

        for leaf in sorted(
            (node for node in graph.routers() if node.metadata["level"] == 0),
            key=lambda node: node.metadata["booksim_order"],
        ):
            graph.metadata["terminal_attachments"].append(
                {"router_id": leaf.id, "count": split}
            )

        for level in range(params.levels - 1):
            for lower_coord in _coords(split, params.levels - 1):
                lower = router_id(level, lower_coord)
                lower_fixed = _fixed_digits(level, lower_coord, params.levels)
                for missing_digit in range(split):
                    full_digits = dict(lower_fixed)
                    full_digits[level] = missing_digit
                    upper_coord = _coord_from_full_digits(
                        excluded_level=level + 1,
                        full_digits=full_digits,
                        levels=params.levels,
                    )
                    upper = router_id(level + 1, upper_coord)
                    self._add_fattree_link(graph, links, lower, upper, level)
        return graph

    @staticmethod
    def _add_fattree_link(
        graph: TopologyGraph,
        links: LinkParameters,
        lower: str,
        upper: str,
        lower_level: int,
    ) -> None:
        up_spec = links.resolve(
            lower,
            upper,
            link_class=_link_class(links, lower_level, "up"),
        )
        down_spec = links.resolve(
            upper,
            lower,
            link_class=_link_class(links, lower_level, "down"),
        )
        graph.add_link(
            Link.from_spec(
                lower,
                upper,
                up_spec,
                {
                    "class": _link_class(links, lower_level, "up") or "default",
                    "direction": "up",
                    "lower_level": lower_level,
                    "upper_level": lower_level + 1,
                },
            )
        )
        graph.add_link(
            Link.from_spec(
                upper,
                lower,
                down_spec,
                {
                    "class": _link_class(links, lower_level, "down") or "default",
                    "direction": "down",
                    "lower_level": lower_level,
                    "upper_level": lower_level + 1,
                },
            )
        )


def router_id(level: int, coord: tuple[int, ...]) -> str:
    return "ft.l" + str(level) + "." + ".".join(str(value) for value in coord)


def _coords(split: int, width: int) -> list[tuple[int, ...]]:
    return list(product(range(split), repeat=width))


def _fixed_digits(level: int, coord: tuple[int, ...], levels: int) -> dict[int, int]:
    fixed: dict[int, int] = {}
    coord_index = 0
    for digit_position in range(levels):
        if digit_position == level:
            continue
        fixed[digit_position] = int(coord[coord_index])
        coord_index += 1
    return fixed


def _coord_from_full_digits(
    *,
    excluded_level: int,
    full_digits: dict[int, int],
    levels: int,
) -> tuple[int, ...]:
    return tuple(
        full_digits[digit_position]
        for digit_position in range(levels)
        if digit_position != excluded_level
    )


def _role(level: int, levels: int) -> str:
    if level == 0:
        return "leaf"
    if level == levels - 1:
        return "root"
    return "intermediate"


def _link_class(
    links: LinkParameters,
    lower_level: int,
    direction: str,
) -> str | None:
    level_class = f"level_{lower_level}_{direction}"
    if level_class in links.classes:
        return level_class
    if direction in links.classes:
        return direction
    return None

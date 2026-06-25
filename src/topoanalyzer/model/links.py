from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from topoanalyzer.model.validation import ValidationReport


Coordinate = tuple[int, ...]


@dataclass(frozen=True)
class LinkSpec:
    latency_cycles: int
    bandwidth: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LinkSpec":
        return cls(
            latency_cycles=int(data["latency_cycles"]),
            bandwidth=str(data["bandwidth"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "latency_cycles": self.latency_cycles,
            "bandwidth": self.bandwidth,
        }

    def validate(self) -> ValidationReport:
        report = ValidationReport()
        if self.latency_cycles <= 0:
            report.add_error(
                "link latency must be positive",
                latency_cycles=self.latency_cycles,
            )
        if not self.bandwidth:
            report.add_error("link bandwidth must be non-empty")
        return report


@dataclass(frozen=True)
class LinkOverride:
    src: Coordinate | str
    dst: Coordinate | str
    spec: LinkSpec
    directed: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LinkOverride":
        src = _parse_endpoint(data["src"])
        dst = _parse_endpoint(data["dst"])
        spec = LinkSpec.from_dict(data)
        return cls(
            src=src,
            dst=dst,
            spec=spec,
            directed=bool(data.get("directed", False)),
        )

    def matches(self, src: Coordinate | str, dst: Coordinate | str) -> bool:
        if self.src == src and self.dst == dst:
            return True
        return not self.directed and self.src == dst and self.dst == src

    def to_dict(self) -> dict[str, Any]:
        return {
            "src": self.src,
            "dst": self.dst,
            "directed": self.directed,
            **self.spec.to_dict(),
        }


@dataclass(frozen=True)
class LinkParameters:
    default: LinkSpec
    classes: dict[str, LinkSpec] = field(default_factory=dict)
    overrides: tuple[LinkOverride, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LinkParameters":
        default = LinkSpec.from_dict(data["default"])
        classes = {
            str(name): LinkSpec.from_dict(spec)
            for name, spec in data.get("classes", {}).items()
        }
        overrides = tuple(
            LinkOverride.from_dict(item) for item in data.get("overrides", [])
        )
        return cls(default=default, classes=classes, overrides=overrides)

    def resolve(
        self,
        src: Coordinate | str,
        dst: Coordinate | str,
        link_class: str | None = None,
    ) -> LinkSpec:
        for override in self.overrides:
            if override.matches(src, dst):
                return override.spec
        if link_class and link_class in self.classes:
            return self.classes[link_class]
        return self.default

    def validate(self, allowed_classes: Iterable[str] | None = None) -> ValidationReport:
        report = ValidationReport()
        report.merge(self.default.validate())
        for name, spec in self.classes.items():
            if allowed_classes is not None and name not in allowed_classes:
                report.add_error("unknown link class", link_class=name)
            class_report = spec.validate()
            for issue in class_report.issues:
                report.issues.append(
                    type(issue)(
                        issue.level,
                        issue.message,
                        {**issue.context, "link_class": name},
                    )
                )
        for idx, override in enumerate(self.overrides):
            override_report = override.spec.validate()
            for issue in override_report.issues:
                report.issues.append(
                    type(issue)(
                        issue.level,
                        issue.message,
                        {**issue.context, "override_index": idx},
                    )
                )
        return report

    def is_homogeneous(self) -> bool:
        specs = [self.default, *self.classes.values()]
        specs.extend(override.spec for override in self.overrides)
        return all(spec == self.default for spec in specs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "default": self.default.to_dict(),
            "classes": {name: spec.to_dict() for name, spec in self.classes.items()},
            "overrides": [override.to_dict() for override in self.overrides],
        }


def _parse_endpoint(value: Any) -> Coordinate | str:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return tuple(int(item) for item in value)
    return str(value)

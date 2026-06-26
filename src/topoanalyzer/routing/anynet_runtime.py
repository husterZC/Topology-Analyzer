from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import ClassVar

from topoanalyzer.model.graph import TopologyGraph
from topoanalyzer.model.routing import RoutingTable
from topoanalyzer.model.validation import ValidationReport
from topoanalyzer.routing.base import RoutingGenerator
from topoanalyzer.routing.dragonfly_min import DragonflyMinimalRoutingGenerator
from topoanalyzer.routing.dragonfly_valiant_hash import (
    DragonflyValiantHashRoutingGenerator,
)
from topoanalyzer.routing.hypercube_ecube import HypercubeECubeRoutingGenerator
from topoanalyzer.routing.hypercube_valiant_hash import (
    HypercubeValiantHashRoutingGenerator,
)
from topoanalyzer.routing.lln_table import LLNTableRoutingGenerator
from topoanalyzer.routing.slimnoc_min import SlimNoCMinimalRoutingGenerator
from topoanalyzer.routing.slimnoc_valiant_hash import (
    SlimNoCValiantHashRoutingGenerator,
)


@dataclass(frozen=True)
class AnyNetRuntimeRoutingGenerator(RoutingGenerator):
    """Marker table for BookSim anynet runtime routing functions.

    The representative static routing table is used for topology sanity checks
    and metadata export. BookSim must use the generated runtime routing function
    rather than the representative paths for actual adaptive decisions.
    """

    seed: int = 0
    candidates: int = 4
    adaptive_threshold: int = 0

    name: ClassVar[str]
    topology_type: ClassVar[str]
    routing_function: ClassVar[str]
    algorithm: ClassVar[str]
    required_vcs: ClassVar[int]
    description: ClassVar[str]
    vc_policy: ClassVar[dict[str, str]]

    def validate(self, graph: TopologyGraph) -> ValidationReport:
        report = ValidationReport()
        if graph.topology_type != self.topology_type:
            report.add_error(
                f"{self.name} routing requires a {self.topology_type} topology",
                topology_type=graph.topology_type,
            )
        if not graph.is_connected():
            report.add_error(f"{self.name} routing requires a connected graph")
        return report

    def generate(self, graph: TopologyGraph) -> RoutingTable:
        report = self.validate(graph)
        report.raise_if_errors()

        table = copy.deepcopy(self.representative_generator().generate(graph))
        table.name = self.name
        table.metadata = {
            **table.metadata,
            "algorithm": self.algorithm,
            "description": self.description,
            "seed": self.seed,
            "candidates": self.candidates,
            "adaptive_threshold": self.adaptive_threshold,
            "vc_policy": dict(self.vc_policy),
            "required_vcs": self.required_vcs,
            "booksim_runtime_routing": {
                "backend": "anynet_runtime",
                "topology": "anynet",
                "routing_function": self.routing_function,
                "seed": self.seed,
                "candidates": self.candidates,
                "adaptive_threshold": self.adaptive_threshold,
                "required_vcs": self.required_vcs,
            },
        }
        return table

    def representative_generator(self) -> RoutingGenerator:
        raise NotImplementedError


class DragonflyUGALLRuntimeRoutingGenerator(AnyNetRuntimeRoutingGenerator):
    name = "dragonfly_ugal_l_runtime"
    topology_type = "dragonfly"
    routing_function = "dragonfly_ugal_l"
    algorithm = "booksim_runtime_dragonfly_ugal_l"
    required_vcs = 3
    description = (
        "BookSim runtime local UGAL-style Dragonfly routing. The source router "
        "chooses minimal or Valiant-like non-minimal routing from local credit "
        "pressure; the representative table uses minimal Dragonfly routing."
    )
    vc_policy = {
        "0": "deterministic escape/minimal fallback",
        "1": "adaptive minimal route",
        "2": "non-minimal route after intermediate selection",
    }

    def representative_generator(self) -> RoutingGenerator:
        return DragonflyMinimalRoutingGenerator()


class DragonflyValGRuntimeRoutingGenerator(AnyNetRuntimeRoutingGenerator):
    name = "dragonfly_valg_runtime"
    topology_type = "dragonfly"
    routing_function = "dragonfly_valg"
    algorithm = "booksim_runtime_dragonfly_valg"
    required_vcs = 3
    description = (
        "BookSim runtime Valiant-global Dragonfly baseline. Packets route via "
        "a hashed/random intermediate group before the final destination group."
    )
    vc_policy = {
        "0": "source to intermediate group",
        "1": "intermediate to destination group",
        "2": "destination-group delivery",
    }

    def representative_generator(self) -> RoutingGenerator:
        return DragonflyValiantHashRoutingGenerator(seed=self.seed)


class DragonflyValNRuntimeRoutingGenerator(DragonflyValGRuntimeRoutingGenerator):
    name = "dragonfly_valn_runtime"
    routing_function = "dragonfly_valn"
    algorithm = "booksim_runtime_dragonfly_valn"
    required_vcs = 4
    description = (
        "BookSim runtime Valiant-node Dragonfly baseline. Packets route via a "
        "hashed/random intermediate router, which can avoid intermediate-group "
        "local-link hot spots better than VALg."
    )
    vc_policy = {
        "0": "source group to intermediate router",
        "1": "intermediate local detour",
        "2": "intermediate group to destination group",
        "3": "destination-group delivery",
    }


class DragonflyPARRuntimeRoutingGenerator(AnyNetRuntimeRoutingGenerator):
    name = "dragonfly_par_runtime"
    topology_type = "dragonfly"
    routing_function = "dragonfly_par"
    algorithm = "booksim_runtime_dragonfly_par"
    required_vcs = 5
    description = (
        "BookSim runtime Progressive Adaptive Routing approximation for "
        "Dragonfly. Source-group routers may re-evaluate a previous UGAL "
        "decision using local credit pressure."
    )
    vc_policy = {
        "0": "escape/minimal fallback",
        "1": "initial adaptive minimal",
        "2": "progressive source-group detour",
        "3": "non-minimal transit",
        "4": "final delivery",
    }

    def representative_generator(self) -> RoutingGenerator:
        return DragonflyValiantHashRoutingGenerator(seed=self.seed)


class HypercubeMinAdaptiveRuntimeRoutingGenerator(AnyNetRuntimeRoutingGenerator):
    name = "hypercube_min_adaptive_runtime"
    topology_type = "hypercube"
    routing_function = "hypercube_min_adaptive"
    algorithm = "booksim_runtime_hypercube_min_adaptive"
    required_vcs = 2
    description = (
        "BookSim runtime minimal-adaptive Hypercube routing. The escape path is "
        "deterministic E-cube; higher VCs can choose among shortest dimensions "
        "using local credit pressure."
    )
    vc_policy = {
        "0": "deterministic E-cube escape",
        "1": "minimal adaptive dimensions",
    }

    def representative_generator(self) -> RoutingGenerator:
        return HypercubeECubeRoutingGenerator()


class HypercubeValiantRuntimeRoutingGenerator(AnyNetRuntimeRoutingGenerator):
    name = "hypercube_valiant_runtime"
    topology_type = "hypercube"
    routing_function = "hypercube_valiant"
    algorithm = "booksim_runtime_hypercube_valiant"
    required_vcs = 2
    description = (
        "BookSim runtime Hypercube Valiant baseline. Packets use a hashed/random "
        "intermediate node and deterministic shortest routing in each phase."
    )
    vc_policy = {
        "0": "source to intermediate",
        "1": "intermediate to destination",
    }

    def representative_generator(self) -> RoutingGenerator:
        return HypercubeValiantHashRoutingGenerator(seed=self.seed)


class HypercubeUGALLRuntimeRoutingGenerator(HypercubeValiantRuntimeRoutingGenerator):
    name = "hypercube_ugal_l_runtime"
    routing_function = "hypercube_ugal_l"
    algorithm = "booksim_runtime_hypercube_ugal_l"
    required_vcs = 3
    description = (
        "BookSim runtime local UGAL-style Hypercube routing. The source chooses "
        "minimal adaptive routing or a Valiant-like detour from local credit "
        "pressure."
    )
    vc_policy = {
        "0": "deterministic E-cube escape",
        "1": "adaptive minimal route",
        "2": "non-minimal route after intermediate selection",
    }


class SlimNoCUGALLRuntimeRoutingGenerator(AnyNetRuntimeRoutingGenerator):
    name = "slimnoc_ugal_l_runtime"
    topology_type = "slimnoc"
    routing_function = "slimnoc_ugal_l"
    algorithm = "booksim_runtime_slimnoc_ugal_l"
    required_vcs = 3
    description = (
        "BookSim runtime local UGAL routing for SlimNoC/SlimFly. It chooses "
        "between minimal and Valiant-like paths from local output credit "
        "pressure."
    )
    vc_policy = {
        "0": "deterministic minimal escape",
        "1": "adaptive minimal route",
        "2": "non-minimal route after intermediate selection",
    }

    def representative_generator(self) -> RoutingGenerator:
        return SlimNoCMinimalRoutingGenerator()


class SlimNoCUGALGRuntimeRoutingGenerator(SlimNoCUGALLRuntimeRoutingGenerator):
    name = "slimnoc_ugal_g_runtime"
    routing_function = "slimnoc_ugal_g"
    algorithm = "booksim_runtime_slimnoc_ugal_g"
    description = (
        "BookSim runtime UGAL-G-style SlimNoC/SlimFly routing. This backend "
        "samples multiple non-minimal candidates and scores path pressure more "
        "globally than UGAL-L where BookSim exposes the needed credits."
    )


class SlimNoCValiantRuntimeRoutingGenerator(AnyNetRuntimeRoutingGenerator):
    name = "slimnoc_valiant_runtime"
    topology_type = "slimnoc"
    routing_function = "slimnoc_valiant"
    algorithm = "booksim_runtime_slimnoc_valiant"
    required_vcs = 4
    description = (
        "BookSim runtime SlimNoC/SlimFly Valiant baseline using a hashed/random "
        "intermediate router."
    )
    vc_policy = {
        "0": "first hop toward intermediate",
        "1": "final hop toward intermediate",
        "2": "first hop from intermediate",
        "3": "final hop to destination",
    }

    def representative_generator(self) -> RoutingGenerator:
        return SlimNoCValiantHashRoutingGenerator(seed=self.seed)


class LLNAdaptiveLayerRuntimeRoutingGenerator(AnyNetRuntimeRoutingGenerator):
    name = "lln_adaptive_layer_runtime"
    topology_type = "lln"
    routing_function = "lln_adaptive_layer"
    algorithm = "booksim_runtime_lln_adaptive_layer"
    required_vcs = 3
    description = (
        "BookSim runtime LLN adaptive-layer extension. The LLN paper uses "
        "deterministic table routing; this extension chooses among runtime "
        "minimal/long-link candidates from local credit pressure."
    )
    vc_policy = {
        "0": "pre-horizontal vertical or deterministic escape",
        "1": "horizontal or long-link phase",
        "2": "post-horizontal vertical delivery",
    }

    def representative_generator(self) -> RoutingGenerator:
        return LLNTableRoutingGenerator()

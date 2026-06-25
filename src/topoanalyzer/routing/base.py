from __future__ import annotations

from abc import ABC, abstractmethod

from topoanalyzer.model.graph import TopologyGraph
from topoanalyzer.model.routing import RoutingTable
from topoanalyzer.model.validation import ValidationReport


class RoutingGenerator(ABC):
    name: str

    @abstractmethod
    def generate(self, graph: TopologyGraph) -> RoutingTable:
        raise NotImplementedError

    @abstractmethod
    def validate(self, graph: TopologyGraph) -> ValidationReport:
        raise NotImplementedError

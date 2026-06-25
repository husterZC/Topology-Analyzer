from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from topoanalyzer.model.graph import TopologyGraph
from topoanalyzer.model.links import LinkParameters
from topoanalyzer.model.validation import ValidationReport


class TopologyBuilder(ABC):
    name: str

    @abstractmethod
    def build(self, params: Any, links: LinkParameters) -> TopologyGraph:
        raise NotImplementedError

    @abstractmethod
    def validate(self, params: Any, links: LinkParameters) -> ValidationReport:
        raise NotImplementedError

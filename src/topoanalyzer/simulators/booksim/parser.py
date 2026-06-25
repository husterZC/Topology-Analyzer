from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SimulationMetrics:
    average_packet_latency: float | None = None
    average_network_latency: float | None = None
    accepted_rate: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "average_packet_latency": self.average_packet_latency,
            "average_network_latency": self.average_network_latency,
            "accepted_rate": self.accepted_rate,
            "raw": dict(self.raw),
        }


def parse_booksim_output(text: str) -> SimulationMetrics:
    raw: dict[str, Any] = {}
    packet_latency = _last_float(
        text,
        [
            r"Average\s+packet\s+latency\s*[:=]\s*([-+0-9.eE]+)",
            r"Packet\s+latency\s+average\s*[:=]\s*([-+0-9.eE]+)",
            r"Overall\s+average\s+latency\s*[:=]\s*([-+0-9.eE]+)",
        ],
    )
    network_latency = _last_float(
        text,
        [
            r"Average\s+network\s+latency\s*[:=]\s*([-+0-9.eE]+)",
            r"Network\s+latency\s+average\s*[:=]\s*([-+0-9.eE]+)",
        ],
    )
    accepted_rate = _last_float(
        text,
        [
            r"Accepted\s+rate\s*[:=]\s*([-+0-9.eE]+)",
            r"Overall\s+accepted\s+rate\s*[:=]\s*([-+0-9.eE]+)",
            r"Accepted\s+packet\s+rate\s+average\s*[:=]\s*([-+0-9.eE]+)",
        ],
    )
    if packet_latency is not None:
        raw["matched_packet_latency"] = packet_latency
    if network_latency is not None:
        raw["matched_network_latency"] = network_latency
    if accepted_rate is not None:
        raw["matched_accepted_rate"] = accepted_rate
    return SimulationMetrics(
        average_packet_latency=packet_latency,
        average_network_latency=network_latency,
        accepted_rate=accepted_rate,
        raw=raw,
    )


def _last_float(text: str, patterns: list[str]) -> float | None:
    for pattern in patterns:
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        if matches:
            return float(matches[-1])
    return None

from __future__ import annotations

from collections import defaultdict

from topoanalyzer.model.routing import RoutingTable

Channel = tuple[str, str, int]


def channel_dependency_has_cycle(table: RoutingTable) -> tuple[bool, list[Channel]]:
    graph: dict[Channel, set[Channel]] = defaultdict(set)
    for route, path in table.paths.items():
        vc = table.route_vcs.get(route, 0)
        channels = [(src, dst, vc) for src, dst in zip(path[:-1], path[1:])]
        for first, second in zip(channels[:-1], channels[1:]):
            graph[first].add(second)
            graph.setdefault(second, set())

    visited: set[Channel] = set()
    active: set[Channel] = set()
    stack: list[Channel] = []

    def visit(channel: Channel) -> list[Channel] | None:
        visited.add(channel)
        active.add(channel)
        stack.append(channel)
        for neighbor in graph[channel]:
            if neighbor not in visited:
                cycle = visit(neighbor)
                if cycle:
                    return cycle
            elif neighbor in active:
                start = stack.index(neighbor)
                return stack[start:] + [neighbor]
        active.remove(channel)
        stack.pop()
        return None

    for channel in list(graph):
        if channel in visited:
            continue
        cycle = visit(channel)
        if cycle:
            return True, cycle
    return False, []

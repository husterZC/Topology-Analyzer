from __future__ import annotations

from typing import Any

from topoanalyzer.model.links import LinkParameters
from topoanalyzer.model.system import System
from topoanalyzer.routing.graph_lash import GraphLashRoutingGenerator
from topoanalyzer.routing.graph_updown import GraphUpDownRoutingGenerator
from topoanalyzer.routing.mesh_xy import Mesh2DXYRoutingGenerator
from topoanalyzer.topologies.mesh2d import Mesh2DParams, Mesh2DTopologyBuilder


def build_system_from_dict(data: dict[str, Any]) -> System:
    name = str(data["name"])
    topology_spec = data["topology"]
    topology_type = str(topology_spec["type"])
    routing_spec = data.get("routing", {"type": "mesh_xy"})
    routing_type = str(routing_spec["type"])

    link_params = LinkParameters.from_dict(data["links"])

    if topology_type == "mesh2d":
        topology_params = Mesh2DParams.from_dict(topology_spec["params"])
        topology_builder = Mesh2DTopologyBuilder()
    else:
        raise ValueError(f"unsupported topology type: {topology_type}")

    graph = topology_builder.build(topology_params, link_params)

    if routing_type == "mesh_xy":
        routing_generator = Mesh2DXYRoutingGenerator()
    elif routing_type == "graph_lash":
        routing_generator = GraphLashRoutingGenerator(
            max_vcs=int(routing_spec.get("max_vcs", 4)),
            candidate_paths=int(routing_spec.get("candidate_paths", 8)),
        )
    elif routing_type == "graph_updown":
        routing_generator = GraphUpDownRoutingGenerator(root=routing_spec.get("root"))
    else:
        raise ValueError(f"unsupported routing type: {routing_type}")

    routing_table = routing_generator.generate(graph)
    system = System(
        name=name,
        topology_type=topology_type,
        topology_params=topology_params.to_dict(),
        link_params=link_params,
        graph=graph,
        routing_table=routing_table,
        metadata={"routing": routing_spec},
    )
    system.validate().raise_if_errors()
    return system

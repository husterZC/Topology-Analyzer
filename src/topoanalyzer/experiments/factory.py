from __future__ import annotations

from typing import Any

from topoanalyzer.model.links import LinkParameters
from topoanalyzer.model.system import System
from topoanalyzer.routing.dragonfly_min import DragonflyMinimalRoutingGenerator
from topoanalyzer.routing.dragonfly_valiant_hash import (
    DragonflyValiantHashRoutingGenerator,
)
from topoanalyzer.routing.fattree_anca import FatTreeANCARoutingGenerator
from topoanalyzer.routing.fattree_common import parse_disabled_links
from topoanalyzer.routing.fattree_dmodc import FatTreeDmodcRoutingGenerator
from topoanalyzer.routing.fattree_dmodk import FatTreeDmodKRoutingGenerator
from topoanalyzer.routing.fattree_lca import FatTreeLCARoutingGenerator
from topoanalyzer.routing.fattree_nca_hash import FatTreeNCAHashRoutingGenerator
from topoanalyzer.routing.graph_lash import GraphLashRoutingGenerator
from topoanalyzer.routing.graph_updown import GraphUpDownRoutingGenerator
from topoanalyzer.routing.hypercube_ecube import HypercubeECubeRoutingGenerator
from topoanalyzer.routing.hypercube_lash import HypercubeLashRoutingGenerator
from topoanalyzer.routing.hypercube_valiant_hash import (
    HypercubeValiantHashRoutingGenerator,
)
from topoanalyzer.routing.mesh_xy import Mesh2DXYRoutingGenerator
from topoanalyzer.routing.mesh_xyz import Mesh3DXYZRoutingGenerator
from topoanalyzer.routing.ruche_lash import Ruche3DLashRoutingGenerator
from topoanalyzer.routing.ruche_valiant_hash import (
    Ruche3DValiantHashRoutingGenerator,
)
from topoanalyzer.routing.ruche_xyz import Ruche3DXYZRoutingGenerator
from topoanalyzer.routing.torus_xy import Torus2DXYRoutingGenerator
from topoanalyzer.routing.torus_xyz import Torus3DXYZRoutingGenerator
from topoanalyzer.topologies.dragonfly import DragonflyParams, DragonflyTopologyBuilder
from topoanalyzer.topologies.fattree import FatTreeParams, FatTreeTopologyBuilder
from topoanalyzer.topologies.hypercube import HypercubeParams, HypercubeTopologyBuilder
from topoanalyzer.topologies.mesh2d import Mesh2DParams, Mesh2DTopologyBuilder
from topoanalyzer.topologies.mesh3d import Mesh3DParams, Mesh3DTopologyBuilder
from topoanalyzer.topologies.ruche3d import Ruche3DParams, Ruche3DTopologyBuilder
from topoanalyzer.topologies.torus2d import Torus2DParams, Torus2DTopologyBuilder
from topoanalyzer.topologies.torus3d import Torus3DParams, Torus3DTopologyBuilder


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
    elif topology_type == "mesh3d":
        topology_params = Mesh3DParams.from_dict(topology_spec["params"])
        topology_builder = Mesh3DTopologyBuilder()
    elif topology_type == "torus2d":
        topology_params = Torus2DParams.from_dict(topology_spec["params"])
        topology_builder = Torus2DTopologyBuilder()
    elif topology_type == "torus3d":
        topology_params = Torus3DParams.from_dict(topology_spec["params"])
        topology_builder = Torus3DTopologyBuilder()
    elif topology_type == "ruche3d":
        topology_params = Ruche3DParams.from_dict(topology_spec["params"])
        topology_builder = Ruche3DTopologyBuilder()
    elif topology_type == "hypercube":
        topology_params = HypercubeParams.from_dict(topology_spec["params"])
        topology_builder = HypercubeTopologyBuilder()
    elif topology_type == "dragonfly":
        topology_params = DragonflyParams.from_dict(topology_spec["params"])
        topology_builder = DragonflyTopologyBuilder()
    elif topology_type == "fattree":
        topology_params = FatTreeParams.from_dict(topology_spec["params"])
        topology_builder = FatTreeTopologyBuilder()
    else:
        raise ValueError(f"unsupported topology type: {topology_type}")

    graph = topology_builder.build(topology_params, link_params)

    if routing_type == "mesh_xy":
        routing_generator = Mesh2DXYRoutingGenerator()
    elif routing_type == "mesh_xyz":
        routing_generator = Mesh3DXYZRoutingGenerator()
    elif routing_type == "torus_xy":
        routing_generator = Torus2DXYRoutingGenerator()
    elif routing_type == "torus_xyz":
        routing_generator = Torus3DXYZRoutingGenerator()
    elif routing_type == "ruche_xyz":
        routing_generator = Ruche3DXYZRoutingGenerator()
    elif routing_type == "ruche_lash":
        routing_generator = Ruche3DLashRoutingGenerator(
            max_vcs=int(routing_spec.get("max_vcs", 8)),
            candidate_paths=int(routing_spec.get("candidate_paths", 8)),
        )
    elif routing_type == "ruche_valiant_hash":
        routing_generator = Ruche3DValiantHashRoutingGenerator(
            seed=int(routing_spec.get("seed", 0)),
        )
    elif routing_type == "hypercube_ecube":
        routing_generator = HypercubeECubeRoutingGenerator()
    elif routing_type == "hypercube_lash":
        routing_generator = HypercubeLashRoutingGenerator(
            max_vcs=int(routing_spec.get("max_vcs", 4)),
            candidate_paths=int(routing_spec.get("candidate_paths", 8)),
            seed=int(routing_spec.get("seed", 0)),
        )
    elif routing_type == "hypercube_valiant_hash":
        routing_generator = HypercubeValiantHashRoutingGenerator(
            seed=int(routing_spec.get("seed", 0)),
        )
    elif routing_type == "dragonfly_min":
        routing_generator = DragonflyMinimalRoutingGenerator()
    elif routing_type == "dragonfly_valiant_hash":
        routing_generator = DragonflyValiantHashRoutingGenerator(
            seed=int(routing_spec.get("seed", 0)),
            nonminimal_same_group=bool(routing_spec.get("nonminimal_same_group", False)),
        )
    elif routing_type == "fattree_lca":
        routing_generator = FatTreeLCARoutingGenerator()
    elif routing_type == "fattree_nca_hash":
        routing_generator = FatTreeNCAHashRoutingGenerator(
            seed=int(routing_spec.get("seed", 0)),
        )
    elif routing_type == "fattree_dmodk":
        routing_generator = FatTreeDmodKRoutingGenerator()
    elif routing_type == "fattree_dmodc":
        routing_generator = FatTreeDmodcRoutingGenerator(
            disabled_links=parse_disabled_links(routing_spec.get("disabled_links")),
        )
    elif routing_type == "fattree_anca":
        routing_generator = FatTreeANCARoutingGenerator()
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

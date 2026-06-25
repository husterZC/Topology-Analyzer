import unittest

from topoanalyzer.model.links import LinkParameters
from topoanalyzer.model.routing import RoutingTable
from topoanalyzer.model.system import System
from topoanalyzer.routing.deadlock import channel_dependency_has_cycle
from topoanalyzer.routing.graph_lash import GraphLashRoutingGenerator
from topoanalyzer.routing.graph_updown import GraphUpDownRoutingGenerator
from topoanalyzer.routing.mesh_xy import Mesh2DXYRoutingGenerator
from topoanalyzer.topologies.mesh2d import Mesh2DParams, Mesh2DTopologyBuilder


class RoutingTests(unittest.TestCase):
    def test_xy_routing_moves_x_then_y(self):
        links = LinkParameters.from_dict(
            {"default": {"latency_cycles": 2, "bandwidth": "64GB/s"}}
        )
        params = Mesh2DParams(x=3, y=2)
        graph = Mesh2DTopologyBuilder().build(params, links)
        table = Mesh2DXYRoutingGenerator().generate(graph)

        self.assertEqual(
            table.paths[("r.0.0", "r.2.1")],
            ["r.0.0", "r.1.0", "r.2.0", "r.2.1"],
        )
        system = System(
            name="mesh",
            topology_type="mesh2d",
            topology_params=params.to_dict(),
            link_params=links,
            graph=graph,
            routing_table=table,
        )
        self.assertTrue(system.validate().ok)

    def test_graph_updown_routing_is_deadlock_free_on_mesh(self):
        links = LinkParameters.from_dict(
            {"default": {"latency_cycles": 2, "bandwidth": "64GB/s"}}
        )
        params = Mesh2DParams(x=4, y=4)
        graph = Mesh2DTopologyBuilder().build(params, links)
        table = GraphUpDownRoutingGenerator(root="r.0.0").generate(graph)

        self.assertEqual(table.name, "graph_updown")
        self.assertEqual(table.metadata["root"], "r.0.0")
        self.assertEqual(table.paths[("r.3.3", "r.0.0")][-1], "r.0.0")
        system = System(
            name="mesh_updown",
            topology_type="mesh2d",
            topology_params=params.to_dict(),
            link_params=links,
            graph=graph,
            routing_table=table,
        )
        self.assertTrue(system.validate().ok)

    def test_channel_dependency_check_is_vc_aware(self):
        cyclic = RoutingTable(name="cyclic")
        cyclic.add_path("a", "c", ["a", "b", "c"], vc=0)
        cyclic.add_path("b", "a", ["b", "c", "a"], vc=0)
        cyclic.add_path("c", "b", ["c", "a", "b"], vc=0)

        self.assertTrue(channel_dependency_has_cycle(cyclic)[0])

        layered = RoutingTable(name="layered")
        layered.add_path("a", "c", ["a", "b", "c"], vc=0)
        layered.add_path("b", "a", ["b", "c", "a"], vc=1)
        layered.add_path("c", "b", ["c", "a", "b"], vc=2)

        self.assertFalse(channel_dependency_has_cycle(layered)[0])

    def test_graph_lash_uses_vc_layers_for_shortest_paths(self):
        links = LinkParameters.from_dict(
            {"default": {"latency_cycles": 2, "bandwidth": "64GB/s"}}
        )
        params = Mesh2DParams(x=3, y=3)
        graph = Mesh2DTopologyBuilder().build(params, links)
        table = GraphLashRoutingGenerator(max_vcs=4, candidate_paths=8).generate(graph)

        self.assertEqual(table.name, "graph_lash")
        self.assertLessEqual(table.metadata["used_vcs"], 4)
        self.assertEqual(
            len(table.paths[("r.2.2", "r.0.2")]) - 1,
            2,
        )
        system = System(
            name="mesh_lash",
            topology_type="mesh2d",
            topology_params=params.to_dict(),
            link_params=links,
            graph=graph,
            routing_table=table,
        )
        self.assertTrue(system.validate().ok)


if __name__ == "__main__":
    unittest.main()

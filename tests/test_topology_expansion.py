import tempfile
import unittest
from pathlib import Path

from topoanalyzer.experiments.factory import build_system_from_dict
from topoanalyzer.model.links import LinkParameters
from topoanalyzer.simulators.booksim.backend import BookSimBackend
from topoanalyzer.simulators.booksim.config import BookSimOptions
from topoanalyzer.topologies.dragonfly import DragonflyParams, DragonflyTopologyBuilder
from topoanalyzer.topologies.hypercube import HypercubeParams, HypercubeTopologyBuilder
from topoanalyzer.topologies.mesh3d import Mesh3DParams, Mesh3DTopologyBuilder
from topoanalyzer.topologies.ruche3d import Ruche3DParams, Ruche3DTopologyBuilder
from topoanalyzer.topologies.slimnoc import SlimNoCParams, SlimNoCTopologyBuilder
from topoanalyzer.topologies.torus2d import Torus2DParams, Torus2DTopologyBuilder
from topoanalyzer.topologies.torus3d import Torus3DParams, Torus3DTopologyBuilder


def _links():
    return LinkParameters.from_dict(
        {"default": {"latency_cycles": 1, "bandwidth": "64GB/s"}}
    )


class TopologyExpansionTests(unittest.TestCase):
    def test_builds_mesh3d(self):
        graph = Mesh3DTopologyBuilder().build(Mesh3DParams(x=2, y=2, z=2), _links())

        self.assertEqual(len(graph.routers()), 8)
        self.assertEqual(len(graph.links), 24)
        self.assertTrue(graph.is_connected())

    def test_builds_torus2d_with_wrap_classes(self):
        links = LinkParameters.from_dict(
            {
                "default": {"latency_cycles": 1, "bandwidth": "64GB/s"},
                "classes": {
                    "x_wrap": {"latency_cycles": 3, "bandwidth": "32GB/s"},
                    "y_wrap": {"latency_cycles": 4, "bandwidth": "16GB/s"},
                },
            }
        )
        graph = Torus2DTopologyBuilder().build(Torus2DParams(x=4, y=3), links)

        self.assertEqual(len(graph.routers()), 12)
        self.assertEqual(len(graph.links), 48)
        self.assertEqual(graph.link_between("t2.3.0", "t2.0.0").latency_cycles, 3)
        self.assertEqual(graph.link_between("t2.0.2", "t2.0.0").latency_cycles, 4)

    def test_builds_torus3d(self):
        graph = Torus3DTopologyBuilder().build(Torus3DParams(x=3, y=3, z=3), _links())

        self.assertEqual(len(graph.routers()), 27)
        self.assertEqual(len(graph.links), 162)
        self.assertTrue(graph.is_connected())

    def test_builds_ruche3d_with_express_links(self):
        graph = Ruche3DTopologyBuilder().build(
            Ruche3DParams(x=4, y=4, z=4, stride_x=2, stride_y=2, stride_z=2),
            _links(),
        )

        self.assertEqual(len(graph.routers()), 64)
        self.assertTrue(graph.is_connected())
        self.assertIsNotNone(graph.link_between("ru3.0.0.0", "ru3.2.0.0"))
        self.assertTrue(
            graph.link_between("ru3.0.0.0", "ru3.2.0.0").metadata["ruche"]
        )

    def test_builds_hypercube(self):
        graph = HypercubeTopologyBuilder().build(HypercubeParams(dimension=4), _links())

        self.assertEqual(len(graph.routers()), 16)
        self.assertEqual(len(graph.links), 64)
        self.assertTrue(graph.is_connected())

    def test_builds_dragonfly(self):
        graph = DragonflyTopologyBuilder().build(
            DragonflyParams(p=2, a=4, h=2),
            _links(),
        )

        self.assertEqual(len(graph.routers()), 36)
        self.assertEqual(graph.metadata["terminal_count"], 72)
        self.assertEqual(
            len([link for link in graph.links if link.metadata["class"] == "local"]),
            108,
        )
        self.assertEqual(
            len([link for link in graph.links if link.metadata["class"] == "global"]),
            72,
        )
        self.assertTrue(graph.is_connected())

    def test_builds_slimnoc_q5_paper_scale(self):
        graph = SlimNoCTopologyBuilder().build(
            SlimNoCParams(q=5, concentration=4, layout="subgroup"),
            _links(),
        )

        self.assertEqual(len(graph.routers()), 50)
        self.assertEqual(len(graph.links), 350)
        self.assertEqual(graph.metadata["network_radix"], 7)
        self.assertEqual(graph.metadata["radix"], 11)
        self.assertEqual(graph.metadata["terminal_count"], 200)
        self.assertEqual(
            len([link for link in graph.links if link.metadata["class"] == "intra_0"]),
            50,
        )
        self.assertEqual(
            len([link for link in graph.links if link.metadata["class"] == "intra_1"]),
            50,
        )
        self.assertEqual(
            len([link for link in graph.links if link.metadata["class"] == "cross"]),
            250,
        )
        self.assertTrue(graph.is_connected())

    def test_builds_slimnoc_q9_nonprime_field_paper_scale(self):
        graph = SlimNoCTopologyBuilder().build(
            SlimNoCParams(q=9, concentration=8, layout="group"),
            _links(),
        )

        self.assertEqual(len(graph.routers()), 162)
        self.assertEqual(len(graph.links), 2106)
        self.assertEqual(graph.metadata["field"]["characteristic"], 3)
        self.assertEqual(graph.metadata["field"]["degree"], 2)
        self.assertEqual(graph.metadata["network_radix"], 13)
        self.assertEqual(graph.metadata["terminal_count"], 1296)
        self.assertTrue(graph.is_connected())

    def test_builds_slimnoc_q8_power_of_two_paper_scale(self):
        graph = SlimNoCTopologyBuilder().build(
            SlimNoCParams(q=8, concentration=8, layout="subgroup"),
            _links(),
        )

        self.assertEqual(len(graph.routers()), 128)
        self.assertEqual(len(graph.links), 1536)
        self.assertEqual(graph.metadata["delta"], 0)
        self.assertEqual(graph.metadata["network_radix"], 12)
        self.assertEqual(graph.metadata["terminal_count"], 1024)
        self.assertTrue(graph.is_connected())

    def test_new_topology_systems_validate(self):
        cases = [
            ("mesh3d", {"x": 2, "y": 2, "z": 2}, "mesh_xyz"),
            ("torus2d", {"x": 3, "y": 3}, "torus_xy"),
            ("torus3d", {"x": 3, "y": 3, "z": 3}, "torus_xyz"),
            (
                "ruche3d",
                {"x": 4, "y": 4, "z": 4, "stride": 2},
                "ruche_xyz",
            ),
            ("hypercube", {"dimension": 4}, "hypercube_ecube"),
            ("dragonfly", {"p": 2, "a": 4, "h": 2}, "dragonfly_min"),
            ("slimnoc", {"q": 5, "concentration": 4}, "slimnoc_min"),
        ]

        for topology_type, params, routing_type in cases:
            with self.subTest(topology_type=topology_type):
                system = build_system_from_dict(
                    {
                        "name": f"{topology_type}_{routing_type}",
                        "topology": {"type": topology_type, "params": params},
                        "links": {
                            "default": {
                                "latency_cycles": 1,
                                "bandwidth": "64GB/s",
                            }
                        },
                        "routing": {"type": routing_type},
                    }
                )

                self.assertTrue(system.validate().ok)

    def test_stronger_routing_candidates_validate(self):
        cases = [
            (
                "ruche3d",
                {"x": 3, "y": 3, "z": 3, "stride": 2},
                {"type": "ruche_lash", "max_vcs": 8, "candidate_paths": 8},
                {
                    "ruche_x": {"latency_cycles": 2, "bandwidth": "128GB/s"},
                    "ruche_y": {"latency_cycles": 2, "bandwidth": "128GB/s"},
                    "ruche_z": {"latency_cycles": 2, "bandwidth": "128GB/s"},
                },
            ),
            (
                "ruche3d",
                {"x": 4, "y": 4, "z": 4, "stride": 2},
                {"type": "ruche_valiant_hash", "seed": 0},
                {
                    "ruche_x": {"latency_cycles": 2, "bandwidth": "128GB/s"},
                    "ruche_y": {"latency_cycles": 2, "bandwidth": "128GB/s"},
                    "ruche_z": {"latency_cycles": 2, "bandwidth": "128GB/s"},
                },
            ),
            (
                "hypercube",
                {"dimension": 4},
                {"type": "hypercube_lash", "max_vcs": 4, "candidate_paths": 8},
                {},
            ),
            (
                "hypercube",
                {"dimension": 4},
                {"type": "hypercube_valiant_hash", "seed": 0},
                {},
            ),
            (
                "dragonfly",
                {"p": 2, "a": 4, "h": 2},
                {"type": "dragonfly_valiant_hash", "seed": 0},
                {"global": {"latency_cycles": 3, "bandwidth": "128GB/s"}},
            ),
            (
                "slimnoc",
                {"q": 5, "concentration": 4},
                {"type": "slimnoc_valiant_hash", "seed": 0},
                {"cross": {"latency_cycles": 2, "bandwidth": "128GB/s"}},
            ),
        ]

        for topology_type, params, routing, classes in cases:
            with self.subTest(routing=routing["type"]):
                system = build_system_from_dict(
                    {
                        "name": f"{topology_type}_{routing['type']}",
                        "topology": {"type": topology_type, "params": params},
                        "links": {
                            "default": {
                                "latency_cycles": 1,
                                "bandwidth": "64GB/s",
                            },
                            "classes": classes,
                        },
                        "routing": routing,
                    }
                )

                self.assertTrue(system.validate().ok)

    def test_dragonfly_valiant_requires_exported_vcs(self):
        system = build_system_from_dict(
            {
                "name": "dragonfly_valiant",
                "topology": {"type": "dragonfly", "params": {"p": 2, "a": 4, "h": 2}},
                "links": {
                    "default": {"latency_cycles": 1, "bandwidth": "64GB/s"},
                    "classes": {
                        "global": {"latency_cycles": 3, "bandwidth": "128GB/s"}
                    },
                },
                "routing": {"type": "dragonfly_valiant_hash", "seed": 0},
            }
        )

        self.assertEqual(
            max(vc for hop_vcs in system.routing_table.path_vcs.values() for vc in hop_vcs),
            3,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaisesRegex(ValueError, "uses VC 3"):
                BookSimBackend().materialize(
                    system,
                    BookSimOptions(traffic="uniform", injection_rate=0.01),
                    Path(tmpdir) / "too_few_vcs",
                )
            BookSimBackend().materialize(
                system,
                BookSimOptions(traffic="uniform", injection_rate=0.01, num_vcs=4),
                Path(tmpdir) / "four_vcs",
            )
            route_text = ((Path(tmpdir) / "four_vcs") / "anynet.routes").read_text(
                encoding="utf-8"
            )

        self.assertIn(" 3\n", route_text)

    def test_slimnoc_valiant_requires_exported_vcs(self):
        system = build_system_from_dict(
            {
                "name": "slimnoc_q5_valiant",
                "topology": {
                    "type": "slimnoc",
                    "params": {"q": 5, "concentration": 4},
                },
                "links": {
                    "default": {"latency_cycles": 1, "bandwidth": "64GB/s"},
                    "classes": {
                        "cross": {"latency_cycles": 2, "bandwidth": "128GB/s"}
                    },
                },
                "routing": {"type": "slimnoc_valiant_hash", "seed": 0},
            }
        )

        self.assertEqual(system.routing_table.metadata["max_hops"], 4)
        self.assertEqual(
            max(vc for hop_vcs in system.routing_table.path_vcs.values() for vc in hop_vcs),
            3,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaisesRegex(ValueError, "uses VC 3"):
                BookSimBackend().materialize(
                    system,
                    BookSimOptions(traffic="uniform", injection_rate=0.01),
                    Path(tmpdir) / "too_few_vcs",
                )
            BookSimBackend().materialize(
                system,
                BookSimOptions(traffic="uniform", injection_rate=0.01, num_vcs=4),
                Path(tmpdir) / "four_vcs",
            )
            route_text = ((Path(tmpdir) / "four_vcs") / "anynet.routes").read_text(
                encoding="utf-8"
            )

        self.assertIn(" 3\n", route_text)

    def test_anynet_materializes_new_topology(self):
        system = build_system_from_dict(
            {
                "name": "hypercube_d3_ecube",
                "topology": {"type": "hypercube", "params": {"dimension": 3}},
                "links": {"default": {"latency_cycles": 1, "bandwidth": "64GB/s"}},
                "routing": {"type": "hypercube_ecube"},
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            BookSimBackend().materialize(
                system,
                BookSimOptions(traffic="uniform", injection_rate=0.01),
                Path(tmpdir),
            )

            self.assertTrue((Path(tmpdir) / "anynet.net").exists())
            self.assertTrue((Path(tmpdir) / "anynet.routes").exists())


if __name__ == "__main__":
    unittest.main()

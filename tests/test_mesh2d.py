import unittest

from topoanalyzer.model.links import LinkParameters
from topoanalyzer.topologies.mesh2d import Mesh2DParams, Mesh2DTopologyBuilder


class Mesh2DTests(unittest.TestCase):
    def test_builds_rectangular_mesh_with_oriented_links(self):
        links = LinkParameters.from_dict(
            {
                "default": {"latency_cycles": 2, "bandwidth": "64GB/s"},
                "classes": {
                    "x": {"latency_cycles": 2, "bandwidth": "64GB/s"},
                    "y": {"latency_cycles": 5, "bandwidth": "16GB/s"},
                },
            }
        )
        graph = Mesh2DTopologyBuilder().build(Mesh2DParams(x=3, y=2), links)

        self.assertEqual(len(graph.routers()), 6)
        self.assertEqual(len(graph.links), 14)
        self.assertTrue(graph.is_connected())
        y_link = graph.link_between("r.0.0", "r.0.1")
        self.assertIsNotNone(y_link)
        self.assertEqual(y_link.latency_cycles, 5)
        self.assertEqual(y_link.bandwidth, "16GB/s")

    def test_rejects_out_of_bounds_override(self):
        links = LinkParameters.from_dict(
            {
                "default": {"latency_cycles": 2, "bandwidth": "64GB/s"},
                "overrides": [
                    {
                        "src": [0, 0],
                        "dst": [9, 0],
                        "latency_cycles": 4,
                        "bandwidth": "32GB/s",
                    }
                ],
            }
        )
        report = Mesh2DTopologyBuilder().validate(Mesh2DParams(x=2, y=2), links)

        self.assertFalse(report.ok)


if __name__ == "__main__":
    unittest.main()

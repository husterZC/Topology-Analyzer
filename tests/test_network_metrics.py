import unittest

from topoanalyzer.benchmarks.network_metrics import summarize_system
from topoanalyzer.experiments.factory import build_system_from_dict


def _system(topology_type, params, routing_type, links=None):
    return build_system_from_dict(
        {
            "name": f"{topology_type}_{routing_type}",
            "topology": {"type": topology_type, "params": params},
            "links": links
            or {"default": {"latency_cycles": 1, "bandwidth": "64GB/s"}},
            "routing": {"type": routing_type},
        }
    )


class NetworkMetricsTests(unittest.TestCase):
    def test_large_mesh_uses_axis_formula(self):
        metrics = summarize_system(
            _system("mesh2d", {"x": 5, "y": 5}, "mesh_xy")
        )

        self.assertEqual(metrics.bisection_bandwidth, "320GB/s")
        self.assertEqual(metrics.bisection_method, "mesh_axis_bisection_formula")
        self.assertEqual(metrics.bisection_partition_sizes, (12, 13))

    def test_large_hypercube_uses_dimension_formula(self):
        metrics = summarize_system(
            _system("hypercube", {"dimension": 5}, "hypercube_ecube")
        )

        self.assertEqual(metrics.bisection_bandwidth, "1024GB/s")
        self.assertEqual(
            metrics.bisection_method,
            "hypercube_dimension_bisection_formula",
        )
        self.assertEqual(metrics.diameter, 5)

    def test_ubmesh_uses_nd_fullmesh_formula(self):
        metrics = summarize_system(
            _system(
                "ubmesh",
                {"dimensions": [8, 8], "dimension_names": ["x", "y"]},
                "ubmesh_dor",
            )
        )

        self.assertEqual(metrics.bisection_bandwidth, "8192GB/s")
        self.assertEqual(
            metrics.bisection_method,
            "ubmesh_nd_fullmesh_bisection_formula",
        )

    def test_large_dragonfly_uses_group_level_estimate(self):
        metrics = summarize_system(
            _system("dragonfly", {"p": 2, "a": 8, "h": 2}, "dragonfly_min")
        )

        self.assertEqual(metrics.bisection_bandwidth, "4608GB/s")
        self.assertEqual(
            metrics.bisection_method,
            "dragonfly_group_bisection_estimate",
        )
        self.assertEqual(metrics.bisection_partition_sizes, (64, 72))
        self.assertIn("crossing_global_links=72", metrics.bisection_note)

    def test_large_fattree_uses_terminal_bisection_estimate(self):
        metrics = summarize_system(
            _system("fattree", {"radix": 8, "levels": 4}, "fattree_lca")
        )

        self.assertEqual(metrics.bisection_bandwidth, "8192GB/s")
        self.assertEqual(
            metrics.bisection_method,
            "fattree_terminal_bisection_estimate",
        )
        self.assertEqual(metrics.bisection_partition_sizes, (128, 128))

    def test_large_slimnoc_uses_group_level_estimate(self):
        metrics = summarize_system(
            _system(
                "slimnoc",
                {"q": 9, "concentration": 8},
                "slimnoc_min",
            )
        )

        self.assertEqual(metrics.bisection_bandwidth, "20480GB/s")
        self.assertEqual(
            metrics.bisection_method,
            "slimnoc_group_bisection_estimate",
        )
        self.assertIn("crossing_cross_links=320", metrics.bisection_note)

    def test_large_lln_uses_projected_estimate(self):
        metrics = summarize_system(
            _system(
                "lln",
                {"x": 4, "y": 4, "layers": 5},
                "lln_table",
            )
        )

        self.assertEqual(metrics.bisection_bandwidth, "4096GB/s")
        self.assertEqual(
            metrics.bisection_method,
            "lln_projected_bisection_estimate",
        )


if __name__ == "__main__":
    unittest.main()

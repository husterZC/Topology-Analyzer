import tempfile
import unittest
from pathlib import Path

from topoanalyzer.experiments.factory import build_system_from_dict
from topoanalyzer.model.links import LinkParameters
from topoanalyzer.simulators.booksim.backend import BookSimBackend
from topoanalyzer.simulators.booksim.config import BookSimOptions
from topoanalyzer.topologies.lln import (
    LLNParams,
    LLNTopologyBuilder,
    router_id,
    square_full_coverage_total_layers,
    square_max_side_for_cache_layers,
)


def _links() -> LinkParameters:
    return LinkParameters.from_dict(
        {
            "default": {"latency_cycles": 1, "bandwidth": "64GB/s"},
            "classes": {
                "long": {"latency_cycles": 2, "bandwidth": "64GB/s"},
                "vertical": {"latency_cycles": 1, "bandwidth": "64GB/s"},
            },
        }
    )


class LLNTests(unittest.TestCase):
    def test_square_full_coverage_formula_matches_paper_table(self):
        self.assertEqual(square_full_coverage_total_layers(4), 5)
        self.assertEqual(square_full_coverage_total_layers(5), 8)
        self.assertEqual(square_full_coverage_total_layers(6), 11)
        self.assertEqual(square_max_side_for_cache_layers(4), 4)
        self.assertEqual(square_max_side_for_cache_layers(7), 5)
        self.assertEqual(square_max_side_for_cache_layers(10), 6)

    def test_builds_paper_4x4x5_full_coverage_topology(self):
        graph = LLNTopologyBuilder().build(
            LLNParams(x=4, y=4, layers=5),
            _links(),
        )

        self.assertEqual(len(graph.routers()), 80)
        self.assertEqual(graph.metadata["required_long_edges"], 96)
        self.assertEqual(graph.metadata["placed_long_edges"], 96)
        self.assertEqual(graph.metadata["missing_long_edges"], 0)
        self.assertEqual(graph.metadata["vertical_pillars"], 4)
        self.assertEqual(graph.metadata["full_coverage"], True)
        self.assertEqual(graph.metadata["diameter"], 3)
        self.assertEqual(
            len([link for link in graph.links if link.metadata["class"] == "long"]),
            192,
        )
        self.assertEqual(
            len([link for link in graph.links if link.metadata["class"] == "vertical"]),
            320,
        )
        self.assertTrue(graph.is_connected())

    def test_rejects_full_coverage_when_layers_are_insufficient(self):
        report = LLNTopologyBuilder().validate(
            LLNParams(x=4, y=4, layers=4),
            _links(),
        )

        self.assertFalse(report.ok)
        self.assertIn("full_clique coverage", report.errors[0].message)

    def test_allows_partial_greedy_when_layers_are_insufficient(self):
        graph = LLNTopologyBuilder().build(
            LLNParams(x=4, y=4, layers=4, coverage="partial_greedy"),
            _links(),
        )

        self.assertGreater(graph.metadata["missing_long_edges"], 0)
        self.assertFalse(graph.metadata["full_coverage"])

    def test_lln_table_routing_uses_three_hop_long_link_path(self):
        system = _system({"x": 4, "y": 4, "layers": 5}, "lln_table")

        path = system.routing_table.paths[
            (router_id(0, 0, 0), router_id(3, 3, 4))
        ]

        self.assertEqual(len(path), 4)
        self.assertEqual(path[0], router_id(0, 0, 0))
        self.assertEqual(path[-1], router_id(3, 3, 4))
        self.assertEqual(system.routing_table.path_vcs[(path[0], path[-1])], [0, 1, 2])
        self.assertGreater(system.routing_table.metadata["fallback_routes"], 0)
        self.assertTrue(system.validate().ok)

    def test_lln_dor_fallback_routes_missing_pairs_through_core_mesh(self):
        system = _system(
            {"x": 4, "y": 4, "layers": 4, "coverage": "partial_greedy"},
            "lln_dor_fallback",
        )

        self.assertGreater(system.routing_table.metadata["fallback_routes"], 0)
        self.assertTrue(system.validate().ok)

    def test_booksim_anynet_materializes_lln_table_routes(self):
        system = _system({"x": 2, "y": 2, "layers": 3}, "lln_table")
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = BookSimBackend(backend="auto").materialize(
                system,
                BookSimOptions(
                    traffic="uniform",
                    injection_rate=0.01,
                    sample_cycles=10,
                    warmup_cycles=1,
                    num_vcs=3,
                ),
                Path(tmpdir),
            )

            self.assertTrue(config_path.exists())
            self.assertTrue((Path(tmpdir) / "anynet.net").exists())
            self.assertTrue((Path(tmpdir) / "anynet.routes").exists())


def _system(params: dict[str, object], routing_type: str):
    return build_system_from_dict(
        {
            "name": f"lln_{routing_type}",
            "topology": {"type": "lln", "params": params},
            "links": {
                "default": {"latency_cycles": 1, "bandwidth": "64GB/s"},
                "classes": {
                    "long": {"latency_cycles": 2, "bandwidth": "64GB/s"},
                    "vertical": {"latency_cycles": 1, "bandwidth": "64GB/s"},
                },
            },
            "routing": {"type": routing_type},
        }
    )


if __name__ == "__main__":
    unittest.main()

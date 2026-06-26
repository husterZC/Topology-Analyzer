import unittest
import tempfile
from pathlib import Path

from topoanalyzer.experiments.factory import build_system_from_dict
from topoanalyzer.simulators.booksim.backend import BookSimBackend
from topoanalyzer.simulators.booksim.config import (
    BookSimConfigGenerator,
    BookSimOptions,
    BookSimUnsupportedError,
)
from topoanalyzer.simulators.booksim.parser import parse_booksim_output


def _system(x=4, y=4, links=None):
    return build_system_from_dict(
        {
            "name": f"mesh2d_{x}x{y}",
            "topology": {"type": "mesh2d", "params": {"x": x, "y": y}},
            "links": links
            or {"default": {"latency_cycles": 1, "bandwidth": "64GB/s"}},
            "routing": {"type": "mesh_xy"},
        }
    )


class BookSimTests(unittest.TestCase):
    def test_generates_anynet_table_config_by_default(self):
        config = BookSimConfigGenerator().generate(
            _system(),
            BookSimOptions(traffic="uniform", injection_rate=0.05),
            network_file="/tmp/anynet.net",
            route_table_file="/tmp/anynet.routes",
        )

        self.assertIn("topology = anynet;", config)
        self.assertIn("routing_function = min;", config)
        self.assertIn("network_file = /tmp/anynet.net;", config)
        self.assertIn("route_table_file = /tmp/anynet.routes;", config)
        self.assertIn("injection_rate_uses_flits = 0;", config)

    def test_generates_flit_rate_config(self):
        config = BookSimConfigGenerator().generate(
            _system(),
            BookSimOptions(
                traffic="uniform",
                injection_rate=0.05,
                injection_rate_unit="flits/node/cycle",
                packet_size=5,
            ),
            network_file="/tmp/anynet.net",
            route_table_file="/tmp/anynet.routes",
        )

        self.assertIn("injection_rate = 0.05;", config)
        self.assertIn("packet_size = 5;", config)
        self.assertIn("injection_rate_uses_flits = 1;", config)

    def test_generates_stock_mesh_config_when_requested(self):
        config = BookSimConfigGenerator(backend="stock_mesh").generate(
            _system(),
            BookSimOptions(traffic="uniform", injection_rate=0.05),
        )

        self.assertIn("topology = mesh;", config)
        self.assertIn("k = 4;", config)
        self.assertIn("n = 2;", config)
        self.assertIn("routing_function = dor;", config)
        self.assertIn("use_noc_latency = 1;", config)

    def test_rejects_rectangular_stock_mesh(self):
        with self.assertRaises(BookSimUnsupportedError):
            BookSimConfigGenerator(backend="stock_mesh").generate(
                _system(x=4, y=2),
                BookSimOptions(traffic="uniform", injection_rate=0.05),
            )

    def test_rejects_heterogeneous_stock_mesh(self):
        system = _system(
            links={
                "default": {"latency_cycles": 2, "bandwidth": "64GB/s"},
                "classes": {
                    "x": {"latency_cycles": 2, "bandwidth": "64GB/s"},
                    "y": {"latency_cycles": 5, "bandwidth": "16GB/s"},
                },
            }
        )
        with self.assertRaises(BookSimUnsupportedError):
            BookSimConfigGenerator(backend="stock_mesh").generate(
                system,
                BookSimOptions(traffic="uniform", injection_rate=0.05),
            )

    def test_rejects_non_stock_mesh_link_latency(self):
        system = _system(
            links={"default": {"latency_cycles": 2, "bandwidth": "64GB/s"}}
        )
        with self.assertRaises(BookSimUnsupportedError):
            BookSimConfigGenerator(backend="stock_mesh").generate(
                system,
                BookSimOptions(traffic="uniform", injection_rate=0.05),
            )

    def test_custom_backend_materializes_graph_updown_routes(self):
        system = build_system_from_dict(
            {
                "name": "mesh2d_4x4_graph_updown",
                "topology": {"type": "mesh2d", "params": {"x": 4, "y": 4}},
                "links": {"default": {"latency_cycles": 2, "bandwidth": "64GB/s"}},
                "routing": {"type": "graph_updown", "root": "r.0.0"},
            }
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = BookSimBackend().materialize(
                system,
                BookSimOptions(traffic="uniform", injection_rate=0.05),
                Path(tmpdir),
            )
            config = config_path.read_text(encoding="utf-8")

            self.assertIn("topology = anynet;", config)
            self.assertIn("route_table_file =", config)
            self.assertTrue((Path(tmpdir) / "anynet.net").exists())
            route_table = (Path(tmpdir) / "anynet.routes").read_text(encoding="utf-8")
            self.assertIn("0 15", route_table)

    def test_custom_backend_materializes_rectangular_heterogeneous_mesh(self):
        system = _system(
            x=4,
            y=2,
            links={
                "default": {"latency_cycles": 2, "bandwidth": "64GB/s"},
                "classes": {
                    "x": {"latency_cycles": 2, "bandwidth": "64GB/s"},
                    "y": {"latency_cycles": 5, "bandwidth": "16GB/s"},
                },
            },
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            BookSimBackend().materialize(
                system,
                BookSimOptions(traffic="uniform", injection_rate=0.05),
                Path(tmpdir),
            )
            network = (Path(tmpdir) / "anynet.net").read_text(encoding="utf-8")
            mapping = (Path(tmpdir) / "anynet_mapping.json").read_text(
                encoding="utf-8"
            )

            self.assertIn("router 0 node 0 router 1 2 router 4 5", network)
            self.assertIn('"bandwidth": "16GB/s"', mapping)

    def test_runtime_ubmesh_apr_backend_materializes_without_route_table(self):
        system = build_system_from_dict(
            {
                "name": "ubmesh_3x3_apr_runtime",
                "topology": {
                    "type": "ubmesh",
                    "params": {
                        "dimensions": [3, 3],
                        "dimension_names": ["x", "y"],
                    },
                },
                "links": {
                    "default": {"latency_cycles": 1, "bandwidth": "64GB/s"},
                },
                "routing": {"type": "ubmesh_apr_runtime", "seed": 7},
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = BookSimBackend(backend="auto").materialize(
                system,
                BookSimOptions(traffic="uniform", injection_rate=0.01, num_vcs=2),
                Path(tmpdir),
            )
            config = config_path.read_text(encoding="utf-8")

            self.assertIn("routing_function = ubmesh_apr;", config)
            self.assertIn("ubmesh_apr_dimensions = 3,3;", config)
            self.assertIn("ubmesh_apr_seed = 7;", config)
            self.assertTrue((Path(tmpdir) / "anynet.net").exists())
            self.assertTrue((Path(tmpdir) / "anynet_mapping.json").exists())
            self.assertFalse((Path(tmpdir) / "anynet.routes").exists())

    def test_runtime_ubmesh_apr_rejects_single_vc(self):
        system = build_system_from_dict(
            {
                "name": "ubmesh_3x3_apr_runtime",
                "topology": {
                    "type": "ubmesh",
                    "params": {"dimensions": [3, 3]},
                },
                "links": {
                    "default": {"latency_cycles": 1, "bandwidth": "64GB/s"},
                },
                "routing": {"type": "ubmesh_apr_runtime"},
            }
        )

        with self.assertRaisesRegex(BookSimUnsupportedError, "at least 2 VCs"):
            BookSimConfigGenerator(backend="auto").generate(
                system,
                BookSimOptions(traffic="uniform", injection_rate=0.01, num_vcs=1),
                network_file="/tmp/anynet.net",
            )

    def test_runtime_dragonfly_ugal_backend_materializes_without_route_table(self):
        system = build_system_from_dict(
            {
                "name": "dragonfly_p2_a4_h2_ugal",
                "topology": {
                    "type": "dragonfly",
                    "params": {"p": 2, "a": 4, "h": 2},
                },
                "links": {
                    "default": {"latency_cycles": 1, "bandwidth": "64GB/s"},
                },
                "routing": {
                    "type": "dragonfly_ugal_l_runtime",
                    "seed": 3,
                    "candidates": 5,
                    "adaptive_threshold": 7,
                },
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = BookSimBackend(backend="auto").materialize(
                system,
                BookSimOptions(traffic="uniform", injection_rate=0.01, num_vcs=3),
                Path(tmpdir),
            )
            config = config_path.read_text(encoding="utf-8")

            self.assertIn("routing_function = dragonfly_ugal_l;", config)
            self.assertIn("anynet_runtime_seed = 3;", config)
            self.assertIn("anynet_runtime_candidates = 5;", config)
            self.assertIn("anynet_runtime_threshold = 7;", config)
            self.assertTrue((Path(tmpdir) / "anynet.net").exists())
            self.assertFalse((Path(tmpdir) / "anynet.routes").exists())

    def test_runtime_dragonfly_par_enforces_required_vcs(self):
        system = build_system_from_dict(
            {
                "name": "dragonfly_p2_a4_h2_par",
                "topology": {
                    "type": "dragonfly",
                    "params": {"p": 2, "a": 4, "h": 2},
                },
                "links": {
                    "default": {"latency_cycles": 1, "bandwidth": "64GB/s"},
                },
                "routing": {"type": "dragonfly_par_runtime"},
            }
        )

        with self.assertRaisesRegex(BookSimUnsupportedError, "at least 5 VCs"):
            BookSimConfigGenerator(backend="auto").generate(
                system,
                BookSimOptions(traffic="uniform", injection_rate=0.01, num_vcs=4),
                network_file="/tmp/anynet.net",
            )

    def test_missing_booksim_error_mentions_bootstrap(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "booksim.cfg"
            config_path.write_text("topology = anynet;\n", encoding="utf-8")

            with self.assertRaisesRegex(FileNotFoundError, "make bootstrap"):
                BookSimBackend(executable="definitely_missing_booksim").run_config(
                    config_path
                )

    def test_parses_common_metrics(self):
        metrics = parse_booksim_output(
            """
            Average packet latency = 12.5
            Average network latency = 8.0
            Accepted rate = 0.045
            """
        )

        self.assertEqual(metrics.average_packet_latency, 12.5)
        self.assertEqual(metrics.average_network_latency, 8.0)
        self.assertEqual(metrics.accepted_rate, 0.045)

    def test_parses_booksim_latency_output_labels(self):
        metrics = parse_booksim_output(
            """
            Packet latency average = 16.9213
            Network latency average = 16.7953
            Accepted packet rate average = 0.0100319
            """
        )

        self.assertEqual(metrics.average_packet_latency, 16.9213)
        self.assertEqual(metrics.average_network_latency, 16.7953)
        self.assertEqual(metrics.accepted_rate, 0.0100319)


if __name__ == "__main__":
    unittest.main()

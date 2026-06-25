import unittest

from topoanalyzer.experiments.factory import build_system_from_dict
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
    def test_generates_square_mesh_config(self):
        config = BookSimConfigGenerator().generate(
            _system(),
            BookSimOptions(traffic="uniform", injection_rate=0.05),
        )

        self.assertIn("topology = mesh;", config)
        self.assertIn("k = 4;", config)
        self.assertIn("n = 2;", config)
        self.assertIn("routing_function = dor;", config)
        self.assertIn("use_noc_latency = 1;", config)
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
        )

        self.assertIn("injection_rate = 0.05;", config)
        self.assertIn("packet_size = 5;", config)
        self.assertIn("injection_rate_uses_flits = 1;", config)

    def test_rejects_rectangular_stock_mesh(self):
        with self.assertRaises(BookSimUnsupportedError):
            BookSimConfigGenerator().generate(
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
            BookSimConfigGenerator().generate(
                system,
                BookSimOptions(traffic="uniform", injection_rate=0.05),
            )

    def test_rejects_non_stock_mesh_link_latency(self):
        system = _system(
            links={"default": {"latency_cycles": 2, "bandwidth": "64GB/s"}}
        )
        with self.assertRaises(BookSimUnsupportedError):
            BookSimConfigGenerator().generate(
                system,
                BookSimOptions(traffic="uniform", injection_rate=0.05),
            )

    def test_rejects_graph_updown_routing_until_custom_backend_exists(self):
        system = build_system_from_dict(
            {
                "name": "mesh2d_4x4_graph_updown",
                "topology": {"type": "mesh2d", "params": {"x": 4, "y": 4}},
                "links": {"default": {"latency_cycles": 2, "bandwidth": "64GB/s"}},
                "routing": {"type": "graph_updown", "root": "r.0.0"},
            }
        )
        with self.assertRaises(BookSimUnsupportedError):
            BookSimConfigGenerator().generate(
                system,
                BookSimOptions(traffic="uniform", injection_rate=0.05),
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


if __name__ == "__main__":
    unittest.main()

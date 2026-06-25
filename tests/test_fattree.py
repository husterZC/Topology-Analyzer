import tempfile
import unittest
from pathlib import Path

from topoanalyzer.experiments.factory import build_system_from_dict
from topoanalyzer.model.links import LinkParameters
from topoanalyzer.simulators.booksim.backend import BookSimBackend
from topoanalyzer.simulators.booksim.config import BookSimConfigGenerator
from topoanalyzer.simulators.booksim.config import BookSimOptions
from topoanalyzer.topologies.fattree import FatTreeParams, FatTreeTopologyBuilder


def _links():
    return LinkParameters.from_dict(
        {"default": {"latency_cycles": 1, "bandwidth": "64GB/s"}}
    )


def _fattree_system(radix=4, levels=3):
    return build_system_from_dict(
        {
            "name": f"fattree_r{radix}_l{levels}_lca",
            "topology": {"type": "fattree", "params": {"radix": radix, "levels": levels}},
            "links": {"default": {"latency_cycles": 1, "bandwidth": "64GB/s"}},
            "routing": {"type": "fattree_lca"},
        }
    )


def _fattree_hash_system(radix=4, levels=3):
    return build_system_from_dict(
        {
            "name": f"fattree_r{radix}_l{levels}_nca_hash",
            "topology": {"type": "fattree", "params": {"radix": radix, "levels": levels}},
            "links": {"default": {"latency_cycles": 1, "bandwidth": "64GB/s"}},
            "routing": {"type": "fattree_nca_hash", "seed": 0},
        }
    )


def _fattree_routing_system(routing):
    return build_system_from_dict(
        {
            "name": f"fattree_r8_l4_{routing['type']}",
            "topology": {"type": "fattree", "params": {"radix": 8, "levels": 4}},
            "links": {"default": {"latency_cycles": 1, "bandwidth": "64GB/s"}},
            "routing": routing,
        }
    )


class FatTreeTests(unittest.TestCase):
    def test_builds_level4_radix8_fattree(self):
        graph = FatTreeTopologyBuilder().build(
            FatTreeParams(radix=8, levels=4),
            _links(),
        )

        self.assertEqual(len(graph.routers()), 256)
        self.assertEqual(graph.metadata["terminal_count"], 256)
        self.assertEqual(len(graph.metadata["terminal_attachments"]), 64)
        self.assertEqual(len(graph.links), 1536)

    def test_fattree_lca_routes_up_then_down(self):
        system = _fattree_system()
        path = system.routing_table.paths[("ft.l0.0.0", "ft.l0.1.1")]
        directions = [
            system.graph.link_between(current, next_hop).metadata["direction"]
            for current, next_hop in zip(path[:-1], path[1:])
        ]

        self.assertTrue(system.validate().ok)
        self.assertIn("up", directions)
        self.assertIn("down", directions)
        if "down" in directions:
            first_down = directions.index("down")
            self.assertNotIn("up", directions[first_down:])

    def test_booksim_anynet_exports_terminals_on_leaf_routers_only(self):
        system = _fattree_system()

        with tempfile.TemporaryDirectory() as tmpdir:
            BookSimBackend().materialize(
                system,
                BookSimOptions(traffic="uniform", injection_rate=0.01),
                Path(tmpdir),
            )
            network_lines = (Path(tmpdir) / "anynet.net").read_text(
                encoding="utf-8"
            ).splitlines()
            route_lines = [
                line
                for line in (Path(tmpdir) / "anynet.routes")
                .read_text(encoding="utf-8")
                .splitlines()
                if line and not line.startswith("#")
            ]

        self.assertEqual(sum(line.count(" node ") for line in network_lines), 8)
        self.assertTrue(all(" node " in line for line in network_lines[:4]))
        self.assertTrue(all(" node " not in line for line in network_lines[4:]))
        self.assertEqual(len(route_lines), 12 * 8)

    def test_fattree_nca_hash_balances_terminal_routes(self):
        system = _fattree_hash_system(radix=8, levels=4)
        terminal_routes = system.routing_table.metadata["terminal_next_hops"]
        root_counts: dict[str, int] = {}
        edge_counts: dict[tuple[str, str], int] = {}
        attachments = system.graph.metadata["terminal_attachments"]
        terminals: list[tuple[int, str]] = []
        terminal_id = 0
        for attachment in attachments:
            for _ in range(int(attachment["count"])):
                terminals.append((terminal_id, attachment["router_id"]))
                terminal_id += 1

        for attachment in attachments:
            source = attachment["router_id"]
            for terminal_id, destination in terminals:
                if source == destination:
                    continue
                current = source
                seen = {current}
                directions = []
                while current != destination:
                    next_hop = terminal_routes[current][str(terminal_id)]["next_hop"]
                    edge_counts[(current, next_hop)] = (
                        edge_counts.get((current, next_hop), 0) + 1
                    )
                    directions.append(
                        system.graph.link_between(current, next_hop).metadata[
                            "direction"
                        ]
                    )
                    current = next_hop
                    self.assertNotIn(current, seen)
                    seen.add(current)
                    if system.graph.nodes[current].metadata["level"] == 3:
                        root_counts[current] = root_counts.get(current, 0) + 1

                if "down" in directions:
                    first_down = directions.index("down")
                    self.assertNotIn("up", directions[first_down:])

        up_links = [
            (link.src, link.dst)
            for link in system.graph.links
            if link.metadata["direction"] == "up"
        ]
        down_links = [
            (link.src, link.dst)
            for link in system.graph.links
            if link.metadata["direction"] == "down"
        ]
        self.assertEqual(len(root_counts), 64)
        self.assertEqual(sum(1 for link in up_links if link in edge_counts), len(up_links))
        self.assertEqual(
            sum(1 for link in down_links if link in edge_counts),
            len(down_links),
        )

    def test_booksim_anynet_uses_terminal_specific_fattree_routes(self):
        system = _fattree_hash_system()

        with tempfile.TemporaryDirectory() as tmpdir:
            BookSimBackend().materialize(
                system,
                BookSimOptions(traffic="uniform", injection_rate=0.01),
                Path(tmpdir),
            )
            route_lines = [
                line
                for line in (Path(tmpdir) / "anynet.routes")
                .read_text(encoding="utf-8")
                .splitlines()
                if line and not line.startswith("#")
            ]

        router0_nonlocal_ports = {
            int(port)
            for router, terminal, port, _vc in (
                line.split() for line in route_lines
            )
            if router == "0" and int(terminal) >= 2
        }
        self.assertGreater(len(router0_nonlocal_ports), 1)

    def test_fattree_static_balanced_routing_modes_validate(self):
        for routing_type in ("fattree_nca_hash", "fattree_dmodk", "fattree_dmodc"):
            with self.subTest(routing_type=routing_type):
                system = _fattree_routing_system({"type": routing_type})
                roots, up_used, down_used = _terminal_route_usage(system)

                self.assertTrue(system.validate().ok)
                self.assertEqual(len(roots), 64)
                self.assertGreaterEqual(up_used, 704)
                self.assertGreaterEqual(down_used, 384)

    def test_fattree_dmodc_avoids_disabled_up_link(self):
        disabled = "ft.l0.0.0.0->ft.l1.0.0.0"
        system = _fattree_routing_system(
            {"type": "fattree_dmodc", "disabled_links": [disabled]}
        )
        routes = system.routing_table.metadata["terminal_next_hops"]["ft.l0.0.0.0"]

        self.assertTrue(system.validate().ok)
        self.assertEqual(
            system.routing_table.metadata["disabled_links"],
            [{"src": "ft.l0.0.0.0", "dst": "ft.l1.0.0.0"}],
        )
        self.assertNotIn(
            "ft.l1.0.0.0",
            {str(route["next_hop"]) for route in routes.values()},
        )

    def test_fattree_anca_uses_stock_fattree_backend(self):
        system = _fattree_routing_system({"type": "fattree_anca"})

        config = BookSimConfigGenerator(backend="auto").generate(
            system,
            BookSimOptions(
                traffic="uniform",
                injection_rate=0.01,
                injection_rate_unit="flits/node/cycle",
            ),
        )

        self.assertIn("topology = fattree;", config)
        self.assertIn("k = 4;", config)
        self.assertIn("n = 4;", config)
        self.assertIn("routing_function = anca;", config)
        self.assertNotIn("route_table_file", config)

    def test_fattree_anca_rejects_static_anynet_backend(self):
        system = _fattree_routing_system({"type": "fattree_anca"})

        with self.assertRaisesRegex(ValueError, "requires a BookSim runtime"):
            BookSimConfigGenerator(backend="anynet_table").generate(
                system,
                BookSimOptions(traffic="uniform", injection_rate=0.01),
            )


def _terminal_route_usage(system):
    terminal_routes = system.routing_table.metadata["terminal_next_hops"]
    attachments = system.graph.metadata["terminal_attachments"]
    terminals: list[tuple[int, str]] = []
    terminal_id = 0
    for attachment in attachments:
        for _ in range(int(attachment["count"])):
            terminals.append((terminal_id, attachment["router_id"]))
            terminal_id += 1

    roots: dict[str, int] = {}
    edges: set[tuple[str, str]] = set()
    for attachment in attachments:
        source = attachment["router_id"]
        for terminal_id, destination in terminals:
            if source == destination:
                continue
            current = source
            while current != destination:
                next_hop = str(terminal_routes[current][str(terminal_id)]["next_hop"])
                edges.add((current, next_hop))
                current = next_hop
                if system.graph.nodes[current].metadata["level"] == 3:
                    roots[current] = roots.get(current, 0) + 1

    up_links = [
        (link.src, link.dst)
        for link in system.graph.links
        if link.metadata["direction"] == "up"
    ]
    down_links = [
        (link.src, link.dst)
        for link in system.graph.links
        if link.metadata["direction"] == "down"
    ]
    return (
        roots,
        sum(1 for link in up_links if link in edges),
        sum(1 for link in down_links if link in edges),
    )


if __name__ == "__main__":
    unittest.main()

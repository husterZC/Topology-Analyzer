import json
import tempfile
import unittest
from pathlib import Path

from topoanalyzer.cli import main
from topoanalyzer.experiments.factory import build_system_from_dict
from topoanalyzer.viewer import build_scene, export_viewer


def _system(topology_type, params, routing):
    return build_system_from_dict(
        {
            "name": f"{topology_type}_{routing}",
            "topology": {"type": topology_type, "params": params},
            "links": {
                "default": {"latency_cycles": 1, "bandwidth": "64GB/s"},
            },
            "routing": {"type": routing},
        }
    )


class ViewerTests(unittest.TestCase):
    def test_builds_topology_specific_scenes(self):
        cases = [
            _system(
                "lln",
                {"x": 4, "y": 4, "layers": 5, "coverage": "full_clique"},
                "lln_table",
            ),
            _system(
                "ubmesh",
                {"dimensions": [3, 3, 2], "dimension_names": ["x", "y", "z"]},
                "ubmesh_dor",
            ),
            _system("slimnoc", {"q": 5, "concentration": 1}, "slimnoc_min"),
            _system("dragonfly", {"p": 2, "a": 4, "h": 2}, "dragonfly_min"),
            _system("hypercube", {"dimension": 4}, "hypercube_ecube"),
        ]

        for system in cases:
            with self.subTest(system=system.name):
                scene = build_scene(system)
                self.assertEqual(
                    scene["system"]["router_count"],
                    len(system.graph.routers()),
                )
                terminal_nodes = [
                    node for node in scene["nodes"] if node["kind"] == "terminal"
                ]
                self.assertEqual(
                    len(scene["nodes"]),
                    len(system.graph.routers()) + scene["system"]["terminal_count"],
                )
                self.assertEqual(
                    len(terminal_nodes),
                    scene["system"]["terminal_count"],
                )
                self.assertTrue(
                    all(
                        node["metadata"].get("attached_router")
                        for node in terminal_nodes
                    )
                )
                self.assertGreater(len(scene["links"]), 0)
                self.assertTrue(
                    any(
                        link["kind"] == "terminal_attachment"
                        for link in scene["links"]
                    )
                )
                self.assertGreater(len(scene["legend"]["linkGroups"]), 0)
                for node in scene["nodes"]:
                    self.assertEqual(len(node["position"]), 3)
                self.assertIn("cameraPresets", scene["layout"])

    def test_export_viewer_writes_static_files(self):
        system = _system(
            "ubmesh",
            {"dimensions": [3, 3], "dimension_names": ["x", "y"]},
            "ubmesh_dor",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output = export_viewer(system, Path(tmpdir) / "viewer")

            self.assertTrue((output / "index.html").exists())
            self.assertTrue((output / "viewer.js").exists())
            self.assertTrue((output / "style.css").exists())
            self.assertTrue((output / "vendor" / "three" / "three.min.js").exists())
            scene = json.loads((output / "scene.json").read_text(encoding="utf-8"))
            self.assertEqual(scene["system"]["name"], system.name)
            html = (output / "index.html").read_text(encoding="utf-8")
            self.assertNotIn("__SCENE_JSON__", html)
            self.assertIn(system.name, html)

    def test_slimnoc_figure7b_scene_separates_intergroup_links(self):
        system = _system(
            "slimnoc",
            {"q": 9, "concentration": 8, "layout": "paper_figure7b"},
            "slimnoc_min",
        )

        scene = build_scene(system)

        self.assertEqual(scene["system"]["router_count"], 162)
        self.assertEqual(scene["system"]["terminal_count"], 1296)
        self.assertEqual(scene["layout"]["name"], "slimnoc_groups")
        link_groups = {group["name"] for group in scene["legend"]["linkGroups"]}
        self.assertIn("local cross links", link_groups)
        self.assertIn("inter-group cross links", link_groups)

        counts = {}
        for link in scene["links"]:
            if link.get("kind") == "network":
                counts[link["group"]] = counts.get(link["group"], 0) + 1

        self.assertEqual(counts["local cross links"], 162)
        self.assertEqual(counts["inter-group cross links"], 1296)

        nodes = {node["id"]: node for node in scene["nodes"]}
        self.assertGreater(
            abs(
                nodes["sn.g0.a1.b0"]["position"][0]
                - nodes["sn.g0.a0.b0"]["position"][0]
            ),
            3.0,
        )
        self.assertNotEqual(
            nodes["sn.g0.a0.b0"]["position"][1],
            nodes["sn.g1.a0.b0"]["position"][1],
        )

    def test_view_cli_exports_index(self):
        system_file = (
            Path(__file__).resolve().parents[1]
            / "examples"
            / "systems"
            / "hypercube"
            / "ecube"
            / "hypercube_d4_ecube.yaml"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "hypercube_view"
            status = main(["view", str(system_file), "--output-dir", str(output)])

            self.assertEqual(status, 0)
            self.assertTrue((output / "index.html").exists())
            self.assertTrue((output / "scene.json").exists())

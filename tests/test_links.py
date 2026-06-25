import unittest

from topoanalyzer.model.links import LinkParameters


class LinkParameterTests(unittest.TestCase):
    def test_resolution_order_override_class_default(self):
        params = LinkParameters.from_dict(
            {
                "default": {"latency_cycles": 2, "bandwidth": "64GB/s"},
                "classes": {
                    "x": {"latency_cycles": 3, "bandwidth": "32GB/s"},
                },
                "overrides": [
                    {
                        "src": [0, 0],
                        "dst": [1, 0],
                        "latency_cycles": 9,
                        "bandwidth": "8GB/s",
                    }
                ],
            }
        )

        self.assertEqual(params.resolve((0, 0), (1, 0), "x").latency_cycles, 9)
        self.assertEqual(params.resolve((1, 0), (0, 0), "x").latency_cycles, 9)
        self.assertEqual(params.resolve((1, 0), (2, 0), "x").latency_cycles, 3)
        self.assertEqual(params.resolve((1, 0), (1, 1), "y").latency_cycles, 2)


if __name__ == "__main__":
    unittest.main()

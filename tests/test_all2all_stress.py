import tempfile
import unittest
from pathlib import Path

from topoanalyzer.benchmarks.all2all_stress import (
    All2AllBenchmarkCase,
    All2AllStressBenchmark,
    All2AllStressRunner,
)
from topoanalyzer.experiments.factory import build_system_from_dict
from topoanalyzer.simulators.booksim.backend import BookSimBackend


def _mesh2d_system():
    return build_system_from_dict(
        {
            "name": "mesh2d_2x2_xy",
            "topology": {"type": "mesh2d", "params": {"x": 2, "y": 2}},
            "links": {"default": {"latency_cycles": 1, "bandwidth": "64GB/s"}},
            "routing": {"type": "mesh_xy"},
        }
    )


class All2AllStressTests(unittest.TestCase):
    def test_transfer_sizes_accept_range_mapping(self):
        benchmark = All2AllStressBenchmark.from_dict(
            {
                "type": "all2all_stress",
                "transfer_sizes": {
                    "range": {"start": 64, "stop": 256, "step": 64}
                },
            }
        )

        self.assertEqual(benchmark.transfer_sizes, [64, 128, 192])

    def test_transfer_sizes_accept_range_string_in_case_override(self):
        benchmark = All2AllStressBenchmark(
            transfer_sizes=[64],
            packet_size=8,
        )
        override = benchmark.with_overrides(
            {"transfer_sizes": "range(128, 384, 128)"}
        )

        self.assertEqual(override.transfer_sizes, [128, 256])
        self.assertEqual(override.packet_size, 8)

    def test_packetization_one_packet_per_pair_uses_transfer_size_as_packet_size(self):
        benchmark = All2AllStressBenchmark.from_dict(
            {
                "type": "all2all_stress",
                "transfer_sizes": [8, 16],
                "packet_size": "transfer_size",
            }
        )

        self.assertEqual(benchmark.packetization, "one_packet_per_pair")
        self.assertEqual(benchmark.packet_size_for_transfer(8), 8)
        self.assertEqual(benchmark.packets_per_pair(8), 1)
        self.assertEqual(benchmark.batch_size_packets_per_node(8, 4), 3)

    def test_dry_run_writes_batch_configs_and_results(self):
        system = _mesh2d_system()
        benchmark = All2AllStressBenchmark(
            transfer_sizes=[8, 16],
            transfer_size_unit="flits",
            packet_size=4,
            injection_rate=1.0,
            repetitions=1,
        )
        case = All2AllBenchmarkCase(system.name, system, benchmark)

        with tempfile.TemporaryDirectory() as tmpdir:
            output = All2AllStressRunner(BookSimBackend()).run(
                [case],
                benchmark,
                Path(tmpdir),
                dry_run=True,
                progress=False,
                run_name="all2all_dry",
            )

            config_path = (
                output
                / "booksim"
                / "mesh2d_2x2_xy"
                / "size_8_rep_0"
                / "booksim.cfg"
            )
            self.assertTrue(config_path.exists())
            config = config_path.read_text(encoding="utf-8")
            self.assertIn("traffic = all2all;", config)
            self.assertIn("sim_type = batch;", config)
            self.assertIn("packet_size = 4;", config)
            self.assertIn("batch_size = 6;", config)

            csv_text = (
                output / "results" / "all2all_stress.csv"
            ).read_text(encoding="utf-8")
            self.assertIn("transfer_size", csv_text)
            self.assertIn("average_runtime_cycles", csv_text)
            self.assertIn("batch_size_packets_per_node", csv_text)
            self.assertIn("dry_run", csv_text)

    def test_dry_run_one_packet_mode_writes_transfer_size_packet_size(self):
        system = _mesh2d_system()
        benchmark = All2AllStressBenchmark(
            transfer_sizes=[8, 16],
            transfer_size_unit="flits",
            packet_size=4,
            packetization="one_packet_per_pair",
            injection_rate=1.0,
            repetitions=1,
        )
        case = All2AllBenchmarkCase(system.name, system, benchmark)

        with tempfile.TemporaryDirectory() as tmpdir:
            output = All2AllStressRunner(BookSimBackend()).run(
                [case],
                benchmark,
                Path(tmpdir),
                dry_run=True,
                progress=False,
                run_name="all2all_one_packet_dry",
            )

            size_8_config = (
                output
                / "booksim"
                / "mesh2d_2x2_xy"
                / "size_8_rep_0"
                / "booksim.cfg"
            ).read_text(encoding="utf-8")
            size_16_config = (
                output
                / "booksim"
                / "mesh2d_2x2_xy"
                / "size_16_rep_0"
                / "booksim.cfg"
            ).read_text(encoding="utf-8")

            self.assertIn("packet_size = 8;", size_8_config)
            self.assertIn("batch_size = 3;", size_8_config)
            self.assertIn("packet_size = 16;", size_16_config)
            self.assertIn("batch_size = 3;", size_16_config)

            csv_text = (
                output / "results" / "all2all_stress.csv"
            ).read_text(encoding="utf-8")
            self.assertIn("packetization", csv_text)
            self.assertIn("one_packet_per_pair", csv_text)


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

from topoanalyzer.benchmarks.latency_vs_injection import (
    BenchmarkCase,
    LatencyInjectionBenchmark,
    LatencyInjectionPlotSettings,
    LatencyInjectionRunner,
)
from topoanalyzer.experiments.factory import build_system_from_dict
from topoanalyzer.simulators.booksim.backend import BookSimBackend


class BenchmarkTests(unittest.TestCase):
    def test_dry_run_writes_configs_and_results(self):
        system = build_system_from_dict(
            {
                "name": "mesh2d_2x2_xy",
                "topology": {"type": "mesh2d", "params": {"x": 2, "y": 2}},
                "links": {"default": {"latency_cycles": 1, "bandwidth": "64GB/s"}},
                "routing": {"type": "mesh_xy"},
            }
        )
        benchmark = LatencyInjectionBenchmark(
            injection_rates=[0.01, 0.02],
            injection_rate_unit="flits/node/cycle",
            repetitions=1,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            output = LatencyInjectionRunner(BookSimBackend()).run(
                [system],
                benchmark,
                Path(tmpdir),
                dry_run=True,
                progress=False,
                run_name="dry",
            )

            self.assertTrue(
                (
                    output
                    / "booksim"
                    / "mesh2d_2x2_xy"
                    / "inj_0.010000_rep_0"
                    / "booksim.cfg"
                ).exists()
            )
            self.assertTrue(
                (output / "results" / "latency_vs_injection.csv").exists()
            )
            csv_text = (output / "results" / "latency_vs_injection.csv").read_text(
                encoding="utf-8"
            )
            self.assertIn("injection_rate_unit", csv_text)
            self.assertIn("flits/node/cycle", csv_text)

    def test_case_specific_benchmark_overrides(self):
        system = build_system_from_dict(
            {
                "name": "mesh2d_2x2_xy",
                "topology": {"type": "mesh2d", "params": {"x": 2, "y": 2}},
                "links": {"default": {"latency_cycles": 1, "bandwidth": "64GB/s"}},
                "routing": {"type": "mesh_xy"},
            }
        )
        benchmark = LatencyInjectionBenchmark(
            injection_rates=[0.01, 0.02],
            injection_rate_unit="packets/node/cycle",
            repetitions=1,
        )
        case = BenchmarkCase(
            name="mesh2d_2x2_short",
            system=system,
            benchmark=benchmark.with_overrides(
                {
                    "injection_rates": [0.03],
                    "injection_rate_unit": "flits/node/cycle",
                    "packet_size": 4,
                    "repetitions": 2,
                }
            ),
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            output = LatencyInjectionRunner(BookSimBackend()).run(
                [case],
                benchmark,
                Path(tmpdir),
                dry_run=True,
                progress=False,
                run_name="case_override",
            )

            self.assertTrue(
                (
                    output
                    / "booksim"
                    / "mesh2d_2x2_short"
                    / "inj_0.030000_rep_0"
                    / "booksim.cfg"
                ).exists()
            )
            self.assertTrue(
                (
                    output
                    / "booksim"
                    / "mesh2d_2x2_short"
                    / "inj_0.030000_rep_1"
                    / "booksim.cfg"
                ).exists()
            )
            self.assertFalse(
                (
                    output
                    / "booksim"
                    / "mesh2d_2x2_short"
                    / "inj_0.010000_rep_0"
                    / "booksim.cfg"
                ).exists()
            )
            config_text = (
                output
                / "booksim"
                / "mesh2d_2x2_short"
                / "inj_0.030000_rep_0"
                / "booksim.cfg"
            ).read_text(encoding="utf-8")
            self.assertIn("packet_size = 4;", config_text)
            self.assertIn("injection_rate_uses_flits = 1;", config_text)

    def test_plot_settings_accept_log_y_axis(self):
        settings = LatencyInjectionPlotSettings.from_dict({"y_axis": "log"})

        self.assertEqual(settings.y_scale, "log")


if __name__ == "__main__":
    unittest.main()

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
from topoanalyzer.experiments.loader import load_document
from topoanalyzer.simulators.booksim.backend import BookSimBackend
from topoanalyzer.cli import _load_benchmark_cases


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
                (
                    output
                    / "booksim"
                    / "mesh2d_2x2_xy"
                    / "inj_0.010000_rep_0"
                    / "anynet.net"
                ).exists()
            )
            self.assertTrue(
                (
                    output
                    / "booksim"
                    / "mesh2d_2x2_xy"
                    / "inj_0.010000_rep_0"
                    / "anynet.routes"
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
            metrics_text = (output / "results" / "metrics.txt").read_text(
                encoding="utf-8"
            )
            self.assertIn("[mesh2d_2x2_xy]", metrics_text)
            self.assertIn("nodes: 4", metrics_text)
            self.assertIn("routers: 4", metrics_text)
            self.assertIn("links: 8", metrics_text)
            self.assertIn("max_router_radix: 3", metrics_text)
            self.assertIn("diameter: 2", metrics_text)
            self.assertIn("bisection_bandwidth: 128GB/s", metrics_text)
            self.assertIn("bisection_method: exact_balanced_router_cut", metrics_text)

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

    def test_injection_rates_accept_range_mapping(self):
        benchmark = LatencyInjectionBenchmark.from_dict(
            {
                "type": "latency_vs_injection_rate",
                "injection_rates": {
                    "range": {"start": 0.001, "stop": 0.1, "step": 0.004}
                },
            }
        )

        self.assertEqual(len(benchmark.injection_rates), 25)
        self.assertEqual(benchmark.injection_rates[0], 0.001)
        self.assertAlmostEqual(
            benchmark.injection_rates[1] - benchmark.injection_rates[0],
            0.004,
        )
        self.assertEqual(benchmark.injection_rates[-1], 0.097)

    def test_injection_rates_accept_range_string_in_case_override(self):
        benchmark = LatencyInjectionBenchmark(
            injection_rates=[0.01, 0.02],
            repetitions=1,
        )
        override = benchmark.with_overrides(
            {"injection_rates": "range(0.01, 0.05, 0.02)"}
        )

        self.assertEqual(override.injection_rates, [0.01, 0.03])

    def test_stop_on_error_is_preserved_in_overrides(self):
        benchmark = LatencyInjectionBenchmark.from_dict(
            {
                "type": "latency_vs_injection_rate",
                "injection_rates": [0.01],
                "stop_on_error": True,
            }
        )

        self.assertTrue(benchmark.stop_on_error)
        self.assertTrue(benchmark.with_overrides({"packet_size": 2}).stop_on_error)

    def test_stop_on_error_records_first_error_then_aborts(self):
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
            repetitions=1,
            stop_on_error=True,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            output_root = Path(tmpdir)
            with self.assertRaisesRegex(RuntimeError, "benchmark stopped"):
                LatencyInjectionRunner(
                    BookSimBackend(executable="definitely_missing_booksim")
                ).run(
                    [system],
                    benchmark,
                    output_root,
                    progress=False,
                    run_name="stop_on_error",
                )

            csv_text = (
                output_root
                / "stop_on_error"
                / "results"
                / "latency_vs_injection.csv"
            ).read_text(encoding="utf-8")
            self.assertIn("status", csv_text)
            self.assertIn("error", csv_text)
            self.assertIn("0.01", csv_text)
            self.assertNotIn("0.02", csv_text)

    def test_plot_settings_accept_log_y_axis(self):
        settings = LatencyInjectionPlotSettings.from_dict({"y_axis": "log"})

        self.assertEqual(settings.y_scale, "log")

    def test_plot_settings_accept_y_max(self):
        settings = LatencyInjectionPlotSettings.from_dict({"y_max": 5000})

        self.assertEqual(settings.y_max, 5000.0)

    def test_plot_settings_reject_non_positive_y_max(self):
        with self.assertRaisesRegex(ValueError, "plot y_max"):
            LatencyInjectionPlotSettings.from_dict({"y_max": 0})

    def test_fattree_vs_mesh_benchmark_uses_same_terminal_count(self):
        benchmark_file = (
            Path(__file__).resolve().parents[1]
            / "examples"
            / "benchmarks"
            / "comparisons"
            / "latency_vs_injection_fattree_r8_l4_vs_mesh_16x16.yaml"
        )
        spec = load_document(benchmark_file)
        benchmark = LatencyInjectionBenchmark.from_dict(spec["benchmark"])
        cases = _load_benchmark_cases(spec, benchmark_file.parent, benchmark)

        self.assertEqual(benchmark.injection_rates[0], 0.001)
        self.assertEqual(len(benchmark.injection_rates), 25)
        self.assertAlmostEqual(
            benchmark.injection_rates[1] - benchmark.injection_rates[0],
            0.004,
        )
        self.assertLessEqual(benchmark.injection_rates[-1], 0.1)
        self.assertEqual(
            [case.system.graph.metadata["terminal_count"] for case in cases],
            [256, 256],
        )
        self.assertEqual(
            [case.system.topology_type for case in cases],
            ["fattree", "mesh2d"],
        )
        self.assertEqual(cases[0].system.routing_table.name, "fattree_nca_hash")


if __name__ == "__main__":
    unittest.main()

import unittest

from topoanalyzer.plotting.latency import _latency_series, _x_axis_label


class LatencyPlotTests(unittest.TestCase):
    def test_latency_series_uses_accepted_rate_for_x_axis_in_injection_order(self):
        rows = [
            {
                "case": "mesh",
                "system": "mesh_system",
                "injection_rate": "0.100",
                "injection_rate_unit": "flits/node/cycle",
                "accepted_rate": "0.090",
                "average_packet_latency": "12.0",
            },
            {
                "case": "mesh",
                "system": "mesh_system",
                "injection_rate": "0.200",
                "injection_rate_unit": "flits/node/cycle",
                "accepted_rate": "0.080",
                "average_packet_latency": "20.0",
            },
        ]

        series = _latency_series(rows)
        points = series["mesh"]

        self.assertEqual([point.injection_rate for point in points], [0.100, 0.200])
        self.assertEqual([point.accepted_rate for point in points], [0.090, 0.080])

    def test_latency_series_averages_repetitions_by_injection_rate(self):
        rows = [
            {
                "case": "mesh",
                "system": "mesh_system",
                "injection_rate": "0.100",
                "accepted_rate": "0.070",
                "average_packet_latency": "10.0",
            },
            {
                "case": "mesh",
                "system": "mesh_system",
                "injection_rate": "0.100",
                "accepted_rate": "0.090",
                "average_packet_latency": "14.0",
            },
        ]

        point = _latency_series(rows)["mesh"][0]

        self.assertAlmostEqual(point.accepted_rate, 0.080)
        self.assertAlmostEqual(point.latency, 12.0)

    def test_latency_series_skips_rows_without_accepted_rate(self):
        rows = [
            {
                "case": "mesh",
                "system": "mesh_system",
                "injection_rate": "0.100",
                "accepted_rate": "",
                "average_packet_latency": "12.0",
            }
        ]

        self.assertFalse(_latency_series(rows))

    def test_x_axis_label_reports_accepted_rate_units(self):
        rows = [{"injection_rate_unit": "flits/node/cycle"}]

        self.assertEqual(
            _x_axis_label(rows),
            "Accepted rate (flits/node/cycle)",
        )


if __name__ == "__main__":
    unittest.main()

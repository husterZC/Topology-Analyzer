# Plot YAML Settings

Plot settings appear at the top level of a benchmark YAML file under `plot:`.

```yaml
plot:
  y_scale: log
  y_max: 10000
  emit_companion_plot: true
```

## Fields

### `y_scale`

Controls the primary latency plot y-axis.

Supported values:

- `linear`
- `log`
- `log_y`
- `logarithmic`

Aliases `log_y` and `logarithmic` normalize to `log`.

Default:

```yaml
plot:
  y_scale: linear
```

Example:

```yaml
plot:
  y_scale: log
```

With log scale, the primary plot title becomes:

```text
Latency vs Injection Rate (log scale)
```

### `y_max`

Optional positive number that sets the maximum y-axis limit for latency plots.
Points above this value are clipped visually, but remain unchanged in the CSV
and JSON results.

```yaml
plot:
  y_max: 10000
```

This limit is applied to both the primary plot and the companion plot when
`emit_companion_plot` is true.

### `emit_companion_plot`

When true, the benchmark runner also writes the opposite y-axis scale.

```yaml
plot:
  y_scale: log
  emit_companion_plot: true
```

Outputs:

```text
plots/latency_vs_injection.png          # log y-axis
plots/latency_vs_injection.pdf
plots/latency_vs_injection_linear.png   # linear y-axis companion
plots/latency_vs_injection_linear.pdf
```

If the primary scale is linear, the companion is:

```text
plots/latency_vs_injection_log.png
plots/latency_vs_injection_log.pdf
```

Default:

```yaml
emit_companion_plot: true
```

## Axis Labels

The x-axis values are measured injection rates computed from the result CSV:

```text
accepted_rate * packet_size
```

This converts BookSim's accepted packet rate to an accepted flit injection
rate for flit-rate sweeps. It is still measured throughput, not the configured
offered `injection_rate` sweep point. The axis label uses the benchmark rate
unit:

```text
Injection rate (flits/node/cycle)
```

or:

```text
Injection rate (packets/node/cycle)
```

If rows contain mixed units, the label becomes:

```text
Injection rate (mixed units)
```

The y-axis is always:

```text
Average packet latency (cycles)
```

Rows are grouped by configured offered `injection_rate` so repetitions of the
same sweep point are averaged together. Line segments are drawn in increasing
offered `injection_rate` order, while each point's x-coordinate remains the
averaged measured `accepted_rate * packet_size`.

## Plot Input

The plotter reads:

```text
results/latency_vs_injection.csv
```

Only rows with:

```text
status == ok
```

at least one latency metric, a parseable `accepted_rate`, and a positive
`packet_size` are plotted. For older CSV files without `packet_size`, the
plotter uses `1`.

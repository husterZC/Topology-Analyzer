# Plot YAML Settings

Plot settings appear at the top level of a benchmark YAML file under `plot:`.

```yaml
plot:
  x_scale: linear
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

### `x_scale`

Controls the primary x-axis for `all2all_stress` plots.
`latency_vs_injection_rate` currently keeps a linear x-axis.

Supported values:

- `linear`
- `log`
- `logarithmic`

Default:

```yaml
plot:
  x_scale: linear
```

### `y_max`

Optional positive number that sets the maximum y-axis limit for latency or
runtime plots. Points above this value are clipped visually, but remain
unchanged in the CSV and JSON results.

```yaml
plot:
  y_max: 10000
```

This limit is applied to both the primary plot and the companion plot when
`emit_companion_plot` is true.

For linear y-axis plots, the displayed range is `0..y_max`. For log y-axis
plots, the upper bound is `y_max` and the lower bound remains positive.

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

### `latency_vs_injection_rate`

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

### `all2all_stress`

The all-to-all stress plot reads:

```text
results/all2all_stress.csv
```

The x-axis is the configured transfer size per source-destination pair:

```text
Transfer size per source-destination pair (flits)
```

or:

```text
Transfer size per source-destination pair (bytes)
```

The y-axis is:

```text
All-to-all runtime (cycles)
```

Only rows with `status == ok` and a parseable `average_runtime_cycles` are
plotted. Repetitions of the same transfer size are averaged together before
drawing line segments.

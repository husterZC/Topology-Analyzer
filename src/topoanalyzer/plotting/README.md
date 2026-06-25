# Plot YAML Settings

Plot settings appear at the top level of a benchmark YAML file under `plot:`.

```yaml
plot:
  y_scale: log
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
Latency vs Accepted Rate (log scale)
```

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

The x-axis values are measured `accepted_rate` values from the result CSV, not
the configured offered `injection_rate` sweep points. The axis label uses the
benchmark rate unit:

```text
Accepted rate (flits/node/cycle)
```

or:

```text
Accepted rate (packets/node/cycle)
```

If rows contain mixed units, the label becomes:

```text
Accepted rate (mixed units)
```

The y-axis is always:

```text
Average packet latency (cycles)
```

Rows are grouped by configured offered `injection_rate` so repetitions of the
same sweep point are averaged together. Line segments are drawn in increasing
offered `injection_rate` order, while each point's x-coordinate remains the
averaged measured `accepted_rate`.

## Plot Input

The plotter reads:

```text
results/latency_vs_injection.csv
```

Only rows with:

```text
status == ok
```

at least one latency metric, and a parseable `accepted_rate` are plotted.

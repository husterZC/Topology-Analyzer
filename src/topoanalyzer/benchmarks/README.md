# Benchmark YAML Settings

Benchmark YAML drives experiments over one or more systems.

```yaml
benchmark:
  type: latency_vs_injection_rate
  injection_rates:
    range:
      start: 0.001
      stop: 0.1
      step: 0.004
  injection_rate_unit: flits/node/cycle
  packet_size: 1
  traffic: uniform
  warmup_cycles: 3
  sample_cycles: 5000
  max_samples: 10
  repetitions: 1
  num_vcs: 2
  vc_buffer_size: 8
  router_latency: 1
  timeout_seconds: 120
  stop_on_error: false

systems:
  - path: ../../systems/mesh2d/xy/mesh2d_4x4_xy.yaml

booksim:
  executable: booksim
  backend: anynet_table

output_dir: runs
```

## Top-Level Fields

Required:

- `benchmark`: benchmark type and default benchmark settings.
- `systems`: list of systems or benchmark cases.

Optional:

- `plot`: plot settings; see `../plotting/README.md`.
- `booksim`: BookSim backend settings; see `../simulators/booksim/README.md`.
- `output_dir`: output root. Defaults to `runs`.

## `benchmark.type: latency_vs_injection_rate`

Runs BookSim once per:

```text
case x injection_rate x repetition
```

Then writes:

```text
results/latency_vs_injection.csv
results/latency_vs_injection.json
results/metrics.txt
plots/latency_vs_injection.png
plots/latency_vs_injection.pdf
```

The sweep is configured by offered `injection_rate`, but the latency plot uses
BookSim's measured `accepted_rate * packet_size` on the x-axis. The offered
rate remains in the CSV so each plotted point can be traced back to the
requested load.

`results/metrics.txt` summarizes each benchmarked system's static network
characteristics: terminal/injection nodes, routers, directed links, exact
router-hop diameter, and bisection bandwidth. The bisection entry includes a
method field because small systems use an exact balanced router cut, while
larger systems use a topology formula or coordinate-axis cut when exact
enumeration would be too expensive.

### Fields

```yaml
benchmark:
  type: latency_vs_injection_rate
  injection_rates:
    range:
      start: 0.001
      stop: 0.1
      step: 0.004
  injection_rate_unit: flits/node/cycle
  packet_size: 1
  traffic: uniform
  warmup_cycles: 3
  sample_cycles: 5000
  max_samples: 10
  repetitions: 1
  num_vcs: 2
  vc_buffer_size: 8
  router_latency: 1
  timeout_seconds: 120
  stop_on_error: false
```

Field reference:

- `type`: must be `latency_vs_injection_rate`.
- `injection_rates`: explicit list of numeric rates or a range specification. Required.
- `injection_rate_unit`: `flits/node/cycle` or `packets/node/cycle`. Optional, default `packets/node/cycle`.
- `packet_size`: packet size in flits. Optional, default `1`.
- `traffic`: BookSim traffic pattern string. Optional, default `uniform`.
- `warmup_cycles`: passed to BookSim as `warmup_periods`. Optional, default `10000`.
- `sample_cycles`: passed to BookSim as `sample_period`. Optional, default `50000`.
- `max_samples`: passed to BookSim as `max_samples`. Optional, default `10`.
- `repetitions`: number of repetitions per injection rate. Optional, default `1`.
- `num_vcs`: BookSim `num_vcs`. Optional, default `2`.
- `vc_buffer_size`: BookSim `vc_buf_size`. Optional, default `8`.
- `router_latency`: stored in options for future router models. Current BookSim anynet path does not lower it directly.
- `timeout_seconds`: optional per-run subprocess timeout.
- `stop_on_error`: stop the sweep after the first `error` or `failed` run point. Optional, default `false`.

### Traffic Patterns

`traffic` is passed directly to BookSim as the `traffic = ...;` config field.
Topology-Analyzer does not currently validate the traffic string before launch,
so unsupported or incompatible patterns fail inside BookSim.

`uniform` is the default. It is stochastic uniform random traffic: each packet
source chooses a random destination from the BookSim terminal ID range. It is
not a deterministic all-to-all permutation.

Common BookSim2 traffic strings:

| Traffic | Description | Notes |
|---|---|---|
| `uniform` | Random destination over all terminals. | Safest generic baseline. |
| `randperm(seed)` | Fixed random one-to-one destination permutation. | Good repeatable permutation baseline. |
| `hotspot(...)` | Weighted hotspot destination traffic. | Useful for imbalance and contention studies. |
| `background(...)` | Uniform random traffic excluding selected destinations. | Requires an exclusion list. |
| `bitcomp` | Bit-complement permutation. | Node count must be a power of two. |
| `bitrev` | Bit-reversal permutation. | Node count must be a power of two. |
| `shuffle` | Shuffle permutation. | Node count must be a power of two. |
| `transpose` | Bit-transpose permutation. | Node count must be an even power of two. |
| `diagonal` | Random diagonal/local-style pattern. | BookSim built-in synthetic pattern. |
| `asymmetric` | Asymmetric half-network pattern. | BookSim built-in synthetic pattern. |
| `taper64` | Special local-plus-random 64-node pattern. | Requires exactly 64 terminals. |
| `tornado(k,n,xr)` | Tornado pattern for k-ary n-dimensional-style networks. | Parameters must match the intended indexing. |
| `neighbor(k,n,xr)` | Neighbor pattern for k-ary n-dimensional-style networks. | Parameters must match the intended indexing. |
| `badperm_yarc(k,n,xr)` | YARC adversarial permutation. | Topology/indexing specific. |
| `bad_dragon(k,n)` | Dragonfly bad permutation. | Intended for dragonfly-style layouts. |

For topology-independent benchmarking on the `anynet` backend, prefer
`uniform`, `randperm(seed)`, and one or more `hotspot(...)` cases first. Add
the topology-specific/adversarial patterns only when their node-count and
indexing assumptions match the system under test.

By default the runner records an `error` row and continues to the next run point
when one BookSim invocation fails. Set:

```yaml
benchmark:
  stop_on_error: true
```

to abort the sweep immediately after writing the first failed record.

### Injection Rate Lists And Ranges

Explicit lists remain supported:

```yaml
injection_rates: [0.01, 0.02, 0.04]
```

For regular sweeps, use a stop-exclusive range:

```yaml
injection_rates:
  range:
    start: 0.001
    stop: 0.1
    step: 0.004
```

This expands like Python `range(start, stop, step)`, so the example above
produces 25 rates from `0.001` through `0.097`.

The compact quoted form is also accepted:

```yaml
injection_rates: "range(0.001, 0.1, 0.004)"
```

To include an exactly reachable endpoint, set `inclusive: true`:

```yaml
injection_rates:
  range:
    start: 0.01
    stop: 0.05
    step: 0.02
    inclusive: true
```

### Injection Rate Units

For:

```yaml
injection_rate_unit: flits/node/cycle
packet_size: 5
```

the BookSim config includes:

```text
packet_size = 5;
injection_rate_uses_flits = 1;
```

BookSim converts the configured flit rate to packet injection rate internally
using the average packet size.

For:

```yaml
injection_rate_unit: packets/node/cycle
```

the BookSim config includes:

```text
injection_rate_uses_flits = 0;
```

## `systems` Entries

Each `systems` entry creates a benchmark case.

### String Path

```yaml
systems:
  - ../../systems/mesh2d/xy/mesh2d_4x4_xy.yaml
```

The case name defaults to the system name.

### Mapping With Path

```yaml
systems:
  - path: ../../systems/mesh2d/xy/mesh2d_4x4_xy.yaml
```

Equivalent to the string form, but allows overrides.

### Case Name And Benchmark Override

```yaml
systems:
  - path: ../../systems/mesh2d/xy/mesh2d_16x16_xy.yaml
    case: mesh2d_16x16_short
    benchmark:
      injection_rates: "range(0.01, 0.05, 0.02)"
      timeout_seconds: 300
```

Override aliases:

- `benchmark`
- `settings`
- `parameters`

Overrides are merged onto the top-level `benchmark` defaults.

### Inline System

```yaml
systems:
  - name: inline_mesh2d_2x2
    topology:
      type: mesh2d
      params:
        x: 2
        y: 2
    links:
      default:
        latency_cycles: 1
        bandwidth: 64GB/s
    routing:
      type: mesh_xy
```

This is useful for short experiments, but for repeatable research runs prefer
separate system YAML files.

## Output Layout

```text
runs/<run-name>/
  cases/<case-name>/
    case.json
  systems/<system-name>/
    system.json
    topology.json
    routing_table.json
    validation.json
  booksim/<case-name>/inj_<rate>_rep_<n>/
    booksim.cfg
    anynet.net
    anynet.routes
    anynet_mapping.json
    stdout.txt
    stderr.txt
  results/
    latency_vs_injection.csv
    latency_vs_injection.json
    metrics.txt
  plots/
    latency_vs_injection.png
    latency_vs_injection.pdf
```

The result CSV includes:

- `case`
- `system`
- `injection_rate`
- `injection_rate_unit`
- `packet_size`
- `repetition`
- `status`
- `average_packet_latency`
- `average_network_latency`
- `accepted_rate`
- `config_path`
- `error`

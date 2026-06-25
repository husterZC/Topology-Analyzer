# Topology-Analyzer

Topology-Analyzer is a research harness for NoC topology modeling, routing-table
generation, and BookSim benchmarking.

The internal model is deliberately not a BookSim config. A system is modeled as:

```text
Topology type
+ topology-specific parameters
+ resolved link parameters
+ routing table
```

That system can then be validated, exported, or lowered into a simulator backend.
The first implemented path is:

```text
2D mesh + heterogeneous-capable link model + XY routing + BookSim latency sweep
```

The repository also includes graph-based routing generators. `graph_updown`
builds a BFS spanning tree and emits conservative up*/down* routes. `graph_lash`
keeps shortest candidate paths where possible and assigns routes to virtual
channel layers so each layer's channel dependency graph stays acyclic.

## Layout

```text
src/topoanalyzer/
  model/              canonical graph, link, routing, and system objects
  topologies/         topology builders such as mesh2d
  routing/            routing-table generators and deadlock checks
  simulators/booksim/ BookSim config generation, execution, and parsing
  benchmarks/         reusable benchmark runners
  plotting/           result plotting
  experiments/        YAML/JSON loading and system factory
examples/
  benchmarks/         benchmark specs grouped by topology
  systems/            system specs grouped by topology/routing/link style
tests/                focused unit tests
```

Detailed YAML-setting docs live next to the implementation:

```text
src/topoanalyzer/doc/README.md
src/topoanalyzer/model/doc/README.md
src/topoanalyzer/topologies/doc/README.md
src/topoanalyzer/routing/doc/README.md
src/topoanalyzer/benchmarks/doc/README.md
src/topoanalyzer/plotting/doc/README.md
src/topoanalyzer/experiments/doc/README.md
src/topoanalyzer/simulators/doc/README.md
src/topoanalyzer/simulators/booksim/doc/README.md
```

## Install

```bash
pip install -e .
```

or:

```bash
make install
```

Useful Make targets:

```bash
make help
make test
make clean-runs
make clean-build
make clean
```

## Validate A System

```bash
topoanalyzer validate examples/systems/mesh2d/xy/mesh2d_4x4_xy.yaml
```

## Build Artifacts

```bash
topoanalyzer build examples/systems/mesh2d/xy/mesh2d_4x4_xy.yaml --output-dir build/mesh2d_4x4_xy
```

This writes:

```text
system.json
topology.json
routing_table.json
validation.json
```

## Dry-Run A Benchmark

```bash
topoanalyzer benchmark examples/benchmarks/mesh2d/latency_vs_injection_mesh2d.yaml --dry-run
```

Dry-run mode creates the run directory and BookSim config files without launching
BookSim.

## Run A BookSim Sweep

Make sure the configured BookSim binary exists on `PATH`, or set the executable
in the benchmark YAML.

```bash
topoanalyzer benchmark examples/benchmarks/mesh2d/latency_vs_injection_mesh2d.yaml
```

To compare square 2D mesh scales:

```bash
topoanalyzer benchmark examples/benchmarks/mesh2d/latency_vs_injection_mesh2d_scales.yaml
```

Benchmark files support global defaults plus per-system overrides. This is useful
when a large mesh needs a shorter injection sweep or a longer timeout than a
small mesh:

```yaml
benchmark:
  type: latency_vs_injection_rate
  injection_rates: [0.01, 0.02, 0.04, 0.08, 0.12, 0.16, 0.20]
  injection_rate_unit: flits/node/cycle
  packet_size: 1
  repetitions: 1
  timeout_seconds: 120

plot:
  y_scale: log
  emit_companion_plot: true

systems:
  - path: ../../systems/mesh2d/xy/mesh2d_2x2_xy.yaml
  - path: ../../systems/mesh2d/xy/mesh2d_4x4_xy.yaml
  - path: ../../systems/mesh2d/xy/mesh2d_16x16_xy.yaml
    benchmark:
      injection_rates: [0.01, 0.02, 0.04]
      timeout_seconds: 300
```

Supported injection-rate units are `flits/node/cycle` and
`packets/node/cycle`. For BookSim, `flits/node/cycle` emits
`injection_rate_uses_flits = 1`; BookSim then converts the configured flit rate
to packet injection rate using `packet_size`.

With `plot.y_scale: log`, the primary `latency_vs_injection.png` uses a log
y-axis. If `emit_companion_plot` is true, the runner also writes the opposite
scale as `latency_vs_injection_linear.png` or `latency_vs_injection_log.png`.

Each run is self-contained:

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
    stdout.txt
    stderr.txt
  results/
    latency_vs_injection.csv
    latency_vs_injection.json
  plots/
    latency_vs_injection.png
    latency_vs_injection.pdf
```

## Link Parameter Formats

Simple homogeneous links:

```yaml
links:
  default:
    latency_cycles: 2
    bandwidth: 64GB/s
```

Orientation-specific links:

```yaml
links:
  default:
    latency_cycles: 2
    bandwidth: 64GB/s
  classes:
    x:
      latency_cycles: 2
      bandwidth: 64GB/s
    y:
      latency_cycles: 5
      bandwidth: 16GB/s
```

Pair override:

```yaml
links:
  default:
    latency_cycles: 2
    bandwidth: 64GB/s
  overrides:
    - src: [0, 0]
      dst: [1, 0]
      latency_cycles: 7
      bandwidth: 8GB/s
```

Resolution order is:

```text
pair override > link class/orientation > default
```

## Current BookSim Backend Limitations

The internal model supports rectangular meshes and heterogeneous links. The
initial stock BookSim adapter only lowers square 2D meshes with homogeneous
channel latency and homogeneous bandwidth metadata, because standard BookSim
mesh configs expose one `k` and one global `channel_latency`.

For heterogeneous links or rectangular meshes, the model and validation still
work, but the current BookSim adapter reports an unsupported-feature error. The
next backend step is to add generated/custom BookSim topology code for those
cases.

The same limitation applies to graph-generated routing tables such as
`graph_updown` and `graph_lash`: the generated routing table is validated and
exported by Topology-Analyzer, but stock BookSim config generation currently
only lowers `mesh_xy` to `routing_function = dor`. Simulating arbitrary routing
tables requires a custom BookSim routing function or a table-driven BookSim
backend.

`graph_lash` is intended as the better general-topology static-routing baseline:
it tries shortest/simple candidate paths and places each route into the lowest
VC layer whose channel dependency graph remains acyclic. If the candidate set is
already acyclic, it may use one VC; otherwise it uses additional VCs up to
`max_vcs`.

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
The default implemented BookSim path is:

```text
System graph + generated routing table + custom BookSim anynet/table backend
```

The repository also includes graph-based routing generators. `graph_updown`
builds a BFS spanning tree and emits conservative up*/down* routes. `graph_lash`
keeps shortest candidate paths where possible and assigns routes to virtual
channel layers so each layer's channel dependency graph stays acyclic. Built-in
regular topologies include 2D/3D mesh, 2D/3D torus, 3D ruche, Hypercube,
Dragonfly, SlimNoC, UBMesh, and Fat-tree. Ruche, Hypercube, Dragonfly, SlimNoC,
and UBMesh include stronger static candidates such as LASH-style VC routing and
Valiant/VALg/APR-style hashed intermediate routing. Fat-tree systems can use
topology-specific
`fattree_lca` routing as a simple baseline or `fattree_nca_hash` routing as the
recommended balanced static baseline. The Fat-tree package also includes
`fattree_dmodk`, `fattree_dmodc`, and BookSim-runtime `fattree_anca`.

## Layout

```text
src/topoanalyzer/
  model/              canonical graph, link, routing, and system objects
  topologies/         topology builders such as mesh2d, torus3d, slimnoc
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
src/topoanalyzer/README.md
src/topoanalyzer/model/README.md
src/topoanalyzer/topologies/README.md
src/topoanalyzer/routing/README.md
src/topoanalyzer/benchmarks/README.md
src/topoanalyzer/plotting/README.md
src/topoanalyzer/experiments/README.md
src/topoanalyzer/simulators/README.md
src/topoanalyzer/simulators/booksim/README.md
```

## Install

Recommended full setup:

```bash
make bootstrap
source .venv/bin/activate
```

Python 3.10 or newer is required. `make bootstrap` auto-prefers `python3.12`,
`python3.11`, then `python3.10`. If your cluster's default `python3` is older,
choose an interpreter explicitly:

```bash
make bootstrap BOOTSTRAP_PYTHON=python3.11
```

If a previous failed bootstrap created `.venv` with an older Python, remove it
and rerun:

```bash
rm -rf .venv
make bootstrap BOOTSTRAP_PYTHON=python3.11
```

`make bootstrap` creates `.venv`, installs Topology-Analyzer in editable mode,
clones BookSim2 into `external/booksim2`, applies the `anynet` route-table
overlay, builds BookSim, and links the resulting binary as:

```text
.venv/bin/booksim
bin/booksim
```

This is the easiest way to avoid benchmark failures such as:

```text
[Errno 2] No such file or directory: 'booksim'
```

Python-only setup:

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
make bootstrap
make python-env
source .venv/bin/activate
make test
make booksim-fetch
make booksim-apply-overlay BOOKSIM_DIR=/path/to/booksim2
make booksim-build BOOKSIM_DIR=/path/to/booksim2
make booksim-link
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

Dry-run mode creates the run directory and BookSim input files without launching
BookSim.

## Run A BookSim Sweep

Make sure the configured BookSim binary exists on `PATH`, or set the executable
in the benchmark YAML. The default `anynet_table` backend requires the BookSim2
overlay in [booksim_overlays/booksim2](</scratch2/chi/SoftHier_porj/codex/Topology-Analyzer/booksim_overlays/booksim2/README.md>).
Running `make bootstrap` handles this by building BookSim and linking it into
`.venv/bin/booksim`; the backend also checks the repo-local `.venv/bin/booksim`,
`bin/booksim`, and `external/booksim2/src/booksim` when YAML uses
`executable: booksim`.

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
  injection_rates:
    range:
      start: 0.01
      stop: 0.21
      step: 0.04
  injection_rate_unit: flits/node/cycle
  packet_size: 1
  repetitions: 1
  timeout_seconds: 120
  stop_on_error: true

plot:
  y_scale: log
  emit_companion_plot: true

systems:
  - path: ../../systems/mesh2d/xy/mesh2d_2x2_xy.yaml
  - path: ../../systems/mesh2d/xy/mesh2d_4x4_xy.yaml
  - path: ../../systems/mesh2d/xy/mesh2d_16x16_xy.yaml
    benchmark:
      injection_rates: "range(0.01, 0.05, 0.02)"
      timeout_seconds: 300
```

Supported injection-rate units are `flits/node/cycle` and
`packets/node/cycle`. For BookSim, `flits/node/cycle` emits
`injection_rate_uses_flits = 1`; BookSim then converts the configured flit rate
to packet injection rate using `packet_size`.

`injection_rates` can be an explicit numeric list or a stop-exclusive
`range(start, stop, step)` specification. For example, `start: 0.001`,
`stop: 0.1`, and `step: 0.004` expands to 25 rates from `0.001` through
`0.097`.

By default, a failed BookSim point is recorded as an `error` row and the sweep
continues. Set `benchmark.stop_on_error: true` to write the failed record and
abort immediately.

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
    anynet.net
    anynet.routes
    anynet_mapping.json
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

## BookSim Backend

`booksim.backend` defaults to `anynet_table`.

```yaml
booksim:
  executable: /path/to/booksim
  backend: anynet_table
```

For every system, this backend writes:

- `anynet.net`: arbitrary router graph for BookSim `topology = anynet`.
- `anynet.routes`: deterministic table-driven routes, including VC selection.
- `anynet_mapping.json`: router, terminal, link, latency, and bandwidth metadata.
- `booksim.cfg`: config pointing at those generated files.

This removes the old stock-mesh blockers for rectangular meshes, heterogeneous
router-link latency, and graph-generated routing tables such as `graph_updown`
and `graph_lash`.

Before running BookSim, apply the overlay:

```bash
patch -p1 -d /path/to/booksim2 < booksim_overlays/booksim2/table_anynet.patch
make -C /path/to/booksim2/src
```

The legacy stock mesh backend is still available for comparison:

```yaml
booksim:
  backend: stock_mesh
```

That compatibility backend is intentionally narrow: square `mesh2d`, `mesh_xy`,
homogeneous 1-cycle links.

Remaining limitation: BookSim2 `FlitChannel` exposes per-link latency but not a
native per-link bandwidth field. Topology-Analyzer preserves bandwidth in
`anynet_mapping.json`; modeling true per-edge bandwidth needs a deeper BookSim
channel-model extension.

`graph_lash` is intended as the better general-topology static-routing baseline:
it tries shortest/simple candidate paths and places each route into the lowest
VC layer whose channel dependency graph remains acyclic. If the candidate set is
already acyclic, it may use one VC; otherwise it uses additional VCs up to
`max_vcs`.

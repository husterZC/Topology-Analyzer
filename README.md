# Topology-Analyzer

Topology-Analyzer is a research harness for NoC topology modeling.
It builds topology graphs, generates routing tables, validates systems, and runs
BookSim latency benchmarks.

The core system model is:

```text
topology + link parameters + routing table
```

For detailed setup, YAML formats, output layout, and backend notes, see
[details.md](details.md).

## Fast Start

Build the Python environment and BookSim:

```bash
make bootstrap
source .venv/bin/activate
```

Python 3.10 or newer is required. If your cluster's default `python3` is too
old, choose an interpreter explicitly:

```bash
make bootstrap BOOTSTRAP_PYTHON=python3.11
```

Run a dry benchmark first:

```bash
topoanalyzer benchmark examples/benchmarks/mesh2d/latency_vs_injection_mesh2d.yaml --dry-run
```

Run a real BookSim sweep:

```bash
topoanalyzer benchmark examples/benchmarks/mesh2d/latency_vs_injection_mesh2d.yaml
```

Useful commands:

```bash
make help
make test
make clean-runs
```

## Supported Topologies

| Topology | YAML Type | Main Parameters | Notes |
|---|---|---|---|
| 2D Mesh | `mesh2d` | `x`, `y`, `concentration` | Rectangular mesh. |
| 3D Mesh | `mesh3d` | `x`, `y`, `z`, `concentration` | Rectangular 3D mesh. |
| 2D Torus | `torus2d` | `x`, `y`, `concentration` | Wraparound links. |
| 3D Torus | `torus3d` | `x`, `y`, `z`, `concentration` | Wraparound links. |
| 3D Ruche | `ruche3d` | `x`, `y`, `z`, `stride`, `concentration` | Mesh plus express links. |
| Hypercube | `hypercube` | `dimension`, `concentration` | Binary hypercube. |
| Dragonfly | `dragonfly` | `p`, `a`, `h`, `groups` | Local groups plus global links. |
| SlimNoC | `slimnoc` | `q`, `concentration` | MMS/SlimFly-style diameter-2 graph. |
| UBMesh | `ubmesh` | `dimensions`, `dimension_names`, `concentration` | nD-FullMesh core from the UBMesh paper. |
| Fat-tree | `fattree` | `radix`, `levels` | Regular radix-split Fat-tree. |

## Supported Routing Algorithms

| Routing Type | Topology | Description |
|---|---|---|
| `mesh_xy` | `mesh2d` | Deterministic XY routing. |
| `mesh_xyz` | `mesh3d` | Deterministic XYZ routing. |
| `torus_xy` | `torus2d` | Conservative table-compatible XY routing. |
| `torus_xyz` | `torus3d` | Conservative table-compatible XYZ routing. |
| `ruche_xyz` | `ruche3d` | Dimension-order routing using ruche express links. |
| `ruche_lash` | `ruche3d` | LASH-style short-path routing with VC assignment. |
| `ruche_valiant_hash` | `ruche3d` | Static Valiant-style hashed intermediate routing. |
| `hypercube_ecube` | `hypercube` | Deterministic E-cube routing. |
| `hypercube_lash` | `hypercube` | Minimal path-diversity routing with VC assignment. |
| `hypercube_valiant_hash` | `hypercube` | Static Valiant-style hashed intermediate routing. |
| `dragonfly_min` | `dragonfly` | Minimal local/global/local routing. |
| `dragonfly_valiant_hash` | `dragonfly` | Static VALg-style hashed intermediate-group routing. |
| `slimnoc_min` | `slimnoc` | Static shortest-path SlimNoC routing. |
| `slimnoc_valiant_hash` | `slimnoc` | Static Valiant-style hashed intermediate-router routing. |
| `ubmesh_shortest` | `ubmesh` | Minimum-hop nD-FullMesh routing. |
| `ubmesh_dor` | `ubmesh` | Deterministic dimension-order routing. |
| `ubmesh_apr_hash` | `ubmesh` | Static APR-style hashed detour routing. |
| `ubmesh_apr_runtime` | `ubmesh` | BookSim runtime APR marker backend. |
| `ubmesh_tfc` | `ubmesh` | Static two-VL TFC approximation. |
| `fattree_lca` | `fattree` | Deterministic nearest-common-ancestor routing. |
| `fattree_nca_hash` | `fattree` | Balanced static ECMP-style NCA routing. |
| `fattree_dmodk` | `fattree` | Deterministic D-mod-k-style routing. |
| `fattree_dmodc` | `fattree` | Fault-aware Dmodc-style routing. |
| `fattree_anca` | `fattree` | BookSim runtime adaptive ANCA routing. |
| `graph_updown` | most connected graphs | Generic up*/down* routing. |
| `graph_lash` | most connected graphs | Generic short-path routing with VC assignment. |

## Supported Benchmark Tests

| Benchmark Type | Output | Description |
|---|---|---|
| `latency_vs_injection_rate` | CSV, JSON, PNG, PDF | Sweeps offered injection rate and plots latency against measured accepted rate. |

Set `benchmark.stop_on_error: true` to abort a sweep after the first failed
BookSim point. By default, errors are recorded and the sweep continues.

Example benchmark YAML files:

| Example | Purpose |
|---|---|
| `examples/benchmarks/mesh2d/latency_vs_injection_mesh2d.yaml` | Small 2D mesh sweep. |
| `examples/benchmarks/mesh2d/latency_vs_injection_mesh2d_scales.yaml` | Multi-scale 2D mesh sweep. |
| `examples/benchmarks/comparisons/latency_vs_injection_fattree_r8_l4_vs_mesh_16x16.yaml` | Cross-topology comparison. |

## Detailed Docs

- [details.md](details.md): longer project guide.
- [src/topoanalyzer/README.md](src/topoanalyzer/README.md): YAML overview.
- [src/topoanalyzer/topologies/README.md](src/topoanalyzer/topologies/README.md): topology parameters and formulas.
- [src/topoanalyzer/routing/README.md](src/topoanalyzer/routing/README.md): routing settings and algorithm details.
- [src/topoanalyzer/benchmarks/README.md](src/topoanalyzer/benchmarks/README.md): benchmark settings.
- [src/topoanalyzer/simulators/booksim/README.md](src/topoanalyzer/simulators/booksim/README.md): BookSim backend settings.

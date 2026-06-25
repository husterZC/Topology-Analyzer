# Topology-Analyzer YAML Overview

Topology-Analyzer currently consumes two YAML document shapes:

1. **System YAML**: describes one topology instance, link parameters, and routing generator.
2. **Benchmark YAML**: describes one benchmark sweep over one or more systems.

The CLI entry points are:

```bash
topoanalyzer validate <system.yaml>
topoanalyzer build <system.yaml> --output-dir <dir>
topoanalyzer benchmark <benchmark.yaml>
```

## System YAML

```yaml
name: mesh2d_4x4_xy

topology:
  type: mesh2d
  params:
    x: 4
    y: 4
    concentration: 1

links:
  default:
    latency_cycles: 1
    bandwidth: 64GB/s

routing:
  type: mesh_xy
```

Fat-tree systems use the same shape with topology-specific parameters. For
benchmarking, prefer `fattree_nca_hash` over `fattree_lca` because it spreads
equal-cost upward routes across the Fat-tree. Other Fat-tree routing options
include `fattree_dmodk`, `fattree_dmodc`, and BookSim-runtime `fattree_anca`.
Ruche, Hypercube, Dragonfly, SlimNoC, and UBMesh systems also include stronger
static candidates such as `ruche_lash`, `ruche_valiant_hash`,
`hypercube_lash`, `hypercube_valiant_hash`, `dragonfly_valiant_hash`,
`slimnoc_valiant_hash`, `ubmesh_apr_hash`, and `ubmesh_tfc`.

```yaml
name: fattree_r8_l4_nca_hash

topology:
  type: fattree
  params:
    radix: 8
    levels: 4

links:
  default:
    latency_cycles: 1
    bandwidth: 64GB/s

routing:
  type: fattree_nca_hash
  seed: 0
```

Required top-level fields:

- `name`: stable system name used in output directories and plot legends.
- `topology`: topology type and topology-specific parameters.
- `links`: default link parameters plus optional class and pair overrides.
- `routing`: routing-table generator and its parameters.

The factory builds a canonical `System`:

```text
topology type + topology params + resolved links + routing table
```

The system is validated before use. Validation checks graph connectivity,
route coverage, route adjacency, and deadlock freedom through the channel
dependency graph.

## Benchmark YAML

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
  timeout_seconds: 120

plot:
  y_scale: log
  emit_companion_plot: true

systems:
  - path: ../../systems/mesh2d/xy/mesh2d_4x4_xy.yaml
  - path: ../../systems/mesh2d/xy/mesh2d_16x16_xy.yaml
    benchmark:
      injection_rates: "range(0.01, 0.05, 0.02)"

booksim:
  executable: booksim

output_dir: runs
```

Required top-level fields:

- `benchmark`: benchmark type and default benchmark parameters.
- `systems`: list of system entries. Each entry can be a string path, a mapping with `path`, or an inline system specification.

Optional top-level fields:

- `plot`: plot settings.
- `booksim`: simulator backend settings.
- `output_dir`: run output root. Defaults to `runs`.

## Path Rules

For benchmark YAML, system paths are resolved relative to the benchmark YAML's
directory. For example, from `examples/benchmarks/mesh2d/`, this path:

```yaml
systems:
  - path: ../../systems/mesh2d/xy/mesh2d_4x4_xy.yaml
```

resolves to:

```text
examples/systems/mesh2d/xy/mesh2d_4x4_xy.yaml
```

## Detailed Docs

- [model/README.md](model/README.md): canonical system, link, and routing table concepts.
- [topologies/README.md](topologies/README.md): `topology:` YAML settings and topology formulas.
- [routing/README.md](routing/README.md): routing support matrix and `routing:` YAML settings.
- [benchmarks/README.md](benchmarks/README.md): `benchmark:` and `systems:` benchmark settings.
- [plotting/README.md](plotting/README.md): `plot:` YAML settings.
- [experiments/README.md](experiments/README.md): document loading and path behavior.
- [simulators/README.md](simulators/README.md): simulator-backend selection concepts.
- [simulators/booksim/README.md](simulators/booksim/README.md): `booksim:` settings and current BookSim limits.

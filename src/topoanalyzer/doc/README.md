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
  injection_rates: [0.01, 0.02, 0.04]
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
      injection_rates: [0.01, 0.02, 0.04]

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

- `model/doc/README.md`: canonical system, link, and routing table concepts.
- `topologies/doc/README.md`: `topology:` YAML settings.
- `routing/doc/README.md`: `routing:` YAML settings.
- `benchmarks/doc/README.md`: `benchmark:` and `systems:` benchmark settings.
- `plotting/doc/README.md`: `plot:` YAML settings.
- `experiments/doc/README.md`: document loading and path behavior.
- `simulators/doc/README.md`: simulator-backend selection concepts.
- `simulators/booksim/doc/README.md`: `booksim:` settings and current BookSim limits.

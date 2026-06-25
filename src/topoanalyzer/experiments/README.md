# Experiment YAML Loading

The experiments package is responsible for loading YAML/JSON documents and
turning them into `System` objects.

## Supported File Types

`load_document(path)` supports:

- `.yaml`
- `.yml`
- `.json`

YAML requires `PyYAML`, which is included in the project dependencies.

## System Factory

System files are parsed by:

```text
build_system_from_dict(data)
```

Expected shape:

```yaml
name: mesh2d_4x4_xy

topology:
  type: mesh2d
  params:
    x: 4
    y: 4

links:
  default:
    latency_cycles: 1
    bandwidth: 64GB/s

routing:
  type: mesh_xy
```

Factory responsibilities:

1. Parse `links`.
2. Select the topology builder from `topology.type`.
3. Build the canonical graph.
4. Select the routing generator from `routing.type`.
5. Generate the routing table.
6. Build and validate the `System`.

Unsupported topology or routing types raise `ValueError`.

## Benchmark System Path Rules

Benchmark YAML files can reference system YAML files:

```yaml
systems:
  - path: ../../systems/mesh2d/xy/mesh2d_4x4_xy.yaml
```

The CLI resolves these paths relative to the benchmark YAML directory.

Example:

```text
benchmark file:
  examples/benchmarks/mesh2d/latency_vs_injection_mesh2d_scales.yaml

system path:
  ../../systems/mesh2d/xy/mesh2d_4x4_xy.yaml

resolved path:
  examples/systems/mesh2d/xy/mesh2d_4x4_xy.yaml
```

## Benchmark Case Forms

String path:

```yaml
systems:
  - ../../systems/mesh2d/xy/mesh2d_4x4_xy.yaml
```

Mapping path:

```yaml
systems:
  - path: ../../systems/mesh2d/xy/mesh2d_4x4_xy.yaml
```

Named case:

```yaml
systems:
  - path: ../../systems/mesh2d/xy/mesh2d_4x4_xy.yaml
    case: mesh2d_4x4_baseline
```

Per-case benchmark overrides:

```yaml
systems:
  - path: ../../systems/mesh2d/xy/mesh2d_16x16_xy.yaml
    benchmark:
      injection_rates: "range(0.01, 0.05, 0.02)"
      timeout_seconds: 300
```

Inline system:

```yaml
systems:
  - name: inline_mesh
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

## CLI Overrides

The benchmark CLI supports:

```bash
topoanalyzer benchmark <benchmark.yaml> \
  --dry-run \
  --no-progress \
  --run-name <name> \
  --booksim-executable <path>
```

`--booksim-executable` overrides:

```yaml
booksim:
  executable: booksim
```

This is useful when testing against a locally built BookSim binary.

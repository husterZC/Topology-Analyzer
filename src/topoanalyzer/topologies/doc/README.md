# Topology YAML Settings

Topology YAML appears inside a system file under the `topology:` key.

```yaml
topology:
  type: mesh2d
  params:
    x: 4
    y: 4
    concentration: 1
```

The topology builder converts topology-specific parameters plus resolved link
settings into a canonical directed `TopologyGraph`.

## Supported Topologies

### `mesh2d`

Rectangular 2D mesh.

```yaml
topology:
  type: mesh2d
  params:
    x: 4
    y: 4
    concentration: 1
```

Parameters:

- `x`: number of routers in the X dimension. Required, positive integer.
- `y`: number of routers in the Y dimension. Required, positive integer.
- `concentration`: endpoints per router. Optional, positive integer, default `1`.

Router IDs are generated as:

```text
r.<x>.<y>
```

Examples:

```text
r.0.0
r.1.0
r.0.1
```

The current graph contains router nodes and inter-router links. Endpoint count is
stored in graph metadata as `terminal_count`.

## Mesh Link Classes

`mesh2d` supports link classes for heterogeneous settings:

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

Class meanings:

- `x`: links between `(x, y)` and `(x+1, y)`.
- `y`: links between `(x, y)` and `(x, y+1)`.

Pair overrides use coordinate endpoints:

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

The mesh builder validates that override coordinates are in bounds.

## Extending Topologies

New topology builders should follow the same YAML pattern:

```yaml
topology:
  type: <topology-name>
  params:
    <topology-specific-key>: <value>
```

Recommended implementation pattern:

1. Define a topology-specific params dataclass with `from_dict`.
2. Validate topology params and accepted link classes.
3. Build the canonical `TopologyGraph`.
4. Register the builder in `experiments/factory.py`.

Expected future examples:

```yaml
topology:
  type: fattree
  params:
    radix: 4
    levels: 3
```

```yaml
topology:
  type: torus2d
  params:
    x: 8
    y: 8
```

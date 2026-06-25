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

### `fattree`

Radix-split k-ary n-tree / Fat-tree.

```yaml
topology:
  type: fattree
  params:
    radix: 8
    levels: 4
```

Parameters:

- `radix`: router radix. Required, even integer greater than `1`.
- `levels`: number of switch/router levels. Required, integer at least `2`.

The builder uses `split = radix / 2`. For `radix: 8`, `split = 4`.

Generated size:

```text
terminal_count = split ^ levels
routers_per_level = split ^ (levels - 1)
router_count = levels * routers_per_level
```

For `radix: 8, levels: 4`, this gives:

```text
terminal_count = 4 ^ 4 = 256
routers_per_level = 4 ^ 3 = 64
router_count = 4 * 64 = 256
```

Router IDs are generated as:

```text
ft.l<level>.<coord...>
```

Examples:

```text
ft.l0.0.0.0
ft.l1.0.0.0
ft.l3.1.2.3
```

Level `0` routers are leaf routers. Terminals attach only to leaf routers; the
canonical graph stores this in metadata as `terminal_attachments`. This matters
for simulator lowering because routes only need destination entries for routers
that own terminals.

#### Fat-tree Link Classes

`fattree` supports these generic link classes:

```yaml
links:
  default:
    latency_cycles: 1
    bandwidth: 64GB/s
  classes:
    up:
      latency_cycles: 2
      bandwidth: 64GB/s
    down:
      latency_cycles: 1
      bandwidth: 64GB/s
```

It also supports per-level classes, where `level_<n>` is the lower endpoint
level of the inter-router link:

```yaml
links:
  default:
    latency_cycles: 1
    bandwidth: 64GB/s
  classes:
    level_0_up:
      latency_cycles: 2
      bandwidth: 64GB/s
    level_0_down:
      latency_cycles: 2
      bandwidth: 64GB/s
    level_1_up:
      latency_cycles: 4
      bandwidth: 128GB/s
```

Resolution still follows:

```text
pair override > class override > default
```

For Fat-tree pair overrides, use router ID string endpoints.

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

```yaml
topology:
  type: torus2d
  params:
    x: 8
    y: 8
```

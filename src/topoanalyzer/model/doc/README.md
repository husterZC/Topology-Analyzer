# Model YAML Concepts

The model package defines the canonical internal representation used by every
topology, routing algorithm, simulator backend, and benchmark. YAML is parsed
into these model objects before any simulator-specific lowering happens.

## System Object

A system is built from this YAML shape:

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

Internally this becomes:

```text
System
  name
  topology_type
  topology_params
  link_params
  graph
  routing_table
  metadata
```

The canonical graph is directed. Bidirectional physical links are represented as
two directed links.

## Link Parameters

`links.default` is required:

```yaml
links:
  default:
    latency_cycles: 2
    bandwidth: 64GB/s
```

Field meanings:

- `latency_cycles`: positive integer.
- `bandwidth`: string metadata such as `64GB/s`. The model stores this exactly; backends decide whether they can lower it.

Optional class-specific overrides:

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

For `mesh2d`, supported classes are:

- `x`: horizontal mesh links.
- `y`: vertical mesh links.

Optional pair overrides:

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

Override fields:

- `src`: endpoint coordinate for `mesh2d`, for example `[0, 0]`.
- `dst`: endpoint coordinate.
- `latency_cycles`: positive integer.
- `bandwidth`: string metadata.
- `directed`: optional boolean, default `false`.

Resolution order:

```text
pair override > class override > default
```

If `directed: false`, a pair override applies in both directions.

## Routing Table

Routing generators emit:

```text
RoutingTable
  name
  paths[(source, destination)] = [router ids...]
  route_vcs[(source, destination)] = vc
  entries = per-hop table entries
  metadata
```

Every route path must:

- start at its source router,
- end at its destination router,
- use only adjacent graph links,
- be present for every ordered source/destination pair.

`route_vcs` defaults to `0` for generators that do not explicitly use VC layers.

## Validation

`System.validate()` checks:

- graph has nodes,
- router graph is connected,
- every router pair has a route,
- every route uses valid adjacent links,
- the VC-aware channel dependency graph is acyclic.

The channel dependency graph uses `(src, dst, vc)` channels. This means cycles
in different VCs are independent, which is required for LASH-style layered
routing.

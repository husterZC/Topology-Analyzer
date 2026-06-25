# Routing YAML Settings

Routing YAML appears inside a system file under the `routing:` key.

```yaml
routing:
  type: mesh_xy
```

Routing generators consume the canonical topology graph and produce a routing
table. System validation then checks that all routes are valid and deadlock-free
under the VC-aware channel dependency graph.

## Supported Routing Types

### `mesh_xy`

Deterministic XY routing for `mesh2d`.

```yaml
routing:
  type: mesh_xy
```

Behavior:

1. Route in X dimension until destination X is reached.
2. Route in Y dimension until destination Y is reached.
3. Assign all routes to VC `0`.

Use this when:

- the topology is `mesh2d`,
- you want the usual research baseline for 2D mesh.

The default BookSim backend exports this as a table-driven `anynet` route table.
The optional `stock_mesh` backend maps it to:

```text
routing_function = dor;
```

### `graph_updown`

General graph-based up*/down* routing.

```yaml
routing:
  type: graph_updown
  root: r.0.0
```

Fields:

- `root`: optional router ID. If omitted, the lexicographically first router ID is used.

Behavior:

1. Build a BFS spanning tree from the root.
2. Route from source up toward the least common ancestor.
3. Route down toward the destination.
4. Assign all routes to VC `0`.

Why root exists:

- it orients the spanning tree,
- it changes route lengths and load balance,
- different roots can create different traffic concentration.

Strength:

- conservative, simple, topology-agnostic, deadlock-free.

Weakness:

- routes can be longer than shortest paths,
- traffic can concentrate near the root.

### `graph_lash`

LASH-style static graph routing with VC layers.

```yaml
routing:
  type: graph_lash
  max_vcs: 4
  candidate_paths: 8
```

Fields:

- `max_vcs`: maximum VC layers available to the route assignment. Optional, default `4`.
- `candidate_paths`: maximum candidate paths considered per source/destination. Optional, default `8`.

Behavior:

1. Enumerate simple candidate paths in nondecreasing hop count.
2. For each source/destination pair, try assigning a candidate path to VC layers.
3. Accept the first path/VC assignment whose channel dependency graph remains acyclic.
4. Fail if no candidate can be placed within `max_vcs`.

This is generally preferable to `graph_updown` as a general-topology static
routing baseline because it preserves shortest paths more often and uses VCs to
break dependency cycles.

Important notes:

- If the selected path set is already acyclic, `graph_lash` may use only one VC.
- `max_vcs` is a hard limit. If routing fails, increase `max_vcs` or `candidate_paths`.
- Benchmark `num_vcs` must be greater than the largest VC used by the generated table.
- Use the default BookSim `anynet_table` backend for direct simulation.

## Route Table Validation

All routing generators are validated through:

```text
route coverage
route adjacency
VC-aware channel dependency graph acyclicity
```

The channel identity is:

```text
(source_router, destination_router, vc)
```

This matters for layered routing because a dependency cycle in VC0 can be broken
by moving one route to VC1.

## Adding A New Routing Generator

Recommended YAML pattern:

```yaml
routing:
  type: <routing-name>
  <parameter>: <value>
```

Implementation checklist:

1. Implement `RoutingGenerator.generate(graph)`.
2. Emit `RoutingTable.add_path(..., vc=<layer>)`.
3. Add metadata documenting the algorithm and chosen parameters.
4. Run `channel_dependency_has_cycle(table)`.
5. Register the generator in `experiments/factory.py`.

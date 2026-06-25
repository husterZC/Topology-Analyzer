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

### `fattree_lca`

Topology-specific least-common-ancestor routing for `fattree`.

```yaml
routing:
  type: fattree_lca
```

Behavior:

1. Use Fat-tree link metadata to separate upward and downward channels.
2. Route from the current router upward to a nearest common ancestor.
3. Route downward to the destination leaf router.
4. Never route upward after taking a downward hop.
5. Assign all routes to VC `0`.

Fat-tree systems attach terminals only to leaf routers. Therefore
`fattree_lca` emits routes from every router to every terminal-attached leaf
router, not routes to every internal/root router. This matches BookSim terminal
destinations and avoids unnecessary root-to-root routes.

Use this when:

- the topology is `fattree`,
- you want a deterministic but intentionally simple topology-specific baseline,
- you want levels greater than 3 without relying on a root-oriented spanning tree.

Important limitation:

- equal-cost upward choices are resolved by router ordering, so this route can
  concentrate traffic badly in large Fat-trees. Prefer `fattree_nca_hash` for
  benchmark comparisons unless you explicitly want this baseline.

### `fattree_nca_hash`

Topology-specific nearest-common-ancestor routing for `fattree` with static
hashing across equal-cost upward links.

```yaml
routing:
  type: fattree_nca_hash
  seed: 0
```

Fields:

- `seed`: optional integer used by the stable hash. Default `0`.

Behavior:

1. Use Fat-tree link metadata to separate upward and downward channels.
2. For each destination terminal, route upward until the current router can
   reach the destination leaf with downward hops only.
3. Select each upward equal-cost parent with a stable hash of the current
   router, destination terminal ID, and `seed`.
4. Route downward to the destination leaf.
5. Never route upward after taking a downward hop.
6. Assign all routes to VC `0`.

The BookSim `anynet_table` exporter consumes the terminal-specific next-hop
metadata emitted by this generator:

```text
routing_table.metadata["terminal_next_hops"][current_router][destination_terminal]
```

This is necessary for Fat-tree path diversity because multiple terminals can
attach to the same leaf router. Router-to-router routes alone collapse those
terminals onto the same path.

Use this when:

- the topology is `fattree`,
- you want a balanced static routing baseline,
- you need levels greater than 3,
- you want a table-driven route that remains deterministic and repeatable.

This is not a true adaptive routing algorithm. It does not inspect runtime
queue occupancy or credits. For an ANCA-style experiment, add a BookSim runtime
routing function that chooses among upward ports dynamically and use that as a
separate backend mode.

### `fattree_dmodk`

Deterministic D-mod-k-style modulo routing for `fattree`.

```yaml
routing:
  type: fattree_dmodk
```

Behavior:

1. Use nearest-common-ancestor up/down routing.
2. On each upward hop at level `l`, choose the parent with:

```text
floor(destination_terminal / split^l) mod available_parent_count
```

3. Route downward once the destination leaf can be reached with downward hops.
4. Assign all routes to VC `0`.

Use this when:

- you want a deterministic static modulo baseline,
- you want repeatable table-driven results without hashing,
- you are comparing against ECMP-style `fattree_nca_hash`.

### `fattree_dmodc`

Dmodc-style availability-aware modulo routing for `fattree`.

```yaml
routing:
  type: fattree_dmodc
  disabled_links:
    - ft.l0.0.0.0->ft.l1.0.0.0
    - src: ft.l0.0.0.1
      dst: ft.l1.0.0.1
```

Fields:

- `disabled_links`: optional list of directed router links that the route table
  must avoid. Entries can be `src->dst` strings or `{src, dst}` mappings.

Behavior:

1. Use nearest-common-ancestor up/down routing.
2. Filter disabled directed links out of the routing graph.
3. On each upward hop, choose among currently viable parents with the same
   level-aware modulo rule as `fattree_dmodk`.
4. Continue upward if a covering router has no viable downward path because of
   disabled links.
5. Fail during route generation if strict up/down routing cannot reach a
   required terminal without a disabled link.

This is a Dmodc-style baseline for the regular Fat-tree model in this repo, not
a complete implementation of every PGFT rerouting rule from the Dmodc papers.
It is useful for static fault-avoidance experiments where the remaining up/down
graph is still routable.

### `fattree_anca`

BookSim runtime adaptive nearest-common-ancestor routing for `fattree`.

```yaml
routing:
  type: fattree_anca
```

This routing type validates the Topology-Analyzer Fat-tree system but is not
lowered through `anynet.routes`. To simulate true adaptive routing, use:

```yaml
booksim:
  backend: auto
```

or:

```yaml
booksim:
  backend: stock_fattree
```

The generated BookSim config uses:

```text
topology = fattree;
k = radix / 2;
n = levels;
routing_function = anca;
```

Use this when:

- you want runtime credit-aware/adaptive BookSim routing,
- homogeneous 1-cycle links are acceptable,
- you do not need the custom anynet table backend for this system.

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

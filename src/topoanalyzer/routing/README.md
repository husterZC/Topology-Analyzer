# Routing Algorithms

Routing YAML appears inside a system file under the `routing:` key.

```yaml
routing:
  type: mesh_xy
```

Routing generators consume the canonical topology graph and produce a routing
table. System validation checks route coverage, route adjacency, and deadlock
freedom through the VC-aware channel dependency graph.

## Topology Support Matrix

| Topology | Supported Routing Types | Short Description |
|---|---|---|
| `mesh2d` | `mesh_xy` | Deterministic XY dimension-order baseline. |
| `mesh2d` and most connected graphs | `graph_updown`, `graph_lash` | Topology-agnostic graph routing baselines. |
| `mesh3d` | `mesh_xyz` | Deterministic XYZ dimension-order baseline. |
| `mesh3d` and most connected graphs | `graph_updown`, `graph_lash` | Topology-agnostic graph routing baselines. |
| `torus2d` | `torus_xy` | Conservative table-compatible XY routing; wrap links are modeled but not used. |
| `torus2d` and most connected graphs | `graph_updown`, `graph_lash` | Topology-agnostic graph routing baselines. |
| `torus3d` | `torus_xyz` | Conservative table-compatible XYZ routing; wrap links are modeled but not used. |
| `torus3d` and most connected graphs | `graph_updown`, `graph_lash` | Topology-agnostic graph routing baselines. |
| `ruche3d` | `ruche_xyz` | Dimension-order routing that uses stride-length ruche express links. |
| `ruche3d` | `ruche_lash` | Short-path graph routing over mesh and ruche links with VC assignment. |
| `ruche3d` | `ruche_valiant_hash` | Static Valiant-style hashed intermediate routing. |
| `ruche3d` and most connected graphs | `graph_updown`, `graph_lash` | Generic graph baselines; `ruche_lash` is the topology-specific wrapper. |
| `hypercube` | `hypercube_ecube` | Deterministic E-cube bit-order routing. |
| `hypercube` | `hypercube_lash` | Minimal path-diversity routing with LASH-style VC assignment. |
| `hypercube` | `hypercube_valiant_hash` | Static Valiant-style hashed intermediate routing. |
| `hypercube` and most connected graphs | `graph_updown`, `graph_lash` | Topology-agnostic graph routing baselines. |
| `dragonfly` | `dragonfly_min` | Minimal local/global/local routing with VC phase split. |
| `dragonfly` | `dragonfly_valiant_hash` | Static VALg-style hashed intermediate-group routing. |
| `dragonfly` and most connected graphs | `graph_updown`, `graph_lash` | Generic graph baselines; runtime UGAL/PAR are not table routes. |
| `fattree` | `fattree_lca` | Simple deterministic nearest-common-ancestor baseline. |
| `fattree` | `fattree_nca_hash` | Balanced static ECMP-style nearest-common-ancestor baseline. |
| `fattree` | `fattree_dmodk` | Deterministic D-mod-k-style modulo baseline. |
| `fattree` | `fattree_dmodc` | Availability-aware Dmodc-style modulo baseline. |
| `fattree` | `fattree_anca` | BookSim runtime adaptive ANCA; not exported as static `anynet.routes`. |
| `fattree` and most connected graphs | `graph_updown`, `graph_lash` | Generic graph baselines when topology-specific routes are not desired. |

## Routing Algorithm Details

<details>
<summary><code>mesh_xy</code>: deterministic XY routing for <code>mesh2d</code></summary>

```yaml
routing:
  type: mesh_xy
```

Behavior:

1. Route in X until destination X is reached.
2. Route in Y until destination Y is reached.
3. Assign all route channels to VC `0`.

Use this as the standard 2D mesh baseline. The optional `stock_mesh` BookSim
backend lowers this to `routing_function = dor` for square homogeneous meshes.

</details>

<details>
<summary><code>mesh_xyz</code>: deterministic XYZ routing for <code>mesh3d</code></summary>

```yaml
routing:
  type: mesh_xyz
```

Behavior:

1. Route in X.
2. Route in Y.
3. Route in Z.
4. Assign all route channels to VC `0`.

</details>

<details>
<summary><code>torus_xy</code> and <code>torus_xyz</code>: conservative torus baselines</summary>

```yaml
routing:
  type: torus_xy
```

```yaml
routing:
  type: torus_xyz
```

The graph contains wrap links, but these static table-compatible baselines route
without using them. True minimal torus routing with dateline VCs needs runtime
state, because a router must know whether a packet has crossed the dateline.

Use these as conservative topology baselines until a dedicated BookSim runtime
torus backend is added.

</details>

<details>
<summary><code>ruche_xyz</code>: express-link dimension-order routing for <code>ruche3d</code></summary>

```yaml
routing:
  type: ruche_xyz
```

Behavior:

1. Route X, then Y, then Z.
2. Use a `ruche_<axis>` express link when the remaining distance in that axis is
   at least the configured stride.
3. Use base mesh links for the final remainder.
4. Assign all route channels to VC `0`.

This generator targets non-wrap `ruche3d`.

</details>

<details>
<summary><code>ruche_lash</code>: graph shortest-path VC routing for <code>ruche3d</code></summary>

```yaml
routing:
  type: ruche_lash
  max_vcs: 8
  candidate_paths: 8
```

Behavior:

1. Treat base mesh links and ruche express links as graph edges.
2. Enumerate short candidate paths.
3. Assign each route to the first VC layer that keeps the channel dependency
   graph acyclic.

Use this when express links should be selected by graph path quality rather than
strict XYZ dimension order.

</details>

<details>
<summary><code>ruche_valiant_hash</code>: static Valiant-style routing for <code>ruche3d</code></summary>

```yaml
routing:
  type: ruche_valiant_hash
  seed: 0
```

Behavior:

1. Select a deterministic hashed intermediate router.
2. Route source-to-intermediate with `ruche_xyz` on VC `0`.
3. Route intermediate-to-destination with `ruche_xyz` on VC `1`.
4. Fall back to direct `ruche_xyz` if no simple intermediate path is suitable.

This is static and repeatable; it is not per-packet randomized Valiant routing.

</details>

<details>
<summary><code>hypercube_ecube</code>: deterministic E-cube routing for <code>hypercube</code></summary>

```yaml
routing:
  type: hypercube_ecube
```

Behavior:

1. Compute `source XOR destination`.
2. Flip differing bits in least-significant-bit-first order.
3. Assign all route channels to VC `0`.

This is the usual deterministic dimension-order baseline for binary hypercubes.

</details>

<details>
<summary><code>hypercube_lash</code>: minimal path-diversity routing for <code>hypercube</code></summary>

```yaml
routing:
  type: hypercube_lash
  max_vcs: 4
  candidate_paths: 8
  seed: 0
```

Behavior:

1. Generate several minimal bit-flip orders.
2. Include deterministic and hashed bit orders.
3. Assign the first candidate that keeps the channel dependency graph acyclic
   within the configured VC budget.

This is a static approximation of minimal adaptive hypercube routing.

</details>

<details>
<summary><code>hypercube_valiant_hash</code>: static Valiant-style routing for <code>hypercube</code></summary>

```yaml
routing:
  type: hypercube_valiant_hash
  seed: 0
```

Behavior:

1. Select a deterministic hashed intermediate router.
2. Route source-to-intermediate with E-cube on VC `0`.
3. Route intermediate-to-destination with E-cube on VC `1`.
4. Avoid static paths that pass through the final destination before completion.

</details>

<details>
<summary><code>dragonfly_min</code>: minimal routing for <code>dragonfly</code></summary>

```yaml
routing:
  type: dragonfly_min
```

Behavior:

1. If source and destination are in the same group, route over the local link.
2. Otherwise route local-to-global-gateway, take one global link, then route
   locally inside the destination group.
3. Use VC `0` before and through the global hop.
4. Use VC `1` for destination-group local hops.

Benchmarks should use at least `num_vcs: 2`.

</details>

<details>
<summary><code>dragonfly_valiant_hash</code>: static VALg-style routing for <code>dragonfly</code></summary>

```yaml
routing:
  type: dragonfly_valiant_hash
  seed: 0
  nonminimal_same_group: false
```

Behavior:

1. Pick a hashed intermediate group that is neither source group nor destination
   group.
2. Route to that group, then route from it to the destination group.
3. Use four VC phases:
   - VC `0`: source-group local hop and first global hop.
   - VC `1`: intermediate-group local hop.
   - VC `2`: second global hop.
   - VC `3`: destination-group local hop.

Benchmarks using this static route table need at least:

```yaml
benchmark:
  num_vcs: 4
```

True UGAL, PAR, and far-end-congestion-aware Dragonfly algorithms need runtime
queue/credit state and should be implemented as BookSim runtime routing
backends.

</details>

<details>
<summary><code>fattree_lca</code>: deterministic nearest-common-ancestor routing</summary>

```yaml
routing:
  type: fattree_lca
```

Behavior:

1. Route upward to a nearest common ancestor.
2. Route downward to the destination leaf router.
3. Never route upward after taking a downward hop.
4. Assign all route channels to VC `0`.

This is intentionally simple and can concentrate traffic. Prefer
`fattree_nca_hash` for balanced static Fat-tree benchmarks.

</details>

<details>
<summary><code>fattree_nca_hash</code>: balanced static NCA routing for <code>fattree</code></summary>

```yaml
routing:
  type: fattree_nca_hash
  seed: 0
```

Behavior:

1. Route upward only until the current router can reach the destination leaf by
   downward hops.
2. Select equal-cost upward parents with a stable hash.
3. Route downward to the destination leaf.
4. Emit terminal-specific next-hop metadata so multiple terminals attached to
   the same leaf can still use different paths.

</details>

<details>
<summary><code>fattree_dmodk</code>: deterministic D-mod-k-style routing</summary>

```yaml
routing:
  type: fattree_dmodk
```

On each upward hop at level `l`, choose the parent with:

```text
floor(destination_terminal / split^l) mod available_parent_count
```

Use this as a deterministic modulo baseline against `fattree_nca_hash`.

</details>

<details>
<summary><code>fattree_dmodc</code>: availability-aware Dmodc-style routing</summary>

```yaml
routing:
  type: fattree_dmodc
  disabled_links:
    - ft.l0.0.0.0->ft.l1.0.0.0
```

Behavior:

1. Filter disabled directed links out of the route search.
2. Use the D-mod-k-style modulo rule among currently viable parents.
3. Fail route generation if strict up/down routing cannot reach a required
   terminal without a disabled link.

This is a Dmodc-style baseline for the regular Fat-tree model in this repo, not
a complete PGFT rerouting implementation.

</details>

<details>
<summary><code>fattree_anca</code>: BookSim runtime adaptive ANCA routing</summary>

```yaml
routing:
  type: fattree_anca
```

This routing type validates the Topology-Analyzer Fat-tree system but is not
lowered through `anynet.routes`. Use:

```yaml
booksim:
  backend: auto
```

The generated BookSim config uses native Fat-tree routing:

```text
topology = fattree;
k = radix / 2;
n = levels;
routing_function = anca;
```

</details>

<details>
<summary><code>graph_updown</code>: topology-agnostic up*/down* routing</summary>

```yaml
routing:
  type: graph_updown
  root: r.0.0
```

Behavior:

1. Build a BFS spanning tree from the root.
2. Route from source up toward the least common ancestor.
3. Route down toward the destination.
4. Assign all route channels to VC `0`.

This is conservative and deadlock-free, but can produce longer routes and
traffic concentration near the root.

</details>

<details>
<summary><code>graph_lash</code>: topology-agnostic short-path VC routing</summary>

```yaml
routing:
  type: graph_lash
  max_vcs: 4
  candidate_paths: 8
```

Behavior:

1. Enumerate short/simple candidate paths.
2. Assign each route to the first VC layer whose channel dependency graph
   remains acyclic.

Use this as a general graph-based baseline when a topology-specific routing
algorithm is not available or when heterogeneous/faulted links need graph-level
analysis.

</details>

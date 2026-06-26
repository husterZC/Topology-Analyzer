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

## Formula Conventions

These formulas describe the graph models implemented in this repository.

- `c`: concentration, endpoints per router.
- `b`: homogeneous one-way bandwidth of one bidirectional link pair.
- `b_x`, `b_y`, `b_z`: one-way bandwidth for links in each dimension.
- `R`: router count.
- `N`: terminal/end-node count represented by graph metadata.
- For SlimNoC formulas, `q` is the finite-field order and `p` is
  concentration/endpoints per router.
- For Dragonfly formulas, `p` is terminals per router, `a` is routers per
  group, `h` is global links per router, and `g` is group count. In YAML, `g`
  is configured with the `groups` field.
- For UBMesh formulas, `dimensions=[L_0,...,L_{d-1}]` describes the
  nD-FullMesh core and `b_i` is one-way bandwidth for dimension `i`.
- For LLN formulas, `L` is cache-layer count, `T=L+1` is total layer count,
  `G=x*y` is routers per layer, and `M=(x-1)*y+x*(y-1)` is the 2D mesh edge
  count per layer. `p_v` is the modeled number of vertical pillars per router.
- Diameter is router-hop diameter. Terminal injection/ejection hops are not
  modeled as graph links.
- Bisection bandwidth is the minimum one-way aggregate bandwidth across any
  balanced router bisection. For heterogeneous links, use the bandwidth class
  in the formula.

## Max Nodes

| Topology | Parameters | Router Count `R` | Terminal Nodes `N` |
|---|---:|---:|---:|
| `mesh2d` | `x`, `y`, `c` | `x*y` | `c*x*y` |
| `mesh3d` | `x`, `y`, `z`, `c` | `x*y*z` | `c*x*y*z` |
| `torus2d` | `x`, `y`, `c` | `x*y` | `c*x*y` |
| `torus3d` | `x`, `y`, `z`, `c` | `x*y*z` | `c*x*y*z` |
| `ruche3d` | `x`, `y`, `z`, `c` | `x*y*z` | `c*x*y*z` |
| `hypercube` | `dimension=d`, `c` | `2^d` | `c*2^d` |
| `dragonfly` | `p`, `a`, `h`, `g` | `g*a` | `g*a*p` |
| `dragonfly` default max | `g=a*h+1` | `a*(a*h+1)` | `a*p*(a*h+1)` |
| `slimnoc` | `q`, `p` | `2*q^2` | `2*q^2*p` |
| `ubmesh` | `dimensions=[L_i]`, `c` | `prod_i L_i` | `c*prod_i L_i` |
| `lln` | `x`, `y`, `T`, `c` | `x*y*T` | `c*x*y*T` |
| `fattree` | `radix=r`, `levels=L`, `s=r/2` | `L*s^(L-1)` | `s^L` |

For topologies with explicit dimensions, the implementation has no fixed
mathematical maximum beyond memory/runtime limits and validation constraints.

## Diameter

| Topology | Router-Hop Diameter |
|---|---:|
| `mesh2d` | `(x-1) + (y-1)` |
| `mesh3d` | `(x-1) + (y-1) + (z-1)` |
| `torus2d` | `floor(x/2) + floor(y/2)` |
| `torus3d` | `floor(x/2) + floor(y/2) + floor(z/2)` |
| `ruche3d` non-wrap | `sum_A floor((L_A-1)/s_A) + ((L_A-1) mod s_A)` for `A in {x,y,z}` |
| `hypercube` | `d` |
| `dragonfly` full default | `3` for cross-group worst case |
| `slimnoc` | `2` |
| `ubmesh` | `count_i(L_i > 1)` |
| `lln` full coverage | `3` |
| `lln` partial coverage | `<= (x-1)+(y-1)+2` |
| `fattree` | `2*(L-1)` between leaf routers |

For `ruche3d`, `L_A` is the dimension length and `s_A` is the ruche stride in
axis `A`. Wrap-ruche diameter depends on the wrap routing policy; the current
table-driven `ruche_xyz` and `ruche_valiant_hash` generators support non-wrap
ruche systems.

## Bisection Bandwidth

| Topology | Minimum One-Way Bisection Bandwidth |
|---|---:|
| `mesh2d` | `min(y*b_x, x*b_y)` |
| `mesh3d` | `min(y*z*b_x, x*z*b_y, x*y*b_z)` |
| `torus2d` | `min(2*y*b_x, 2*x*b_y)` |
| `torus3d` | `min(2*y*z*b_x, 2*x*z*b_y, 2*x*y*b_z)` |
| `ruche3d` non-wrap | `min_A P_A * (b_A + E(L_A,s_A,m_A)*b_ruche_A)` |
| `hypercube` | `2^(d-1)*b` |
| `dragonfly` group-level | `floor(g^2/4)*b_global` |
| `slimnoc` exact graph cut | `b * min_{size(S)=q^2} cut_edges(S)` |
| `ubmesh` dimension-aligned min-bisection | `min_i (R/L_i)*floor(L_i/2)*ceil(L_i/2)*b_i` |
| `lln` full projected clique estimate | `min(floor(G^2/4)*b_long, G*p_v*b_vertical)` |
| `fattree` ideal full bisection | `floor(N/2)*b` |

For the `ruche3d` formula:

- `P_x=y*z`, `P_y=x*z`, and `P_z=x*y`.
- `m_A=floor(L_A/2)` is the bisection cut position in axis `A`.
- `E(L,s,m)` is the number of stride-`s` ruche links crossing that cut per line:

```text
E(L,s,m) = max(0, min(m-1, L-s-1) - max(0, m-s) + 1)
```

Dragonfly bisection is shown at group granularity for the default full
one-link-per-group-pair arrangement. Exact router-level bisection can vary with
terminal partitioning and global-link placement.

SlimNoC exact bisection is stated as the graph min-bisection. For the natural
group-level SlimNoC cut, every pair of groups contributes `2*(q-1)` links, so
the group-cut capacity is `2*(q-1)*floor(q/2)*ceil(q/2)*b`.

Fat-tree bisection assumes a regular full-bisection Fat-tree with homogeneous
link bandwidth. With per-level link bandwidths, the bisection is limited by the
minimum aggregate capacity of the cut level.

## Topology Details

<details>
<summary><code>mesh2d</code>: rectangular 2D mesh</summary>

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

Router IDs:

```text
r.<x>.<y>
```

Link classes:

- `x`: links between `(x, y)` and `(x+1, y)`.
- `y`: links between `(x, y)` and `(x, y+1)`.

Pair overrides use 2D coordinate endpoints:

```yaml
links:
  overrides:
    - src: [0, 0]
      dst: [1, 0]
      latency_cycles: 7
      bandwidth: 8GB/s
```

</details>

<details>
<summary><code>mesh3d</code>: rectangular 3D mesh</summary>

```yaml
topology:
  type: mesh3d
  params:
    x: 4
    y: 4
    z: 2
    concentration: 1
```

Parameters:

- `x`, `y`, `z`: routers in each dimension. Required, positive integers.
- `concentration`: endpoints per router. Optional, positive integer, default `1`.

Router IDs:

```text
r3.<x>.<y>.<z>
```

Link classes:

- `x`: links between `(x, y, z)` and `(x+1, y, z)`.
- `y`: links between `(x, y, z)` and `(x, y+1, z)`.
- `z`: links between `(x, y, z)` and `(x, y, z+1)`.

Pair overrides use 3D coordinate endpoints, for example `src: [0, 0, 0]`.

</details>

<details>
<summary><code>torus2d</code>: 2D torus with wraparound links</summary>

```yaml
topology:
  type: torus2d
  params:
    x: 4
    y: 4
    concentration: 1
```

Parameters:

- `x`, `y`: routers in each dimension. Required, integers at least `3`.
- `concentration`: endpoints per router. Optional, positive integer, default `1`.

Router IDs:

```text
t2.<x>.<y>
```

Link classes:

- `x`, `y`: non-wrap nearest-neighbor links.
- `x_wrap`, `y_wrap`: links connecting opposite edges.

The builder requires each dimension to be at least `3` because this graph model
does not represent parallel links cleanly. A 2-node torus dimension would need
parallel channels between the same router pair.

</details>

<details>
<summary><code>torus3d</code>: 3D torus with wraparound links</summary>

```yaml
topology:
  type: torus3d
  params:
    x: 3
    y: 3
    z: 3
    concentration: 1
```

Parameters:

- `x`, `y`, `z`: routers in each dimension. Required, integers at least `3`.
- `concentration`: endpoints per router. Optional, positive integer, default `1`.

Router IDs:

```text
t3.<x>.<y>.<z>
```

Link classes:

- `x`, `y`, `z`: non-wrap nearest-neighbor links.
- `x_wrap`, `y_wrap`, `z_wrap`: links connecting opposite faces.

</details>

<details>
<summary><code>ruche3d</code>: 3D mesh plus long-range express links</summary>

```yaml
topology:
  type: ruche3d
  params:
    x: 4
    y: 4
    z: 4
    stride: 2
    concentration: 1
```

Parameters:

- `x`, `y`, `z`: routers in each dimension. Required, positive integers.
- `stride`: default ruche stride for all dimensions. Optional, default `2`.
- `stride_x`, `stride_y`, `stride_z`: per-axis stride overrides. Optional.
- `wrap`: whether ruche links wrap around the dimension. Optional, default `false`.
- `concentration`: endpoints per router. Optional, positive integer, default `1`.

Router IDs:

```text
ru3.<x>.<y>.<z>
```

Link classes:

- `x`, `y`, `z`: base 3D mesh links.
- `ruche_x`, `ruche_y`, `ruche_z`: express links with the configured stride.

The current `ruche_xyz`, `ruche_lash`, and `ruche_valiant_hash` routing
generators are intended for non-wrap ruche systems. Wrap ruche topologies can be
modeled, but need a routing generator with runtime state or graph-routing logic
that can be exported safely.

</details>

<details>
<summary><code>hypercube</code>: binary hypercube</summary>

```yaml
topology:
  type: hypercube
  params:
    dimension: 4
    concentration: 1
```

Parameters:

- `dimension`: cube dimension `d`; router count is `2^d`. Required, positive integer.
- `concentration`: endpoints per router. Optional, positive integer, default `1`.

Router IDs:

```text
hc.<value>
```

Link classes:

- `cube`: generic hypercube links.
- `dim_<n>`: links for bit dimension `n`, for example `dim_0`.

Pair overrides use router ID string endpoints, for example `hc.0`.

</details>

<details>
<summary><code>dragonfly</code>: all-to-all local-group Dragonfly</summary>

```yaml
topology:
  type: dragonfly
  params:
    p: 2
    a: 4
    h: 2
    groups: 9
```

Parameters:

| Symbol | YAML field | Meaning | Constraint |
|---|---|---|---|
| `p` | `p` | Concentration: terminal/end nodes attached to each router. | Positive integer. |
| `a` | `a` | Routers per group. Each group is modeled as an all-to-all local clique of `a` routers. | Integer greater than `1`. |
| `h` | `h` | Global links per router. A group therefore has `a*h` global ports. | Positive integer. |
| `g` | `groups` | Number of Dragonfly groups. | Optional; defaults to `a*h + 1`. Must satisfy `g - 1 <= a*h`. |

The default `groups = a*h + 1` is the fully populated Dragonfly case: every
group can connect to every other group using exactly one inter-group link,
because each group has `a*h` global ports and needs `g - 1` peer-group links.
You can set a smaller `groups` value to model a partially populated Dragonfly.

The implemented router and terminal counts are:

```text
routers R = g * a
terminals N = g * a * p
```

Generated router radix metadata:

```text
radix = p + h + a - 1
```

Router IDs:

```text
df.g<group>.r<router>
```

Link classes:

- `local`: all-to-all links inside each group.
- `global`: one inter-group link for each group pair in the default full Dragonfly.

Pair overrides use router ID string endpoints.

</details>

<details>
<summary><code>slimnoc</code>: SlimNoC / MMS diameter-2 graph</summary>

```yaml
topology:
  type: slimnoc
  params:
    q: 5
    concentration: 4
    layout: subgroup
```

Parameters:

| Symbol | YAML field | Meaning | Constraint |
|---|---|---|---|
| `q` | `q` | Finite-field order controlling the MMS/SlimNoC router graph. | Prime power with `q = 4w + delta`, `delta in {-1, 0, 1}`. The current builder covers the paper's `q=5`, `q=8`, and `q=9` systems. |
| `p` | `concentration` or `p` | Terminal/end nodes attached to each router. | Positive integer. |
| - | `layout` | Metadata-only placement hint: `group`, `paper_figure7b`, `subgroup`, or `basic`. | Optional, default `group`. |

Derived values:

```text
delta in {-1, 0, 1}, where q = 4*w + delta
network radix k' = (3*q - delta) / 2
router radix k = k' + p
routers R = 2*q^2
terminals N = 2*q^2*p
diameter D = 2
```

The builder constructs finite-field arithmetic for `F_q`. Prime `q` uses
ordinary modular arithmetic; non-prime prime powers such as `q=9` use a
polynomial field representation, so the generated graph is not the incorrect
integer-modulo-9 graph.

Paper-scale examples:

- `q=5`, `p=4`: `R=50`, `N=200`, `k'=7`.
- `q=8`, `p=8`: `R=128`, `N=1024`, `k'=12`.
- `q=9`, `p=8`: `R=162`, `N=1296`, `k'=13`.

The Figure 7(b) SN-L system is modeled by:

```yaml
topology:
  type: slimnoc
  params:
    q: 9
    concentration: 8
    layout: paper_figure7b
```

The paper omits the inter-group wires in Figure 7(b). In the implemented full
graph, those omitted wires are the `cross` links where the source group and
target group differ. More concretely, each router `sn.g0.a<a>.b<b>` connects to
one router in every type-1 subgroup `m`:

```text
sn.g0.a<a>.b<b> <-> sn.g1.a<m>.b<c>, where c = b - m*a in F_q
```

When `m == a`, this is a local cross link inside one displayed group. When
`m != a`, this is an inter-group cross link.

Router IDs:

```text
sn.g<subgroup_type>.a<subgroup>.b<position>
```

These correspond to the paper label `[G | a, b]`, using zero-based field
element IDs.

Link classes:

- `intra_0`: links inside subgroup type `0`, using generator set `X`.
- `intra_1`: links inside subgroup type `1`, using generator set `X'`.
- `cross`: links between subgroup types, generated by `c = b - m*a`.

Pair overrides use router ID string endpoints.

<pre>Reference used: SlimNoC paper, arXiv <font color="#06989A">2010.10683</font>: https://arxiv.org/pdf/2010.10683</pre>

</details>

<details>
<summary><code>ubmesh</code>: nD-FullMesh / UBMesh core</summary>

```yaml
topology:
  type: ubmesh
  params:
    dimensions: [8, 8, 4, 4]
    dimension_names: [x, y, z, a]
    concentration: 1
```

Parameters:

- `dimensions`: number of routers along each nD-FullMesh dimension. Required,
  non-empty list of positive integers.
- `dimension_names`: optional names for dimensions. If present, the length must
  match `dimensions`.
- `concentration`: endpoints per router. Optional, positive integer, default `1`.

Connectivity:

Routers are coordinate tuples. Two routers are adjacent when they differ in
exactly one coordinate, and the edge can jump directly to any other value in
that dimension. This is the UBMesh paper's localized nD-FullMesh core, which is
also a Hamming/HyperX-style product of complete graphs.

Derived values:

```text
routers R = prod_i L_i
terminals N = c * prod_i L_i
network radix k' = sum_i (L_i - 1)
router radix k = k' + c
diameter D = count_i(L_i > 1)
```

Paper-scale examples:

- Intra-rack 2D-FullMesh `dimensions=[8,8]`: `R=64`, `k'=14`, `D=2`.
- UBMesh-Pod 4D-FullMesh `dimensions=[8,8,4,4]`: `R=1024`, `k'=20`, `D=4`.

Router IDs:

```text
ub.<coord0>.<coord1>...
```

Link classes:

- `dim_<n>`: generic per-dimension class, for example `dim_0`.
- A matching `dimension_names` entry can also be used as a class name, for
  example `x`, `y`, `z`, or `a`.

Pair overrides can use coordinate endpoints:

```yaml
links:
  overrides:
    - src: [0, 0, 0, 0]
      dst: [7, 0, 0, 0]
      latency_cycles: 3
      bandwidth: 32GB/s
```

or router ID endpoints such as `ub.0.0.0.0`.

<pre>Reference used: UBMesh paper, arXiv <font color="#06989A">2503.20377</font>: https://arxiv.org/pdf/2503.20377</pre>

</details>

<details>
<summary><code>lln</code>: low-radix low-diameter 3D long-link network</summary>

```yaml
topology:
  type: lln
  params:
    x: 4
    y: 4
    layers: 5
    concentration: 1
    horizontal_ports: 4
    vertical_pillars: 4
    min_long_hops: 2
    coverage: full_clique
```

Parameters:

- `x`, `y`: routers in the projected 2D grid. Required, integers at least `2`.
- `layers`: total 3D layers, including core layer `0`. Required unless using
  `cache_layers`, which is interpreted as `layers = cache_layers + 1`.
- `concentration`: endpoints per router. Optional, positive integer, default
  `1`.
- `horizontal_ports`: maximum long-link degree per router in one cache layer.
  Optional, default `4`, matching the paper's low-radix target.
- `vertical_pillars`: modeled number of vertical pillar bundles per router.
  Optional, default `4`. The current graph uses one abstract vertical edge
  between layer pairs and records the pillar count in metadata/formulas.
- `min_long_hops`: minimum projected Manhattan distance for a long link.
  Optional, default `2`; 1-hop pairs are handled by the core mesh.
- `coverage`: `full_clique` or `partial_greedy`. `full_clique` requires every
  non-mesh projected pair to be placed in one cache layer.

Connectivity:

Layer `0` preserves a normal 2D mesh. Cache layers contain deterministic greedy
placements of long projected links. Each `(x,y)` vertical column has one-hop
abstract vertical connectivity between every layer, matching the paper's
one-hop pillar assumption. The projected long links slice a clique across cache
layers while respecting per-layer mesh-equivalent link count and per-router
horizontal port budget.

Parameter constraints:

```text
x >= 2
y >= 2
layers >= 2
cache_layers = layers - 1
G = x*y
M = (x-1)*y + x*(y-1)
K = G*(G-1)/2
required_long_edges = K - M
```

For `coverage: full_clique`, the cache layers must be enough to place every
non-mesh projected pair as a long link:

```text
cache_layers >= ceil(required_long_edges / M)
layers >= 1 + ceil((K - M) / M)
```

This is a necessary lower bound. The implementation also enforces the
per-router `horizontal_ports` budget during deterministic greedy placement, so
some sizes may need more layers than the lower bound. Use `coverage:
full_clique` when insufficient layers should be rejected. Use `coverage:
partial_greedy` when missing long links are acceptable and should be routed
through the preserved core mesh.

For a square `k x k` LLN with `horizontal_ports=4` and `min_long_hops=2`, the
paper's lower bound for full coverage is:

```text
cache_layers_min = ceil(k*(k+1)/4 - 1)
total_layers_min = cache_layers_min + 1
```

Examples:

- `4x4`: `cache_layers_min=4`, so `layers=5`.
- `5x5`: `cache_layers_min=7`, so `layers=8`.
- `6x6`: `cache_layers_min=10`, so `layers=11`.

For a non-concentrated `16x16` router grid, full coverage needs about `69`
total layers with the repository's greedy placement. That is usually too large
for practical experiments. The example
`examples/systems/lln/table/lln_16x16term_c4_8x8x19_table.yaml` follows the
paper's CMesh scaling idea instead: an `8x8` router grid with
`concentration=4` represents `16x16` terminals per layer and uses `layers=19`
for full greedy coverage.

Router IDs:

```text
lln.<x>.<y>.<layer>
```

Link classes:

- `core_x`, `core_y`: core-layer mesh links.
- `long`: cache-layer long links.
- `vertical`: one-hop vertical pillar links.

Pair overrides use 3D coordinate endpoints such as `src: [0, 0, 0]`.

<pre>Reference used: A low-radix and low-diameter 3D interconnection network design, IEEE document <font color="#06989A">4798234</font>: https://ieeexplore.ieee.org/document/4798234</pre>

</details>

<details>
<summary><code>fattree</code>: radix-split k-ary n-tree / Fat-tree</summary>

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

Router IDs:

```text
ft.l<level>.<coord...>
```

Level `0` routers are leaf routers. Terminals attach only to leaf routers; the
canonical graph stores this in metadata as `terminal_attachments`.

Generic link classes:

- `up`: lower-level router to upper-level router.
- `down`: upper-level router to lower-level router.

Per-level classes are also supported, where `level_<n>` is the lower endpoint
level of the inter-router link:

```yaml
links:
  classes:
    level_0_up:
      latency_cycles: 2
      bandwidth: 64GB/s
    level_0_down:
      latency_cycles: 2
      bandwidth: 64GB/s
```

Pair overrides use router ID string endpoints.

</details>

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

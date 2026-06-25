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
- Diameter is router-hop diameter. Terminal injection/ejection hops are not
  modeled as graph links.
- Bisection bandwidth is one-way aggregate bandwidth across a balanced router
  bisection. For heterogeneous links, use the bandwidth class in the formula.

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
| `fattree` | `2*(L-1)` between leaf routers |

For `ruche3d`, `L_A` is the dimension length and `s_A` is the ruche stride in
axis `A`. Wrap-ruche diameter depends on the wrap routing policy; the current
table-driven `ruche_xyz` and `ruche_valiant_hash` generators support non-wrap
ruche systems.

## Bisection Bandwidth

| Topology | One-Way Bisection Bandwidth |
|---|---:|
| `mesh2d` | `min(y*b_x, x*b_y)` |
| `mesh3d` | `min(y*z*b_x, x*z*b_y, x*y*b_z)` |
| `torus2d` | `min(2*y*b_x, 2*x*b_y)` |
| `torus3d` | `min(2*y*z*b_x, 2*x*z*b_y, 2*x*y*b_z)` |
| `ruche3d` non-wrap | `min_A P_A * (b_A + E(L_A,s_A,m_A)*b_ruche_A)` |
| `hypercube` | `2^(d-1)*b` |
| `dragonfly` group-level | `floor(g^2/4)*b_global` |
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

- `p`: terminals per router. Required, positive integer.
- `a`: routers per group. Required, integer greater than `1`.
- `h`: global links per router. Required, positive integer.
- `groups`: number of groups. Optional, default `a*h + 1`.

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

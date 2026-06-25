# BookSim YAML Settings

BookSim settings appear at the top level of a benchmark YAML file.

```yaml
booksim:
  executable: booksim
  backend: anynet_table
```

## Fields

### `executable`

Command or path used to launch BookSim.

```yaml
booksim:
  executable: booksim
```

or:

```yaml
booksim:
  executable: /tmp/booksim2/src/booksim
```

The CLI can override this:

```bash
topoanalyzer benchmark examples/benchmarks/mesh2d/latency_vs_injection_mesh2d_scales.yaml \
  --booksim-executable /tmp/booksim2/src/booksim
```

### `backend`

BookSim lowering mode. Optional, default `anynet_table`.

```yaml
booksim:
  backend: anynet_table
```

Supported values:

- `auto`: choose `stock_fattree` for `fattree_anca`,
  `ubmesh_apr_runtime` for `ubmesh_apr_runtime`, otherwise use `anynet_table`.
- `anynet_table`: default custom backend. Emits BookSim `anynet` topology plus a generated route table.
- `stock_mesh`: legacy compatibility backend for stock BookSim mesh experiments.
- `stock_fattree`: native BookSim Fat-tree backend for `fattree_anca`.
- `ubmesh_apr_runtime`: BookSim `anynet` topology plus a runtime
  `ubmesh_apr` routing function for `ubmesh_apr_runtime`.

## Generated Config

For the default `anynet_table` backend, each simulation point writes:

```text
booksim/<case-name>/inj_<rate>_rep_<n>/
  booksim.cfg
  anynet.net
  anynet.routes
  anynet_mapping.json
```

Important generated fields:

```text
topology = anynet;
routing_function = min;
network_file = <absolute path to anynet.net>;
route_table_file = <absolute path to anynet.routes>;
traffic = <traffic>;
injection_rate = <rate>;
packet_size = <packet_size>;
injection_rate_uses_flits = <0 or 1>;
sim_type = latency;
warmup_periods = <warmup_cycles>;
sample_period = <sample_cycles>;
max_samples = <max_samples>;
num_vcs = <num_vcs>;
vc_buf_size = <vc_buffer_size>;
```

`anynet.net` encodes the router graph and per-directed-router-link latency.
Terminal entries intentionally omit explicit weights because this BookSim2
parser treats node weights incorrectly when mixed with router links; terminal
injection/ejection latency remains the default 1 cycle.

`anynet.routes` is table-driven:

```text
<router> <destination_terminal> <output_port> <vc>
```

The BookSim overlay in `booksim_overlays/booksim2` loads that table and applies
the VC as an absolute BookSim VC index. The benchmark `num_vcs` must be greater
than the largest VC used by the generated routing table.

`anynet_mapping.json` records the Topology-Analyzer router IDs, terminal IDs,
link latency, and bandwidth metadata used to generate the BookSim files.

If a topology graph provides `terminal_attachments` metadata, the exporter
attaches BookSim terminals only to those routers. Fat-tree uses this so only
leaf routers own terminals. If `terminal_attachments` is absent, the exporter
falls back to mesh-style `concentration` terminals on every router.

If a routing table provides:

```text
routing_table.metadata["terminal_next_hops"]
```

the exporter uses those terminal-specific next hops. Otherwise it falls back to
the canonical router-to-router route table. `fattree_nca_hash` uses this path so
different destination terminals attached to the same leaf router can still use
different equal-cost Fat-tree paths.

## Required BookSim2 Overlay

Stock BookSim2 `anynet` computes shortest paths internally and does not accept
an external route table. Apply the overlay before running `anynet_table` configs:

```bash
patch -p1 -d /path/to/booksim2 < booksim_overlays/booksim2/table_anynet.patch
make -C /path/to/booksim2/src
```

Without the overlay, BookSim will reject `route_table_file` as an unknown config
field.

## Injection Rate Units

Benchmark YAML:

```yaml
benchmark:
  injection_rate_unit: flits/node/cycle
  packet_size: 4
```

generates:

```text
packet_size = 4;
injection_rate_uses_flits = 1;
```

Benchmark YAML:

```yaml
benchmark:
  injection_rate_unit: packets/node/cycle
```

generates:

```text
injection_rate_uses_flits = 0;
```

## Legacy `stock_mesh` Backend

For:

```yaml
booksim:
  backend: stock_mesh
```

the backend writes a conventional stock mesh config:

```text
topology = mesh;
k = <mesh x dimension>;
n = 2;
routing_function = dor;
use_noc_latency = 1;
```

This compatibility backend supports only:

```text
topology.type = mesh2d
routing.type = mesh_xy
x == y
homogeneous link bandwidth metadata
homogeneous link latency
latency_cycles == 1
```

Unsupported stock cases raise a `BookSimUnsupportedError`.

## Native `stock_fattree` Backend

For:

```yaml
booksim:
  backend: stock_fattree
```

or:

```yaml
booksim:
  backend: auto
```

with `routing.type: fattree_anca`, the backend writes:

```text
topology = fattree;
k = <radix / 2>;
n = <levels>;
routing_function = anca;
```

This path uses BookSim's runtime adaptive Fat-tree routing function rather than
the static `anynet.routes` table. It currently requires:

```text
topology.type = fattree
routing.type = fattree_anca
homogeneous link latency
latency_cycles == 1
homogeneous link bandwidth metadata
```

Use `anynet_table` for `fattree_nca_hash`, `fattree_dmodk`, and
`fattree_dmodc`.

## Runtime `ubmesh_apr_runtime` Backend

For:

```yaml
booksim:
  backend: auto
```

with:

```yaml
routing:
  type: ubmesh_apr_runtime
```

the backend writes `anynet.net`, `anynet_mapping.json`, and a `booksim.cfg`
without `anynet.routes`:

```text
topology = anynet;
routing_function = ubmesh_apr;
network_file = <generated anynet.net>;
ubmesh_apr_dimensions = <comma-separated dimensions>;
ubmesh_apr_seed = <seed>;
ubmesh_apr_vl_policy = tfc_two_virtual_lanes;
```

This path is for a BookSim build that implements a runtime `ubmesh_apr`
routing function. Unlike `ubmesh_apr_hash` and `ubmesh_tfc`, it is not a static
route table. The generated config requires at least `num_vcs: 2`.

Unsupported examples:

```yaml
topology:
  type: mesh2d
  params:
    x: 4
    y: 2
```

Reason: stock BookSim mesh config uses one `k`, so rectangular mesh needs a
custom topology.

```yaml
links:
  default:
    latency_cycles: 2
    bandwidth: 64GB/s
```

Reason: this stock BookSim mesh path does not expose a general per-link channel
latency config; the mesh implementation uses its built-in 1-cycle mesh channel
latency behavior.

```yaml
routing:
  type: graph_lash
```

Reason: stock BookSim config can lower `mesh_xy` to `routing_function = dor`,
but cannot consume arbitrary table-driven routing generated by
Topology-Analyzer. Use `anynet_table` for those systems.

## Remaining Backend Work

The default backend now covers arbitrary graph lowering, per-link latency, and
table-driven routing. Remaining work:

- true per-link bandwidth in BookSim channel behavior,
- additional true adaptive routing functions that can inspect runtime credit or
  queue state, for example UGAL-style Dragonfly routing,
- optional directed-only links if a future topology needs one-way channels,
- richer parser support for additional BookSim output modes.

# BookSim2 AnyNet Table Overlay

Topology-Analyzer's default BookSim backend emits:

- `booksim.cfg`
- `anynet.net`
- `anynet.routes`
- `anynet_mapping.json`

The generated config uses:

```text
topology = anynet;
routing_function = min;
network_file = <generated anynet.net>;
route_table_file = <generated anynet.routes>;
```

Stock BookSim2 supports `anynet` topology files, but its built-in `min_anynet`
routing function computes shortest paths internally and does not read an
external route table. Apply `table_anynet.patch` to a BookSim2 checkout to make
`AnyNet` load the generated route table.

The easiest repo-local setup is:

```bash
make bootstrap
source .venv/bin/activate
```

This clones BookSim2, applies this overlay, builds BookSim, and links the binary
as `.venv/bin/booksim`.

From the root of a BookSim2 checkout:

```bash
patch -p1 < /path/to/Topology-Analyzer/booksim_overlays/booksim2/table_anynet.patch
make -C src
```

The route table format is one entry per router and destination terminal:

```text
<router> <destination_terminal> <output_port> <vc>
```

The generated `anynet.net` intentionally writes terminal entries without an
explicit latency value:

```text
router 0 node 0 router 1 2 router 4 5
```

This avoids a parser quirk in this BookSim2 `anynet` implementation where a
weighted `node` entry on a mixed router/node line can be interpreted as a router
self-link. Router-to-router link latencies are still explicit.

The overlay preserves BookSim's existing shortest-path `anynet` behavior when
`route_table_file` is empty. When the field is set, every router must have a
route-table entry for every terminal.

Current scope:

- arbitrary router graph topology through `anynet.net`,
- per-directed-router-link latency through `anynet.net`,
- deterministic table-driven routing through `anynet.routes`,
- static VC selection per route-table entry.

Per-link bandwidth remains metadata in `anynet_mapping.json`; this BookSim2
channel model does not expose per-edge bandwidth.

# Examples

Example files are grouped by role.

```text
examples/
  benchmarks/
    mesh2d/          benchmark specs that reference one or more systems
  systems/
    mesh2d/
      xy/            BookSim-ready square 2D mesh systems with XY routing
      graph_lash/    shortest-path graph routing with VC layers
      graph_updown/  graph-analyzed up*/down* routing table systems
      link_variants/ heterogeneous link parameter examples
```

Benchmark system paths are relative to the benchmark YAML file location.

Useful entry points:

```bash
topoanalyzer validate examples/systems/mesh2d/xy/mesh2d_4x4_xy.yaml
topoanalyzer validate examples/systems/mesh2d/graph_lash/mesh2d_4x4_graph_lash.yaml
topoanalyzer validate examples/systems/mesh2d/graph_updown/mesh2d_4x4_graph_updown.yaml
topoanalyzer benchmark examples/benchmarks/mesh2d/latency_vs_injection_mesh2d_scales.yaml --dry-run
```

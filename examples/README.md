# Examples

Example files are grouped by role.

```text
examples/
  benchmarks/
    mesh2d/          benchmark specs that reference one or more systems
    comparisons/     cross-topology benchmark specs
  systems/
    fattree/
      anca/          Fat-tree systems using BookSim runtime adaptive ANCA
      dmodc/         Fat-tree systems with Dmodc-style fault-aware modulo routing
      dmodk/         Fat-tree systems with deterministic D-mod-k routing
      lca/           Fat-tree systems with topology-specific LCA routing
      nca_hash/      Fat-tree systems with balanced static NCA hash routing
    mesh2d/
      xy/            2D mesh XY baseline systems
      graph_lash/    shortest-path graph routing with VC layers
      graph_updown/  graph-analyzed up*/down* routing table systems
      link_variants/ heterogeneous link parameter examples
```

Benchmark system paths are relative to the benchmark YAML file location.

Useful entry points:

```bash
topoanalyzer validate examples/systems/mesh2d/xy/mesh2d_4x4_xy.yaml
topoanalyzer validate examples/systems/fattree/lca/fattree_r8_l4_lca.yaml
topoanalyzer validate examples/systems/fattree/nca_hash/fattree_r8_l4_nca_hash.yaml
topoanalyzer validate examples/systems/fattree/dmodk/fattree_r8_l4_dmodk.yaml
topoanalyzer validate examples/systems/fattree/dmodc/fattree_r8_l4_dmodc.yaml
topoanalyzer validate examples/systems/fattree/anca/fattree_r8_l4_anca.yaml
topoanalyzer validate examples/systems/mesh2d/graph_lash/mesh2d_4x4_graph_lash.yaml
topoanalyzer validate examples/systems/mesh2d/graph_updown/mesh2d_4x4_graph_updown.yaml
topoanalyzer benchmark examples/benchmarks/mesh2d/latency_vs_injection_mesh2d_scales.yaml --dry-run
topoanalyzer benchmark examples/benchmarks/comparisons/latency_vs_injection_fattree_r8_l4_vs_mesh_16x16.yaml --dry-run
```

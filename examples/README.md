# Examples

Example files are grouped by role.

```text
examples/
  benchmarks/
    mesh2d/          benchmark specs that reference one or more systems
    comparisons/     cross-topology benchmark specs
  systems/
    dragonfly/
      min/           Dragonfly systems with minimal VC-split routing
      valiant_hash/  Dragonfly systems with static VALg-style hashed routing
    fattree/
      anca/          Fat-tree systems using BookSim runtime adaptive ANCA
      dmodc/         Fat-tree systems with Dmodc-style fault-aware modulo routing
      dmodk/         Fat-tree systems with deterministic D-mod-k routing
      lca/           Fat-tree systems with topology-specific LCA routing
      nca_hash/      Fat-tree systems with balanced static NCA hash routing
    hypercube/
      ecube/         Hypercube systems with deterministic E-cube routing
      lash/          Hypercube systems with minimal path-diversity VC routing
      valiant_hash/  Hypercube systems with static Valiant-style hashed routing
    mesh2d/
      xy/            2D mesh XY baseline systems
      graph_lash/    shortest-path graph routing with VC layers
      graph_updown/  graph-analyzed up*/down* routing table systems
      link_variants/ heterogeneous link parameter examples
    mesh3d/
      xyz/           3D mesh XYZ baseline systems
    ruche3d/
      lash/          3D ruche systems with graph shortest-path VC routing
      valiant_hash/  3D ruche systems with static Valiant-style hashed routing
      xyz/           3D ruche systems with express-link XYZ routing
    torus2d/
      xy/            2D torus topology with conservative XY routing
    torus3d/
      xyz/           3D torus topology with conservative XYZ routing
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
topoanalyzer validate examples/systems/mesh3d/xyz/mesh3d_4x4x2_xyz.yaml
topoanalyzer validate examples/systems/torus2d/xy/torus2d_4x4_xy.yaml
topoanalyzer validate examples/systems/torus3d/xyz/torus3d_3x3x3_xyz.yaml
topoanalyzer validate examples/systems/ruche3d/xyz/ruche3d_4x4x4_s2_xyz.yaml
topoanalyzer validate examples/systems/ruche3d/lash/ruche3d_3x3x3_s2_lash.yaml
topoanalyzer validate examples/systems/ruche3d/valiant_hash/ruche3d_4x4x4_s2_valiant_hash.yaml
topoanalyzer validate examples/systems/hypercube/ecube/hypercube_d4_ecube.yaml
topoanalyzer validate examples/systems/hypercube/lash/hypercube_d4_lash.yaml
topoanalyzer validate examples/systems/hypercube/valiant_hash/hypercube_d4_valiant_hash.yaml
topoanalyzer validate examples/systems/dragonfly/min/dragonfly_p2_a4_h2_min.yaml
topoanalyzer validate examples/systems/dragonfly/valiant_hash/dragonfly_p2_a4_h2_valiant_hash.yaml
topoanalyzer validate examples/systems/mesh2d/graph_lash/mesh2d_4x4_graph_lash.yaml
topoanalyzer validate examples/systems/mesh2d/graph_updown/mesh2d_4x4_graph_updown.yaml
topoanalyzer benchmark examples/benchmarks/mesh2d/latency_vs_injection_mesh2d_scales.yaml --dry-run
topoanalyzer benchmark examples/benchmarks/comparisons/latency_vs_injection_fattree_r8_l4_vs_mesh_16x16.yaml --dry-run
```

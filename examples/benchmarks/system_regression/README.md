# System Regression Benchmarks

This folder contains small BookSim latency-vs-injection smoke benchmarks for
the example systems under `examples/systems`.

## CI-Sized Regression

Run the bounded regression set:

```sh
topoanalyzer benchmark examples/benchmarks/system_regression/latency_vs_injection_ci.yaml --no-progress
```

The CI-sized file uses three injection-rate points:

```text
0.001, 0.01, 0.1 flits/node/cycle
```

It uses `booksim.backend: auto`, so runtime-routed examples such as
`fattree_anca` and `ubmesh_apr_runtime` select their custom BookSim backend,
while static-routing examples use the table-driven `anynet` backend.

The benchmark uses `num_vcs: 5` because the adaptive runtime examples include
`dragonfly_par_runtime`, which reserves five VC phases. Systems that need fewer
VCs still run correctly with the larger VC budget.

CI uses `latency_vs_injection_ci_materialize.yaml` with `--dry-run` for the
same CI-sized system list. It uses one injection point to avoid repeating
route-table export for each point while still checking that every bounded
system can be loaded, routed, lowered to BookSim config, and materialized.

## BookSim CI Smoke

Run the smaller real-simulator smoke used by CI:

```sh
topoanalyzer benchmark examples/benchmarks/system_regression/latency_vs_injection_booksim_smoke.yaml --no-progress
```

This file keeps the same three injection-rate points but samples representative
systems across table-driven `anynet`, stock Fat-tree runtime ANCA, LLN table
routing, SlimNoC minimal routing, and static UBMesh APR-hash routing. The
broader `latency_vs_injection_ci.yaml` file is still the all-system CI-sized
sweep, including runtime APR materialization, but it is more appropriate for
local regression runs or dry materialization checks.

Runtime anynet algorithms are kept in a separate smoke file so the CI smoke can
stay representative and short. Use the dedicated adaptive smoke below to
exercise those runtime routing functions.

## Full-Root Fat-Tree BookSim Smoke

Run the full-root Fat-tree smoke:

```sh
topoanalyzer benchmark examples/benchmarks/system_regression/latency_vs_injection_fattree_fullroot_booksim_smoke.yaml --no-progress
```

This file runs one low-rate point over `root_mode: full` Fat-tree systems using
all Fat-tree routing modes: `fattree_lca`, `fattree_nca_hash`, `fattree_dmodk`,
`fattree_dmodc`, and `fattree_anca`. Full-root `fattree_anca` uses
`anynet_table` under `booksim.backend: auto`, because native BookSim Fat-tree
models the half-root shape.

## Adaptive Runtime BookSim Smoke

Run the real-simulator adaptive runtime smoke:

```sh
topoanalyzer benchmark examples/benchmarks/system_regression/latency_vs_injection_adaptive_runtime_booksim_smoke.yaml --no-progress
```

This file runs one low-rate point over the runtime anynet algorithms:

- Dragonfly: `dragonfly_ugal_l_runtime`, `dragonfly_valg_runtime`,
  `dragonfly_valn_runtime`, `dragonfly_par_runtime`
- Hypercube: `hypercube_min_adaptive_runtime`, `hypercube_valiant_runtime`,
  `hypercube_ugal_l_runtime`
- SlimNoC: `slimnoc_ugal_l_runtime`, `slimnoc_ugal_g_runtime`,
  `slimnoc_valiant_runtime`
- LLN: `lln_adaptive_layer_runtime`
- UBMesh: `ubmesh_apr_runtime`

It uses `num_vcs: 5` because `dragonfly_par_runtime` is the highest-VC runtime
case in the current set.

## Large Manual Regression

Run the large-scale examples manually:

```sh
topoanalyzer benchmark examples/benchmarks/system_regression/latency_vs_injection_large_manual.yaml --no-progress
```

These examples are intentionally not part of CI:

- `lln_16x16term_c4_8x8x19_table.yaml`: full LLN table generation is large.
- `ubmesh_8x8x4x4_apr_runtime.yaml`: large nD-UBMesh runtime-routing graph.

They remain represented here so every example system has a corresponding
regression benchmark entry, but they are separated from the CI path to keep
GitHub Actions bounded.

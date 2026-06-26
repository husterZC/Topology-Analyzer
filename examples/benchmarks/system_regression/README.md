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

The benchmark uses `num_vcs: 4` because the current example routing tables use
VC IDs up to 3. Systems that need fewer VCs still run correctly with the larger
VC budget.

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

`ubmesh_apr_runtime` is not included in the real BookSim CI smoke because the
repo-local BookSim overlay currently provides the table-driven `anynet` backend,
but not a compiled `ubmesh_apr` runtime routing function.

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

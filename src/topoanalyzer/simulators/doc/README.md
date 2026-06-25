# Simulator YAML Settings

Simulator settings live at the top level of a benchmark YAML file. The only
implemented backend today is BookSim.

```yaml
booksim:
  executable: booksim
```

The benchmark runner uses simulator backends for three operations:

1. Materialize simulator input files.
2. Run the simulator process.
3. Parse raw simulator output into metrics.

## Backend Boundaries

The internal system model is not a simulator config. Simulator backends lower a
validated `System` into backend-specific input files.

This matters because the model may support features the current backend cannot
lower yet. For example:

- heterogeneous mesh link latency,
- rectangular mesh in stock BookSim config,
- arbitrary routing tables such as `graph_lash`.

Backends must reject unsupported features explicitly instead of silently
approximating them.

## Current Backend

See:

```text
simulators/booksim/doc/README.md
```

for the `booksim:` YAML settings and current lowering limitations.

# Simulator YAML Settings

Simulator settings live at the top level of a benchmark YAML file. The only
implemented backend today is BookSim.

```yaml
booksim:
  executable: booksim
  backend: anynet_table
```

The benchmark runner uses simulator backends for three operations:

1. Materialize simulator input files.
2. Run the simulator process.
3. Parse raw simulator output into metrics.

## Backend Boundaries

The internal system model is not a simulator config. Simulator backends lower a
validated `System` into backend-specific input files.

This matters because each backend has an explicit lowering contract. The default
BookSim `anynet_table` backend lowers:

- arbitrary router graphs accepted by BookSim `anynet`,
- per-directed-router-link latency,
- deterministic routing tables, including VC selection.

Backends must reject unsupported features explicitly instead of silently
approximating them.

## Current Backend

See:

```text
simulators/booksim/doc/README.md
```

for the `booksim:` YAML settings, overlay instructions, and remaining lowering
limits.

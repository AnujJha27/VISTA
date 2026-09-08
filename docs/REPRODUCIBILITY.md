# Reproducibility

This file records the commands needed to reproduce the current artifact on a
fresh machine.

## Environment

Required:

- Linux or WSL2;
- GNU Make;
- `g++` or `clang++` with C++17 support;
- SQLite development headers and library;
- Python 3.11 or newer;
- Lean installed with `elan`;
- `nlohmann/json` headers.

Recommended checks:

```bash
g++ --version
make --version
python3 --version
lean --version
lake --version
```

## Core verifier and orchestration

From the repository root:

```bash
make clean
make test
make wsl-smoke
make benchmark
make benchmark-repeat
make sanity-demo
make vista-demo
```

Expected result:

- `make test` builds the C++ verifier, builds the bundled Lean project, and
  runs C++, orchestrator, and DFT certification unit tests.
- `make wsl-smoke` sends a mock LLM proof through the real verifier.
- `make benchmark` writes `benchmark-results.json`.
- `make benchmark-repeat` writes `benchmark-repeat-results.json` with
  run-to-run variance.
- `make sanity-demo` writes a draft hypothesis manifest and report under
  `build/`.
- `make vista-demo` runs the deterministic bundled agentic workflow over
  `ProofSearch.PhysicsToy` and writes a durable run under
  `build/runs/vista-physics-toy`.

Inspect the bundled demo:

```bash
./vista replay build/runs/vista-physics-toy
./vista tui --run-dir build/runs/vista-physics-toy --once
```

## Terminal UI

Run:

```bash
make tui
```

For a non-interactive terminal report:

```bash
python3 -m dftcert.tui --once
```

## Model adapter demos

VISTA can run with:

- the deterministic checked-in adapter;
- OpenRouter's free-model route through `OPENROUTER_API_KEY`;
- generic OpenAI-compatible local/cluster servers;
- Maestro cluster presets: `maestro`, `piano`, `sitar`, and `violin`.

Examples:

```bash
./vista demo physics-toy --llm openrouter-free

export VISTA_OPENAI_BASE_URL=http://cluster-node:8000/v1
export VISTA_OPENAI_MODEL=local-lean-coder
./vista demo physics-toy --llm openai-compatible

./vista demo physics-toy --llm maestro
```

Real credentials belong in `.env`, which is ignored. Commit only
`.env.example`.

## DFT certificate example

The DFT certificate example uses the vendored `examples/dft/lean` Testv2
formalization by default. Set `DFT_PROJECT` only when checking a separate
reviewed Testv2 checkout:

```bash
export DFT_PROJECT=examples/dft/lean
make dftcert-obligations
make dftcert-assemble-example
make dftcert-certify-example
```

`dftcert-certify-example` requires `--trusted-local` internally and is intended
only for the repository-owned example certificate. Do not use that mode for
arbitrary uploaded Lean source.

## DFT presentation carousel

These commands create separate, inspectable run directories for the four
important outcomes. Only `certified` runs agentic Lean proof search; the other
three are deterministic policy fixtures that demonstrate an explicit refusal
before proof search.

```bash
./vista demo dft --scenario certified --llm maestro --run-dir build/runs/dft-certified
./vista demo dft --scenario non-self-adjoint --run-dir build/runs/dft-non-self-adjoint
./vista demo dft --scenario missing-assumptions --run-dir build/runs/dft-missing
./vista demo dft --scenario formalization-gap --run-dir build/runs/dft-gap

./vista tui --run-dir build/runs/dft-non-self-adjoint --once
```

## Benchmark interpretation

The default benchmark is a smoke benchmark, not a paper-scale evaluation. It
separates cold verification from warm-cache checks and reports:

- total attempts;
- verified attempts;
- cold-cache elapsed time;
- warm-cache elapsed time;
- cache hit rate;
- p50/p95 latency;
- configured resource limits.

For a paper or poster, run the benchmark repeatedly on the target machine and
report hardware, OS/WSL version, Lean version, and mean/standard deviation.

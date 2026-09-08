# Vendored Testv2 DFT Formalization

This is a source snapshot of the local `Testv2` Lean formalization used by the
VISTA DFT demo. It is intentionally kept inside the VISTA repo so demo runs
do not depend on an external checkout or branch state.

First-time setup on a machine:

```bash
lake update mathlib
lake exe cache get
lake build Testv2.Verifier
```

Then run the demo from the VISTA repo root:

```bash
python ./vista demo dft --llm maestro --run-dir build/runs/dft-maestro-live-1
```

For a presentation sequence, use the reviewed proof-search case followed by
the three deterministic policy outcomes:

```bash
python ./vista demo dft --scenario certified --llm maestro --run-dir build/runs/dft-certified
python ./vista demo dft --scenario non-self-adjoint --run-dir build/runs/dft-non-self-adjoint
python ./vista demo dft --scenario missing-assumptions --run-dir build/runs/dft-missing
python ./vista demo dft --scenario formalization-gap --run-dir build/runs/dft-gap
```

Only `certified` runs Lean proof search. The other cases deliberately stop at
the policy boundary and can be viewed with `./vista tui --run-dir <run-dir>`.

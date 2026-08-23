# VISTA Structural V2 evaluation

This is an artifact-grounding evaluation, not a test of physical derivative discontinuities or LLM proof search. `corpus_manifest.json` is independently authored ground truth; `corpus_models.py` only constructs artifacts.

Run from the repository root in the frozen PyTorch/Lean environment:

```bash
python evaluation/structural_v2/run.py --generate --results evaluation/structural_v2/results/vista-structural-eval-v2-r2-regression
```

It exports 48 PT2 artifacts under `build/vista-structural-v2-corpus`, runs each three times through the production extractor, `dftcert.structural` lowering, translation validator, policy assessment, obligation compiler, and certificate checker, and writes `evaluation/structural_v2/results/`. Each case has raw extraction, contracts, derivations, IR, validation, policy, obligations, Lean/certificate evidence, and tampering records. `score.py` writes CSV, JSON, and Markdown tables.

The regression corpus and fresh held-out corpus are separate. The fresh 12-case manifest is committed before execution and must not be relabeled or used to revise semantic rules after results are observed. Each r2 bundle records a corpus-freeze revision separately from its execution revision. Preserved bundles include `results/vista-structural-eval-v2-pre-fix` and `results/vista-structural-eval-v2-r2-regression`.

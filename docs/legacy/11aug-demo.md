# VISTA demo — 11 August

Run this on Maestro from `/home/anuj/vista`.

```bash
module load miniconda
conda activate vista
cd /home/anuj/vista
```

## Certified artifact → certificate

Show the exported model artifacts:

```bash
ls build/structural-v2-models/*.pt2
```

Safely extract and lower the certified artifact into Structural IR:

```bash
./vista structural analyze-pt2 \
  build/structural-v2-models/certified-ring.pt2 \
  --constraints examples/dft/structural-v2-input-constraints.json \
  --output build/prof-demo-ir.json
```

Show the policy result, artifact binding, and translation validation:

```bash
./vista structural report \
  --ir build/prof-demo-ir.json \
  --output build/prof-demo-report.json
```

Show why each high-level claim was derived:

```bash
python -c "import json; x=json.load(open('build/prof-demo-ir.json')); print(json.dumps(x['translation']['semantic_derivations'], indent=2))"
```

Generate the exact Lean obligations and build the DFT Lean project:

```bash
./vista structural generate \
  --ir build/prof-demo-ir.json \
  --jsonl > build/prof-demo-tasks.jsonl

cd examples/dft/lean && lake build && cd ../..
```

Run the untrusted proof-search layer and Lean verifier:

```bash
PROOF_SEARCH_ALLOW_GENERATED_OBLIGATIONS=1 \
PROOF_SEARCH_PROJECT_DIR=/home/anuj/vista/examples/dft/lean \
PROOF_SEARCH_DB=/home/anuj/vista/build/prof-demo.db \
python -m orchestrator.cli \
  --provider command \
  --llm-command "python examples/orchestrator/vista_demo_llm.py" \
  --verifier build/proof-search \
  --full-process --small-model \
  --max-epochs 3 --stagnation-epochs 2 \
  --journal-dir build/runs/prof-demo/journal \
  --run-dir build/runs/prof-demo \
  < build/prof-demo-tasks.jsonl \
  > build/prof-demo-results.jsonl

python -c "import json; [print(x['id'], x['status']) for x in map(json.loads, open('build/prof-demo-results.jsonl'))]"
```

Expected: three `verified` obligations.

Inspect the proof-search trace and accepted Lean proofs:

```bash
./vista tui --run-dir build/runs/prof-demo --once
./vista review --run-dir build/runs/prof-demo --once
```

Assemble the certificate and verify its generated Lean source independently:

```bash
./vista structural assemble \
  --ir build/prof-demo-ir.json \
  --proof-results build/prof-demo-results.jsonl \
  --source-output build/ProfDemoCertificate.lean \
  --report-output build/prof-demo-certificate.json

./vista structural check-certificate \
  --project examples/dft/lean \
  --source build/ProfDemoCertificate.lean \
  --trusted-local
```

Expected final status: `verified`.

## Negative control

Show that VISTA fails closed when the required nonlocal coupling is not covered:

```bash
./vista structural analyze-pt2 \
  build/structural-v2-models/too-shallow-ring.pt2 \
  --constraints examples/dft/structural-v2-input-constraints.json \
  --output build/prof-too-shallow-ir.json

./vista structural report \
  --ir build/prof-too-shallow-ir.json \
  --output build/prof-too-shallow-report.json
```

Expected: `structural_requirements_not_met`, with a witness that message depth
two cannot cover the required coupling from site 0 to site 3.

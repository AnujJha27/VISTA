# Noether / VISTA

> Turn a structural belief about a model into a Lean-checked certificate.

## What this is

You have an exported model and believe its architecture has some property:
an operator is built a certain way, a computation is guaranteed to have a
certain shape, some structural invariant holds by construction, regardless
of what the model is later trained on. Running the model and checking
outputs on some inputs can't establish this. Sampling never proves a
structural guarantee holds for every input, and it says nothing about *why*
a property holds.

This project takes a different approach: it reads a model's real exported
computation graph directly (never a description of what the graph is
supposed to do), derives specific structural facts from it, and uses those
facts to instantiate a formal statement in Lean. Lean's kernel, the same
trusted core that checks any formally verified mathematical proof, either
accepts that statement or it doesn't; nothing else gets a vote, not an LLM,
not a test suite, not a human's read of the code. The resulting certificate
hash-binds every derived fact back to the exact artifact bytes it came
from, so it says something concrete: this specific file's computation graph
yields facts that instantiate a proven theorem, and Lean checked the proof.

If a fact needed to complete the proof can't be derived from the artifact
or from the mathematics itself, the tool doesn't guess or paper over it:
it's left as a visible, named, unproven assumption on the final
certificate, so nobody mistakes "we assumed this" for "we proved this."

```text
model.pt2 → artifact-grounded structural facts → generated Lean obligations → certificate
```

## How it works

1. **Extract.** A model is exported to a `.pt2` file. A sandboxed extractor
   reads its computation graph and records the raw nodes, operations, and
   any small integer/boolean buffers, never a trained parameter's
   floating-point values. The file's SHA-256 hash identifies the exact
   artifact from here on.
2. **Derive structural facts.** Deterministic rules read that raw graph and
   derive specific claims about how it's built, e.g. how many distinct
   components it has, whether a computation is constructed a certain way,
   whether some declared invariant holds structurally. Every claim records
   exactly which graph nodes it came from, so it can be traced back and
   independently re-checked.
3. **Match to a theorem's requirements.** A Lean theorem states the actual
   requirement. The tool checks which of the theorem's premises the derived
   facts can satisfy, which need a human-supplied interpretation (e.g.
   which exported output corresponds to which role), and which need an
   explicit assumption because nothing in the artifact or the theory can
   establish them.
4. **Certify.** A Lean source file is generated that states the theorem
   applied to the concrete derived/assumed values, and Lean's kernel
   compiles and checks it. The resulting certificate is a JSON bundle
   hash-bound to the exact artifact, the specification, and the Lean
   project, so anyone can independently re-verify it without re-trusting
   any single field just because it's already in the bundle.

An assumption that can't be established from the artifact or the theory
never gets silently proven. It stays a visible, unproven premise on the
generated theorem, and the certificate says so explicitly.

The harness itself (`dftcert/verification/`) is domain-agnostic: it knows
about Lean theorems, artifacts, packages, and certificates, nothing about
any specific field. A domain adapter (`dftcert/structural/`) plugs in the
actual structural facts one domain cares about. The one adapter in this
repo right now is for a density-functional-theory case study (a learned
exchange-correlation functional, checked for properties like self-adjointness
and long-range coupling capacity); see
[examples/theorem_centric_demo/README.md](examples/theorem_centric_demo/README.md)
for that specific worked example and what its certificate actually says.

## Quick start

```bash
python examples/theorem_centric_demo/build_package.py
python examples/theorem_centric_demo/extract_artifact.py
python vista verify start \
  --extraction-result examples/theorem_centric_demo/extraction-result.json \
  --package examples/theorem_centric_demo/vista-package.json \
  --session examples/theorem_centric_demo/session.json \
  --project examples/dft/lean --trusted-local --timeout-s 180
```

This walks a real, committed `.pt2` fixture through the whole pipeline. It
will report which premises are already satisfied and which one still needs
an explicit assumption. Accept it and continue:

```bash
python examples/theorem_centric_demo/accept_assumption.py
python vista verify start \
  --extraction-result examples/theorem_centric_demo/extraction-result.json \
  --package examples/theorem_centric_demo/vista-package.json \
  --session examples/theorem_centric_demo/session.json \
  --project examples/dft/lean --trusted-local --timeout-s 180

python vista verify certify \
  --session examples/theorem_centric_demo/session.json \
  --package examples/theorem_centric_demo/vista-package.json \
  --project examples/dft/lean \
  --output-dir examples/theorem_centric_demo/certificate \
  --trusted-local --timeout-s 180
```

Inspect `examples/theorem_centric_demo/certificate/*-report.json` for the
result: which facts came straight from the artifact, which were a declared
interpretation, which were an explicit assumption, and which Lean itself
proved by computation.

```bash
make
make test
```

builds and tests everything else in the repository (a C++ verifier service,
an older policy-based certification pipeline, and an LLM proof-search
orchestrator that this same trust boundary also applies to).

## Trust boundary

This certifies structural compatibility, not numerical accuracy, training
convergence, or experimental agreement. Lean checks the generated theorem,
not the model's binary file itself. A certificate trusts the sandboxed
extractor and the human-reviewed interpretation of which output means what;
it never trusts an accepted assumption as proven. That assumption remains
a visible, unproven premise on the certificate theorem, forever.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

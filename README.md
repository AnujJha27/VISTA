# Noether / VISTA

> Turn a structural belief about a model into a Lean-checked certificate.

## What this is

Machine-learned models are increasingly used to replace hand-derived
formulas in physics simulations. The running example throughout this
codebase is a learned exchange-correlation (XC) functional for density
functional theory (DFT), where a neural network stands in for a term that
used to be a fixed mathematical expression. That's only trustworthy if the
network's *architecture* actually respects the mathematical structure the
physics demands: an operator has to be self-adjoint, it has to be able to
represent interactions between sites that aren't neighbors, the XC term
has to allow a real discontinuity where the physics requires one. These
are properties of how the model is *built*, not of what it learns; they
should hold before a single weight is trained, and they should hold
regardless of what data it's later trained on.

The normal way to gain confidence in a model, running it and checking the
outputs, can't establish this. Sampling outputs on some inputs never proves
an architectural guarantee holds for every input, and it says nothing about
*why* a property holds. What you actually want is closer to a compiler
warning that's been upgraded to a mathematical proof: inspect the model's
real computation graph, decide whether it's built the way a theorem
requires, and have an independent, mechanical proof checker, not a human
and not another neural network, confirm that judgment.

That's what this project does. It takes a real exported model file, reads
its computation graph directly (never the researcher's description of what
the graph is supposed to do), derives specific structural facts from it,
and generates a Lean theorem stating that the *exact artifact* has the
property in question. Lean's kernel, the same trusted core that checks any
formally verified mathematical proof, either accepts that theorem or it
doesn't. If a fact needed to complete the proof can't be derived from the
artifact or from the mathematics itself, the tool doesn't guess or paper
over it: that fact is left as a visible, named, unproven assumption on the
final certificate, so nobody mistakes "we assumed this" for "we proved
this."

```text
model.pt2 → artifact-grounded structural facts → generated Lean obligations → certificate
```

## How it works

1. **Extract.** A model is exported to a `.pt2` file. A sandboxed extractor
   reads its computation graph and records the raw nodes, operations, and
   any small integer/boolean buffers (e.g. an adjacency matrix), never a
   trained parameter's floating-point values. The file's SHA-256 hash
   identifies the exact artifact from here on.
2. **Derive structural facts.** Deterministic rules read that raw graph and
   derive specific claims: how many sites there are, whether the operator
   is built as `B + Bᵀ` (self-adjoint by construction), whether the
   exchange-correlation term has the discontinuity a hinge activation
   gives it, how many message-passing hops connect any two sites. Every
   claim records exactly which graph nodes it came from, so it can be
   traced back and independently re-checked.
3. **Match to a theorem's requirements.** A Lean theorem states the actual
   requirement, e.g. "this operator is self-adjoint and can represent a
   non-local coupling." The tool checks which of the theorem's premises
   the derived facts can satisfy, which need a human-supplied
   interpretation (e.g. "this output is the exchange-correlation energy"),
   and which need an explicit assumption because nothing in the artifact
   or the theory can establish them.
4. **Certify.** A Lean source file is generated that states the theorem
   applied to the concrete derived/assumed values, and Lean's kernel
   compiles and checks it. The resulting certificate is a JSON bundle
   hash-bound to the exact artifact, the specification, and the Lean
   project, so anyone can independently re-verify it without re-trusting
   any single field just because it's already in the bundle.

An assumption that can't be established from the artifact or the theory
never gets silently proven. It stays a visible, unproven premise on the
generated theorem, and the certificate says so explicitly.

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

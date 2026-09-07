# Noether / VISTA

> Turn a structural belief about a model into a Lean-checked certificate.

You have an exported model and believe it has a property: information can
reach the sites that need to interact; an XC construction has the required
hinge; an operator is self-adjoint by construction. A test can sample
outputs, but it can't prove a structural property holds for the exact
artifact you have. This project can: it turns the architectural claim into a
theorem about the exact artifact, and has Lean's kernel check the proof —
never an LLM, never a test suite, never a human's read of the code.

```text
model.pt2 → artifact-grounded structural facts → generated Lean obligations → certificate
```

## How it works

1. **Extract.** A model is exported to a `.pt2` file. A sandboxed extractor
   reads its computation graph and records the raw nodes, operations, and
   any small integer/boolean buffers (e.g. an adjacency matrix) — never a
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
   project — so anyone can independently re-verify it without re-trusting
   any single field just because it's already in the bundle.

An assumption that can't be established from the artifact or the theory
never gets silently proven — it stays a visible, unproven premise on the
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
it never trusts an accepted assumption as proven — that assumption remains
a visible, unproven premise on the certificate theorem, forever.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

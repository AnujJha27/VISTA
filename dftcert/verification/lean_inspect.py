"""Structured Lean declaration introspection (spec section 8). Never parses
`#print` text with regex: a generated probe source uses Lean's own
`Environment`/`Meta` APIs to emit one marker-prefixed JSON payload, and the
Python side parses only that.

The probe is run with the caller's own `lean_command` from the supplied
Lean project root, exactly like `dftcert.structural.core.
verify_structural_certificate` already runs generated certificates -- same
subprocess/timeout/trust-boundary shape, reused rather than reinvented.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from collections.abc import Sequence
from string import Template
from typing import Any

from ..manifest import ManifestError

_MARKER = "VISTA_INSPECT_JSON:"
_MARKER_LINE = re.compile(re.escape(_MARKER) + r"(.*)$")

# The pretty-printer options used for the *fingerprint* source string: fully
# qualified names, no notation/unicode macros, every implicit argument shown
# -- a canonical machine representation, deliberately never the same string
# a human-facing `#print`/default pretty-print would produce (spec 8.1/8.2).
_CANONICAL_PP_LEAN = (
    "(Options.empty)\n"
    "    |>.setBool `pp.all true\n"
    "    |>.setBool `pp.fullNames true\n"
    "    |>.setBool `pp.notation false\n"
    "    |>.setBool `pp.unicode false\n"
    "    |>.setBool `pp.universes true"
)

# `Template`, not `str.format`: the Lean source below is full of literal
# `{`/`}` (Lean's own structure/set syntax), which `.format` would try to
# parse as replacement fields.
_PROBE_TEMPLATE = Template('''import Lean
$imports

open Lean Elab Meta Command

private def vistaNameOfDotted (s : String) : Name :=
  (s.splitOn ".").foldl (fun n c => Name.mkStr n c) Name.anonymous

private def vistaBinderInfoStr : BinderInfo → String
  | .default => "explicit"
  | .implicit => "implicit"
  | .strictImplicit => "strictImplicit"
  | .instImplicit => "instanceImplicit"

private def vistaDeclKindStr : ConstantInfo → String
  | .axiomInfo _ => "axiom"
  | .defnInfo _ => "def"
  | .thmInfo _ => "theorem"
  | .opaqueInfo _ => "opaque"
  | .quotInfo _ => "quot"
  | .inductInfo _ => "inductive"
  | .ctorInfo _ => "constructor"
  | .recInfo _ => "recursor"

/-- Direct constants used by a declaration's type/value, for the transitive
    (informational, audit-only per spec section 17) dependency closure. -/
private def vistaDirectUses : ConstantInfo → Array Name
  | .thmInfo v => v.type.getUsedConstants ++ v.value.getUsedConstants
  | .defnInfo v => v.type.getUsedConstants ++ v.value.getUsedConstants
  | .axiomInfo v => v.type.getUsedConstants
  | .opaqueInfo v => v.type.getUsedConstants ++ v.value.getUsedConstants
  | _ => #[]

/-- Transitive closure of constants used by `start`'s type/value, restricted
    to `start`'s own root namespace ("within the imported theory", spec
    section 17) -- otherwise this walks straight into the thousands of Init/
    Lean/Mathlib library-internal constants behind even one `Nat` lemma,
    which is audit noise, not a project requirement. Still walked
    transitively *through* out-of-namespace constants (a helper lemma might
    route back through the user's own namespace via a `Mathlib`-defined
    combinator), just not reported unless in-namespace. -/
private def vistaRootComponent : Name → Name
  | .anonymous => .anonymous
  | .str .anonymous s => .str .anonymous s
  | .num .anonymous n => .num .anonymous n
  | .str p _ => vistaRootComponent p
  | .num p _ => vistaRootComponent p

private partial def vistaUsedConstantsClosure (env : Environment) (start : Name) : Array Name :=
  let root := vistaRootComponent start
  let rec go (seen : NameSet) : List Name → NameSet
    | [] => seen
    | n :: rest =>
      if seen.contains n then go seen rest
      else
        let seen := seen.insert n
        match env.find? n with
        | some ci => go seen (rest ++ (vistaDirectUses ci).toList)
        | none => go seen rest
  (go {} [start]).toArray.filter (fun n => n != start && vistaRootComponent n == root) |>.qsort Name.lt

private def vistaCanonicalOptions : Options :=
  $canonical_options

private def vistaInspectOne (env : Environment) (declStr : String) : TermElabM Json := do
  let name := vistaNameOfDotted declStr
  match env.find? name with
  | none => return Json.mkObj [("declaration", declStr), ("exists", Json.bool false)]
  | some ci =>
    let (binders, conclDisplay, conclCanonical) ← Meta.forallTelescope ci.type fun fvars concl => do
      let mut acc : Array Json := #[]
      for fvar in fvars do
        let ldecl ← fvar.fvarId!.getDecl
        let isP ← Meta.isProp ldecl.type
        let display := toString (← Meta.ppExpr ldecl.type)
        let canonical := toString (← withOptions (fun _ => vistaCanonicalOptions) <| Meta.ppExpr ldecl.type)
        acc := acc.push (Json.mkObj [
          ("name", Json.str ldecl.userName.toString),
          ("binder_info", Json.str (vistaBinderInfoStr ldecl.binderInfo)),
          ("is_prop", Json.bool isP),
          ("type_display", Json.str display),
          ("type_fingerprint_source", Json.str canonical),
        ])
      let conclDisplay := toString (← Meta.ppExpr concl)
      let conclCanonical := toString (← withOptions (fun _ => vistaCanonicalOptions) <| Meta.ppExpr concl)
      return (acc, conclDisplay, conclCanonical)
    let axioms ← Lean.collectAxioms name
    let deps := vistaUsedConstantsClosure env name
    return Json.mkObj [
      ("declaration", Json.str declStr),
      ("exists", Json.bool true),
      ("kind", Json.str (vistaDeclKindStr ci)),
      ("binders", Json.arr binders),
      ("conclusion_display", Json.str conclDisplay),
      ("conclusion_fingerprint_source", Json.str conclCanonical),
      ("axioms", Json.arr (axioms.map (fun n => Json.str n.toString))),
      ("dependencies", Json.arr (deps.map (fun n => Json.str n.toString))),
    ]

#eval show CommandElabM Unit from do
  let env ← getEnv
  let names : List String := $declarations
  let results ← liftTermElabM (names.mapM (vistaInspectOne env))
  logInfo m!"$marker{(Json.arr results.toArray).compress}"
''')


def _lean_string_literal(value: str) -> str:
    return json.dumps(value)


def _render_probe(*, imports: list[str], declarations: list[str]) -> str:
    return _PROBE_TEMPLATE.substitute(
        imports="\n".join(f"import {module}" for module in imports),
        canonical_options=_CANONICAL_PP_LEAN,
        declarations="[" + ", ".join(_lean_string_literal(name) for name in declarations) + "]",
        marker=_MARKER,
    )


class LeanIntrospectionError(RuntimeError):
    """The probe could not be run, or ran without producing the marker
    payload -- a tool/introspection failure (spec section 25), not a
    statement about any declaration's truth."""


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _finish_binder(binder: dict[str, Any]) -> dict[str, Any]:
    return {
        **binder,
        "type_fingerprint": _fingerprint(binder["type_fingerprint_source"]),
    }


def _finish_declaration(entry: dict[str, Any]) -> dict[str, Any]:
    if not entry.get("exists"):
        return {"declaration": entry["declaration"], "exists": False}
    return {
        **entry,
        "binders": [_finish_binder(binder) for binder in entry["binders"]],
        "conclusion_fingerprint": _fingerprint(entry["conclusion_fingerprint_source"]),
    }


def run_marker_probe(
    *, project_root: str | Path, source: str, marker: str,
    lean_command: Sequence[str] = ("lake", "env", "lean", "-j", "1"),
    timeout_s: int = 300, trusted_local: bool = False,
) -> Any:
    """Run a generated Lean probe source from `project_root` via the
    caller's own `lean_command`, and return the JSON payload of the last
    `marker`-prefixed line in its output. Shared by every VISTA Lean probe
    (`inspect_declarations` here, `dftcert.verification.bindings`'
    candidate-matching probe) -- same subprocess/timeout/trust-boundary
    shape `dftcert.structural.core.verify_structural_certificate` already
    uses for generated certificates."""
    if not trusted_local:
        raise ManifestError(
            "Lean introspection requires --trusted-local until a compiler sandbox is configured"
        )
    if not lean_command:
        raise ManifestError("Lean command cannot be empty")
    root = Path(project_root).resolve()
    marker_line = re.compile(re.escape(marker) + r"(.*)$")
    with tempfile.TemporaryDirectory(prefix="vista-probe-") as directory:
        probe_path = Path(directory) / "VistaProbe.lean"
        probe_path.write_text(source, encoding="utf-8")
        try:
            process = subprocess.run(
                [*lean_command, str(probe_path)], cwd=root,
                capture_output=True, encoding="utf-8", errors="replace",
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as error:
            raise LeanIntrospectionError(f"Lean probe timed out after {timeout_s}s") from error
        except OSError as error:
            raise LeanIntrospectionError(f"cannot start Lean: {error}") from error
    diagnostics = (process.stdout or "") + (process.stderr or "")
    matches = [match.group(1) for line in diagnostics.splitlines() for match in [marker_line.search(line)] if match]
    if not matches:
        raise LeanIntrospectionError(
            f"Lean probe produced no marker payload (exit code {process.returncode}): "
            f"{diagnostics.strip()[-4000:]}"
        )
    return json.loads(matches[-1])


def inspect_declarations(
    *, project_root: str | Path, imports: list[str], declarations: list[str],
    lean_command: Sequence[str] = ("lake", "env", "lean", "-j", "1"),
    timeout_s: int = 300, trusted_local: bool = False,
) -> dict[str, dict[str, Any]]:
    """Run the structured inspector for `declarations` (fully qualified Lean
    names) after `import`ing `imports`, from `project_root` via the caller's
    own `lean_command`. Returns `{declaration_name: inspection_result}`."""
    if not declarations:
        raise ManifestError("Lean introspection needs at least one declaration name")
    payload = run_marker_probe(
        project_root=project_root, source=_render_probe(imports=imports, declarations=declarations),
        marker=_MARKER, lean_command=lean_command, timeout_s=timeout_s, trusted_local=trusted_local,
    )
    if not isinstance(payload, list):
        raise LeanIntrospectionError("Lean introspection payload must be a JSON array")
    return {entry["declaration"]: _finish_declaration(entry) for entry in payload}

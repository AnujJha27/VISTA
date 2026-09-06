"""Theorem binder/premise resolution engine (spec section 12): for one
selected entrypoint, resolve data binders via `dftcert.verification.
bindings`, then walk proposition binders left to right and try, in strict
order: (1) deterministic Lean-checked discharge, (3) leave as an explicit
external assumption -- decided by the caller, never here -- or (4) leave
unresolved. Route 2 (handing an undischarged premise to the existing
proof-search orchestrator) is out of scope for this phase; nothing here
forecloses wiring it in later at the same point Route 1 gives up.

Failure to discharge a premise deterministically is not evidence that it is
false (spec section 2.5/12.3) -- this module only ever reports `unresolved`,
never invents a witness of falsity.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from collections.abc import Sequence
from typing import Any

from ..manifest import ManifestError
from .bindings import resolve_data_binders
from .lean_inspect import run_marker_probe
from .model import FormalBindingCandidate

_MARKER = "VISTA_DISCHARGE_JSON:"

# Tried in order; the first that elaborates as a proof of the (fully
# data-instantiated) premise wins. Both are checked by Lean's kernel like
# any other proof -- this never "trusts" a tactic name.
_ROUTE1_TACTICS = ["rfl", "by decide"]

_PROBE = '''import Lean
{imports}

open Lean Elab Meta Command Term

private def vistaNameOfDotted (s : String) : Name :=
  (s.splitOn ".").foldl (fun n c => Name.mkStr n c) Name.anonymous

private def vistaCanonicalOptions : Options :=
  {canonical_options}

private def vistaTryElab (env : Environment) (exprStr : String) (expectedType : Expr) :
    TermElabM (Option Expr) := do
  try
    let stx ← ofExcept (Lean.Parser.runParserCategory env `term exprStr "<vista>")
    let e ← elabTermEnsuringType stx (some expectedType)
    Term.synthesizeSyntheticMVarsNoPostponing
    let e ← instantiateMVars e
    if e.hasExprMVar || e.hasSorry then
      return none
    return some e
  catch _ =>
    return none

#eval show CommandElabM Unit from do
  let env ← getEnv
  let entrypointName := vistaNameOfDotted {entrypoint}
  match env.find? entrypointName with
  | none =>
    logInfo m!"{marker}{{Json.mkObj [("error", Json.str "entrypoint not found")]}}"
  | some ci => liftTermElabM do
    let (mvars, _, concl) ← Meta.forallMetaTelescope ci.type
    let resolvedData : List (Nat × String) := {resolved_data}
    let tactics : List String := {tactics}
    let mut report : Array Json := #[]
    for i in [0:mvars.size] do
      let mvarId := mvars[i]!.mvarId!
      let expectedType ← instantiateMVars (← mvarId.getType)
      let isP ← Meta.isProp expectedType
      if isP then
        let display := toString (← Meta.ppExpr expectedType)
        let canonical := toString (← withOptions (fun _ => vistaCanonicalOptions) <| Meta.ppExpr expectedType)
        if expectedType.hasExprMVar then
          report := report.push (Json.mkObj [
            ("index", Json.str (toString i)), ("kind", Json.str "premise"),
            ("status", Json.str "unresolved"), ("type_display", Json.str display),
            ("type_fingerprint_source", Json.str canonical)])
        else
          let mut proved : Option (String × Expr) := none
          for tactic in tactics do
            if proved.isNone then
              match ← vistaTryElab env tactic expectedType with
              | some e => proved := some (tactic, e)
              | none => pure ()
          match proved with
          | some (tactic, e) =>
            mvarId.assign e
            report := report.push (Json.mkObj [
              ("index", Json.str (toString i)), ("kind", Json.str "premise"),
              ("status", Json.str "formally_discharged"), ("proof_tactic", Json.str tactic),
              ("type_display", Json.str display), ("type_fingerprint_source", Json.str canonical)])
          | none =>
            report := report.push (Json.mkObj [
              ("index", Json.str (toString i)), ("kind", Json.str "premise"),
              ("status", Json.str "unresolved"), ("type_display", Json.str display),
              ("type_fingerprint_source", Json.str canonical)])
      else
        match resolvedData.lookup i with
        | none =>
          report := report.push (Json.mkObj [("index", Json.str (toString i)), ("kind", Json.str "data"), ("status", Json.str "unresolved")])
        | some exprStr =>
          match ← vistaTryElab env exprStr expectedType with
          | some e =>
            mvarId.assign e
            report := report.push (Json.mkObj [("index", Json.str (toString i)), ("kind", Json.str "data"), ("status", Json.str "resolved")])
          | none =>
            report := report.push (Json.mkObj [("index", Json.str (toString i)), ("kind", Json.str "data"), ("status", Json.str "unresolved")])
    let conclInstantiated ← instantiateMVars concl
    let conclDisplay := toString (← Meta.ppExpr conclInstantiated)
    let conclCanonical := toString (← withOptions (fun _ => vistaCanonicalOptions) <| Meta.ppExpr conclInstantiated)
    report := report.push (Json.mkObj [
      ("kind", Json.str "conclusion"), ("type_display", Json.str conclDisplay),
      ("type_fingerprint_source", Json.str conclCanonical),
      ("has_unresolved_dependency", Json.bool conclInstantiated.hasExprMVar)])
    logInfo m!"{marker}{{(Json.arr report).compress}}"
'''

# Same canonical-fingerprint options as `lean_inspect`: fully qualified,
# no notation/unicode, every implicit shown -- never the display string.
_CANONICAL_PP_LEAN = (
    "(Options.empty)\n"
    "    |>.setBool `pp.all true\n"
    "    |>.setBool `pp.fullNames true\n"
    "    |>.setBool `pp.notation false\n"
    "    |>.setBool `pp.unicode false\n"
    "    |>.setBool `pp.universes true"
)


def _lean_string_literal(value: str) -> str:
    return json.dumps(value)


def _lean_pair_list(pairs: list[tuple[int, str]]) -> str:
    items = ", ".join(f"({index}, {_lean_string_literal(expr)})" for index, expr in pairs)
    return f"[{items}]"


def _lean_string_list(items: list[str]) -> str:
    return "[" + ", ".join(_lean_string_literal(item) for item in items) + "]"


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def discharge_premises(
    *, project_root: str | Path, imports: list[str], entrypoint: str,
    resolved_data: dict[int, str],
    lean_command: Sequence[str] = ("lake", "env", "lean", "-j", "1"),
    timeout_s: int = 300, trusted_local: bool = False,
) -> list[dict[str, Any]]:
    """Attempt Route 1 (deterministic Lean-checked discharge) for every
    proposition binder of `entrypoint`, given already-decided `resolved_data`
    (binder index -> Lean expression, from `bindings.resolve_data_binders`).
    A premise depending on a binder absent from `resolved_data` is reported
    `unresolved` -- never guessed, never treated as false."""
    if not entrypoint:
        raise ManifestError("discharge_premises needs an entrypoint")
    source = _PROBE.format(
        imports="\n".join(f"import {module}" for module in imports),
        canonical_options=_CANONICAL_PP_LEAN,
        entrypoint=_lean_string_literal(entrypoint),
        resolved_data=_lean_pair_list(sorted(resolved_data.items())),
        tactics=_lean_string_list(_ROUTE1_TACTICS),
        marker=_MARKER,
    )
    payload = run_marker_probe(
        project_root=project_root, source=source, marker=_MARKER,
        lean_command=lean_command, timeout_s=timeout_s, trusted_local=trusted_local,
    )
    if isinstance(payload, dict) and "error" in payload:
        raise ManifestError(f"premise discharge failed: {payload['error']}")
    if not isinstance(payload, list):
        raise ManifestError("premise discharge payload must be a JSON array")
    results = []
    for entry in payload:
        if "index" in entry:
            entry = {**entry, "index": int(entry["index"])}
        if "type_fingerprint_source" in entry:
            entry["type_fingerprint"] = _fingerprint(entry["type_fingerprint_source"])
        results.append(entry)
    return results


def resolve_entrypoint(
    *, project_root: str | Path, imports: list[str], entrypoint: str,
    candidates: Sequence[FormalBindingCandidate], forced_choices: dict[int, str] | None = None,
    lean_command: Sequence[str] = ("lake", "env", "lean", "-j", "1"),
    timeout_s: int = 300, trusted_local: bool = False,
) -> dict[str, Any]:
    """The full section-12 pipeline for one entrypoint: resolve data binders
    against adapter candidates, then attempt deterministic discharge of
    every proposition binder given whatever data got resolved. Returns
    `{"data_binders": [...], "premises": [...], "conclusion": {...}}` --
    the first two ordered by binder index; a caller (a
    `VerificationSession`) merges these into nodes and handles Route 3
    (explicit assumption) itself. `conclusion` is the target's own
    conclusion type, fully data-instantiated (its own
    `has_unresolved_dependency` flag says whether any data binder it needs
    is still unresolved/ambiguous)."""
    by_key = {candidate.key: candidate.lean_expr for candidate in candidates}
    data_results = resolve_data_binders(
        project_root=project_root, imports=imports, entrypoint=entrypoint,
        candidates=candidates, forced_choices=forced_choices,
        lean_command=lean_command, timeout_s=timeout_s, trusted_local=trusted_local,
    )
    resolved_data = {
        entry["index"]: by_key[entry["chosen_candidate_key"]]
        for entry in data_results if entry.get("status") == "resolved"
    }
    premise_results = discharge_premises(
        project_root=project_root, imports=imports, entrypoint=entrypoint,
        resolved_data=resolved_data, lean_command=lean_command,
        timeout_s=timeout_s, trusted_local=trusted_local,
    )
    premises_by_index = {entry["index"]: entry for entry in premise_results if entry["kind"] == "premise"}
    conclusion = next(entry for entry in premise_results if entry["kind"] == "conclusion")
    return {
        "data_binders": [entry for entry in data_results if entry["kind"] == "data"],
        "premises": [premises_by_index[index] for index in sorted(premises_by_index)],
        "conclusion": conclusion,
    }

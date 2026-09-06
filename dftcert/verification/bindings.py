"""Lean-checked data-binder resolution (spec section 11): never match a
theorem's data binders to adapter candidates by Python type-string or
binder-name heuristics -- ask Lean whether each candidate expression
actually elaborates against the binder's real (possibly earlier-binder-
dependent) type, one binder at a time, left to right.
"""
from __future__ import annotations

import json
from pathlib import Path
from collections.abc import Sequence
from typing import Any

from ..manifest import ManifestError
from .lean_inspect import run_marker_probe
from .model import FormalBindingCandidate

_MARKER = "VISTA_BINDING_JSON:"

_PROBE_HEADER = '''import Lean
{imports}

open Lean Elab Meta Command Term

private def vistaNameOfDotted (s : String) : Name :=
  (s.splitOn ".").foldl (fun n c => Name.mkStr n c) Name.anonymous

/-- Elaborate `exprStr` against `expectedType`; `none` on any elaboration
    failure (a wrong-typed candidate is rejected by Lean itself, never by
    Python string comparison -- spec section 27.3). -/
private def vistaTryElab (env : Environment) (exprStr : String) (expectedType : Expr) :
    TermElabM (Option Expr) := do
  try
    let stx ← ofExcept (Lean.Parser.runParserCategory env `term exprStr "<vista-candidate>")
    let e ← elabTermEnsuringType stx (some expectedType)
    Term.synthesizeSyntheticMVarsNoPostponing
    let e ← instantiateMVars e
    if e.hasExprMVar || e.hasSorry then
      return none
    return some e
  catch _ =>
    return none
'''

_PROBE_BODY = '''
#eval show CommandElabM Unit from do
  let env ← getEnv
  let entrypointName := vistaNameOfDotted {entrypoint}
  match env.find? entrypointName with
  | none =>
    logInfo m!"{marker}{{Json.mkObj [("error", Json.str "entrypoint not found")]}}"
  | some ci => liftTermElabM do
    let (mvars, _, _) ← Meta.forallMetaTelescope ci.type
    let forcedChoices : List (Nat × String) := {forced_choices}
    let candidates : List (String × String) := {candidates}
    let mut report : Array Json := #[]
    for i in [0:mvars.size] do
      let mvarId := mvars[i]!.mvarId!
      let expectedType ← instantiateMVars (← mvarId.getType)
      let isP ← Meta.isProp expectedType
      if isP then
        report := report.push (Json.mkObj [("index", Json.str (toString i)), ("kind", Json.str "premise")])
      else
        match forcedChoices.lookup i with
        | some key =>
          match candidates.lookup key with
          | none =>
            report := report.push (Json.mkObj [
              ("index", Json.str (toString i)), ("kind", Json.str "data"),
              ("status", Json.str "forced_choice_unknown_key"), ("chosen_candidate_key", Json.str key)])
          | some exprStr =>
            match ← vistaTryElab env exprStr expectedType with
            | some e =>
              mvarId.assign e
              report := report.push (Json.mkObj [
                ("index", Json.str (toString i)), ("kind", Json.str "data"), ("status", Json.str "resolved"),
                ("chosen_candidate_key", Json.str key), ("matching_candidate_keys", Json.arr #[Json.str key])])
            | none =>
              report := report.push (Json.mkObj [
                ("index", Json.str (toString i)), ("kind", Json.str "data"),
                ("status", Json.str "forced_choice_failed"), ("chosen_candidate_key", Json.str key)])
        | none =>
          let mut hits : Array (String × Expr) := #[]
          for (key, exprStr) in candidates do
            match ← vistaTryElab env exprStr expectedType with
            | some e => hits := hits.push (key, e)
            | none => pure ()
          if hits.size == 1 then
            mvarId.assign hits[0]!.2
            report := report.push (Json.mkObj [
              ("index", Json.str (toString i)), ("kind", Json.str "data"), ("status", Json.str "resolved"),
              ("chosen_candidate_key", Json.str hits[0]!.1),
              ("matching_candidate_keys", Json.arr (hits.map (fun m => Json.str m.1)))])
          else if hits.size == 0 then
            report := report.push (Json.mkObj [
              ("index", Json.str (toString i)), ("kind", Json.str "data"), ("status", Json.str "unresolved"),
              ("matching_candidate_keys", Json.arr #[])])
          else
            report := report.push (Json.mkObj [
              ("index", Json.str (toString i)), ("kind", Json.str "data"), ("status", Json.str "ambiguous_binding"),
              ("matching_candidate_keys", Json.arr (hits.map (fun m => Json.str m.1)))])
    logInfo m!"{marker}{{(Json.arr report).compress}}"
'''


def _lean_string_literal(value: str) -> str:
    return json.dumps(value)


def _lean_string_pair_list(pairs: list[tuple[Any, str]]) -> str:
    items = ", ".join(
        f"({key if isinstance(key, int) else _lean_string_literal(key)}, {_lean_string_literal(value)})"
        for key, value in pairs
    )
    return f"[{items}]"


def resolve_data_binders(
    *, project_root: str | Path, imports: list[str], entrypoint: str,
    candidates: Sequence[FormalBindingCandidate],
    forced_choices: dict[int, str] | None = None,
    lean_command: Sequence[str] = ("lake", "env", "lean", "-j", "1"),
    timeout_s: int = 300, trusted_local: bool = False,
) -> list[dict[str, Any]]:
    """For every binder of `entrypoint`'s telescope, in order: `kind:
    "premise"` for a Prop binder (left for `dftcert.verification.resolver`);
    otherwise `kind: "data"` with `status` one of `resolved` (with
    `chosen_candidate_key`), `ambiguous_binding`, `unresolved`, or -- for an
    already-decided `forced_choices` entry that no longer typechecks --
    `forced_choice_failed`. Never picks among multiple typechecking
    candidates itself (spec section 11)."""
    if not entrypoint:
        raise ManifestError("resolve_data_binders needs an entrypoint")
    candidate_pairs = [(candidate.key, candidate.lean_expr) for candidate in candidates]
    if len({key for key, _ in candidate_pairs}) != len(candidate_pairs):
        raise ManifestError("binding candidates must have distinct keys")
    source = (
        _PROBE_HEADER.format(imports="\n".join(f"import {module}" for module in imports))
        + _PROBE_BODY.format(
            entrypoint=_lean_string_literal(entrypoint),
            forced_choices=_lean_string_pair_list(list((forced_choices or {}).items())),
            candidates=_lean_string_pair_list(candidate_pairs),
            marker=_MARKER,
        )
    )
    payload = run_marker_probe(
        project_root=project_root, source=source, marker=_MARKER,
        lean_command=lean_command, timeout_s=timeout_s, trusted_local=trusted_local,
    )
    if isinstance(payload, dict) and "error" in payload:
        raise ManifestError(f"binding resolution failed: {payload['error']}")
    if not isinstance(payload, list):
        raise ManifestError("binding resolution payload must be a JSON array")
    return [{**entry, "index": int(entry["index"])} for entry in payload]

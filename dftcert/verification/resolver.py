"""Theorem binder/premise resolution engine: for one selected entrypoint,
walk its full binder telescope in Lean itself, recording real dependency
edges from Lean's own expression structure (never guessed from
pretty-printed text), then try, per proposition binder, deterministic
Lean-checked discharge, else leave it for the caller to accept as an
external assumption, or leave unresolved. Failure to discharge a premise
deterministically is not evidence it is false -- this module only ever
reports `unresolved`, never invents a witness of falsity.

Binder classes:
  explicit                -- tried against adapter candidates.
  instanceImplicit        -- tried against Lean's `synthInstance` first,
                             never offered artifact candidates.
  implicit/strictImplicit -- left unassigned for transitive unification by
                             a later explicit binder; genuinely unresolved
                             ones are reported as such, never guessed.

A single Lean invocation per entrypoint captures raw (pre-assignment)
binder types and dependency edges, resolves left to right, then reports
final status per binder.

Scope note: the full structural IR is always derived first from the raw
inventory alone, with no awareness of which entrypoint was selected; this
module then asks, per binder, whether one of those facts fills it.
Theorem-driven minimal IR construction is not implemented -- VISTA always
computes the plugin's full fixed fact set, and selection only chooses
among what already exists. This is a scope boundary, not a soundness gap.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from collections.abc import Sequence
from typing import Any

from ..manifest import ManifestError
from .lean_inspect import run_marker_probe
from .model import FormalBindingCandidate

_MARKER = "VISTA_RESOLVE_JSON:"

# Tried in order; each is checked by Lean's kernel like any other proof --
# this never "trusts" a tactic name.
_ROUTE1_TACTICS = ["rfl", "by decide"]

# Same canonical-fingerprint options as `lean_inspect`.
_CANONICAL_PP_LEAN = (
    "(Options.empty)\n"
    "    |>.setBool `pp.all true\n"
    "    |>.setBool `pp.fullNames true\n"
    "    |>.setBool `pp.notation false\n"
    "    |>.setBool `pp.unicode false\n"
    "    |>.setBool `pp.universes true"
)

_PROBE = '''import Lean
{imports}

open Lean Elab Meta Command Term

private def vistaNameOfDotted (s : String) : Name :=
  (s.splitOn ".").foldl (fun n c => Name.mkStr n c) Name.anonymous

private def vistaCanonicalOptions : Options :=
  {canonical_options}

private def vistaBinderInfoStr : BinderInfo → String
  | .default => "explicit"
  | .implicit => "implicit"
  | .strictImplicit => "strictImplicit"
  | .instImplicit => "instanceImplicit"

/-- Elaborate `exprStr` against `expectedType`; `none` on any elaboration
    failure (a wrong-typed candidate is rejected by Lean itself, never by
    Python string comparison). -/
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
    let (mvars, binfo, concl) ← Meta.forallMetaTelescope ci.type
    let forcedChoices : List (Nat × String) := {forced_choices}
    let candidates : List (String × String) := {candidates}
    let tactics : List String := {tactics}

    -- Phase 0: capture each binder's RAW (pre-assignment) type and its
    -- real dependency edges onto earlier binders, before anything is
    -- resolved/assigned -- so dependency detection is never confused by
    -- a later binder's own concrete substitution.
    let mut rawTypes : Array Expr := #[]
    let mut depEdges : Array (Array Nat) := #[]
    for i in [0:mvars.size] do
      let rawType ← mvars[i]!.mvarId!.getType
      rawTypes := rawTypes.push rawType
      let mentioned := (Lean.Expr.collectMVars {{}} rawType).result
      let mut deps : Array Nat := #[]
      for j in [0:i] do
        if mentioned.contains mvars[j]!.mvarId! then
          deps := deps.push j
      depEdges := depEdges.push deps

    -- Phase 1: resolve left to right, one binder at a time.
    let mut chosenKey : Array (Option String) := Array.replicate mvars.size none
    let mut matchingKeys : Array (Array String) := Array.replicate mvars.size #[]
    let mut proofTactic : Array (Option String) := Array.replicate mvars.size none
    let mut instanceSynthesized : Array Bool := Array.replicate mvars.size false
    let mut forcedChoiceUnknown : Array Bool := Array.replicate mvars.size false
    for i in [0:mvars.size] do
      let mvarId := mvars[i]!.mvarId!
      if !(← mvarId.isAssigned) then
        let expectedType ← instantiateMVars rawTypes[i]!
        let isP ← Meta.isProp expectedType
        if isP then
          if !expectedType.hasExprMVar then
            let mut proved : Bool := false
            for tactic in tactics do
              if !proved then
                match ← vistaTryElab env tactic expectedType with
                | some e =>
                  mvarId.assign e
                  proofTactic := proofTactic.set! i (some tactic)
                  proved := true
                | none => pure ()
        else
          let bInfo := vistaBinderInfoStr (binfo[i]!)
          if bInfo == "instanceImplicit" then
            try
              let inst ← Meta.synthInstance expectedType
              mvarId.assign inst
              instanceSynthesized := instanceSynthesized.set! i true
            catch _ => pure ()
          else if bInfo == "implicit" || bInfo == "strictImplicit" then
            pure () -- deliberately left for transitive unification, see module docstring
          else
            match forcedChoices.lookup i with
            | some key =>
              match candidates.lookup key with
              | none => forcedChoiceUnknown := forcedChoiceUnknown.set! i true
              | some exprStr =>
                match ← vistaTryElab env exprStr expectedType with
                | some e =>
                  mvarId.assign e
                  chosenKey := chosenKey.set! i (some key)
                | none => pure ()
            | none =>
              let mut hits : Array (String × Expr) := #[]
              for (key, exprStr) in candidates do
                match ← vistaTryElab env exprStr expectedType with
                | some e => hits := hits.push (key, e)
                | none => pure ()
              matchingKeys := matchingKeys.set! i (hits.map (fun h => h.1))
              if hits.size == 1 then
                mvarId.assign hits[0]!.2
                chosenKey := chosenKey.set! i (some hits[0]!.1)

    -- Phase 2: report final status per binder, reading back whatever
    -- Phase 1 (including transitive unification of implicit binders)
    -- actually assigned.
    let mut report : Array Json := #[]
    for i in [0:mvars.size] do
      let mvarId := mvars[i]!.mvarId!
      let bInfo := vistaBinderInfoStr (binfo[i]!)
      let finalType ← instantiateMVars rawTypes[i]!
      let isP ← Meta.isProp finalType
      let display := toString (← Meta.ppExpr finalType)
      let canonical := toString (← withOptions (fun _ => vistaCanonicalOptions) <| Meta.ppExpr finalType)
      let deps := depEdges[i]!
      let isAssignedNow ← mvarId.isAssigned
      if isP then
        let status := if isAssignedNow then "formally_discharged" else "unresolved"
        let mut fields := #[
          ("index", Json.str (toString i)), ("kind", Json.str "premise"),
          ("binder_info", Json.str bInfo), ("status", Json.str status),
          ("type_display", Json.str display), ("type_fingerprint_source", Json.str canonical),
          ("dependency_indices", Json.arr (deps.map (fun d => Json.str (toString d))))]
        fields := match proofTactic[i]! with
          | some tactic => fields.push ("proof_tactic", Json.str tactic)
          | none => fields
        report := report.push (Json.mkObj fields.toList)
      else
        let mut status := if isAssignedNow then "resolved" else "unresolved"
        -- Must be non-assigning: isDefEq would *assign* an unresolved
        -- mvar to Prop as a side effect, fabricating is_prop_sort for a
        -- still-unresolved binder. whnf + literal Sort 0 match instead.
        let isPropSort := match (← whnf finalType) with
          | .sort .zero => true
          | _ => false
        let mut fields := #[
          ("index", Json.str (toString i)), ("kind", Json.str "data"),
          ("binder_info", Json.str bInfo), ("is_prop_sort", Json.bool isPropSort),
          ("type_display", Json.str display), ("type_fingerprint_source", Json.str canonical),
          ("dependency_indices", Json.arr (deps.map (fun d => Json.str (toString d))))]
        if forcedChoiceUnknown[i]! then
          status := "forced_choice_unknown_key"
        else if instanceSynthesized[i]! then
          fields := fields.push ("resolution", Json.str "instance_synthesized")
        else
          match chosenKey[i]! with
          | some key => fields := fields.push ("chosen_candidate_key", Json.str key)
          | none => pure ()
          if matchingKeys[i]!.size > 1 then
            status := "ambiguous_binding"
            fields := fields.push ("matching_candidate_keys", Json.arr (matchingKeys[i]!.map (fun k => Json.str k)))
        fields := fields.push ("status", Json.str status)
        report := report.push (Json.mkObj fields.toList)

    let conclInstantiated ← instantiateMVars concl
    let conclDisplay := toString (← Meta.ppExpr conclInstantiated)
    let conclCanonical := toString (← withOptions (fun _ => vistaCanonicalOptions) <| Meta.ppExpr conclInstantiated)
    report := report.push (Json.mkObj [
      ("kind", Json.str "conclusion"), ("type_display", Json.str conclDisplay),
      ("type_fingerprint_source", Json.str conclCanonical),
      ("has_unresolved_dependency", Json.bool conclInstantiated.hasExprMVar)])
    logInfo m!"{marker}{{(Json.arr report).compress}}"
'''


def _lean_string_literal(value: str) -> str:
    return json.dumps(value)


def _lean_pair_list(pairs: list[tuple[Any, str]]) -> str:
    items = ", ".join(
        f"({key if isinstance(key, int) else _lean_string_literal(key)}, {_lean_string_literal(value)})"
        for key, value in pairs
    )
    return f"[{items}]"


def _lean_string_list(items: list[str]) -> str:
    return "[" + ", ".join(_lean_string_literal(item) for item in items) + "]"


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def resolve_entrypoint(
    *, project_root: str | Path, imports: list[str], entrypoint: str,
    candidates: Sequence[FormalBindingCandidate], forced_choices: dict[int, str] | None = None,
    lean_command: Sequence[str] = ("lake", "env", "lean", "-j", "1"),
    timeout_s: int = 300, trusted_local: bool = False,
) -> dict[str, Any]:
    """The full resolution pipeline for one entrypoint, in one Lean
    invocation: resolve every binder of its telescope (explicit against
    adapter candidates, instance-implicit via Lean's own typeclass
    synthesis, implicit/strict-implicit left for transitive unification),
    then attempt deterministic discharge of every proposition binder given
    whatever data got resolved. Returns `{"data_binders": [...],
    "premises": [...], "conclusion": {...}}`, the first two ordered by
    binder index and each carrying `binder_info` and `dependency_indices`
    (the earlier binder indices this binder's own type actually mentions,
    per Lean's own expression structure)."""
    if not entrypoint:
        raise ManifestError("resolve_entrypoint needs an entrypoint")
    candidate_pairs = [(candidate.key, candidate.lean_expr) for candidate in candidates]
    if len({key for key, _ in candidate_pairs}) != len(candidate_pairs):
        raise ManifestError("binding candidates must have distinct keys")
    source = _PROBE.format(
        imports="\n".join(f"import {module}" for module in imports),
        canonical_options=_CANONICAL_PP_LEAN,
        entrypoint=_lean_string_literal(entrypoint),
        forced_choices=_lean_pair_list(list((forced_choices or {}).items())),
        candidates=_lean_pair_list(candidate_pairs),
        tactics=_lean_string_list(_ROUTE1_TACTICS),
        marker=_MARKER,
    )
    payload = run_marker_probe(
        project_root=project_root, source=source, marker=_MARKER,
        lean_command=lean_command, timeout_s=timeout_s, trusted_local=trusted_local,
    )
    if isinstance(payload, dict) and "error" in payload:
        raise ManifestError(f"binder resolution failed: {payload['error']}")
    if not isinstance(payload, list):
        raise ManifestError("binder resolution payload must be a JSON array")
    entries = []
    for entry in payload:
        entry = dict(entry)
        if "index" in entry:
            entry["index"] = int(entry["index"])
        if "dependency_indices" in entry:
            entry["dependency_indices"] = [int(item) for item in entry["dependency_indices"]]
        if "type_fingerprint_source" in entry:
            entry["type_fingerprint"] = _fingerprint(entry["type_fingerprint_source"])
        entries.append(entry)
    conclusion = next(entry for entry in entries if entry["kind"] == "conclusion")
    return {
        "data_binders": sorted((e for e in entries if e["kind"] == "data"), key=lambda e: e["index"]),
        "premises": sorted((e for e in entries if e["kind"] == "premise"), key=lambda e: e["index"]),
        "conclusion": conclusion,
    }

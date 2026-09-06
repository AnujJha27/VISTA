"""Theorem-centric certificate generation (spec sections 19/23,
theorem-centric-gaps issues A/B/C): from a `ready_for_certificate` session,
construct the final wrapper theorem for the selected entrypoint using
Lean's own elaborator -- never Python string concatenation assuming every
data binder is an ordinary positional explicit argument. Lean itself:

  - assigns artifact-grounded/specified-interface explicit args and
    formally-discharged premise proofs;
  - synthesizes instance-implicit binders (`lean_resolved`,
    `resolution: instance_synthesized`);
  - leaves other `lean_resolved` (transitively-unified implicit) binders
    untouched, exactly as the resolver left them;
  - turns every `specified_assumption` binder (data or premise) into a
    genuine free binder of the generated theorem via `Meta.mkForallFVars`/
    `mkLambdaFVars` over a fresh metavariable, so a later binder's printed
    type shows its real name (`P`, not `?m.5`) rather than the previous
    "guess a companion Prop binder" heuristic;
  - refuses (raises) if any metavariable is left unassigned at the end --
    never silently guessing a value or coercing a type.

External assumptions survive as real theorem binders; none is ever
emitted as an `axiom` (spec section 13).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from ..manifest import ManifestError, sha256_value
from .lean_inspect import run_marker_probe

_MARKER = "VISTA_CERT_BUILD_JSON:"

# Embedded in the generated certificate source itself (issue C): the
# axiom closure of the *generated* `certificate` declaration, collected in
# the same compilation that type-checks it, since that declaration is a
# transient standalone file, never an importable module `lean_inspect`
# could look back up afterwards.
AXIOM_MARKER = "VISTA_CERT_AXIOMS_JSON:"
_AXIOM_MARKER_LINE = re.compile(re.escape(AXIOM_MARKER) + r"(.*)$")

_PROBE = '''import Lean
{imports}

open Lean Elab Meta Command Term

private def vistaNameOfDotted (s : String) : Name :=
  (s.splitOn ".").foldl (fun n c => Name.mkStr n c) Name.anonymous

-- The generated certificate source must actually RE-ELABORATE correctly
-- in a fresh Lean process, independent of this process's own elaboration
-- order/side effects (e.g. an implicit `{{n : Nat}}` transitively unified
-- here from a later explicit argument's own concrete value must still be
-- determinable when the printed text is re-parsed from scratch) -- so
-- every implicit/instance argument and numeral's type must be shown
-- explicitly, never relying on inference to reconstruct what THIS
-- process already knows.
private def vistaExplicitOptions : Options :=
  (Options.empty)
    |>.setBool `pp.implicit true
    |>.setBool `pp.instances true
    |>.setBool `pp.numericTypes true
    |>.setBool `pp.coercions.types true

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
    logInfo m!"{marker}{{(Json.mkObj [("status", Json.str "error"), ("message", Json.str "entrypoint not found")]).compress}}"
  | some ci => liftTermElabM do
    let (mvars, _binfo, concl) ← Meta.forallMetaTelescope ci.type
    let artifactAssignments : List (Nat × String) := {artifact_assignments}
    let proofAssignments : List (Nat × String) := {proof_assignments}
    let instanceIndices : List Nat := {instance_indices}
    let freeIndices : List (Nat × String) := {free_indices}
    let mut freeMvars : Array Expr := #[]
    let mut errorMsg : Option String := none
    for i in [0:mvars.size] do
      if errorMsg.isNone then
        let mvarId := mvars[i]!.mvarId!
        if !(← mvarId.isAssigned) then
          match artifactAssignments.lookup i with
          | some exprStr =>
            let expectedType ← instantiateMVars (← mvarId.getType)
            match ← vistaTryElab env exprStr expectedType with
            | some e => mvarId.assign e
            | none => errorMsg := some s!"artifact expression for binder {{i}} failed to elaborate against its type"
          | none =>
            match proofAssignments.lookup i with
            | some tactic =>
              let expectedType ← instantiateMVars (← mvarId.getType)
              match ← vistaTryElab env tactic expectedType with
              | some e => mvarId.assign e
              | none => errorMsg := some s!"proof term for binder {{i}} failed to re-elaborate against its type"
            | none =>
              if instanceIndices.contains i then
                let expectedType ← instantiateMVars (← mvarId.getType)
                try
                  let inst ← Meta.synthInstance expectedType
                  mvarId.assign inst
                catch _ =>
                  errorMsg := some s!"instance synthesis for binder {{i}} failed"
              else
                match freeIndices.lookup i with
                | some name =>
                  let expectedType ← instantiateMVars (← mvarId.getType)
                  -- `expectedType` may legitimately still mention EARLIER
                  -- free binders (e.g. `h : P ∧ Q` after `P`/`Q` were
                  -- frozen into fresh named mvars just above) -- that is
                  -- exactly the intended shape `mkForallFVars`/
                  -- `mkLambdaFVars` will later abstract over, not an
                  -- unresolved dependency. Only reject if some OTHER,
                  -- non-free mvar remains.
                  let mentioned := (Lean.Expr.collectMVars {{}} expectedType).result
                  let freeMvarIds := freeMvars.map (fun m => m.mvarId!)
                  if mentioned.any (fun m => !freeMvarIds.contains m) then
                    errorMsg := some s!"free binder {{i}} ({{name}}) still has unresolved dependencies"
                  else
                    let fresh ← mkFreshExprMVar (some expectedType) (userName := Name.mkSimple name)
                    mvarId.assign fresh
                    freeMvars := freeMvars.push fresh
                | none => pure () -- left for transitive unification by a later binder
    if errorMsg.isNone then
      for i in [0:mvars.size] do
        if errorMsg.isNone then
          if !(← mvars[i]!.mvarId!.isAssigned) then
            errorMsg := some s!"binder {{i}} has no recorded resolution and was never assigned -- refusing to guess"
    match errorMsg with
    | some msg =>
      logInfo m!"{marker}{{(Json.mkObj [("status", Json.str "error"), ("message", Json.str msg)]).compress}}"
    | none =>
      let finalConcl ← instantiateMVars concl
      let finalApp ← instantiateMVars (mkAppN (mkConst entrypointName (ci.levelParams.map Level.param)) mvars)
      try
        let wrapperType ← mkForallFVars freeMvars finalConcl (binderInfoForMVars := BinderInfo.default)
        let wrapperValue ← mkLambdaFVars freeMvars finalApp (binderInfoForMVars := BinderInfo.default)
        check wrapperValue
        let typeStr := toString (← withOptions (fun _ => vistaExplicitOptions) <| Meta.ppExpr wrapperType)
        let valueStr := toString (← withOptions (fun _ => vistaExplicitOptions) <| Meta.ppExpr wrapperValue)
        logInfo m!"{marker}{{(Json.mkObj [("status", Json.str "ok"), ("type", Json.str typeStr), ("value", Json.str valueStr)]).compress}}"
      catch ex =>
        let msg ← ex.toMessageData.toString
        logInfo m!"{marker}{{(Json.mkObj [("status", Json.str "error"), ("message", Json.str msg)]).compress}}"
'''


def _ordered_nodes(session: dict[str, Any], entrypoint: str) -> list[tuple[str, dict[str, Any]]]:
    entries = [
        (node_id, node) for node_id, node in session["nodes"].items()
        if node["entrypoint"] == entrypoint
    ]
    return sorted(entries, key=lambda item: int(item[1]["binder_path"]))


def _lean_string_literal(value: str) -> str:
    return json.dumps(value)


def _lean_pair_list(pairs: list[tuple[int, str]]) -> str:
    items = ", ".join(f"({index}, {_lean_string_literal(value)})" for index, value in pairs)
    return f"[{items}]"


def _lean_index_list(indices: list[int]) -> str:
    return "[" + ", ".join(str(index) for index in indices) + "]"


def generate_certificate_source(
    *, session: dict[str, Any], entrypoint: str, namespace: str, lean_import: str,
    project_root: str | Path, imports: list[str] | None = None,
    lean_command=("lake", "env", "lean", "-j", "1"), timeout_s: int = 300, trusted_local: bool = False,
) -> str:
    """The generated wrapper theorem's full Lean source, ready to append
    after `import {lean_import}`. Raises if any node this target's root
    set depends on is not in a resolved/discharged/assumed state -- no
    certificate may be assembled while a required premise is unresolved
    (spec section 19) -- or if Lean itself refuses the constructed
    application (spec/theorem-centric-gaps issue A: Lean, not Python
    string assembly, determines the final application)."""
    nodes = _ordered_nodes(session, entrypoint)
    if not nodes:
        raise ManifestError(f"no nodes recorded for entrypoint {entrypoint!r}")

    artifact_assignments: list[tuple[int, str]] = []
    proof_assignments: list[tuple[int, str]] = []
    instance_indices: list[int] = []
    free_indices: list[tuple[int, str]] = []
    for node_id, node in nodes:
        index = int(node["binder_path"])
        name = node["binder_name"]
        status = node["status"]
        if node["kind"] == "data":
            if status in {"artifact_grounded", "specified_interface"}:
                artifact_assignments.append((index, node["lean_expr"]))
            elif status == "lean_resolved" and node.get("resolution") == "instance_synthesized":
                instance_indices.append(index)
            elif status == "lean_resolved":
                pass  # transitive unification -- left for Lean to have already resolved
            elif status == "specified_assumption":
                free_indices.append((index, name))
            else:
                raise ManifestError(f"cannot generate certificate: node {node_id!r} is {status!r}, not resolved")
        else:
            if status == "formally_discharged":
                proof_assignments.append((index, node["proof_result_ref"]))
            elif status == "specified_assumption":
                free_indices.append((index, name))
            else:
                raise ManifestError(f"cannot generate certificate: node {node_id!r} is {status!r}, not resolved")

    modules = imports if imports is not None else [lean_import]
    source = _PROBE.format(
        imports="\n".join(f"import {module}" for module in modules),
        entrypoint=_lean_string_literal(entrypoint),
        artifact_assignments=_lean_pair_list(artifact_assignments),
        proof_assignments=_lean_pair_list(proof_assignments),
        instance_indices=_lean_index_list(instance_indices),
        free_indices=_lean_pair_list(free_indices),
        marker=_MARKER,
    )
    payload = run_marker_probe(
        project_root=project_root, source=source, marker=_MARKER,
        lean_command=lean_command, timeout_s=timeout_s, trusted_local=trusted_local,
    )
    if payload.get("status") != "ok":
        raise ManifestError(f"certificate construction failed: {payload.get('message')}")

    lines = [
        *(f"import {module}" for module in ["Lean", *modules]),
        "",
        f"namespace {namespace}",
        "",
        f"theorem certificate : {payload['type']} :=",
        f"  {payload['value']}",
        "",
        # Issue C: the axiom closure of THIS generated declaration,
        # collected in the same compilation that type-checks it (it is
        # never saved as an importable module `lean_inspect` could look
        # up afterwards).
        "#eval show Lean.Elab.Command.CommandElabM Unit from do",
        f"  let axioms ← Lean.collectAxioms (`{namespace}.certificate)",
        f'  Lean.logInfo m!"{AXIOM_MARKER}{{(Lean.Json.arr (axioms.map (fun n => Lean.Json.str n.toString))).compress}}"',
        "",
        f"end {namespace}",
        "",
    ]
    return "\n".join(lines)


def parse_certificate_axiom_closure(diagnostics: str) -> list[str]:
    """Extract the generated certificate declaration's own axiom closure
    (issue C) from the compile diagnostics `dftcert.structural.core.
    verify_structural_certificate` returns for the same generated source
    -- never a substitute for it (the selected entrypoint's own closure,
    from `lean_inspect.inspect_declarations`, is recorded separately, for
    audit only)."""
    matches = [
        match.group(1) for line in diagnostics.splitlines()
        for match in [_AXIOM_MARKER_LINE.search(line)] if match
    ]
    if not matches:
        raise ManifestError(
            "compiled certificate source did not emit its axiom-closure marker "
            "-- cannot certify without inspecting the generated declaration's own axioms"
        )
    return json.loads(matches[-1])


def assemble_certificate_report(
    *, session: dict[str, Any], package: dict[str, Any], entrypoint: str,
    certificate_source: str, entrypoint_axiom_closure: list[str],
    certificate_axiom_closure: list[str], allowed_axioms: frozenset[str],
) -> dict[str, Any]:
    """The distinguishing report (spec section 19): every node's provenance
    class, the axiom closure, and whether the result is conditional on any
    external assumption. Does not itself invoke Lean -- pass in the
    already-computed axiom closures and the compiled `certificate_source`'s
    own status separately.

    theorem-centric-gaps issue C: `certificate_axiom_closure` (the axiom
    closure of the *generated* `certificate` declaration itself, not the
    selected entrypoint) is what gates certification -- a resolved data
    binder's own Lean expression, or a future adapter's helper constants,
    could depend on an axiom the entrypoint theorem itself never
    mentions. `entrypoint_axiom_closure` is recorded for audit only."""
    nodes = dict(_ordered_nodes(session, entrypoint))
    if "sorryAx" in certificate_axiom_closure:
        raise ManifestError("certificate blocked: generated certificate's axiom closure includes sorryAx")
    blocking_axioms = sorted(set(certificate_axiom_closure) - allowed_axioms)
    if blocking_axioms:
        raise ManifestError(f"certificate blocked: non-allowlisted axioms {blocking_axioms}")
    by_status: dict[str, list[str]] = {}
    for node_id, node in nodes.items():
        by_status.setdefault(node["status"], []).append(node_id)
    unresolved = [
        *by_status.get("unresolved", []), *by_status.get("ambiguous_binding", []),
    ]
    if unresolved:
        raise ManifestError(f"certificate blocked: unresolved/ambiguous nodes {unresolved}")
    assumptions = [
        node["external_assumption"] for node in nodes.values()
        if node["status"] == "specified_assumption" and node["kind"] == "premise"
    ]
    # Spec section 18: the certificate records exactly which IR provenance
    # nodes actually supported a selected theorem's binders -- not a new
    # general-purpose IR projection, just this target's own evidence_refs.
    used_facts = sorted({ref for node in nodes.values() for ref in node.get("evidence_refs", [])})
    report = {
        "status": "certified",
        "entrypoint": entrypoint,
        "conditional": bool(assumptions),
        "external_assumptions": assumptions,
        "used_facts": used_facts,
        "artifact_grounded_nodes": by_status.get("artifact_grounded", []),
        "specified_interface_nodes": by_status.get("specified_interface", []),
        "lean_resolved_nodes": by_status.get("lean_resolved", []),
        "formally_discharged_nodes": by_status.get("formally_discharged", []),
        "specified_assumption_nodes": by_status.get("specified_assumption", []),
        "entrypoint_axiom_closure": sorted(entrypoint_axiom_closure),
        "certificate_axiom_closure": sorted(certificate_axiom_closure),
        "artifact_binding": session["artifact_binding"],
        "adapter_binding": session["adapter_binding"],
        "formal_package_binding": session["formal_package_binding"],
        "ir_sha256": session["ir_sha256"],
        "certificate_source_sha256": hashlib.sha256(certificate_source.encode()).hexdigest(),
    }
    report["report_sha256"] = sha256_value(report)
    return report

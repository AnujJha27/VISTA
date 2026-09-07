"""The domain-agnostic VISTA structural-verification harness.

Extraction plumbing, hashing, translation-validation re-derivation,
certificate assembly/binding, and Lean invocation live here and know nothing
about any one verification domain. Everything domain-specific is behind the
`StructuralPlugin` interface (`dftcert.structural.plugin`); every public
function below takes a `plugin` argument defaulting to `DFT_CAPABILITY_PLUGIN`
(`dftcert.structural.dft_capability_plugin`), the project's only plugin, so
existing callers keep working unchanged. See `docs/structural-v2/VISTA_GENERALIZATION.md`.
"""
from __future__ import annotations

import hashlib
import os
import re
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from collections.abc import Sequence
from typing import Any

from ..certificate import project_fingerprint
from ..manifest import ManifestError, proof_result_map, sha256_value
from .dft_capability_plugin import DFT_CAPABILITY_PLUGIN
from .plugin import StructuralPlugin

_FORBIDDEN = re.compile(r"\b(sorry|admit|axiom|unsafe)\b")


def _lean_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def structural_ir_from_inventory(
    *, inventory: dict[str, Any], artifact_sha256: str, extractor_version: str,
    input_constraints: dict[str, Any], plugin: StructuralPlugin = DFT_CAPABILITY_PLUGIN,
) -> dict[str, Any]:
    nodes = inventory.get("nodes")
    if not isinstance(nodes, list) or any(not isinstance(node, dict) for node in nodes):
        raise ManifestError("artifact graph inventory is malformed")
    roles = plugin.role_roots(nodes, input_constraints)
    derivation = plugin.derive(inventory=inventory, nodes=nodes, roles=roles, input_constraints=input_constraints)
    inventory_sha256 = sha256_value(inventory)
    state = inventory.get("state", {})
    # Deliberately excludes each tensor's own `sha256` (a content hash of its
    # raw bytes -- for a float parameter, its actual trained values). This
    # fingerprints only the architecture -- shape, dtype, extractor-declared
    # kind, storage aliasing -- so it is unaffected by training and cannot
    # be used, even indirectly through a hash, as evidence about what a
    # parameter's trained values are.
    parameter_structure = {
        name: {
            "shape": value.get("shape"),
            "dtype": value.get("dtype"),
            "state_kind": value.get("state_kind"),
            "aliases": value.get("aliases", [name]),
        }
        for name, value in state.items()
        if isinstance(name, str) and isinstance(value, dict)
    } if isinstance(state, dict) else {}
    translation = {
        "inventory_sha256": inventory_sha256,
        **plugin.translation_sections(derivation=derivation, roles=roles, input_constraints=input_constraints),
    }
    value = {
        "ir_schema_version": plugin.ir_schema_version,
        "source": {
            "kind": "torch_export",
            "artifact_sha256": artifact_sha256,
            "inventory_sha256": inventory_sha256,
            "extractor_version": extractor_version,
            "analyzer_version": plugin.analyzer_version,
            "parameter_structure_sha256": sha256_value(parameter_structure),
            "translation_sha256": sha256_value(translation),
        },
        **plugin.ir_sections(derivation=derivation, input_constraints=input_constraints),
        "translation": translation,
    }
    validate_structural_ir(value, plugin=plugin)
    value["translation_validation"] = validate_translation(
        inventory=inventory, value=value, input_constraints=input_constraints,
        artifact_sha256=artifact_sha256, plugin=plugin,
    )
    return value


def validate_structural_ir(value: dict[str, Any], *, plugin: StructuralPlugin = DFT_CAPABILITY_PLUGIN) -> None:
    if not isinstance(value, dict) or value.get("ir_schema_version") != plugin.ir_schema_version:
        raise ManifestError(f"structural IR must use schema version {plugin.ir_schema_version}")
    source = value.get("source")
    if not isinstance(source, dict) or source.get("kind") not in {
        "torch_export", "confirmed_description"
    }:
        raise ManifestError("structural IR source is invalid")
    translation = value.get("translation")
    if source.get("kind") == "torch_export":
        if not isinstance(translation, dict) or source.get("translation_sha256") != sha256_value(translation):
            raise ManifestError("artifact structural IR needs a hash-bound translation derivation")
    plugin.validate_ir_sections(value)


def validate_translation(
    *, inventory: dict[str, Any], value: dict[str, Any], input_constraints: dict[str, Any],
    artifact_sha256: str | None = None, plugin: StructuralPlugin = DFT_CAPABILITY_PLUGIN,
) -> dict[str, Any]:
    """Independently recheck an artifact IR's derivation against raw graph inventory."""
    validate_structural_ir(value, plugin=plugin)
    if value["source"]["kind"] != "torch_export":
        raise ManifestError("only exported artifacts have a translation derivation")
    if artifact_sha256 is not None and value["source"].get("artifact_sha256") != artifact_sha256:
        raise ManifestError("structural IR source artifact hash does not match the extracted artifact")
    translation = value["translation"]
    if translation.get("inventory_sha256") != sha256_value(inventory):
        raise ManifestError("translation derivation is bound to a different inventory")
    nodes = inventory.get("nodes")
    if not isinstance(nodes, list) or any(not isinstance(node, dict) for node in nodes):
        raise ManifestError("translation validation needs a graph-node inventory")
    roles = plugin.role_roots(nodes, input_constraints)
    if translation.get("roles") != roles:
        raise ManifestError("translation output roles do not match the raw exported graph")
    derivation = plugin.derive(inventory=inventory, nodes=nodes, roles=roles, input_constraints=input_constraints)
    plugin.revalidate(
        inventory=inventory, value=value, input_constraints=input_constraints,
        derivation=derivation, roles=roles,
    )
    return {
        "status": "translation_validated",
        "translation_sha256": sha256_value(translation),
        "inventory_sha256": sha256_value(inventory),
        "checked_claims": ["output_roles", *plugin.checked_claim_names()],
    }


def assess_structural_ir(value: dict[str, Any], *, plugin: StructuralPlugin = DFT_CAPABILITY_PLUGIN) -> dict[str, Any]:
    validate_structural_ir(value, plugin=plugin)
    checks = plugin.checks(value)
    supported = plugin.supported(value)
    disposition = (
        "formalization_required" if not supported
        else "structurally_certifiable" if all(item["satisfied"] for item in checks.values())
        else "structural_requirements_not_met"
    )
    return {
        "status": disposition,
        "ir_sha256": sha256_value(value),
        "source": value["source"],
        "checks": checks,
    }


def structural_failure_witnesses(
    value: dict[str, Any], *, plugin: StructuralPlugin = DFT_CAPABILITY_PLUGIN,
) -> list[dict[str, Any]]:
    assessment = assess_structural_ir(value, plugin=plugin)
    return [
        plugin.failure_witness(name, check)
        for name, check in assessment["checks"].items()
        if not check["satisfied"]
    ]


def structural_report(value: dict[str, Any], *, plugin: StructuralPlugin = DFT_CAPABILITY_PLUGIN) -> dict[str, Any]:
    """Human-facing evidence report; it does not upgrade any trust boundary."""
    assessment = assess_structural_ir(value, plugin=plugin)
    source = value["source"]
    checks = assessment["checks"]
    what_was_checked = plugin.what_was_checked()
    return {
        "report_schema_version": plugin.ir_schema_version,
        "status": assessment["status"],
        "certificate_kind": "artifact" if source["kind"] == "torch_export" else "confirmed_specification",
        "plain_summary": (
            "The exported graph passed every supported structural requirement."
            if assessment["status"] == "structurally_certifiable" else
            "The model is not structurally certifiable under the selected requirements; see concrete witnesses."
            if assessment["status"] == "structural_requirements_not_met" else
            "The exported graph uses a construction outside the currently formalized structural vocabulary."
        ),
        "source_binding": source,
        "translation_validation": value.get("translation_validation"),
        "checks": [
            {
                "name": name,
                "satisfied": check["satisfied"],
                "what_was_checked": what_was_checked[name],
                "evidence": check,
            }
            for name, check in checks.items()
        ],
        "failure_witnesses": structural_failure_witnesses(value, plugin=plugin),
        "trust_boundary": plugin.trust_boundary_lines(),
    }


def structural_model_description(
    value: dict[str, Any], *, plugin: StructuralPlugin = DFT_CAPABILITY_PLUGIN,
) -> str:
    """Readable, deterministic context for local proof agents and reports."""
    validate_structural_ir(value, plugin=plugin)
    source = value["source"]
    translation = value.get("translation", {})
    lines = [
        "Structural report context (deterministic, not an LLM interpretation) --"
        " combines the analyst's declared interface/requirements with facts"
        " derived from the exported graph; individual lines below say which is which:",
        f"- Source: {source['kind']}; binding hash: {source.get('artifact_sha256', source.get('description_sha256', 'unknown'))}.",
        *plugin.model_description_lines(value),
    ]
    if source["kind"] == "torch_export":
        lines.extend([
            f"- Declared output roots (specified): {translation.get('roles', {})}.",
            f"- Adjacency evidence (derived): state {translation.get('topology', {}).get('state_name')!r}; graph nodes {translation.get('topology', {}).get('adjacency_aliases', [])}.",
            "- Translation validation independently rechecked every derived claim above against the raw exported inventory.",
        ])
    lines.append(
        "Scope: pre-training architectural capability only; VISTA never uses trained "
        "parameter values as verification evidence, and this does not assess training "
        "convergence, numerical accuracy, or experiment."
    )
    return "\n".join(lines)


def generate_structural_obligations(
    value: dict[str, Any], *, plugin: StructuralPlugin = DFT_CAPABILITY_PLUGIN,
) -> dict[str, Any]:
    assessment = assess_structural_ir(value, plugin=plugin)
    source = value["source"]
    source_hash = (
        source.get("artifact_sha256") or source.get("description_sha256")
    )
    if not isinstance(source_hash, str) or not source_hash:
        raise ManifestError("structural IR source hash is missing")
    ir_hash = assessment["ir_sha256"]
    namespace = f"DFTCert.StructuralRun_{ir_hash[:12]}"
    preamble = (
        f"namespace {namespace}\n\n"
        f'def sourceSha256 : String := "{_lean_string(source_hash)}"\n'
        f'def irSha256 : String := "{ir_hash}"\n'
        f"{plugin.lean_preamble_fields(value, namespace)}\n\n"
        f"end {namespace}\n"
    )
    statements = plugin.lean_statements(value, namespace, assessment["checks"])
    expected = {fact: assessment["checks"][fact]["satisfied"] for fact in statements}
    tasks = []
    for fact, theorem in statements.items():
        tasks.append({
            "id": f"{ir_hash[:12]}-{fact}",
            "fact": fact,
            "status": "proof_required",
            "project": "testv2",
            "module": plugin.lean_import,
            "verification_mode": "generated_obligation",
            "theorem": theorem,
            "preamble": preamble,
            "preamble_sha256": hashlib.sha256(preamble.encode()).hexdigest(),
            "structural_expected": expected[fact],
            "ir_sha256": ir_hash,
            "source_sha256": source_hash,
            "context": (
                structural_model_description(value, plugin=plugin) + "\n\n"
                + f"VISTA obligation generated deterministically from the common IR by the "
                f"{plugin.name!r} plugin. Prove the exact Boolean structural result. Prefer "
                "`by decide`, whose result is reduced by Lean's kernel for this small finite input."
            ),
            "subgoals": [{
                "id": f"evaluate-{fact}",
                "theorem": theorem,
                "depends_on": [],
                "context": "Reduce the generic structural checker on the generated finite data.",
            }],
            "limits": {"wall_time_ms": 600000, "cpu_time_s": 480, "memory_mb": 8192},
        })
    return {
        "status": "obligations_generated",
        "compiler_version": plugin.compiler_version,
        "ir_sha256": ir_hash,
        "source_sha256": source_hash,
        "policy_version": plugin.policy_version,
        "disposition": assessment["status"],
        "assessment": assessment,
        "failure_witnesses": structural_failure_witnesses(value, plugin=plugin),
        "obligations": tasks,
    }


def assemble_structural_certificate(
    value: dict[str, Any], proof_results: Any, *, plugin: StructuralPlugin = DFT_CAPABILITY_PLUGIN,
) -> tuple[str, dict[str, Any]]:
    generated = generate_structural_obligations(value, plugin=plugin)
    translation_validation = value.get("translation_validation")
    if value["source"]["kind"] == "torch_export" and (
        not isinstance(translation_validation, dict)
        or translation_validation.get("status") != "translation_validated"
        or translation_validation.get("translation_sha256")
        != value["source"].get("translation_sha256")
    ):
        raise ManifestError("artifact certificate assembly requires a validated translation derivation")
    results = proof_result_map(proof_results)
    declarations: list[str] = []
    evidence: list[dict[str, Any]] = []
    for task in generated["obligations"]:
        result = results.get(task["id"])
        if not result or result.get("status") != "verified":
            raise ManifestError(f"obligation {task['id']!r} has no verified result")
        winner = result.get("winner")
        patch = winner.get("patch") if isinstance(winner, dict) else None
        if not isinstance(patch, str) or not patch.strip() or _FORBIDDEN.search(patch):
            raise ManifestError(f"obligation {task['id']!r} has an unsafe or missing winner")
        declarations.append(f"{task['theorem']} := {patch}\n")
        evidence.append({
            "id": task["id"],
            "fact": task["fact"],
            "proof_sha256": hashlib.sha256(patch.encode()).hexdigest(),
            "orchestrator_status": "verified",
        })
    namespace = f"DFTCert.StructuralRun_{generated['ir_sha256'][:12]}"
    source = (
        f"import {plugin.lean_import}\n\n"
        + generated["obligations"][0]["preamble"] + "\n"
        + "\n".join(declarations) + "\n"
        + f"theorem generated_source_binding : {namespace}.sourceSha256 = "
        + f"\"{generated['source_sha256']}\" := rfl\n"
        + f"theorem generated_ir_binding : {namespace}.irSha256 = "
        + f"\"{generated['ir_sha256']}\" := rfl\n\n"
        + f"#check (generated_source_binding : {namespace}.sourceSha256 = "
        + f"\"{generated['source_sha256']}\")\n"
        + f"#check (generated_ir_binding : {namespace}.irSha256 = "
        + f"\"{generated['ir_sha256']}\")\n"
    )
    source_kind = value["source"]["kind"]
    report = {
        "report_schema_version": plugin.ir_schema_version,
        "status": "assembled_pending_certificate_check",
        "certificate_kind": (
            "artifact" if source_kind == "torch_export" else "confirmed_specification"
        ),
        "policy_version": plugin.policy_version,
        "compiler_version": plugin.compiler_version,
        "source": value["source"],
        "source_sha256": generated["source_sha256"],
        "ir_sha256": generated["ir_sha256"],
        "capabilities": value.get("capabilities"),
        "certificate_source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "structural_disposition": generated["disposition"],
        "failure_witnesses": generated["failure_witnesses"],
        "translation_validation": translation_validation,
        "obligations": evidence,
    }
    report["report_sha256"] = sha256_value(report)
    return source, report


def verify_structural_certificate(
    *, project_root: str | Path, certificate_source: str | Path,
    lean_command: Sequence[str] = ("lake", "env", "lean", "-j", "1"),
    timeout_s: int = 60, trusted_local: bool = False,
) -> dict[str, Any]:
    if not trusted_local:
        raise ManifestError(
            "certificate compilation requires --trusted-local until a compiler sandbox is configured"
        )
    if not lean_command:
        raise ManifestError("Lean command cannot be empty")
    root = Path(project_root).resolve()
    source_path = Path(certificate_source).resolve()
    source = source_path.read_text(encoding="utf-8")
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="dftcert-v2-") as directory:
        check = Path(directory) / "StructuralCertificateCheck.lean"
        check.write_text(source, encoding="utf-8")
        # `lake env lean` forks a `lean` child rather than exec-ing into it,
        # so killing only the direct child on timeout leaks a runaway `lean`
        # process that then contends with later invocations. Run it in its
        # own process group (POSIX only) so a timeout can take the whole
        # group down via Popen directly (subprocess.run's timeout only kills
        # the immediate child).
        popen_kwargs: dict[str, Any] = {}
        if hasattr(os, "setsid"):
            popen_kwargs["start_new_session"] = True
        handle = subprocess.Popen(
            [*lean_command, str(check)], cwd=root,
            encoding="utf-8", errors="replace",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            **popen_kwargs,
        )
        try:
            stdout, _ = handle.communicate(timeout=timeout_s)
            status = "verified" if handle.returncode == 0 else "lean_error"
            diagnostics = stdout
        except subprocess.TimeoutExpired:
            status = "timeout"
            if "start_new_session" in popen_kwargs:
                try:
                    os.killpg(os.getpgid(handle.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                handle.kill()
            diagnostics = f"timed out after {timeout_s}s (process group terminated)"
            handle.wait(timeout=10)
    return {
        "version": 2,
        "status": status,
        "project_root": str(root),
        "project_fingerprint": project_fingerprint(root),
        "certificate_source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "diagnostics": diagnostics,
    }


def confirmed_description_ir(
    *, description: str, topology: dict[str, Any], message_passing: dict[str, Any],
    xc: dict[str, Any], operator: dict[str, Any], locality: dict[str, Any],
    confirmed_claims: list[dict[str, Any]] | None = None,
    plugin: StructuralPlugin = DFT_CAPABILITY_PLUGIN,
) -> dict[str, Any]:
    """Human-confirmed (no artifact) specification path. Not yet routed
    through the plugin interface -- still DFT-shaped regardless of `plugin`.
    See docs/structural-v2/VISTA_GENERALIZATION.md open questions.

    `locality` is the human's confirmed claim (`{"expected": "local" |
    "non_local"}`) -- kept as the parameter/CLI name since that is the
    property a human is actually attesting to, but it is lowered here into
    the `capabilities` shape the (pre-training) plugin's IR actually uses,
    not a real-weight `locality` observation (there are no extracted values
    in this path at all)."""
    description_hash = hashlib.sha256(description.encode()).hexdigest()
    expected_locality = locality.get("expected")
    if expected_locality not in {"local", "non_local"}:
        raise ManifestError("locality.expected must be 'local' or 'non_local'")
    # A human-confirmed specification has no real extracted tensor to declare
    # a grouped domain/codomain axis layout for; default to the plain n x n
    # matrix layout unless the confirmed claims say otherwise, so existing
    # confirmed-description operator claims (which never mentioned a layout)
    # keep working unchanged.
    operator = {"layout": {"output_axes": [0], "input_axes": [1]}, **operator}
    # A pure English-description specification has no message-passing graph
    # to trace either: the coverage claim is vacuously true/not-applicable,
    # exactly like every recipe this plugin currently recognizes from a real
    # artifact. A human confirms non-local capacity directly, mirroring how
    # they already confirm topology/xc/operator in this path -- a different
    # (weaker) trust level than an artifact's derived facts, which the
    # certificate_kind ("confirmed_specification") already communicates.
    capabilities = {
        "expected_locality": expected_locality,
        "all_pairs_reachable": True,
        "all_pairs_reachable_applicable": False,
        "unreachable_pairs": None,
        "operator_message_depth": None,
        "non_local_capacity": expected_locality == "non_local",
    }
    value = {
        "ir_schema_version": plugin.ir_schema_version,
        "source": {
            "kind": "confirmed_description",
            "description_sha256": description_hash,
            "confirmation_sha256": sha256_value({
                "topology": topology,
                "message_passing": message_passing,
                "xc": xc,
                "operator": operator,
                "capabilities": capabilities,
                "confirmed_claims": confirmed_claims or [],
            }),
            "confirmed_claims": confirmed_claims or [],
        },
        "topology": topology,
        "message_passing": message_passing,
        "xc": xc,
        "operator": operator,
        "capabilities": capabilities,
    }
    validate_structural_ir(value, plugin=plugin)
    return value

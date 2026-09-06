"""Authoring surface for the canonical `ResolvedVerificationPackage` JSON
(spec sections 6-7). `VerificationPackageBuilder` is normal Python the user
runs themselves; the trusted verification CLI only ever consumes the
resolved JSON this module writes, never imports/executes user Python.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..certificate import project_fingerprint
from ..manifest import ManifestError, sha256_value
from .model import validate_package


def _entry_module(entrypoint: str) -> str:
    """Auto-derived module guess for an entrypoint with no explicit
    `entry_modules` override -- only correct when a declaration's
    namespace happens to match its module path (spec/theorem-centric-gaps
    issue 13: this is NOT assumed in general; pass `entry_modules`
    explicitly whenever they differ)."""
    if "." not in entrypoint:
        raise ManifestError(f"entrypoint {entrypoint!r} must be a fully qualified Lean declaration name")
    return entrypoint.rsplit(".", 1)[0]


class VerificationPackageBuilder:
    def __init__(
        self, *, lean_project: str | Path, entrypoints: list[str], adapter,
        interface_contract: dict[str, Any], entry_modules: list[str] | None = None,
        binding_choices: list[dict[str, str]] | None = None,
        external_assumptions: list[dict[str, Any]] | None = None,
        axiom_policy: dict[str, Any] | None = None,
        selection_source: str = "python",
    ) -> None:
        """`adapter` is a `StructuralPlugin` instance (or anything exposing
        `.semantic_identity`) -- its identity is computed from the
        executing implementation itself (spec issue 4), never authored as
        free text. `entry_modules`, if given, is used verbatim (spec issue
        13: a declaration's namespace need not match its module path);
        otherwise it is guessed from each entrypoint's own namespace."""
        if not entrypoints:
            raise ManifestError("verification package needs at least one entrypoint")
        root = Path(lean_project)
        toolchain_path = root / "lean-toolchain"
        if not toolchain_path.is_file():
            raise ManifestError(f"{root} is not a Lean project (no lean-toolchain file)")
        entrypoints = sorted(set(entrypoints))
        modules = sorted(set(entry_modules)) if entry_modules is not None else sorted({
            _entry_module(name) for name in entrypoints
        })
        self._package = {
            "schema_version": 1,
            "adapter": adapter.semantic_identity,
            "lean_theory": {
                "project_fingerprint": project_fingerprint(root),
                "toolchain": toolchain_path.read_text(encoding="utf-8").strip(),
                "entry_modules": modules,
                "entrypoints": entrypoints,
            },
            "interface_contract": interface_contract,
            "binding_choices": sorted(
                (binding_choices or []),
                key=lambda choice: (choice["entrypoint"], choice["binder_path"]),
            ),
            "external_assumptions": list(external_assumptions or []),
            "axiom_policy": {"additional_allowed": sorted(set((axiom_policy or {}).get("additional_allowed", [])))},
            "selection_source": selection_source,
        }
        validate_package(self._package)

    def as_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(self._package))

    def sha256(self) -> str:
        return sha256_value(self._package)

    def write(self, path: str | Path) -> str:
        Path(path).write_text(
            json.dumps(self._package, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
        return self.sha256()


def load_package(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_package(value)
    return value


def add_binding_choice(
    path: str | Path, *, entrypoint: str, binder_path: str, candidate_key: str,
) -> str:
    """Persist an explicit ambiguous-binding choice into the package file
    itself (spec issue 7/9: a binding choice is authored package state,
    not TUI-local state) -- replaces any prior choice for the same
    (entrypoint, binder_path). Returns the package's new sha256; the
    caller must re-run `start_session` (which re-checks Lean) to actually
    apply it -- this never re-picks a session's node status by itself."""
    package = load_package(path)
    choices = [
        choice for choice in package["binding_choices"]
        if not (choice["entrypoint"] == entrypoint and choice["binder_path"] == binder_path)
    ]
    choices.append({"entrypoint": entrypoint, "binder_path": binder_path, "candidate_key": candidate_key})
    package["binding_choices"] = sorted(choices, key=lambda choice: (choice["entrypoint"], choice["binder_path"]))
    validate_package(package)
    Path(path).write_text(json.dumps(package, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return sha256_value(package)


def add_external_assumption(
    path: str | Path, *, premise_id: str, proposition_fingerprint: str, rationale: str,
) -> str:
    """Persist an interactively-accepted assumption into the package file
    itself (spec/theorem-centric-gaps issue E: an accepted assumption is
    authored package state, exactly like a binding choice via
    `add_binding_choice`, not TUI-local/session-local state that vanishes
    the next time the session is re-derived). Replaces any prior assumption
    for the same `premise_id`. Returns the package's new sha256; the caller
    must re-run `start_session` (which re-checks the exact proposition
    fingerprint against Lean) to actually apply it."""
    package = load_package(path)
    assumptions = [
        item for item in package["external_assumptions"] if item["premise_id"] != premise_id
    ]
    assumptions.append({
        "premise_id": premise_id, "proposition_fingerprint": proposition_fingerprint, "rationale": rationale,
    })
    package["external_assumptions"] = sorted(assumptions, key=lambda item: item["premise_id"])
    validate_package(package)
    Path(path).write_text(json.dumps(package, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return sha256_value(package)


def package_sha256(value: dict[str, Any]) -> str:
    validate_package(value)
    return sha256_value(value)

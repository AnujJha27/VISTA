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
    if "." not in entrypoint:
        raise ManifestError(f"entrypoint {entrypoint!r} must be a fully qualified Lean declaration name")
    return entrypoint.rsplit(".", 1)[0]


class VerificationPackageBuilder:
    def __init__(
        self, *, lean_project: str | Path, entrypoints: list[str], adapter_profile: str,
        interface_contract: dict[str, Any], adapter_version: str = "unversioned",
        binding_choices: list[dict[str, str]] | None = None,
        external_assumptions: list[dict[str, Any]] | None = None,
        selection_source: str = "python",
    ) -> None:
        if not entrypoints:
            raise ManifestError("verification package needs at least one entrypoint")
        root = Path(lean_project)
        toolchain_path = root / "lean-toolchain"
        if not toolchain_path.is_file():
            raise ManifestError(f"{root} is not a Lean project (no lean-toolchain file)")
        entrypoints = sorted(set(entrypoints))
        self._package = {
            "schema_version": 1,
            "adapter": {"profile": adapter_profile, "adapter_version": adapter_version},
            "lean_theory": {
                "project_fingerprint": project_fingerprint(root),
                "toolchain": toolchain_path.read_text(encoding="utf-8").strip(),
                "entry_modules": sorted({_entry_module(name) for name in entrypoints}),
                "entrypoints": entrypoints,
            },
            "interface_contract": interface_contract,
            "binding_choices": sorted(
                (binding_choices or []),
                key=lambda choice: (choice["entrypoint"], choice["binder_path"]),
            ),
            "external_assumptions": list(external_assumptions or []),
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


def package_sha256(value: dict[str, Any]) -> str:
    validate_package(value)
    return sha256_value(value)

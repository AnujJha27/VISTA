#!/usr/bin/env python3
"""Safely extract the demo's real .pt2 fixture into a trusted-local
extraction result JSON `vista verify start` can consume directly (bypassing
the Bubblewrap sandbox -- see the README for why that's `--trusted-local`
here specifically, and how to use the real sandbox instead).

Run from the repository root:

    python examples/theorem_centric_demo/extract_artifact.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from extractors.torch_export_worker import extract  # noqa: E402

ARTIFACT = PROJECT_ROOT / "tests" / "fixtures" / "certified_ring.pt2"


def main() -> None:
    result = extract(ARTIFACT)
    (HERE / "extraction-result.json").write_text(json.dumps(result), encoding="utf-8")
    print(f"wrote {HERE / 'extraction-result.json'} (artifact_sha256={result['artifact_sha256']})")


if __name__ == "__main__":
    main()

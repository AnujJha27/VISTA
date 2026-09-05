"""Generate only the V3 corpus PT2 artifacts; labels live independently in the manifests.

Reuses the same parametrized candidate model factory as V2
(`evaluation.structural_v2.corpus_models`) -- V3 changes only how the
locality claim is verified, not the candidate architectures.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "structural_v2"))
from corpus_models import make_model


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=HERE / "corpus_manifest.json", type=Path)
    parser.add_argument("--output-dir", default=HERE.parent.parent / "build" / "vista-structural-v3-corpus", type=Path)
    options = parser.parse_args()
    manifest = json.loads(options.manifest.read_text())
    options.output_dir.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(20260906)
    for case in manifest["cases"]:
        model = make_model(case["model"]).eval()
        torch.export.save(
            torch.export.export(model, (torch.randn(case["model"]["sites"], 1),)),
            options.output_dir / f'{case["id"]}.pt2',
        )
        print(options.output_dir / f'{case["id"]}.pt2', file=sys.stderr)
    return 0


if __name__ == "__main__": raise SystemExit(main())

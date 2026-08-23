import json
import importlib.util
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
import unittest


class StructuralV2EvaluationTests(unittest.TestCase):
    def test_independent_corpus_has_frozen_48_case_split(self):
        root = Path(__file__).resolve().parents[1] / "evaluation" / "structural_v2"
        cases = json.loads((root / "corpus_manifest.json").read_text())["cases"]
        self.assertEqual(len(cases), 48)
        self.assertEqual(Counter(item["domain"] for item in cases), {"spatial": 16, "operator": 16, "xc": 16})
        self.assertEqual(Counter(item["split"] for item in cases), {"development": 24, "evaluation": 24})
        self.assertTrue(all("expected" in item and "rationale" in item for item in cases))

    def test_fresh_held_out_corpus_has_fixed_labels_before_execution(self):
        root = Path(__file__).resolve().parents[1] / "evaluation" / "structural_v2"
        cases = json.loads((root / "fresh_held_out_manifest.json").read_text())["cases"]
        self.assertEqual(len(cases), 12)
        self.assertEqual(Counter(item["domain"] for item in cases), {"spatial": 4, "operator": 4, "xc": 4})
        self.assertTrue(all(item["split"] == "held_out" for item in cases))
        self.assertTrue(all("semantic_status" in item["expected"] for item in cases))

    def test_condition_fingerprint_rechecks_manifest_and_sources(self):
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location("structural_score", root / "evaluation" / "structural_v2" / "score.py")
        score = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(score)
        manifest = root / "evaluation" / "structural_v2" / "corpus_manifest.json"
        experiment = {"condition_name": "r2", "corpus_freeze_revision": "freeze", "execution_revision": "run"}
        fingerprint = {
            **experiment, "manifest_sha256": score.sha256_file(manifest),
            "source_sha256": {"evaluation/structural_v2/score.py": score.sha256_file(root / "evaluation" / "structural_v2" / "score.py")},
        }
        self.assertEqual(score.verify_condition_fingerprint(SimpleNamespace(manifest=manifest), fingerprint, experiment), [])
        fingerprint["source_sha256"]["evaluation/structural_v2/score.py"] = "0" * 64
        self.assertIn("source_sha256 mismatch", "\n".join(score.verify_condition_fingerprint(SimpleNamespace(manifest=manifest), fingerprint, experiment)))

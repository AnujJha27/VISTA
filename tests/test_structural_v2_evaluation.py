import json
from collections import Counter
from pathlib import Path
import unittest


class StructuralV2EvaluationTests(unittest.TestCase):
    def test_independent_corpus_has_frozen_48_case_split(self):
        root = Path(__file__).resolve().parents[1] / "evaluation" / "structural_v2"
        cases = json.loads((root / "corpus_manifest.json").read_text())["cases"]
        self.assertEqual(len(cases), 48)
        self.assertEqual(Counter(item["domain"] for item in cases), {"spatial": 16, "operator": 16, "xc": 16})
        self.assertEqual(Counter(item["split"] for item in cases), {"development": 24, "evaluation": 24})
        self.assertTrue(all("expected" in item and "rationale" in item for item in cases))

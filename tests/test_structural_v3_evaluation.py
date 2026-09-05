import json
from collections import Counter
from pathlib import Path
import unittest


class StructuralV3EvaluationTests(unittest.TestCase):
    def test_corpus_covers_all_classes_and_has_no_coupling_pairs(self):
        root = Path(__file__).resolve().parents[1] / "evaluation" / "structural_v3"
        cases = json.loads((root / "corpus_manifest.json").read_text())["cases"]
        self.assertEqual(len(cases), 13)
        self.assertEqual(
            Counter(item["class"] for item in cases),
            {"positive": 4, "near_miss": 4, "unsupported": 2, "malformed": 3},
        )
        self.assertTrue(all("expected" in item and "rationale" in item for item in cases))
        for case in cases:
            self.assertNotIn("constraints", case, f"{case['id']}: V3 cases carry no separate constraints/couplings block")
            self.assertIn("expected_locality", case)
        topologies = {case["model"]["topology"] for case in cases}
        self.assertGreaterEqual(len(topologies), 2, "corpus should exercise more than one topology")

    def test_fresh_held_out_corpus_has_fixed_labels_before_execution(self):
        root = Path(__file__).resolve().parents[1] / "evaluation" / "structural_v3"
        cases = json.loads((root / "fresh_held_out_manifest.json").read_text())["cases"]
        self.assertEqual(len(cases), 6)
        self.assertTrue(all("semantic_status" in item["expected"] for item in cases))
        ids = {item["id"] for item in cases}
        self.assertIn("v3h-malformed-missing-locality-field", ids)
        self.assertIn("v3h-unsupported-diagonal-operator", ids)
        self.assertIn("v3h-unsupported-transformed-scaled-operator", ids)
        self.assertIn("v3h-malformed-duplicate-xc-role", ids)

    def test_condition_declares_the_locality_rule(self):
        root = Path(__file__).resolve().parents[1] / "evaluation" / "structural_v3"
        experiment = json.loads((root / "experiment.json").read_text())
        self.assertEqual(experiment["condition_name"], "vista-structural-eval-v3-r1")
        self.assertIn("operator_offdiag_abs_threshold", experiment["semantic_rules"])


if __name__ == "__main__":
    unittest.main()

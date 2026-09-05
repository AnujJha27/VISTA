"""V3: locality claims verified against the candidate's own extracted operator values.

Nobody -- not the candidate, not an analyst, not an external reference file --
supplies specific coupling pairs. An analyst attests a global claim ("local"
or "non_local"); VISTA computes the real fact from the candidate's own
extracted parameter values and reports whether the claim holds.
"""
import copy
import unittest

from dftcert.manifest import ManifestError
from dftcert.structural import (
    generate_structural_obligations,
    structural_ir_from_inventory,
    validate_translation,
)


def _chain_inventory(*, base=None, site_count=4):
    ref = lambda name: {"node": name}
    nodes = [
        {"name": "b_adjacency", "op": "placeholder", "target": "b_adjacency", "args": [], "kwargs": {}},
        {"name": "p_base", "op": "placeholder", "target": "p_base", "args": [], "kwargs": {}},
        {"name": "density", "op": "placeholder", "target": "density", "args": [], "kwargs": {}},
    ]
    current = "density"
    for index in range(3):
        name = f"matmul{'' if index == 0 else f'_{index}'}"
        nodes.append({
            "name": name, "op": "call_function", "target": "aten.matmul.default",
            "args": [ref("b_adjacency"), ref(current)], "kwargs": {},
        })
        current = name
    nodes.extend([
        {"name": "relu", "op": "call_function", "target": "aten.relu.default", "args": [ref("density")], "kwargs": {}},
        {"name": "numpy_t", "op": "call_function", "target": "aten.numpy_T.default", "args": [ref("p_base")], "kwargs": {}},
        {"name": "add", "op": "call_function", "target": "aten.add.Tensor", "args": [ref("p_base"), ref("numpy_t")], "kwargs": {}},
        {"name": "output", "op": "output", "target": "output", "args": [[ref("relu"), ref("add"), ref(current)]], "kwargs": {}},
    ])
    adjacency_values = [[False] * site_count for _ in range(site_count)]
    for i in range(site_count - 1):
        adjacency_values[i][i + 1] = True
    state = {"adjacency": {
        "structural_values": adjacency_values, "graph_inputs": ["b_adjacency"],
        "shape": [site_count, site_count], "dtype": "torch.bool", "sha256": "a",
    }}
    if base is not None:
        state["base"] = {
            "structural_values": base, "structural_value_kind": "numeric",
            "graph_inputs": ["p_base"], "shape": [site_count, site_count],
            "dtype": "torch.float32", "sha256": "b",
        }
    return {"nodes": nodes, "state": state}


def _constraints(*, expected_locality="non_local", **overrides):
    value = {
        "adjacency_state_name": "adjacency", "adjacency_convention": "source_target",
        "output_contracts": [
            {"index": 0, "role": "xc_energy"},
            {"index": 1, "role": "learned_self_energy"},
            {"index": 2, "role": "message_state"},
        ],
        "expected_locality": expected_locality,
    }
    value.update(overrides)
    return value


_DIAGONAL_BASE = [[1, 0, 0, 0], [0, 2, 0, 0], [0, 0, 3, 0], [0, 0, 0, 4]]
_OFFDIAG_BASE = [[0, 0, 0, 1], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]


class LocalityDerivationTests(unittest.TestCase):
    def test_symmetrized_with_diagonal_base_is_observed_local(self):
        ir = structural_ir_from_inventory(
            inventory=_chain_inventory(base=_DIAGONAL_BASE), artifact_sha256="a",
            extractor_version="t", input_constraints=_constraints(expected_locality="local"),
        )
        self.assertTrue(ir["locality"]["available"])
        self.assertTrue(ir["locality"]["observed_local"])
        self.assertEqual(ir["locality"]["off_diagonal_nonzero"], [])

    def test_symmetrized_with_offdiagonal_base_is_observed_non_local(self):
        ir = structural_ir_from_inventory(
            inventory=_chain_inventory(base=_OFFDIAG_BASE), artifact_sha256="a",
            extractor_version="t", input_constraints=_constraints(expected_locality="non_local"),
        )
        self.assertTrue(ir["locality"]["available"])
        self.assertFalse(ir["locality"]["observed_local"])
        self.assertEqual(
            sorted((item["source"], item["target"]) for item in ir["locality"]["off_diagonal_nonzero"]),
            [(0, 3), (3, 0)],
        )

    def test_claim_mismatch_is_recorded_but_does_not_raise(self):
        ir = structural_ir_from_inventory(
            inventory=_chain_inventory(base=_OFFDIAG_BASE), artifact_sha256="a",
            extractor_version="t", input_constraints=_constraints(expected_locality="local"),
        )
        self.assertEqual(ir["locality"]["expected"], "local")
        self.assertFalse(ir["locality"]["observed_local"])

    def test_missing_base_values_leaves_locality_unavailable(self):
        ir = structural_ir_from_inventory(
            inventory=_chain_inventory(base=None), artifact_sha256="a",
            extractor_version="t", input_constraints=_constraints(),
        )
        self.assertFalse(ir["locality"]["available"])
        self.assertIsNone(ir["locality"]["observed_local"])
        self.assertIsNone(ir["locality"]["off_diagonal_nonzero"])

    def test_missing_expected_locality_fails_closed(self):
        with self.assertRaises(ManifestError):
            structural_ir_from_inventory(
                inventory=_chain_inventory(base=_DIAGONAL_BASE), artifact_sha256="a",
                extractor_version="t",
                input_constraints=_constraints(expected_locality="sideways"),
            )

    def test_large_base_beyond_capture_cap_is_unavailable(self):
        # A parameter without structural_values at all (as if it exceeded the
        # extractor's small-tensor cap) must never be guessed at.
        inventory = _chain_inventory(base=_DIAGONAL_BASE)
        del inventory["state"]["base"]["structural_values"]
        ir = structural_ir_from_inventory(
            inventory=inventory, artifact_sha256="a", extractor_version="t",
            input_constraints=_constraints(),
        )
        self.assertFalse(ir["locality"]["available"])


class TranslationValidationTests(unittest.TestCase):
    def test_hand_edited_locality_fails_translation_validation(self):
        inventory = _chain_inventory(base=_OFFDIAG_BASE)
        ir = structural_ir_from_inventory(
            inventory=inventory, artifact_sha256="a", extractor_version="t",
            input_constraints=_constraints(expected_locality="non_local"),
        )
        tampered = copy.deepcopy(ir)
        tampered["locality"]["observed_local"] = True
        tampered["locality"]["off_diagonal_nonzero"] = []
        with self.assertRaises(ManifestError):
            validate_translation(
                inventory=inventory, value=tampered,
                input_constraints=_constraints(expected_locality="non_local"), artifact_sha256="a",
            )

    def test_changed_expected_locality_input_fails_translation_validation(self):
        inventory = _chain_inventory(base=_OFFDIAG_BASE)
        ir = structural_ir_from_inventory(
            inventory=inventory, artifact_sha256="a", extractor_version="t",
            input_constraints=_constraints(expected_locality="non_local"),
        )
        with self.assertRaises(ManifestError):
            validate_translation(
                inventory=inventory, value=ir,
                input_constraints=_constraints(expected_locality="local"), artifact_sha256="a",
            )

    def test_tampered_base_values_are_caught_on_revalidation(self):
        inventory = _chain_inventory(base=_OFFDIAG_BASE)
        ir = structural_ir_from_inventory(
            inventory=inventory, artifact_sha256="a", extractor_version="t",
            input_constraints=_constraints(expected_locality="non_local"),
        )
        retampered_inventory = copy.deepcopy(inventory)
        retampered_inventory["state"]["base"]["structural_values"] = _DIAGONAL_BASE
        with self.assertRaises(ManifestError):
            validate_translation(
                inventory=retampered_inventory, value=ir,
                input_constraints=_constraints(expected_locality="non_local"), artifact_sha256="a",
            )


class LeanObligationTests(unittest.TestCase):
    def test_locality_obligation_generated_when_available(self):
        ir = structural_ir_from_inventory(
            inventory=_chain_inventory(base=_OFFDIAG_BASE), artifact_sha256="a",
            extractor_version="t", input_constraints=_constraints(expected_locality="non_local"),
        )
        generated = generate_structural_obligations(ir)
        facts = {task["fact"] for task in generated["obligations"]}
        self.assertIn("operator_locality_verified", facts)
        task = next(t for t in generated["obligations"] if t["fact"] == "operator_locality_verified")
        self.assertIn("localityMatches", task["theorem"])
        self.assertIn("(0, 3)", task["preamble"])
        self.assertIn("expectedLocal : Bool := false", task["preamble"])

    def test_no_locality_obligation_when_unavailable(self):
        ir = structural_ir_from_inventory(
            inventory=_chain_inventory(base=None), artifact_sha256="a",
            extractor_version="t", input_constraints=_constraints(),
        )
        generated = generate_structural_obligations(ir)
        facts = {task["fact"] for task in generated["obligations"]}
        self.assertNotIn("operator_locality_verified", facts)
        self.assertEqual(generated["disposition"], "formalization_required")

    def test_obligations_are_deterministic(self):
        ir = structural_ir_from_inventory(
            inventory=_chain_inventory(base=_OFFDIAG_BASE), artifact_sha256="a",
            extractor_version="t", input_constraints=_constraints(expected_locality="non_local"),
        )
        first = generate_structural_obligations(ir)
        second = generate_structural_obligations(ir)
        self.assertEqual(first["obligations"], second["obligations"])


if __name__ == "__main__":
    unittest.main()

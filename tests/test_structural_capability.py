"""Pre-training architectural-capability checks -- no extracted floats.

Unlike `DFTPlugin`'s `locality` (a fact about real extracted weights, which
don't exist before training), `DFTCapabilityPlugin`'s `capabilities` are
facts about topology, message-passing depth, and operator-construction
recipe alone.
"""
import unittest

from dftcert.structural.core import generate_structural_obligations, structural_ir_from_inventory
from dftcert.structural.dft_capability_plugin import DFT_CAPABILITY_PLUGIN


def _ref(name):
    return {"node": name}


def _inventory(*, adjacency, stages, symmetrized=True):
    site_count = len(adjacency)
    nodes = [
        {"name": "b_adjacency", "op": "placeholder", "target": "b_adjacency", "args": [], "kwargs": {}},
        {"name": "p_base", "op": "placeholder", "target": "p_base", "args": [], "kwargs": {}},
        {"name": "density", "op": "placeholder", "target": "density", "args": [], "kwargs": {}},
    ]
    current = "density"
    for index in range(stages):
        name = f"matmul{'' if index == 0 else f'_{index}'}"
        nodes.append({
            "name": name, "op": "call_function", "target": "aten.matmul.default",
            "args": [_ref("b_adjacency"), _ref(current)], "kwargs": {},
        })
        current = name
    nodes.append({"name": "relu", "op": "call_function", "target": "aten.relu.default", "args": [_ref("density")], "kwargs": {}})
    if symmetrized:
        nodes.extend([
            {"name": "numpy_t", "op": "call_function", "target": "aten.numpy_T.default", "args": [_ref("p_base")], "kwargs": {}},
            {"name": "add", "op": "call_function", "target": "aten.add.Tensor", "args": [_ref("p_base"), _ref("numpy_t")], "kwargs": {}},
        ])
        operator_root = "add"
    else:
        operator_root = "p_base"
    nodes.append({
        "name": "output", "op": "output", "target": "output",
        "args": [[_ref("relu"), _ref(operator_root), _ref(current)]], "kwargs": {},
    })
    # No numeric `structural_values` anywhere -- V4 needs none.
    state = {"adjacency": {
        "structural_values": adjacency, "graph_inputs": ["b_adjacency"],
        "shape": [site_count, site_count], "dtype": "torch.bool", "sha256": "a",
    }}
    return {"nodes": nodes, "state": state}


def _constraints(expected_locality="non_local"):
    return {
        "adjacency_state_name": "adjacency", "adjacency_convention": "source_target",
        "output_contracts": [
            {"index": 0, "role": "xc_energy"},
            {"index": 1, "role": "learned_self_energy"},
            {"index": 2, "role": "message_state"},
        ],
        "expected_locality": expected_locality,
    }


_RING3 = [[False, True, True], [True, False, True], [True, True, False]]
_CHAIN3 = [[False, True, False], [False, False, True], [False, False, False]]


def _ir(*, expected_locality="non_local", **inventory_kwargs):
    return structural_ir_from_inventory(
        inventory=_inventory(**inventory_kwargs), artifact_sha256="a", extractor_version="t",
        input_constraints=_constraints(expected_locality), plugin=DFT_CAPABILITY_PLUGIN,
    )


class AllPairsReachableTests(unittest.TestCase):
    def test_fully_connected_ring_with_one_stage_covers_all_pairs(self):
        ir = _ir(adjacency=_RING3, stages=1)
        self.assertTrue(ir["capabilities"]["all_pairs_reachable"])
        self.assertEqual(ir["capabilities"]["unreachable_pairs"], [])

    def test_zero_depth_never_covers_distinct_pairs(self):
        ir = _ir(adjacency=_RING3, stages=0)
        self.assertFalse(ir["capabilities"]["all_pairs_reachable"])
        self.assertEqual(len(ir["capabilities"]["unreachable_pairs"]), 6)

    def test_one_directional_chain_never_covers_backward_pairs(self):
        ir = _ir(adjacency=_CHAIN3, stages=2)
        self.assertFalse(ir["capabilities"]["all_pairs_reachable"])
        self.assertIn({"source": 2, "target": 0}, ir["capabilities"]["unreachable_pairs"])


class NonLocalCapacityTests(unittest.TestCase):
    def test_symmetrized_operator_has_capacity_and_guaranteed_self_adjoint(self):
        ir = _ir(adjacency=_RING3, stages=1, symmetrized=True)
        self.assertTrue(ir["capabilities"]["non_local_capacity"])
        checks = generate_structural_obligations(ir, plugin=DFT_CAPABILITY_PLUGIN)["assessment"]["checks"]
        self.assertTrue(checks["non_local_capacity"]["satisfied"])
        self.assertTrue(checks["self_adjoint"]["satisfied"])

    def test_bare_parameter_operator_has_capacity_but_not_guaranteed_self_adjoint(self):
        ir = _ir(adjacency=_RING3, stages=1, symmetrized=False)
        self.assertTrue(ir["capabilities"]["non_local_capacity"])
        checks = generate_structural_obligations(ir, plugin=DFT_CAPABILITY_PLUGIN)["assessment"]["checks"]
        self.assertTrue(checks["non_local_capacity"]["satisfied"])
        self.assertFalse(checks["self_adjoint"]["satisfied"])

    def test_certifiable_without_any_extracted_floats(self):
        inventory = _inventory(adjacency=_RING3, stages=1, symmetrized=True)
        self.assertEqual(set(inventory["state"]), {"adjacency"})  # no numeric weights at all
        ir = structural_ir_from_inventory(
            inventory=inventory, artifact_sha256="a", extractor_version="t",
            input_constraints=_constraints("non_local"), plugin=DFT_CAPABILITY_PLUGIN,
        )
        generated = generate_structural_obligations(ir, plugin=DFT_CAPABILITY_PLUGIN)
        self.assertEqual(generated["disposition"], "structurally_certifiable")


if __name__ == "__main__":
    unittest.main()

"""Pre-training architectural-capability checks -- no extracted floats.

Unlike `DFTPlugin`'s `locality` (a fact about real extracted weights, which
don't exist before training), `DFTCapabilityPlugin`'s `capabilities` are
facts about topology, message-passing depth found within the *operator's
own ancestry*, and operator-construction recipe alone.

The recipes `DFTPlugin`/`DFTCapabilityPlugin` currently recognize (`zero`,
`identity`, `symmetrized`, `unconstrained_parameter`) are all built purely
from parameters/adjoints -- none of them ever consume the adjacency at all.
So `all_pairs_reachable` is honestly `not applicable` for every inventory
these tests can build through the public `structural_ir_from_inventory`
pipeline; `AllPairsReachableUnitTests` below exercises the underlying
reachability/applicability logic directly instead.
"""
import unittest

from dftcert.structural.core import generate_structural_obligations, structural_ir_from_inventory
from dftcert.structural.dft_capability_plugin import DFT_CAPABILITY_PLUGIN, _reachability, _unreachable_pairs


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
    # No numeric `structural_values` anywhere -- the capability plugin needs none.
    state = {
        "adjacency": {
            "structural_values": adjacency, "graph_inputs": ["b_adjacency"],
            "shape": [site_count, site_count], "dtype": "torch.bool", "sha256": "a",
        },
        # research-readiness audit issue 5: `unconstrained_parameter`
        # capacity now requires POSITIVE evidence of trainability -- this
        # fixture's own intent (a genuine trainable weight, as its every
        # caller's assertions confirm) needs a real `state_kind` marker,
        # matching torch.export's own `InputKind.PARAMETER`, not the old
        # fail-open default that let a bare placeholder with no
        # classification at all pass silently.
        "p_base": {"graph_inputs": ["p_base"], "shape": [site_count, site_count], "state_kind": "InputKind.PARAMETER"},
    }
    return {"nodes": nodes, "state": state}


def _constraints(expected_locality="non_local", long_range_pairs=None):
    return {
        "adjacency_state_name": "adjacency", "adjacency_convention": "source_target",
        "output_contracts": [
            {"index": 0, "role": "xc_energy"},
            {"index": 1, "role": "learned_self_energy"},
            {"index": 2, "role": "message_state"},
        ],
        "expected_locality": expected_locality,
        # research-soundness correction: SPECIFIED INTERFACE, never
        # artifact-grounded -- which site pairs count as "long-range" for
        # this 3-site fixture. [0, 2] is a real, in-bounds, distinct pair;
        # pass long_range_pairs=[] to a caller that wants no long-range
        # capacity to be representable at all.
        "long_range_pairs": [[0, 2]] if long_range_pairs is None else long_range_pairs,
    }


_RING3 = [[False, True, True], [True, False, True], [True, True, False]]
_CHAIN3 = [[False, True, False], [False, False, True], [False, False, False]]


def _ir(*, expected_locality="non_local", **inventory_kwargs):
    return structural_ir_from_inventory(
        inventory=_inventory(**inventory_kwargs), artifact_sha256="a", extractor_version="t",
        input_constraints=_constraints(expected_locality), plugin=DFT_CAPABILITY_PLUGIN,
    )


class AllPairsReachableUnitTests(unittest.TestCase):
    """Exercises `_reachability`/`_unreachable_pairs` directly, since no
    currently-recognized operator recipe ever depends on message-passing
    (see module docstring) -- the "applicable" branch can't be reached
    through the public pipeline yet, but the logic itself must be correct
    for whenever a message-passing-derived recipe is recognized."""

    def test_fully_connected_ring_with_one_stage_is_applicable_and_covers_all_pairs(self):
        nodes = [
            {"name": "b_adjacency", "op": "placeholder", "target": "b_adjacency", "args": [], "kwargs": {}},
            {"name": "density", "op": "placeholder", "target": "density", "args": [], "kwargs": {}},
            {"name": "matmul", "op": "call_function", "target": "aten.matmul.default",
             "args": [_ref("b_adjacency"), _ref("density")], "kwargs": {}},
        ]
        edges = [[0, 1], [1, 0], [0, 2], [2, 0], [1, 2], [2, 1]]
        result = _reachability(
            nodes=nodes, operator_root="matmul", adjacency_aliases=["b_adjacency"],
            site_count=3, edges=edges,
        )
        self.assertTrue(result["applicable"])
        self.assertTrue(result["satisfied"])
        self.assertEqual(result["depth"], 1)
        self.assertEqual(result["unreachable_pairs"], [])

    def test_zero_depth_never_covers_distinct_pairs(self):
        edges = [[0, 1], [1, 0], [0, 2], [2, 0], [1, 2], [2, 1]]
        self.assertEqual(len(_unreachable_pairs(3, edges, depth=0)), 6)

    def test_one_directional_chain_never_covers_backward_pairs(self):
        unreachable = _unreachable_pairs(3, [[0, 1], [1, 2]], depth=2)
        self.assertIn({"source": 2, "target": 0}, unreachable)

    def test_operator_not_depending_on_adjacency_is_not_applicable(self):
        nodes = [
            {"name": "b_adjacency", "op": "placeholder", "target": "b_adjacency", "args": [], "kwargs": {}},
            {"name": "p_base", "op": "placeholder", "target": "p_base", "args": [], "kwargs": {}},
        ]
        result = _reachability(
            nodes=nodes, operator_root="p_base", adjacency_aliases=["b_adjacency"],
            site_count=3, edges=[],
        )
        self.assertFalse(result["applicable"])
        self.assertTrue(result["satisfied"])  # vacuous, never "rescued" by an unrelated branch
        self.assertIsNone(result["depth"])
        self.assertIsNone(result["unreachable_pairs"])


class AllPairsReachablePipelineTests(unittest.TestCase):
    def test_every_currently_recognized_operator_recipe_is_not_applicable(self):
        # zero/identity/symmetrized/unconstrained_parameter are all built
        # from placeholders + add/transpose only -- never matmul -- so this
        # must hold for every inventory the public pipeline can produce today.
        for symmetrized in (True, False):
            ir = _ir(adjacency=_RING3, stages=2, symmetrized=symmetrized)
            self.assertFalse(ir["capabilities"]["all_pairs_reachable_applicable"])
            self.assertTrue(ir["capabilities"]["all_pairs_reachable"])
            self.assertIsNone(ir["capabilities"]["operator_message_depth"])
            self.assertIsNone(ir["capabilities"]["unreachable_pairs"])


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

    def test_single_site_never_has_non_local_capacity_even_for_a_free_parameter(self):
        # A 1x1 matrix has no off-diagonal entry to assign, for any recipe.
        ir = _ir(adjacency=[[False]], stages=0, symmetrized=True, expected_locality="non_local")
        self.assertFalse(ir["capabilities"]["non_local_capacity"])
        checks = generate_structural_obligations(ir, plugin=DFT_CAPABILITY_PLUGIN)["assessment"]["checks"]
        self.assertFalse(checks["non_local_capacity"]["satisfied"])

    def test_certifiable_without_any_extracted_floats(self):
        inventory = _inventory(adjacency=_RING3, stages=1, symmetrized=True)
        # No numeric weight values anywhere -- `p_base`'s own state entry
        # (added for issue 5's positive-parameter-classification
        # requirement) carries only graph_inputs/shape/state_kind
        # metadata, never a `structural_values` payload (`adjacency`'s own
        # boolean structural buffer is the one legitimate exception --
        # architecture shape, never a trained weight).
        self.assertNotIn("structural_values", inventory["state"]["p_base"])
        ir = structural_ir_from_inventory(
            inventory=inventory, artifact_sha256="a", extractor_version="t",
            input_constraints=_constraints("non_local"), plugin=DFT_CAPABILITY_PLUGIN,
        )
        generated = generate_structural_obligations(ir, plugin=DFT_CAPABILITY_PLUGIN)
        self.assertEqual(generated["disposition"], "structurally_certifiable")


if __name__ == "__main__":
    unittest.main()

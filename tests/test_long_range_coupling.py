"""Research-soundness correction: the theorem-centric non-locality premise
no longer treats "some off-diagonal matrix entry" as sufficient evidence
of physical long-range coupling -- see `Testv2.StructuralV2.
canRepresentLongRangeCoupling`'s own docstring and `Testv2.Requirements`'
module docstring. `long_range_pairs` is a SPECIFIED-INTERFACE fact (which
site pairs the domain considers long-range), never artifact-grounded; the
architecture only has capacity if it also contains a confirmed free
parameter (never a fixed buffer or unknown classification) with the
freedom to realize coupling on at least one of those specified pairs.
"""
import unittest

from dftcert.structural.core import structural_ir_from_inventory
from dftcert.structural.dft_capability_plugin import DFT_CAPABILITY_PLUGIN


def _ref(name):
    return {"node": name}


def _constraints(*, long_range_pairs=None, layout=None):
    value = {
        "adjacency_state_name": "adjacency", "adjacency_convention": "source_target",
        "output_contracts": [
            {"index": 0, "role": "xc_energy"},
            {"index": 1, "role": "learned_self_energy"},
            {"index": 2, "role": "message_state"},
        ],
        "expected_locality": "non_local",
    }
    if long_range_pairs is not None:
        value["long_range_pairs"] = long_range_pairs
    if layout is not None:
        value["operator_layout"] = layout
    return value


_RING4 = [
    [False, True, False, True], [True, False, True, False],
    [False, True, False, True], [True, False, True, False],
]


def _inventory(*, root_target, root_kwargs=None, state_kind=None, stages=0, orbitals=None):
    """`learned_self_energy` is a bare placeholder `p_base` unless
    `root_target` names a zero/identity-constructing op instead (in which
    case `p_base` is unused and dropped from the graph). `state_kind`
    (if given) is set on `p_base`'s own state entry. `orbitals`, if given,
    makes `p_base` (and the adjacency) rank-4 (`[N, m, N, m]`, a grouped
    layout) instead of a plain `[N, N]` matrix."""
    site_count = len(_RING4)
    nodes = [
        {"name": "b_adjacency", "op": "placeholder", "target": "b_adjacency", "args": [], "kwargs": {}},
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
    if root_target == "p_base":
        nodes.append({"name": "p_base", "op": "placeholder", "target": "p_base", "args": [], "kwargs": {}})
        operator_root = "p_base"
    else:
        nodes.append({
            "name": "op_root", "op": "call_function", "target": root_target,
            "args": [], "kwargs": root_kwargs or {},
        })
        operator_root = "op_root"
    nodes.append({
        "name": "output", "op": "output", "target": "output",
        "args": [[_ref("relu"), _ref(operator_root), _ref(current)]], "kwargs": {},
    })
    state = {
        "adjacency": {
            "structural_values": _RING4, "graph_inputs": ["b_adjacency"],
            "shape": [site_count, site_count], "dtype": "torch.bool", "sha256": "a",
        },
    }
    if root_target == "p_base":
        shape = [site_count, orbitals, site_count, orbitals] if orbitals else [site_count, site_count]
        state["p_base"] = {
            "graph_inputs": ["p_base"], "shape": shape,
            **({"state_kind": state_kind} if state_kind is not None else {}),
        }
    return {"nodes": nodes, "state": state}


def _symmetrized_inventory(*, state_kind=None, orbitals=None):
    """`p_base + adjoint(p_base)` -- the `symmetrized` recipe."""
    site_count = len(_RING4)
    nodes = [
        {"name": "b_adjacency", "op": "placeholder", "target": "b_adjacency", "args": [], "kwargs": {}},
        {"name": "p_base", "op": "placeholder", "target": "p_base", "args": [], "kwargs": {}},
        {"name": "density", "op": "placeholder", "target": "density", "args": [], "kwargs": {}},
        {"name": "relu", "op": "call_function", "target": "aten.relu.default", "args": [_ref("density")], "kwargs": {}},
    ]
    if orbitals:
        nodes.append({
            "name": "adjoint", "op": "call_function", "target": "aten.permute.default",
            "args": [_ref("p_base"), [2, 3, 0, 1]], "kwargs": {},
        })
    else:
        nodes.append({
            "name": "adjoint", "op": "call_function", "target": "aten.transpose.int",
            "args": [_ref("p_base"), 0, 1], "kwargs": {},
        })
    nodes.append({"name": "add", "op": "call_function", "target": "aten.add.Tensor", "args": [_ref("p_base"), _ref("adjoint")], "kwargs": {}})
    nodes.append({
        "name": "output", "op": "output", "target": "output",
        "args": [[_ref("relu"), _ref("add"), _ref("density")]], "kwargs": {},
    })
    shape = [site_count, orbitals, site_count, orbitals] if orbitals else [site_count, site_count]
    state = {
        "adjacency": {
            "structural_values": _RING4, "graph_inputs": ["b_adjacency"],
            "shape": [site_count, site_count], "dtype": "torch.bool", "sha256": "a",
        },
        "p_base": {
            "graph_inputs": ["p_base"], "shape": shape,
            **({"state_kind": state_kind} if state_kind is not None else {}),
        },
    }
    return {"nodes": nodes, "state": state}


def _ir(inventory, **constraint_kwargs):
    return structural_ir_from_inventory(
        inventory=inventory, artifact_sha256="a", extractor_version="t",
        input_constraints=_constraints(**constraint_kwargs), plugin=DFT_CAPABILITY_PLUGIN,
    )


class LongRangePairsTests(unittest.TestCase):
    """A. Long-range pairs."""

    def test_no_long_range_pairs_supplied_means_no_capacity(self):
        ir = _ir(_symmetrized_inventory(state_kind="InputKind.PARAMETER"))
        self.assertEqual(ir.get("long_range_pairs"), [])
        self.assertFalse(ir["capabilities"]["long_range_capacity"])

    def test_empty_long_range_pairs_means_no_capacity(self):
        ir = _ir(_symmetrized_inventory(state_kind="InputKind.PARAMETER"), long_range_pairs=[])
        self.assertFalse(ir["capabilities"]["long_range_capacity"])

    def test_self_pair_is_never_counted_as_a_valid_long_range_pair(self):
        ir = _ir(_symmetrized_inventory(state_kind="InputKind.PARAMETER"), long_range_pairs=[[2, 2]])
        self.assertFalse(ir["capabilities"]["long_range_capacity"])

    def test_out_of_range_pair_is_never_counted(self):
        ir = _ir(_symmetrized_inventory(state_kind="InputKind.PARAMETER"), long_range_pairs=[[0, 4]])
        self.assertFalse(ir["capabilities"]["long_range_capacity"])

    def test_a_valid_distant_pair_is_accepted_as_specified_interface(self):
        ir = _ir(_symmetrized_inventory(state_kind="InputKind.PARAMETER"), long_range_pairs=[[0, 2]])
        self.assertTrue(ir["capabilities"]["long_range_capacity"])
        candidates = {c.key: c for c in DFT_CAPABILITY_PLUGIN.formal_binding_candidates(ir)}
        self.assertEqual(candidates["long_range_pairs"].provenance, "specified_interface")
        self.assertNotEqual(candidates["long_range_pairs"].provenance, "artifact_grounded")


class OperatorCapacityTests(unittest.TestCase):
    """B. Operator capacity."""

    def test_zero_has_no_capacity(self):
        ir = _ir(_inventory(root_target="aten.zeros.default"), long_range_pairs=[[0, 2]])
        self.assertEqual(ir["operator"]["construction"], "zero")
        self.assertFalse(ir["capabilities"]["long_range_capacity"])

    def test_identity_has_no_capacity(self):
        ir = _ir(_inventory(root_target="aten.eye.default"), long_range_pairs=[[0, 2]])
        self.assertEqual(ir["operator"]["construction"], "identity")
        self.assertFalse(ir["capabilities"]["long_range_capacity"])

    def test_known_free_parameter_with_valid_pair_has_capacity(self):
        ir = _ir(_inventory(root_target="p_base", state_kind="InputKind.PARAMETER"), long_range_pairs=[[0, 2]])
        self.assertEqual(ir["operator"]["construction"], "unconstrained_parameter")
        self.assertTrue(ir["capabilities"]["long_range_capacity"])

    def test_free_parameter_with_no_long_range_pair_has_no_capacity(self):
        ir = _ir(_inventory(root_target="p_base", state_kind="InputKind.PARAMETER"), long_range_pairs=[])
        self.assertFalse(ir["capabilities"]["long_range_capacity"])

    def test_site_count_one_has_no_capacity(self):
        inventory = _inventory(root_target="p_base", state_kind="InputKind.PARAMETER")
        inventory["state"]["adjacency"]["structural_values"] = [[False]]
        inventory["state"]["adjacency"]["shape"] = [1, 1]
        ir = _ir(inventory, long_range_pairs=[[0, 0]])
        self.assertEqual(ir["topology"]["site_count"], 1)
        self.assertFalse(ir["capabilities"]["long_range_capacity"])

    def test_unknown_parameter_classification_has_no_capacity(self):
        ir = _ir(_inventory(root_target="p_base", state_kind=None), long_range_pairs=[[0, 2]])
        self.assertEqual(ir["operator"]["construction"], "unsupported")
        self.assertFalse(ir["capabilities"]["long_range_capacity"])

    def test_buffer_has_no_capacity(self):
        ir = _ir(_inventory(root_target="p_base", state_kind="InputKind.BUFFER"), long_range_pairs=[[0, 2]])
        self.assertEqual(ir["operator"]["construction"], "unsupported")
        self.assertFalse(ir["capabilities"]["long_range_capacity"])

    def test_user_input_has_no_capacity(self):
        ir = _ir(_inventory(root_target="p_base", state_kind="InputKind.USER_INPUT"), long_range_pairs=[[0, 2]])
        self.assertEqual(ir["operator"]["construction"], "unsupported")
        self.assertFalse(ir["capabilities"]["long_range_capacity"])


class SymmetrizedLongRangeCapacityTests(unittest.TestCase):
    """C. Symmetrized case: self-adjointness never depends on parameter
    confirmation; long-range capacity always does."""

    def test_trainable_symmetrized_with_valid_pair_has_both(self):
        ir = _ir(_symmetrized_inventory(state_kind="InputKind.PARAMETER"), long_range_pairs=[[0, 2]])
        self.assertEqual(ir["operator"]["construction"], "symmetrized")
        checks = DFT_CAPABILITY_PLUGIN.checks(ir)
        self.assertTrue(checks["self_adjoint"]["satisfied"])
        self.assertTrue(ir["capabilities"]["long_range_capacity"])
        candidates = {c.key: c for c in DFT_CAPABILITY_PLUGIN.formal_binding_candidates(ir)}
        self.assertIn('.parameter "base"', candidates["operator_form"].lean_expr)

    def test_fixed_or_unknown_symmetrized_is_self_adjoint_but_has_no_capacity(self):
        ir = _ir(_symmetrized_inventory(state_kind=None), long_range_pairs=[[0, 2]])
        self.assertEqual(ir["operator"]["construction"], "symmetrized")
        checks = DFT_CAPABILITY_PLUGIN.checks(ir)
        self.assertTrue(checks["self_adjoint"]["satisfied"])
        self.assertFalse(ir["capabilities"]["long_range_capacity"])
        candidates = {c.key: c for c in DFT_CAPABILITY_PLUGIN.formal_binding_candidates(ir)}
        self.assertNotIn('.parameter "base"', candidates["operator_form"].lean_expr)
        self.assertIn("opaque", candidates["operator_form"].lean_expr)


class GroupedLayoutLongRangeCapacityTests(unittest.TestCase):
    """D. Grouped layouts: never reduce to "some flattened off-diagonal
    entry" -- long-range site-coupling capacity is unsupported/unresolved
    (`None`) when the site-axis correspondence isn't established, even for
    a genuinely confirmed free parameter."""

    _GROUPED_LAYOUT = {"output_axes": [0, 1], "input_axes": [2, 3]}

    def test_grouped_layout_with_confirmed_parameter_is_unsupported_not_true(self):
        ir = _ir(
            _symmetrized_inventory(state_kind="InputKind.PARAMETER", orbitals=2),
            long_range_pairs=[[0, 2]], layout=self._GROUPED_LAYOUT,
        )
        self.assertEqual(ir["operator"]["construction"], "symmetrized")
        self.assertIsNone(ir["capabilities"]["long_range_capacity"])
        checks = DFT_CAPABILITY_PLUGIN.checks(ir)
        self.assertTrue(checks["self_adjoint"]["satisfied"])  # never weakened by grouping
        candidates = {c.key: c for c in DFT_CAPABILITY_PLUGIN.formal_binding_candidates(ir)}
        self.assertNotIn('.parameter "base"', candidates["operator_form"].lean_expr)
        self.assertIn("opaque", candidates["operator_form"].lean_expr)

    def test_plain_layout_is_unaffected(self):
        ir = _ir(_symmetrized_inventory(state_kind="InputKind.PARAMETER"), long_range_pairs=[[0, 2]])
        self.assertTrue(ir["capabilities"]["long_range_capacity"])


class MessagePassingIndependenceTests(unittest.TestCase):
    """E. Message-passing depth alone must never change the operator
    long-range-capacity result -- they are unrelated statements about
    unrelated things (GNN receptive field vs. the operator the
    architecture represents)."""

    def test_capacity_is_unchanged_by_message_passing_depth(self):
        # None of the currently-recognized operator recipes (bare or
        # symmetrized parameters) depend on message passing at all -- the
        # `stages` chain here is rooted at `density`, entirely outside the
        # operator's own ancestry, so `operator_message_depth` is honestly
        # `None` ("not applicable") regardless of how many stages exist.
        # `long_range_capacity` must be computed independently of it either
        # way -- this is checked directly, not just inferred from that.
        shallow = _ir(
            _inventory(root_target="p_base", state_kind="InputKind.PARAMETER", stages=0),
            long_range_pairs=[[0, 2]],
        )
        deep = _ir(
            _inventory(root_target="p_base", state_kind="InputKind.PARAMETER", stages=2),
            long_range_pairs=[[0, 2]],
        )
        self.assertIsNone(shallow["capabilities"]["operator_message_depth"])
        self.assertIsNone(deep["capabilities"]["operator_message_depth"])
        self.assertEqual(
            shallow["capabilities"]["long_range_capacity"], deep["capabilities"]["long_range_capacity"],
        )
        self.assertTrue(shallow["capabilities"]["long_range_capacity"])


if __name__ == "__main__":
    unittest.main()

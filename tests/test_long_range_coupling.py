"""Research-soundness correction: the theorem-centric non-locality premise
no longer treats "some off-diagonal matrix entry" as sufficient evidence
of physical long-range coupling, and no longer accepts a hand-supplied
long-range pair list either -- see `Testv2.StructuralV2.
canRepresentLongRangeCoupling`'s own docstring and `Testv2.Requirements`'
module docstring.

VISTA's current operational definition: `LongRange_R(i, j) :=
shortestPathDistance_G(i, j) > R`, where the adjacency graph `G` is
artifact-grounded, `R` (`locality_range`) is a specified interface integer
(default 4), and the long-range relation itself -- which pairs actually
count -- is always DERIVED, never hand-supplied. The architecture only has
capacity if it also contains a confirmed free parameter (never a fixed
buffer or unknown classification) with the freedom to realize coupling on
at least one derived long-range pair.
"""
import unittest

from dftcert.manifest import ManifestError
from dftcert.structural.core import structural_ir_from_inventory
from dftcert.structural.dft_capability_plugin import DFT_CAPABILITY_PLUGIN


def _ref(name):
    return {"node": name}


def _constraints(*, locality_range=None, layout=None):
    value = {
        "adjacency_state_name": "adjacency", "adjacency_convention": "source_target",
        "output_contracts": [
            {"index": 0, "role": "xc_energy"},
            {"index": 1, "role": "learned_self_energy"},
            {"index": 2, "role": "message_state"},
        ],
        "expected_locality": "non_local",
    }
    if locality_range is not None:
        value["locality_range"] = locality_range
    if layout is not None:
        value["operator_layout"] = layout
    return value


# A 6-site chain (path graph, symmetric): 0-1-2-3-4-5. Shortest-path
# distance between the two endpoints is 5 hops; every other pair is
# strictly closer.
_CHAIN6 = [
    [False, True, False, False, False, False],
    [True, False, True, False, False, False],
    [False, True, False, True, False, False],
    [False, False, True, False, True, False],
    [False, False, False, True, False, True],
    [False, False, False, False, True, False],
]

# Two disjoint 2-site components: {0, 1} and {2, 3}, no edges between them.
_DISCONNECTED4 = [
    [False, True, False, False],
    [True, False, False, False],
    [False, False, False, True],
    [False, False, True, False],
]


def _inventory(*, adjacency, root_target, root_kwargs=None, state_kind=None):
    """`learned_self_energy` is a bare placeholder `p_base` unless
    `root_target` names a zero/identity-constructing op instead (in which
    case `p_base` is unused and dropped from the graph)."""
    site_count = len(adjacency)
    nodes = [
        {"name": "b_adjacency", "op": "placeholder", "target": "b_adjacency", "args": [], "kwargs": {}},
        {"name": "density", "op": "placeholder", "target": "density", "args": [], "kwargs": {}},
        {"name": "relu", "op": "call_function", "target": "aten.relu.default", "args": [_ref("density")], "kwargs": {}},
    ]
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
        "args": [[_ref("relu"), _ref(operator_root), _ref("density")]], "kwargs": {},
    })
    state = {
        "adjacency": {
            "structural_values": adjacency, "graph_inputs": ["b_adjacency"],
            "shape": [site_count, site_count], "dtype": "torch.bool", "sha256": "a",
        },
    }
    if root_target == "p_base":
        state["p_base"] = {
            "graph_inputs": ["p_base"], "shape": [site_count, site_count],
            **({"state_kind": state_kind} if state_kind is not None else {}),
        }
    return {"nodes": nodes, "state": state}


def _symmetrized_inventory(*, adjacency, state_kind=None, orbitals=None):
    """`p_base + adjoint(p_base)` -- the `symmetrized` recipe. `orbitals`,
    if given, makes `p_base` rank-4 (`[N, m, N, m]`, a grouped layout) and
    builds the adjoint via `permute` (the only construction a grouped
    layout can recognize) instead of `transpose.int`."""
    site_count = len(adjacency)
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
            "structural_values": adjacency, "graph_inputs": ["b_adjacency"],
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


class DerivedFromArtifactTests(unittest.TestCase):
    """A. The long-range relation is derived automatically from the
    artifact-grounded adjacency graph and `R`, never supplied."""

    def test_extracted_graph_and_default_range_automatically_derives_relation(self):
        ir = _ir(_symmetrized_inventory(adjacency=_CHAIN6, state_kind="InputKind.PARAMETER"))
        self.assertEqual(ir["locality_range"], 4)
        # distance(0, 5) = 5 > 4: derived long-range, with no pair ever
        # supplied by the caller.
        self.assertTrue(ir["capabilities"]["long_range_capacity"])

    def test_changing_range_changes_derived_relation_without_changing_artifact_facts(self):
        narrow = _ir(_symmetrized_inventory(adjacency=_CHAIN6, state_kind="InputKind.PARAMETER"), locality_range=4)
        wide = _ir(_symmetrized_inventory(adjacency=_CHAIN6, state_kind="InputKind.PARAMETER"), locality_range=6)
        self.assertEqual(narrow["topology"], wide["topology"])
        self.assertEqual(narrow["operator"], wide["operator"])
        self.assertTrue(narrow["capabilities"]["long_range_capacity"])
        # Same chain, no pair is more than 6 hops apart (max distance 5):
        # widening R alone flips the derived relation.
        self.assertFalse(wide["capabilities"]["long_range_capacity"])

    def test_no_manually_supplied_pair_can_influence_the_result(self):
        constraints_without_field = _constraints(locality_range=4)
        constraints_with_stray_field = dict(constraints_without_field, long_range_pairs=[[0, 1]])
        inventory = _symmetrized_inventory(adjacency=_CHAIN6, state_kind="InputKind.PARAMETER")
        plain = structural_ir_from_inventory(
            inventory=inventory, artifact_sha256="a", extractor_version="t",
            input_constraints=constraints_without_field, plugin=DFT_CAPABILITY_PLUGIN,
        )
        with_stray_pairs = structural_ir_from_inventory(
            inventory=inventory, artifact_sha256="a", extractor_version="t",
            input_constraints=constraints_with_stray_field, plugin=DFT_CAPABILITY_PLUGIN,
        )
        self.assertEqual(plain["capabilities"], with_stray_pairs["capabilities"])
        self.assertNotIn("long_range_pairs", plain)
        self.assertNotIn("long_range_pairs", with_stray_pairs)


class DisconnectedAndSelfPairTests(unittest.TestCase):
    """B. Disconnected pairs and self-pairs."""

    def test_disconnected_components_are_long_range_at_any_range(self):
        narrow = _ir(_symmetrized_inventory(adjacency=_DISCONNECTED4, state_kind="InputKind.PARAMETER"), locality_range=0)
        wide = _ir(_symmetrized_inventory(adjacency=_DISCONNECTED4, state_kind="InputKind.PARAMETER"), locality_range=100)
        self.assertTrue(narrow["capabilities"]["long_range_capacity"])
        self.assertTrue(wide["capabilities"]["long_range_capacity"])

    def test_self_pair_is_never_a_long_range_witness(self):
        # A single site has no distinct partner at all -- the only "pair"
        # is a self-pair, which must never count, regardless of range.
        inventory = _inventory(adjacency=[[False]], root_target="p_base", state_kind="InputKind.PARAMETER")
        ir = _ir(inventory, locality_range=0)
        self.assertEqual(ir["topology"]["site_count"], 1)
        self.assertFalse(ir["capabilities"]["long_range_capacity"])


class OperatorCapacityTests(unittest.TestCase):
    """C. Operator capacity, over the derived relation."""

    def test_zero_has_no_capacity(self):
        ir = _ir(_inventory(adjacency=_CHAIN6, root_target="aten.zeros.default"), locality_range=4)
        self.assertEqual(ir["operator"]["construction"], "zero")
        self.assertFalse(ir["capabilities"]["long_range_capacity"])

    def test_identity_has_no_capacity(self):
        ir = _ir(_inventory(adjacency=_CHAIN6, root_target="aten.eye.default"), locality_range=4)
        self.assertEqual(ir["operator"]["construction"], "identity")
        self.assertFalse(ir["capabilities"]["long_range_capacity"])

    def test_known_free_parameter_with_a_derived_long_range_pair_has_capacity(self):
        ir = _ir(
            _inventory(adjacency=_CHAIN6, root_target="p_base", state_kind="InputKind.PARAMETER"),
            locality_range=4,
        )
        self.assertEqual(ir["operator"]["construction"], "unconstrained_parameter")
        self.assertTrue(ir["capabilities"]["long_range_capacity"])

    def test_free_parameter_with_no_derived_long_range_pair_has_no_capacity(self):
        ir = _ir(
            _inventory(adjacency=_CHAIN6, root_target="p_base", state_kind="InputKind.PARAMETER"),
            locality_range=6,
        )
        self.assertFalse(ir["capabilities"]["long_range_capacity"])

    def test_unknown_parameter_classification_has_no_capacity(self):
        ir = _ir(_inventory(adjacency=_CHAIN6, root_target="p_base", state_kind=None), locality_range=4)
        self.assertEqual(ir["operator"]["construction"], "unsupported")
        self.assertFalse(ir["capabilities"]["long_range_capacity"])

    def test_buffer_has_no_capacity(self):
        ir = _ir(_inventory(adjacency=_CHAIN6, root_target="p_base", state_kind="InputKind.BUFFER"), locality_range=4)
        self.assertEqual(ir["operator"]["construction"], "unsupported")
        self.assertFalse(ir["capabilities"]["long_range_capacity"])


class SymmetrizedLongRangeCapacityTests(unittest.TestCase):
    """D. Symmetrized case: self-adjointness never depends on parameter
    confirmation; long-range capacity always does."""

    def test_trainable_symmetrized_with_a_derived_pair_has_both(self):
        ir = _ir(_symmetrized_inventory(adjacency=_CHAIN6, state_kind="InputKind.PARAMETER"), locality_range=4)
        self.assertEqual(ir["operator"]["construction"], "symmetrized")
        checks = DFT_CAPABILITY_PLUGIN.checks(ir)
        self.assertTrue(checks["self_adjoint"]["satisfied"])
        self.assertTrue(ir["capabilities"]["long_range_capacity"])
        candidates = {c.key: c for c in DFT_CAPABILITY_PLUGIN.formal_binding_candidates(ir)}
        self.assertIn('.parameter "base"', candidates["operator_form"].lean_expr)
        self.assertEqual(candidates["locality_range"].provenance, "specified_interface")
        self.assertNotEqual(candidates["locality_range"].provenance, "artifact_grounded")

    def test_fixed_or_unknown_symmetrized_is_self_adjoint_but_has_no_capacity(self):
        ir = _ir(_symmetrized_inventory(adjacency=_CHAIN6, state_kind=None), locality_range=4)
        self.assertEqual(ir["operator"]["construction"], "symmetrized")
        checks = DFT_CAPABILITY_PLUGIN.checks(ir)
        self.assertTrue(checks["self_adjoint"]["satisfied"])
        self.assertFalse(ir["capabilities"]["long_range_capacity"])
        candidates = {c.key: c for c in DFT_CAPABILITY_PLUGIN.formal_binding_candidates(ir)}
        self.assertNotIn('.parameter "base"', candidates["operator_form"].lean_expr)
        self.assertIn("opaque", candidates["operator_form"].lean_expr)


class GroupedLayoutUnsupportedTopologyTests(unittest.TestCase):
    """E. Grouped layouts: never reduce to "some flattened off-diagonal
    entry" -- long-range site-coupling capacity is unsupported/unresolved
    (`None`), never guessed, when the site-axis correspondence isn't
    established, even for a genuinely confirmed free parameter."""

    _GROUPED_LAYOUT = {"output_axes": [0, 1], "input_axes": [2, 3]}

    def test_grouped_layout_is_unsupported_not_true(self):
        inventory = _symmetrized_inventory(adjacency=_CHAIN6, state_kind="InputKind.PARAMETER", orbitals=2)
        ir = _ir(inventory, locality_range=4, layout=self._GROUPED_LAYOUT)
        self.assertIsNone(ir["capabilities"]["long_range_capacity"])
        checks = DFT_CAPABILITY_PLUGIN.checks(ir)
        self.assertTrue(checks["self_adjoint"]["satisfied"])  # never weakened by grouping

    def test_missing_adjacency_blocks_the_locality_obligation(self):
        inventory = _symmetrized_inventory(adjacency=_CHAIN6, state_kind="InputKind.PARAMETER")
        del inventory["state"]["adjacency"]
        with self.assertRaises(ManifestError):
            _ir(inventory, locality_range=4)


class SelfAdjointOnlyDemoTests(unittest.TestCase):
    """F. The minimal self-adjointness demo carries no locality fields at
    all -- `locality_range` still defaults, and derivation never errors."""

    def test_self_adjoint_only_interface_has_no_locality_fields(self):
        constraints = _constraints()
        self.assertNotIn("locality_range", constraints)
        ir = _ir(_symmetrized_inventory(adjacency=_CHAIN6, state_kind="InputKind.PARAMETER"))
        self.assertEqual(ir["locality_range"], 4)
        self.assertEqual(ir["operator"]["construction"], "symmetrized")
        checks = DFT_CAPABILITY_PLUGIN.checks(ir)
        self.assertTrue(checks["self_adjoint"]["satisfied"])


if __name__ == "__main__":
    unittest.main()

"""Generalized operator layouts: an operator need not be a literal n x n
matrix. A self-energy stored with site AND orbital axes (shape [N, m, N, m])
is still, mathematically, a linear operator on the flattened N*m-dimensional
space once the domain/codomain axis groups are known -- so VISTA should not
hard-code "operator = rank-2 tensor" into its semantics. These tests cover
the grouped-layout path (`input_constraints.operator_layout`); the default
(omitted) layout's behavior is already covered end-to-end by the existing
V3/capability test suites, which pass unchanged under this generalization.
"""
import unittest

from dftcert.manifest import ManifestError
from dftcert.structural.core import structural_ir_from_inventory


def _ref(name):
    return {"node": name}


def _grouped_inventory(
    *, base, site_count=3, orbitals=2, topology_site_count=None,
    adjoint_target="permute", adjoint_args=None,
):
    """A ring with a `learned_self_energy` built from a rank-4 parameter
    `p_base` of shape [site_count, orbitals, site_count, orbitals] (site and
    orbital axes interleaved into two contiguous axis groups), symmetrized
    via an adjoint node. `topology_site_count` (defaults to `site_count`)
    lets a test declare a topology whose size disagrees with the operator's
    own site axis."""
    topology_site_count = site_count if topology_site_count is None else topology_site_count
    ring = [[False, True, True], [True, False, True], [True, True, False]]
    adjacency = [row[:topology_site_count] for row in ring[:topology_site_count]]
    nodes = [
        {"name": "b_adjacency", "op": "placeholder", "target": "b_adjacency", "args": [], "kwargs": {}},
        {"name": "p_base", "op": "placeholder", "target": "p_base", "args": [], "kwargs": {}},
        {"name": "density", "op": "placeholder", "target": "density", "args": [], "kwargs": {}},
    ]
    if adjoint_target == "permute":
        default_args = [_ref("p_base"), [2, 3, 0, 1]]
        nodes.append({
            "name": "adjoint", "op": "call_function", "target": "aten.permute.default",
            "args": adjoint_args if adjoint_args is not None else default_args, "kwargs": {},
        })
    else:
        nodes.append({
            "name": "adjoint", "op": "call_function", "target": adjoint_target,
            "args": [_ref("p_base")], "kwargs": {},
        })
    nodes.extend([
        {"name": "add", "op": "call_function", "target": "aten.add.Tensor", "args": [_ref("p_base"), _ref("adjoint")], "kwargs": {}},
        {"name": "relu", "op": "call_function", "target": "aten.relu.default", "args": [_ref("density")], "kwargs": {}},
        {"name": "output", "op": "output", "target": "output", "args": [[_ref("relu"), _ref("add"), _ref("density")]], "kwargs": {}},
    ])
    state = {
        "adjacency": {
            "structural_values": adjacency, "graph_inputs": ["b_adjacency"],
            "shape": [topology_site_count, topology_site_count], "dtype": "torch.bool", "sha256": "a",
        },
        "base": {
            "structural_values": base, "structural_value_kind": "numeric",
            "graph_inputs": ["p_base"], "shape": [site_count, orbitals, site_count, orbitals],
            "dtype": "torch.float32", "sha256": "b",
        },
    }
    return {"nodes": nodes, "state": state}


def _constraints(*, expected_locality="non_local", layout=None):
    value = {
        "adjacency_state_name": "adjacency", "adjacency_convention": "source_target",
        "output_contracts": [
            {"index": 0, "role": "xc_energy"},
            {"index": 1, "role": "learned_self_energy"},
            {"index": 2, "role": "message_state"},
        ],
        "expected_locality": expected_locality,
    }
    if layout is not None:
        value["operator_layout"] = layout
    return value


_LAYOUT = {"output_axes": [0, 1], "input_axes": [2, 3], "site_axis": 0}


def _zeros(site_count, orbitals):
    return [[[[0.0] * orbitals for _ in range(site_count)] for _ in range(orbitals)] for _ in range(site_count)]


class GroupedLayoutRecognitionTests(unittest.TestCase):
    def test_permute_with_correct_block_swap_is_recognized_as_symmetrized(self):
        base = _zeros(3, 2)
        ir = structural_ir_from_inventory(
            inventory=_grouped_inventory(base=base), artifact_sha256="a", extractor_version="t",
            input_constraints=_constraints(expected_locality="local", layout=_LAYOUT),
        )
        self.assertEqual(ir["operator"]["construction"], "symmetrized")
        self.assertEqual(ir["operator"]["layout"], _LAYOUT)

    def test_permute_with_wrong_permutation_is_not_recognized_as_adjoint(self):
        base = _zeros(3, 2)
        ir = structural_ir_from_inventory(
            inventory=_grouped_inventory(base=base, adjoint_args=[_ref("p_base"), [1, 0, 3, 2]]),
            artifact_sha256="a", extractor_version="t",
            input_constraints=_constraints(expected_locality="local", layout=_LAYOUT),
        )
        # Falls through to unconstrained_parameter/unsupported -- the wrong
        # permutation is never silently treated as the adjoint.
        self.assertNotEqual(ir["operator"]["construction"], "symmetrized")

    def test_numpy_transpose_is_not_a_valid_adjoint_for_a_grouped_layout(self):
        # numpy_T/.t()/transpose.int can only realize a genuine two-axis swap;
        # for r > 1 axes per side, only an explicit `permute` with the exact
        # block-swap permutation counts.
        base = _zeros(3, 2)
        ir = structural_ir_from_inventory(
            inventory=_grouped_inventory(base=base, adjoint_target="aten.numpy_T.default"),
            artifact_sha256="a", extractor_version="t",
            input_constraints=_constraints(expected_locality="local", layout=_LAYOUT),
        )
        self.assertNotEqual(ir["operator"]["construction"], "symmetrized")


class GroupedLayoutLocalityTests(unittest.TestCase):
    def test_onsite_orbital_mixing_is_still_local(self):
        # Nonzero only at (site=0, orbital 0) x (site=0, orbital 1): same
        # site on both sides -- must NOT be flagged as a non-local coupling.
        base = _zeros(3, 2)
        base[0][0][0][1] = 5.0
        ir = structural_ir_from_inventory(
            inventory=_grouped_inventory(base=base), artifact_sha256="a", extractor_version="t",
            input_constraints=_constraints(expected_locality="local", layout=_LAYOUT),
        )
        self.assertTrue(ir["locality"]["available"])
        self.assertTrue(ir["locality"]["observed_local"])
        self.assertEqual(ir["locality"]["off_diagonal_nonzero"], [])

    def test_cross_site_coupling_is_non_local_regardless_of_orbital(self):
        # Nonzero at (site=0, orbital 0) x (site=1, orbital 0): a genuine
        # site-to-site coupling.
        base = _zeros(3, 2)
        base[0][0][1][0] = 1.0
        ir = structural_ir_from_inventory(
            inventory=_grouped_inventory(base=base), artifact_sha256="a", extractor_version="t",
            input_constraints=_constraints(expected_locality="non_local", layout=_LAYOUT),
        )
        self.assertTrue(ir["locality"]["available"])
        self.assertFalse(ir["locality"]["observed_local"])
        self.assertEqual(
            sorted((item["source"], item["target"]) for item in ir["locality"]["off_diagonal_nonzero"]),
            [(0, 1), (1, 0)],
        )


class OperatorLayoutValidationTests(unittest.TestCase):
    def test_default_layout_matches_plain_matrix_behavior(self):
        base = _zeros(3, 2)
        ir = structural_ir_from_inventory(
            inventory=_grouped_inventory(base=base), artifact_sha256="a", extractor_version="t",
            input_constraints=_constraints(expected_locality="local"),
        )
        self.assertEqual(ir["operator"]["layout"], {"output_axes": [0], "input_axes": [1], "site_axis": 0})
        # site_axis=0 within a [3,2,3,2] tensor at site_axis position within
        # a *default* rank-1 layout expects shape [site_count, site_count] --
        # the rank-4 parameter is therefore an unrecognizable shape under the
        # default layout, so locality is honestly undetermined rather than
        # guessed at.
        self.assertFalse(ir["locality"]["available"])

    def test_reordered_axis_grouping_is_rejected(self):
        with self.assertRaises(ManifestError):
            structural_ir_from_inventory(
                inventory=_grouped_inventory(base=_zeros(3, 2)), artifact_sha256="a", extractor_version="t",
                input_constraints=_constraints(layout={"output_axes": [1, 0], "input_axes": [2, 3], "site_axis": 0}),
            )

    def test_mismatched_group_lengths_are_rejected(self):
        with self.assertRaises(ManifestError):
            structural_ir_from_inventory(
                inventory=_grouped_inventory(base=_zeros(3, 2)), artifact_sha256="a", extractor_version="t",
                input_constraints=_constraints(layout={"output_axes": [0], "input_axes": [1, 2], "site_axis": 0}),
            )

    def test_site_axis_out_of_range_is_rejected(self):
        with self.assertRaises(ManifestError):
            structural_ir_from_inventory(
                inventory=_grouped_inventory(base=_zeros(3, 2)), artifact_sha256="a", extractor_version="t",
                input_constraints=_constraints(layout={"output_axes": [0, 1], "input_axes": [2, 3], "site_axis": 2}),
            )

    def test_operator_site_axis_dimension_must_match_topology_site_count(self):
        # base declares a genuine [3,2,3,2] shape but topology only has 2
        # sites -- the operator's site axis (size 3) disagrees with the
        # declared topology, so locality must be undetermined, never guessed.
        ir = structural_ir_from_inventory(
            inventory=_grouped_inventory(base=_zeros(3, 2), site_count=3, topology_site_count=2),
            artifact_sha256="a", extractor_version="t",
            input_constraints=_constraints(layout=_LAYOUT),
        )
        self.assertFalse(ir["locality"]["available"])


if __name__ == "__main__":
    unittest.main()

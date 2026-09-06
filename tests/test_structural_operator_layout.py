"""Generalized operator layouts: an operator need not be a literal n x n
matrix. A self-energy stored with site AND orbital axes (shape [N, m, N, m])
is still, mathematically, a linear operator on the flattened N*m-dimensional
space once the domain/codomain axis groups are known -- so VISTA should not
hard-code "operator = rank-2 tensor" into its semantics. This only matters
for correctly recognizing the adjoint construction (`self_adjoint`/
`non_local_capacity`) -- this plugin never reads a real tensor's values at
all, so there is no site-projection/locality concept to test here.
"""
import unittest

from dftcert.manifest import ManifestError
from dftcert.structural.core import structural_ir_from_inventory


def _ref(name):
    return {"node": name}


def _grouped_inventory(*, site_count=3, orbitals=2, adjoint_target="permute", adjoint_args=None):
    """A ring with a `learned_self_energy` built from a rank-4 parameter
    `p_base` of shape [site_count, orbitals, site_count, orbitals] (site and
    orbital axes each split into two contiguous axis groups), symmetrized
    via an adjoint node."""
    ring = [[False, True, True], [True, False, True], [True, True, False]]
    adjacency = [row[:site_count] for row in ring[:site_count]]
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
            "shape": [site_count, site_count], "dtype": "torch.bool", "sha256": "a",
        },
        "base": {
            "structural_values": [[[[0.0] * orbitals for _ in range(site_count)] for _ in range(orbitals)] for _ in range(site_count)],
            "structural_value_kind": "numeric",
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


_LAYOUT = {"output_axes": [0, 1], "input_axes": [2, 3]}


class GroupedLayoutRecognitionTests(unittest.TestCase):
    def test_permute_with_correct_block_swap_is_recognized_as_symmetrized(self):
        ir = structural_ir_from_inventory(
            inventory=_grouped_inventory(), artifact_sha256="a", extractor_version="t",
            input_constraints=_constraints(expected_locality="local", layout=_LAYOUT),
        )
        self.assertEqual(ir["operator"]["construction"], "symmetrized")
        self.assertEqual(ir["operator"]["layout"], _LAYOUT)

    def test_permute_with_wrong_permutation_is_not_recognized_as_adjoint(self):
        ir = structural_ir_from_inventory(
            inventory=_grouped_inventory(adjoint_args=[_ref("p_base"), [1, 0, 3, 2]]),
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
        ir = structural_ir_from_inventory(
            inventory=_grouped_inventory(adjoint_target="aten.numpy_T.default"),
            artifact_sha256="a", extractor_version="t",
            input_constraints=_constraints(expected_locality="local", layout=_LAYOUT),
        )
        self.assertNotEqual(ir["operator"]["construction"], "symmetrized")


class OperatorLayoutValidationTests(unittest.TestCase):
    def test_default_layout_is_the_plain_matrix(self):
        ir = structural_ir_from_inventory(
            inventory=_grouped_inventory(), artifact_sha256="a", extractor_version="t",
            input_constraints=_constraints(expected_locality="local"),
        )
        self.assertEqual(ir["operator"]["layout"], {"output_axes": [0], "input_axes": [1]})

    def test_reordered_axis_grouping_is_rejected(self):
        with self.assertRaises(ManifestError):
            structural_ir_from_inventory(
                inventory=_grouped_inventory(), artifact_sha256="a", extractor_version="t",
                input_constraints=_constraints(layout={"output_axes": [1, 0], "input_axes": [2, 3]}),
            )

    def test_mismatched_group_lengths_are_rejected(self):
        with self.assertRaises(ManifestError):
            structural_ir_from_inventory(
                inventory=_grouped_inventory(), artifact_sha256="a", extractor_version="t",
                input_constraints=_constraints(layout={"output_axes": [0], "input_axes": [1, 2]}),
            )


if __name__ == "__main__":
    unittest.main()

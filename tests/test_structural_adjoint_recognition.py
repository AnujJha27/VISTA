"""`_is_adjoint_of` must inspect a transpose/permute node's real axis
arguments, never accept it by op name alone. A no-op call (swapping an axis
with itself, or a permutation that changes nothing) must not be classified
as constructing the adjoint just because its op name is on the reviewed
list -- that would let `self_adjoint`/`non_local_capacity` claim a
guarantee for `B + B` (not generally symmetric) as if it were `B + B^T`.
"""
import unittest

from dftcert.structural.core import structural_ir_from_inventory


def _ref(name):
    return {"node": name}


def _inventory(*, adjoint_target, adjoint_args):
    nodes = [
        {"name": "b_adjacency", "op": "placeholder", "target": "b_adjacency", "args": [], "kwargs": {}},
        {"name": "p_base", "op": "placeholder", "target": "p_base", "args": [], "kwargs": {}},
        {"name": "density", "op": "placeholder", "target": "density", "args": [], "kwargs": {}},
        {"name": "adjoint", "op": "call_function", "target": adjoint_target, "args": adjoint_args, "kwargs": {}},
        {"name": "add", "op": "call_function", "target": "aten.add.Tensor", "args": [_ref("p_base"), _ref("adjoint")], "kwargs": {}},
        {"name": "relu", "op": "call_function", "target": "aten.relu.default", "args": [_ref("density")], "kwargs": {}},
        {"name": "output", "op": "output", "target": "output", "args": [[_ref("relu"), _ref("add"), _ref("density")]], "kwargs": {}},
    ]
    adjacency = [[False, True, False], [False, False, True], [False, False, False]]
    state = {
        "adjacency": {"structural_values": adjacency, "graph_inputs": ["b_adjacency"], "shape": [3, 3], "dtype": "torch.bool", "sha256": "a"},
        "base": {
            "structural_values": [[0.0] * 3 for _ in range(3)], "structural_value_kind": "numeric",
            "graph_inputs": ["p_base"], "shape": [3, 3], "dtype": "torch.float32", "sha256": "b",
        },
    }
    return {"nodes": nodes, "state": state}


def _constraints():
    return {
        "adjacency_state_name": "adjacency", "adjacency_convention": "source_target",
        "output_contracts": [
            {"index": 0, "role": "xc_energy"},
            {"index": 1, "role": "learned_self_energy"},
            {"index": 2, "role": "message_state"},
        ],
        "expected_locality": "local",
    }


def _construction(**inventory_kwargs):
    ir = structural_ir_from_inventory(
        inventory=_inventory(**inventory_kwargs), artifact_sha256="a", extractor_version="t",
        input_constraints=_constraints(),
    )
    return ir["operator"]["construction"]


def _bare_param_inventory(*, state_kind):
    """`learned_self_energy` is directly the bare placeholder `p_base` (no
    add/adjoint) -- the "unconstrained_parameter" recipe path -- with its
    state entry's `state_kind` set as given."""
    nodes = [
        {"name": "b_adjacency", "op": "placeholder", "target": "b_adjacency", "args": [], "kwargs": {}},
        {"name": "p_base", "op": "placeholder", "target": "p_base", "args": [], "kwargs": {}},
        {"name": "density", "op": "placeholder", "target": "density", "args": [], "kwargs": {}},
        {"name": "relu", "op": "call_function", "target": "aten.relu.default", "args": [_ref("density")], "kwargs": {}},
        {"name": "output", "op": "output", "target": "output", "args": [[_ref("relu"), _ref("p_base"), _ref("density")]], "kwargs": {}},
    ]
    adjacency = [[False, True, False], [False, False, True], [False, False, False]]
    state = {
        "adjacency": {"structural_values": adjacency, "graph_inputs": ["b_adjacency"], "shape": [3, 3], "dtype": "torch.bool", "sha256": "a"},
        "base": {
            "structural_values": [[0.0] * 3 for _ in range(3)], "structural_value_kind": "numeric",
            "graph_inputs": ["p_base"], "shape": [3, 3], "dtype": "torch.float32", "sha256": "b",
            **({"state_kind": state_kind} if state_kind is not None else {}),
        },
    }
    return {"nodes": nodes, "state": state}


class NoOpTransposeIsNotAnAdjointTests(unittest.TestCase):
    def test_transpose_int_swapping_an_axis_with_itself_is_not_symmetrized(self):
        self.assertNotEqual(_construction(adjoint_target="aten.transpose.int", adjoint_args=[_ref("p_base"), 0, 0]), "symmetrized")

    def test_permute_with_the_identity_permutation_is_not_symmetrized(self):
        self.assertNotEqual(_construction(adjoint_target="aten.permute.default", adjoint_args=[_ref("p_base"), [0, 1]]), "symmetrized")

    def test_transpose_int_actually_swapping_the_two_axes_is_symmetrized(self):
        self.assertEqual(_construction(adjoint_target="aten.transpose.int", adjoint_args=[_ref("p_base"), 0, 1]), "symmetrized")

    def test_permute_actually_swapping_the_two_axes_is_symmetrized(self):
        self.assertEqual(_construction(adjoint_target="aten.permute.default", adjoint_args=[_ref("p_base"), [1, 0]]), "symmetrized")


class UserInputIsNotAnUnconstrainedParameterTests(unittest.TestCase):
    def test_a_bare_parameter_placeholder_is_recognized(self):
        ir = structural_ir_from_inventory(
            inventory=_bare_param_inventory(state_kind="InputKind.PARAMETER"),
            artifact_sha256="a", extractor_version="t", input_constraints=_constraints(),
        )
        self.assertEqual(ir["operator"]["construction"], "unconstrained_parameter")

    def test_missing_state_kind_metadata_is_still_recognized(self):
        # Permissive when the classification itself isn't available (e.g. an
        # older extractor, or a hand-authored fixture) -- fails closed only
        # on an explicit user-input signal, never on missing metadata.
        ir = structural_ir_from_inventory(
            inventory=_bare_param_inventory(state_kind=None),
            artifact_sha256="a", extractor_version="t", input_constraints=_constraints(),
        )
        self.assertEqual(ir["operator"]["construction"], "unconstrained_parameter")

    def test_a_plain_runtime_input_is_not_an_unconstrained_parameter(self):
        # A placeholder explicitly classified as a runtime user input (not a
        # trained weight) must not be certified as a free/trainable matrix --
        # self_adjoint and non_local_capacity would otherwise describe
        # activation data, not anything the model actually learns.
        ir = structural_ir_from_inventory(
            inventory=_bare_param_inventory(state_kind="InputKind.USER_INPUT"),
            artifact_sha256="a", extractor_version="t", input_constraints=_constraints(),
        )
        self.assertEqual(ir["operator"]["construction"], "unsupported")


if __name__ == "__main__":
    unittest.main()

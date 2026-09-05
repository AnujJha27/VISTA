import Testv2.StructuralV2

namespace DFTCert.StructuralRun_64fe1c141559

def sourceSha256 : String := "74a752c9627ea371de051df9b17cc50a318831c4a7fc2f443345b168fcc84bf9"
def irSha256 : String := "64fe1c141559c6e26d6fcfe8c5a7fd1e15d63fa0c0a81dc1f4f683f4e2d80b45"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 2
-- observedNonzeroOffDiagonal is computed by the analyzer directly from the
-- candidate's own extracted parameter values (rule operator_offdiag_abs_threshold
-- @1, threshold 1e-09).
-- Nobody supplies these pairs; they are read off the candidate's real weights.
def observedNonzeroOffDiagonal : List (Nat × Nat) := [(0, 1), (0, 2), (0, 3), (0, 4), (1, 0), (1, 2), (1, 3), (1, 4), (2, 0), (2, 1), (2, 3), (2, 4), (3, 0), (3, 1), (3, 2), (3, 4), (4, 0), (4, 1), (4, 2), (4, 3)]
def expectedLocal : Bool := false
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_64fe1c141559

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_64fe1c141559.xcForm = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_64fe1c141559.operatorForm = true := by decide

theorem generated_locality_structure : Testv2.StructuralV2.localityMatches DFTCert.StructuralRun_64fe1c141559.expectedLocal DFTCert.StructuralRun_64fe1c141559.observedNonzeroOffDiagonal = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_64fe1c141559.sourceSha256 = "74a752c9627ea371de051df9b17cc50a318831c4a7fc2f443345b168fcc84bf9" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_64fe1c141559.irSha256 = "64fe1c141559c6e26d6fcfe8c5a7fd1e15d63fa0c0a81dc1f4f683f4e2d80b45" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_64fe1c141559.sourceSha256 = "74a752c9627ea371de051df9b17cc50a318831c4a7fc2f443345b168fcc84bf9")
#check (generated_ir_binding : DFTCert.StructuralRun_64fe1c141559.irSha256 = "64fe1c141559c6e26d6fcfe8c5a7fd1e15d63fa0c0a81dc1f4f683f4e2d80b45")

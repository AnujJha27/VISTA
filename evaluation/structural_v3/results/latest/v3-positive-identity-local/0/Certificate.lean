import Testv2.StructuralV2

namespace DFTCert.StructuralRun_b9b7ab1d5b8e

def sourceSha256 : String := "a134938812f2c427201db499a45a7e0c0d63c3564b5e751cc04b629124a8b2b4"
def irSha256 : String := "b9b7ab1d5b8ed29c1eca84bdc3d55cce71fbc9cfaf83db5b69b7fa82a4e83afc"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 2
-- observedNonzeroOffDiagonal is computed by the analyzer directly from the
-- candidate's own extracted parameter values (rule operator_offdiag_abs_threshold
-- @1, threshold 1e-09).
-- Nobody supplies these pairs; they are read off the candidate's real weights.
def observedNonzeroOffDiagonal : List (Nat × Nat) := []
def expectedLocal : Bool := true
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .identity

end DFTCert.StructuralRun_b9b7ab1d5b8e

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_b9b7ab1d5b8e.xcForm = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_b9b7ab1d5b8e.operatorForm = true := by decide

theorem generated_locality_structure : Testv2.StructuralV2.localityMatches DFTCert.StructuralRun_b9b7ab1d5b8e.expectedLocal DFTCert.StructuralRun_b9b7ab1d5b8e.observedNonzeroOffDiagonal = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_b9b7ab1d5b8e.sourceSha256 = "a134938812f2c427201db499a45a7e0c0d63c3564b5e751cc04b629124a8b2b4" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_b9b7ab1d5b8e.irSha256 = "b9b7ab1d5b8ed29c1eca84bdc3d55cce71fbc9cfaf83db5b69b7fa82a4e83afc" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_b9b7ab1d5b8e.sourceSha256 = "a134938812f2c427201db499a45a7e0c0d63c3564b5e751cc04b629124a8b2b4")
#check (generated_ir_binding : DFTCert.StructuralRun_b9b7ab1d5b8e.irSha256 = "b9b7ab1d5b8ed29c1eca84bdc3d55cce71fbc9cfaf83db5b69b7fa82a4e83afc")

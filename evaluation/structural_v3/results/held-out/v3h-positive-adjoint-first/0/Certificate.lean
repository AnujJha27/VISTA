import Testv2.StructuralV2

namespace DFTCert.StructuralRun_cc9a902a33f1

def sourceSha256 : String := "63dbb701e042ce2dd810ae1e41eb89d7c202eef0ebb145501476f872a4cc3fbe"
def irSha256 : String := "cc9a902a33f1d0ca0c14d469729c1f3eec14435cf8076b28ad691171d429cd2d"
def edges : List (Nat × Nat) := [(0, 1), (1, 2), (2, 3)]
def messageDepth : Nat := 2
-- observedNonzeroOffDiagonal is computed by the analyzer directly from the
-- candidate's own extracted parameter values (rule operator_offdiag_abs_threshold
-- @1, threshold 1e-09).
-- Nobody supplies these pairs; they are read off the candidate's real weights.
def observedNonzeroOffDiagonal : List (Nat × Nat) := [(0, 1), (0, 2), (0, 3), (1, 0), (1, 2), (1, 3), (2, 0), (2, 1), (2, 3), (3, 0), (3, 1), (3, 2)]
def expectedLocal : Bool := false
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_cc9a902a33f1

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_cc9a902a33f1.xcForm = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_cc9a902a33f1.operatorForm = true := by decide

theorem generated_locality_structure : Testv2.StructuralV2.localityMatches DFTCert.StructuralRun_cc9a902a33f1.expectedLocal DFTCert.StructuralRun_cc9a902a33f1.observedNonzeroOffDiagonal = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_cc9a902a33f1.sourceSha256 = "63dbb701e042ce2dd810ae1e41eb89d7c202eef0ebb145501476f872a4cc3fbe" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_cc9a902a33f1.irSha256 = "cc9a902a33f1d0ca0c14d469729c1f3eec14435cf8076b28ad691171d429cd2d" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_cc9a902a33f1.sourceSha256 = "63dbb701e042ce2dd810ae1e41eb89d7c202eef0ebb145501476f872a4cc3fbe")
#check (generated_ir_binding : DFTCert.StructuralRun_cc9a902a33f1.irSha256 = "cc9a902a33f1d0ca0c14d469729c1f3eec14435cf8076b28ad691171d429cd2d")

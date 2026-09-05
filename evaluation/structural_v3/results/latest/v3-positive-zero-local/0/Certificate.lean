import Testv2.StructuralV2

namespace DFTCert.StructuralRun_c84ec50fb164

def sourceSha256 : String := "3e9055750cff5dfb67dcba06fccc9b6d8d8dd2cf9dea77bcd0db3f3358623758"
def irSha256 : String := "c84ec50fb164f6602d903a6a972622455f0a77cfcb6f62372bc5ce21ee745e66"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 2
-- observedNonzeroOffDiagonal is computed by the analyzer directly from the
-- candidate's own extracted parameter values (rule operator_offdiag_abs_threshold
-- @1, threshold 1e-09).
-- Nobody supplies these pairs; they are read off the candidate's real weights.
def observedNonzeroOffDiagonal : List (Nat × Nat) := []
def expectedLocal : Bool := true
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .zero

end DFTCert.StructuralRun_c84ec50fb164

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_c84ec50fb164.xcForm = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_c84ec50fb164.operatorForm = true := by decide

theorem generated_locality_structure : Testv2.StructuralV2.localityMatches DFTCert.StructuralRun_c84ec50fb164.expectedLocal DFTCert.StructuralRun_c84ec50fb164.observedNonzeroOffDiagonal = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_c84ec50fb164.sourceSha256 = "3e9055750cff5dfb67dcba06fccc9b6d8d8dd2cf9dea77bcd0db3f3358623758" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_c84ec50fb164.irSha256 = "c84ec50fb164f6602d903a6a972622455f0a77cfcb6f62372bc5ce21ee745e66" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_c84ec50fb164.sourceSha256 = "3e9055750cff5dfb67dcba06fccc9b6d8d8dd2cf9dea77bcd0db3f3358623758")
#check (generated_ir_binding : DFTCert.StructuralRun_c84ec50fb164.irSha256 = "c84ec50fb164f6602d903a6a972622455f0a77cfcb6f62372bc5ce21ee745e66")

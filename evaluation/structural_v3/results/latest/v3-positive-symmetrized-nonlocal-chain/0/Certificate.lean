import Testv2.StructuralV2

namespace DFTCert.StructuralRun_2e85c4dffd94

def sourceSha256 : String := "695aadf6435b1f276f16ffe6f398f9369c5d2f62505fabf6f61abfb06038523c"
def irSha256 : String := "2e85c4dffd94722aa1e3c9ca5bb8bcbdd459676acc1e4fb5603bbd11fdeb7617"
def edges : List (Nat × Nat) := [(0, 1), (1, 2), (2, 3)]
def messageDepth : Nat := 3
-- observedNonzeroOffDiagonal is computed by the analyzer directly from the
-- candidate's own extracted parameter values (rule operator_offdiag_abs_threshold
-- @1, threshold 1e-09).
-- Nobody supplies these pairs; they are read off the candidate's real weights.
def observedNonzeroOffDiagonal : List (Nat × Nat) := [(0, 1), (0, 2), (0, 3), (1, 0), (1, 2), (1, 3), (2, 0), (2, 1), (2, 3), (3, 0), (3, 1), (3, 2)]
def expectedLocal : Bool := false
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_2e85c4dffd94

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_2e85c4dffd94.xcForm = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_2e85c4dffd94.operatorForm = true := by decide

theorem generated_locality_structure : Testv2.StructuralV2.localityMatches DFTCert.StructuralRun_2e85c4dffd94.expectedLocal DFTCert.StructuralRun_2e85c4dffd94.observedNonzeroOffDiagonal = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_2e85c4dffd94.sourceSha256 = "695aadf6435b1f276f16ffe6f398f9369c5d2f62505fabf6f61abfb06038523c" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_2e85c4dffd94.irSha256 = "2e85c4dffd94722aa1e3c9ca5bb8bcbdd459676acc1e4fb5603bbd11fdeb7617" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_2e85c4dffd94.sourceSha256 = "695aadf6435b1f276f16ffe6f398f9369c5d2f62505fabf6f61abfb06038523c")
#check (generated_ir_binding : DFTCert.StructuralRun_2e85c4dffd94.irSha256 = "2e85c4dffd94722aa1e3c9ca5bb8bcbdd459676acc1e4fb5603bbd11fdeb7617")

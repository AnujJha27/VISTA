import Testv2.StructuralV2

namespace DFTCert.StructuralRun_c235881fa59e

def sourceSha256 : String := "78aeddb8e086c55a5ab46736c0fb58a0891cfdb3195ce6b4a0f4fc56baec5fc2"
def irSha256 : String := "c235881fa59ec7010598e1e63da5100bfa0b9090422bc48c7f7b20167ec54cec"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (3, 2), (1, 3), (2, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_c235881fa59e

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_c235881fa59e.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_c235881fa59e.edges DFTCert.StructuralRun_c235881fa59e.messageDepth DFTCert.StructuralRun_c235881fa59e.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_c235881fa59e.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_c235881fa59e.sourceSha256 = "78aeddb8e086c55a5ab46736c0fb58a0891cfdb3195ce6b4a0f4fc56baec5fc2" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_c235881fa59e.irSha256 = "c235881fa59ec7010598e1e63da5100bfa0b9090422bc48c7f7b20167ec54cec" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_c235881fa59e.sourceSha256 = "78aeddb8e086c55a5ab46736c0fb58a0891cfdb3195ce6b4a0f4fc56baec5fc2")
#check (generated_ir_binding : DFTCert.StructuralRun_c235881fa59e.irSha256 = "c235881fa59ec7010598e1e63da5100bfa0b9090422bc48c7f7b20167ec54cec")

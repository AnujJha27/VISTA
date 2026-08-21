import Testv2.StructuralV2

namespace DFTCert.StructuralRun_7cd77a0102d8

def sourceSha256 : String := "d969989439d4a4e40ec241412e282ba59e556bcb41388aa23d592df6f490c7ff"
def irSha256 : String := "7cd77a0102d85b2947ee8fdba0c96a138e20445cb9f3731760e8c6e9facbc6bd"
def edges : List (Nat × Nat) := [(0, 1), (1, 2), (2, 3)]
def messageDepth : Nat := 4
def requiredCouplings : List (Nat × Nat) := [(0, 3)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_7cd77a0102d8

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_7cd77a0102d8.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_7cd77a0102d8.edges DFTCert.StructuralRun_7cd77a0102d8.messageDepth DFTCert.StructuralRun_7cd77a0102d8.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_7cd77a0102d8.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_7cd77a0102d8.sourceSha256 = "d969989439d4a4e40ec241412e282ba59e556bcb41388aa23d592df6f490c7ff" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_7cd77a0102d8.irSha256 = "7cd77a0102d85b2947ee8fdba0c96a138e20445cb9f3731760e8c6e9facbc6bd" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_7cd77a0102d8.sourceSha256 = "d969989439d4a4e40ec241412e282ba59e556bcb41388aa23d592df6f490c7ff")
#check (generated_ir_binding : DFTCert.StructuralRun_7cd77a0102d8.irSha256 = "7cd77a0102d85b2947ee8fdba0c96a138e20445cb9f3731760e8c6e9facbc6bd")

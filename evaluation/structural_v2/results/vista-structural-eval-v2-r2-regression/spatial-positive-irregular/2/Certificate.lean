import Testv2.StructuralV2

namespace DFTCert.StructuralRun_39bbb1ce33d6

def sourceSha256 : String := "25a468c529439fe7f0e2757de95e65a366bc40c3a228b747fb7525fbac2a0f27"
def irSha256 : String := "39bbb1ce33d6352ca975bce6d41e98ac5dc41ed52494ef9ecb6a276c6cb77537"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (3, 2), (1, 3), (2, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_39bbb1ce33d6

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_39bbb1ce33d6.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_39bbb1ce33d6.edges DFTCert.StructuralRun_39bbb1ce33d6.messageDepth DFTCert.StructuralRun_39bbb1ce33d6.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_39bbb1ce33d6.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_39bbb1ce33d6.sourceSha256 = "25a468c529439fe7f0e2757de95e65a366bc40c3a228b747fb7525fbac2a0f27" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_39bbb1ce33d6.irSha256 = "39bbb1ce33d6352ca975bce6d41e98ac5dc41ed52494ef9ecb6a276c6cb77537" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_39bbb1ce33d6.sourceSha256 = "25a468c529439fe7f0e2757de95e65a366bc40c3a228b747fb7525fbac2a0f27")
#check (generated_ir_binding : DFTCert.StructuralRun_39bbb1ce33d6.irSha256 = "39bbb1ce33d6352ca975bce6d41e98ac5dc41ed52494ef9ecb6a276c6cb77537")

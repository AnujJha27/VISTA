import Testv2.StructuralV2

namespace DFTCert.StructuralRun_ea5d835e7296

def sourceSha256 : String := "fa65580ae237bf7c2d3dd86fd5fb383b89a538c4fb293f4e6c8ca7338444e30c"
def irSha256 : String := "ea5d835e729668688266dc38c1603f7defa9cdd48eb081b312070a11fde9a7e0"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (3, 2), (1, 3), (2, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_ea5d835e7296

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_ea5d835e7296.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_ea5d835e7296.edges DFTCert.StructuralRun_ea5d835e7296.messageDepth DFTCert.StructuralRun_ea5d835e7296.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_ea5d835e7296.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_ea5d835e7296.sourceSha256 = "fa65580ae237bf7c2d3dd86fd5fb383b89a538c4fb293f4e6c8ca7338444e30c" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_ea5d835e7296.irSha256 = "ea5d835e729668688266dc38c1603f7defa9cdd48eb081b312070a11fde9a7e0" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_ea5d835e7296.sourceSha256 = "fa65580ae237bf7c2d3dd86fd5fb383b89a538c4fb293f4e6c8ca7338444e30c")
#check (generated_ir_binding : DFTCert.StructuralRun_ea5d835e7296.irSha256 = "ea5d835e729668688266dc38c1603f7defa9cdd48eb081b312070a11fde9a7e0")

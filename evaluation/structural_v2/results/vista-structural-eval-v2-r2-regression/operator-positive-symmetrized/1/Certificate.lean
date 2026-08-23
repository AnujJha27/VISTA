import Testv2.StructuralV2

namespace DFTCert.StructuralRun_f20d09a85d3f

def sourceSha256 : String := "a2a09ff51d4da445041a1cb03de4594c36b023701df4775ffa74834285bbfc89"
def irSha256 : String := "f20d09a85d3f642085fcf63e35d00524f004b87e572587047279554e672b635f"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_f20d09a85d3f

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_f20d09a85d3f.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_f20d09a85d3f.edges DFTCert.StructuralRun_f20d09a85d3f.messageDepth DFTCert.StructuralRun_f20d09a85d3f.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_f20d09a85d3f.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_f20d09a85d3f.sourceSha256 = "a2a09ff51d4da445041a1cb03de4594c36b023701df4775ffa74834285bbfc89" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_f20d09a85d3f.irSha256 = "f20d09a85d3f642085fcf63e35d00524f004b87e572587047279554e672b635f" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_f20d09a85d3f.sourceSha256 = "a2a09ff51d4da445041a1cb03de4594c36b023701df4775ffa74834285bbfc89")
#check (generated_ir_binding : DFTCert.StructuralRun_f20d09a85d3f.irSha256 = "f20d09a85d3f642085fcf63e35d00524f004b87e572587047279554e672b635f")

import Testv2.StructuralV2

namespace DFTCert.StructuralRun_5d42f9b207b2

def sourceSha256 : String := "7e32e6befb8a11a2f711df7a3fc1fa275b6eb12efbd650fddd2f7a7c849de294"
def irSha256 : String := "5d42f9b207b24a6ad39d3b01610ae0973c1a46888aa3dd251b31a4959d016f5c"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (3, 2), (1, 3), (2, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_5d42f9b207b2

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_5d42f9b207b2.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_5d42f9b207b2.edges DFTCert.StructuralRun_5d42f9b207b2.messageDepth DFTCert.StructuralRun_5d42f9b207b2.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_5d42f9b207b2.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_5d42f9b207b2.sourceSha256 = "7e32e6befb8a11a2f711df7a3fc1fa275b6eb12efbd650fddd2f7a7c849de294" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_5d42f9b207b2.irSha256 = "5d42f9b207b24a6ad39d3b01610ae0973c1a46888aa3dd251b31a4959d016f5c" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_5d42f9b207b2.sourceSha256 = "7e32e6befb8a11a2f711df7a3fc1fa275b6eb12efbd650fddd2f7a7c849de294")
#check (generated_ir_binding : DFTCert.StructuralRun_5d42f9b207b2.irSha256 = "5d42f9b207b24a6ad39d3b01610ae0973c1a46888aa3dd251b31a4959d016f5c")

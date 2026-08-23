import Testv2.StructuralV2

namespace DFTCert.StructuralRun_25b16f33d88c

def sourceSha256 : String := "b43159b486e24024d32af50b292cffbf082669fdaa6e46b21fbcb800f70a940d"
def irSha256 : String := "25b16f33d88c0c4c5666625189176d419545cdaa4b62f9094715fae288c43fed"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (3, 2), (1, 3), (2, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_25b16f33d88c

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_25b16f33d88c.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_25b16f33d88c.edges DFTCert.StructuralRun_25b16f33d88c.messageDepth DFTCert.StructuralRun_25b16f33d88c.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_25b16f33d88c.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_25b16f33d88c.sourceSha256 = "b43159b486e24024d32af50b292cffbf082669fdaa6e46b21fbcb800f70a940d" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_25b16f33d88c.irSha256 = "25b16f33d88c0c4c5666625189176d419545cdaa4b62f9094715fae288c43fed" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_25b16f33d88c.sourceSha256 = "b43159b486e24024d32af50b292cffbf082669fdaa6e46b21fbcb800f70a940d")
#check (generated_ir_binding : DFTCert.StructuralRun_25b16f33d88c.irSha256 = "25b16f33d88c0c4c5666625189176d419545cdaa4b62f9094715fae288c43fed")

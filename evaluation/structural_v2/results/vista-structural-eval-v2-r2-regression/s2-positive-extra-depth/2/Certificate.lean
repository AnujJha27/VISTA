import Testv2.StructuralV2

namespace DFTCert.StructuralRun_371afd596a03

def sourceSha256 : String := "be8e572a9e2e94e66438df69728b829981501e72290eca71fd1cf86018842a01"
def irSha256 : String := "371afd596a03696b0b456ed0c4ff01da4ec81c0ed972be5becaefb14c4f71fbb"
def edges : List (Nat × Nat) := [(0, 1), (1, 2), (2, 3)]
def messageDepth : Nat := 4
def requiredCouplings : List (Nat × Nat) := [(0, 3)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_371afd596a03

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_371afd596a03.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_371afd596a03.edges DFTCert.StructuralRun_371afd596a03.messageDepth DFTCert.StructuralRun_371afd596a03.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_371afd596a03.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_371afd596a03.sourceSha256 = "be8e572a9e2e94e66438df69728b829981501e72290eca71fd1cf86018842a01" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_371afd596a03.irSha256 = "371afd596a03696b0b456ed0c4ff01da4ec81c0ed972be5becaefb14c4f71fbb" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_371afd596a03.sourceSha256 = "be8e572a9e2e94e66438df69728b829981501e72290eca71fd1cf86018842a01")
#check (generated_ir_binding : DFTCert.StructuralRun_371afd596a03.irSha256 = "371afd596a03696b0b456ed0c4ff01da4ec81c0ed972be5becaefb14c4f71fbb")

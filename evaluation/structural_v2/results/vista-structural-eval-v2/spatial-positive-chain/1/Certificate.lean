import Testv2.StructuralV2

namespace DFTCert.StructuralRun_ca23e1fc4377

def sourceSha256 : String := "faae472af9871e492ae64dd6cb5b77a4e89529178411c6857d6af44a56ba65e1"
def irSha256 : String := "ca23e1fc43770984f4e185c50144bb0759737a46577dfc12afe1f5c822a5f385"
def edges : List (Nat × Nat) := [(0, 1), (1, 2), (2, 3)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 3)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_ca23e1fc4377

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_ca23e1fc4377.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_ca23e1fc4377.edges DFTCert.StructuralRun_ca23e1fc4377.messageDepth DFTCert.StructuralRun_ca23e1fc4377.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_ca23e1fc4377.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_ca23e1fc4377.sourceSha256 = "faae472af9871e492ae64dd6cb5b77a4e89529178411c6857d6af44a56ba65e1" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_ca23e1fc4377.irSha256 = "ca23e1fc43770984f4e185c50144bb0759737a46577dfc12afe1f5c822a5f385" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_ca23e1fc4377.sourceSha256 = "faae472af9871e492ae64dd6cb5b77a4e89529178411c6857d6af44a56ba65e1")
#check (generated_ir_binding : DFTCert.StructuralRun_ca23e1fc4377.irSha256 = "ca23e1fc43770984f4e185c50144bb0759737a46577dfc12afe1f5c822a5f385")

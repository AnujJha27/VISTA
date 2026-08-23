import Testv2.StructuralV2

namespace DFTCert.StructuralRun_3a37751ca629

def sourceSha256 : String := "1653b66c4f008b0c959a96f1de45c9a541ce0d75d961b67e9b20d37b9e4941e2"
def irSha256 : String := "3a37751ca6299354cfb0415a0019c37494cd8c253a5e205833ce46a44a131571"
def edges : List (Nat × Nat) := [(5, 0), (0, 1), (1, 2), (2, 3), (3, 4), (4, 5)]
def messageDepth : Nat := 4
def requiredCouplings : List (Nat × Nat) := [(0, 3)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_3a37751ca629

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_3a37751ca629.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_3a37751ca629.edges DFTCert.StructuralRun_3a37751ca629.messageDepth DFTCert.StructuralRun_3a37751ca629.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_3a37751ca629.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_3a37751ca629.sourceSha256 = "1653b66c4f008b0c959a96f1de45c9a541ce0d75d961b67e9b20d37b9e4941e2" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_3a37751ca629.irSha256 = "3a37751ca6299354cfb0415a0019c37494cd8c253a5e205833ce46a44a131571" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_3a37751ca629.sourceSha256 = "1653b66c4f008b0c959a96f1de45c9a541ce0d75d961b67e9b20d37b9e4941e2")
#check (generated_ir_binding : DFTCert.StructuralRun_3a37751ca629.irSha256 = "3a37751ca6299354cfb0415a0019c37494cd8c253a5e205833ce46a44a131571")

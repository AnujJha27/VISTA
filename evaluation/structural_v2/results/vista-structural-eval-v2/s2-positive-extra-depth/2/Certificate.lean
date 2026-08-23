import Testv2.StructuralV2

namespace DFTCert.StructuralRun_58f3d663f21f

def sourceSha256 : String := "73448d8c6204ff71a4cf59fce0807985d61c98ed276d8bb89d8f08dd4a5b545f"
def irSha256 : String := "58f3d663f21faecc4da191c771cb8978b1304d74f00e0eaa8c462d74be2512ed"
def edges : List (Nat × Nat) := [(0, 1), (1, 2), (2, 3)]
def messageDepth : Nat := 4
def requiredCouplings : List (Nat × Nat) := [(0, 3)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_58f3d663f21f

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_58f3d663f21f.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_58f3d663f21f.edges DFTCert.StructuralRun_58f3d663f21f.messageDepth DFTCert.StructuralRun_58f3d663f21f.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_58f3d663f21f.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_58f3d663f21f.sourceSha256 = "73448d8c6204ff71a4cf59fce0807985d61c98ed276d8bb89d8f08dd4a5b545f" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_58f3d663f21f.irSha256 = "58f3d663f21faecc4da191c771cb8978b1304d74f00e0eaa8c462d74be2512ed" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_58f3d663f21f.sourceSha256 = "73448d8c6204ff71a4cf59fce0807985d61c98ed276d8bb89d8f08dd4a5b545f")
#check (generated_ir_binding : DFTCert.StructuralRun_58f3d663f21f.irSha256 = "58f3d663f21faecc4da191c771cb8978b1304d74f00e0eaa8c462d74be2512ed")

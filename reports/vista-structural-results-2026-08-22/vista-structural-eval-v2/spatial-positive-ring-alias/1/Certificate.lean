import Testv2.StructuralV2

namespace DFTCert.StructuralRun_62a344ed3b12

def sourceSha256 : String := "f5a787bbafd98b7cbfdcf422345ca66d748cdb9a2f2727f86b3bf8c58fa99644"
def irSha256 : String := "62a344ed3b123c37e33300155a4a314ecd93f24739e3d1e159fbaaa24b1fdf10"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 3)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_62a344ed3b12

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_62a344ed3b12.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_62a344ed3b12.edges DFTCert.StructuralRun_62a344ed3b12.messageDepth DFTCert.StructuralRun_62a344ed3b12.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_62a344ed3b12.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_62a344ed3b12.sourceSha256 = "f5a787bbafd98b7cbfdcf422345ca66d748cdb9a2f2727f86b3bf8c58fa99644" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_62a344ed3b12.irSha256 = "62a344ed3b123c37e33300155a4a314ecd93f24739e3d1e159fbaaa24b1fdf10" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_62a344ed3b12.sourceSha256 = "f5a787bbafd98b7cbfdcf422345ca66d748cdb9a2f2727f86b3bf8c58fa99644")
#check (generated_ir_binding : DFTCert.StructuralRun_62a344ed3b12.irSha256 = "62a344ed3b123c37e33300155a4a314ecd93f24739e3d1e159fbaaa24b1fdf10")

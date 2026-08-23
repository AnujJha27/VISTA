import Testv2.StructuralV2

namespace DFTCert.StructuralRun_c21fd2b4a9c7

def sourceSha256 : String := "61bde6dd3e3206b984339f0317ad45db63d2d755ec0457c947eef6f1d3aeb517"
def irSha256 : String := "c21fd2b4a9c7fd7aeed99fc867a07ba7f826717b30c977e7b371196e8e95aa2f"
def edges : List (Nat × Nat) := [(0, 1), (1, 2), (2, 3)]
def messageDepth : Nat := 4
def requiredCouplings : List (Nat × Nat) := [(0, 3)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_c21fd2b4a9c7

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_c21fd2b4a9c7.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_c21fd2b4a9c7.edges DFTCert.StructuralRun_c21fd2b4a9c7.messageDepth DFTCert.StructuralRun_c21fd2b4a9c7.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_c21fd2b4a9c7.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_c21fd2b4a9c7.sourceSha256 = "61bde6dd3e3206b984339f0317ad45db63d2d755ec0457c947eef6f1d3aeb517" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_c21fd2b4a9c7.irSha256 = "c21fd2b4a9c7fd7aeed99fc867a07ba7f826717b30c977e7b371196e8e95aa2f" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_c21fd2b4a9c7.sourceSha256 = "61bde6dd3e3206b984339f0317ad45db63d2d755ec0457c947eef6f1d3aeb517")
#check (generated_ir_binding : DFTCert.StructuralRun_c21fd2b4a9c7.irSha256 = "c21fd2b4a9c7fd7aeed99fc867a07ba7f826717b30c977e7b371196e8e95aa2f")

import Testv2.StructuralV2

namespace DFTCert.StructuralRun_5306834e12cc

def sourceSha256 : String := "5b23d995fe5e37096c94a6f236f82d312ab7aaedf8ca1823cad600a9066537a0"
def irSha256 : String := "5306834e12cce7dd6d4e7290fdd162b3098f108f3d45800592aac0726ad9d85a"
def edges : List (Nat × Nat) := [(0, 1), (1, 2), (2, 3)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 3)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_5306834e12cc

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_5306834e12cc.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_5306834e12cc.edges DFTCert.StructuralRun_5306834e12cc.messageDepth DFTCert.StructuralRun_5306834e12cc.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_5306834e12cc.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_5306834e12cc.sourceSha256 = "5b23d995fe5e37096c94a6f236f82d312ab7aaedf8ca1823cad600a9066537a0" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_5306834e12cc.irSha256 = "5306834e12cce7dd6d4e7290fdd162b3098f108f3d45800592aac0726ad9d85a" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_5306834e12cc.sourceSha256 = "5b23d995fe5e37096c94a6f236f82d312ab7aaedf8ca1823cad600a9066537a0")
#check (generated_ir_binding : DFTCert.StructuralRun_5306834e12cc.irSha256 = "5306834e12cce7dd6d4e7290fdd162b3098f108f3d45800592aac0726ad9d85a")

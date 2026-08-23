import Testv2.StructuralV2

namespace DFTCert.StructuralRun_122c8c1ec4bc

def sourceSha256 : String := "81ea48a0c860789aa0c042ba1a46a173af67fd50cc5ce395b68970eae936da91"
def irSha256 : String := "122c8c1ec4bc71ff1c52088d57e3d6ac1b6b12e3500d6b6047a375863048eaee"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_122c8c1ec4bc

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_122c8c1ec4bc.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_122c8c1ec4bc.edges DFTCert.StructuralRun_122c8c1ec4bc.messageDepth DFTCert.StructuralRun_122c8c1ec4bc.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_122c8c1ec4bc.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_122c8c1ec4bc.sourceSha256 = "81ea48a0c860789aa0c042ba1a46a173af67fd50cc5ce395b68970eae936da91" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_122c8c1ec4bc.irSha256 = "122c8c1ec4bc71ff1c52088d57e3d6ac1b6b12e3500d6b6047a375863048eaee" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_122c8c1ec4bc.sourceSha256 = "81ea48a0c860789aa0c042ba1a46a173af67fd50cc5ce395b68970eae936da91")
#check (generated_ir_binding : DFTCert.StructuralRun_122c8c1ec4bc.irSha256 = "122c8c1ec4bc71ff1c52088d57e3d6ac1b6b12e3500d6b6047a375863048eaee")

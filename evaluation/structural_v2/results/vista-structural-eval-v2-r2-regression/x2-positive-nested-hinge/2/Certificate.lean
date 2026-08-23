import Testv2.StructuralV2

namespace DFTCert.StructuralRun_8f623075347d

def sourceSha256 : String := "337c104fcd6280fd3dfc14ae078ac46fd62f93c26387fb3685561ad6055ef85d"
def irSha256 : String := "8f623075347d31313aff1652ad563e54274ebbdd35aef71ae79dfd60d0522aa0"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_8f623075347d

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_8f623075347d.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_8f623075347d.edges DFTCert.StructuralRun_8f623075347d.messageDepth DFTCert.StructuralRun_8f623075347d.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_8f623075347d.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_8f623075347d.sourceSha256 = "337c104fcd6280fd3dfc14ae078ac46fd62f93c26387fb3685561ad6055ef85d" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_8f623075347d.irSha256 = "8f623075347d31313aff1652ad563e54274ebbdd35aef71ae79dfd60d0522aa0" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_8f623075347d.sourceSha256 = "337c104fcd6280fd3dfc14ae078ac46fd62f93c26387fb3685561ad6055ef85d")
#check (generated_ir_binding : DFTCert.StructuralRun_8f623075347d.irSha256 = "8f623075347d31313aff1652ad563e54274ebbdd35aef71ae79dfd60d0522aa0")

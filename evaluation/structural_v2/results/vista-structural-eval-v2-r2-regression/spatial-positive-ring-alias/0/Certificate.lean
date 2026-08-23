import Testv2.StructuralV2

namespace DFTCert.StructuralRun_42816f052d72

def sourceSha256 : String := "f0c6c07be9102f0b610a4be0eb5b86909c563813d19c81a215d36e35a7a3ce51"
def irSha256 : String := "42816f052d727cf944c6e8c6edb7bd9495a2430253c5d7e9d7d1bff5f0461026"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 3)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_42816f052d72

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_42816f052d72.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_42816f052d72.edges DFTCert.StructuralRun_42816f052d72.messageDepth DFTCert.StructuralRun_42816f052d72.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_42816f052d72.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_42816f052d72.sourceSha256 = "f0c6c07be9102f0b610a4be0eb5b86909c563813d19c81a215d36e35a7a3ce51" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_42816f052d72.irSha256 = "42816f052d727cf944c6e8c6edb7bd9495a2430253c5d7e9d7d1bff5f0461026" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_42816f052d72.sourceSha256 = "f0c6c07be9102f0b610a4be0eb5b86909c563813d19c81a215d36e35a7a3ce51")
#check (generated_ir_binding : DFTCert.StructuralRun_42816f052d72.irSha256 = "42816f052d727cf944c6e8c6edb7bd9495a2430253c5d7e9d7d1bff5f0461026")

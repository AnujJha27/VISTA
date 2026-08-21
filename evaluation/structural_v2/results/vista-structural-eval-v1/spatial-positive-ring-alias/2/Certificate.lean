import Testv2.StructuralV2

namespace DFTCert.StructuralRun_cee7681085b9

def sourceSha256 : String := "e65ed8c0f782a1759d1ccbb6f7068bbb388e1a87187873e6f6bb9e642d66f31f"
def irSha256 : String := "cee7681085b9b3017d758dbebbbaea6b41f9e2621a05b6000869315f9ca397c1"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 3)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_cee7681085b9

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_cee7681085b9.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_cee7681085b9.edges DFTCert.StructuralRun_cee7681085b9.messageDepth DFTCert.StructuralRun_cee7681085b9.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_cee7681085b9.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_cee7681085b9.sourceSha256 = "e65ed8c0f782a1759d1ccbb6f7068bbb388e1a87187873e6f6bb9e642d66f31f" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_cee7681085b9.irSha256 = "cee7681085b9b3017d758dbebbbaea6b41f9e2621a05b6000869315f9ca397c1" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_cee7681085b9.sourceSha256 = "e65ed8c0f782a1759d1ccbb6f7068bbb388e1a87187873e6f6bb9e642d66f31f")
#check (generated_ir_binding : DFTCert.StructuralRun_cee7681085b9.irSha256 = "cee7681085b9b3017d758dbebbbaea6b41f9e2621a05b6000869315f9ca397c1")

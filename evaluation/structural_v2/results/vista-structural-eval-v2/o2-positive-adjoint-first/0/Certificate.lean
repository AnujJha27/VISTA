import Testv2.StructuralV2

namespace DFTCert.StructuralRun_bb9ed33b1b71

def sourceSha256 : String := "be2ff1e4004dd06c3882f8893186577946b0829134e4631c7ac80fef0b94a6b9"
def irSha256 : String := "bb9ed33b1b718b5e610cf2f0f155ec89ed49f249432d536383db00e8c22064d8"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_bb9ed33b1b71

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_bb9ed33b1b71.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_bb9ed33b1b71.edges DFTCert.StructuralRun_bb9ed33b1b71.messageDepth DFTCert.StructuralRun_bb9ed33b1b71.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_bb9ed33b1b71.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_bb9ed33b1b71.sourceSha256 = "be2ff1e4004dd06c3882f8893186577946b0829134e4631c7ac80fef0b94a6b9" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_bb9ed33b1b71.irSha256 = "bb9ed33b1b718b5e610cf2f0f155ec89ed49f249432d536383db00e8c22064d8" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_bb9ed33b1b71.sourceSha256 = "be2ff1e4004dd06c3882f8893186577946b0829134e4631c7ac80fef0b94a6b9")
#check (generated_ir_binding : DFTCert.StructuralRun_bb9ed33b1b71.irSha256 = "bb9ed33b1b718b5e610cf2f0f155ec89ed49f249432d536383db00e8c22064d8")

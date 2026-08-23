import Testv2.StructuralV2

namespace DFTCert.StructuralRun_534027abd133

def sourceSha256 : String := "08ea55c044fcd9d11f8156874763790398bd40501553a8e8661eacd122d7e0bb"
def irSha256 : String := "534027abd1333ac5a66b4ad89647d24cb8ed55272cdf321628b9e8a400e062f6"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_534027abd133

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_534027abd133.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_534027abd133.edges DFTCert.StructuralRun_534027abd133.messageDepth DFTCert.StructuralRun_534027abd133.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_534027abd133.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_534027abd133.sourceSha256 = "08ea55c044fcd9d11f8156874763790398bd40501553a8e8661eacd122d7e0bb" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_534027abd133.irSha256 = "534027abd1333ac5a66b4ad89647d24cb8ed55272cdf321628b9e8a400e062f6" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_534027abd133.sourceSha256 = "08ea55c044fcd9d11f8156874763790398bd40501553a8e8661eacd122d7e0bb")
#check (generated_ir_binding : DFTCert.StructuralRun_534027abd133.irSha256 = "534027abd1333ac5a66b4ad89647d24cb8ed55272cdf321628b9e8a400e062f6")

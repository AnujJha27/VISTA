import Testv2.StructuralV2

namespace DFTCert.StructuralRun_8dde8dae2d28

def sourceSha256 : String := "05cd15b64774145060848c98f06347f68055e65756f04d363bddf33112343bea"
def irSha256 : String := "8dde8dae2d2859c695a0844bf8c789c9db49de6a4350f784413a5b0efd010166"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_8dde8dae2d28

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_8dde8dae2d28.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_8dde8dae2d28.edges DFTCert.StructuralRun_8dde8dae2d28.messageDepth DFTCert.StructuralRun_8dde8dae2d28.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_8dde8dae2d28.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_8dde8dae2d28.sourceSha256 = "05cd15b64774145060848c98f06347f68055e65756f04d363bddf33112343bea" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_8dde8dae2d28.irSha256 = "8dde8dae2d2859c695a0844bf8c789c9db49de6a4350f784413a5b0efd010166" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_8dde8dae2d28.sourceSha256 = "05cd15b64774145060848c98f06347f68055e65756f04d363bddf33112343bea")
#check (generated_ir_binding : DFTCert.StructuralRun_8dde8dae2d28.irSha256 = "8dde8dae2d2859c695a0844bf8c789c9db49de6a4350f784413a5b0efd010166")

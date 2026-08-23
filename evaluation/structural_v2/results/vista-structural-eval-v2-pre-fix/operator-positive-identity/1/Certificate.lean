import Testv2.StructuralV2

namespace DFTCert.StructuralRun_17906d2a0997

def sourceSha256 : String := "1c8279fc14a6d55302d77a0b8e53ef28ad7c010e33117b4f9337bc7f8531d34b"
def irSha256 : String := "17906d2a099739734d147e6c92534a5decfdfeada222461af84f18b2ba64767d"
def edges : List (Nat × Nat) := [(3, 0), (0, 1), (1, 2), (2, 3)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .identity

end DFTCert.StructuralRun_17906d2a0997

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_17906d2a0997.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_17906d2a0997.edges DFTCert.StructuralRun_17906d2a0997.messageDepth DFTCert.StructuralRun_17906d2a0997.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_17906d2a0997.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_17906d2a0997.sourceSha256 = "1c8279fc14a6d55302d77a0b8e53ef28ad7c010e33117b4f9337bc7f8531d34b" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_17906d2a0997.irSha256 = "17906d2a099739734d147e6c92534a5decfdfeada222461af84f18b2ba64767d" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_17906d2a0997.sourceSha256 = "1c8279fc14a6d55302d77a0b8e53ef28ad7c010e33117b4f9337bc7f8531d34b")
#check (generated_ir_binding : DFTCert.StructuralRun_17906d2a0997.irSha256 = "17906d2a099739734d147e6c92534a5decfdfeada222461af84f18b2ba64767d")

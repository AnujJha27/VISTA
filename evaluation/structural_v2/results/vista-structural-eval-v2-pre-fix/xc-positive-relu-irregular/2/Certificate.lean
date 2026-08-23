import Testv2.StructuralV2

namespace DFTCert.StructuralRun_66fd8952905b

def sourceSha256 : String := "0603663612875bd6a3e58e005d50427c1a2bccf4417a64d67ab707cd3be152b5"
def irSha256 : String := "66fd8952905b7c6924548abb9c5ba11d44b00f86a7ac5c6155c106e46d9afdc3"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (3, 2), (1, 3), (2, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_66fd8952905b

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_66fd8952905b.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_66fd8952905b.edges DFTCert.StructuralRun_66fd8952905b.messageDepth DFTCert.StructuralRun_66fd8952905b.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_66fd8952905b.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_66fd8952905b.sourceSha256 = "0603663612875bd6a3e58e005d50427c1a2bccf4417a64d67ab707cd3be152b5" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_66fd8952905b.irSha256 = "66fd8952905b7c6924548abb9c5ba11d44b00f86a7ac5c6155c106e46d9afdc3" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_66fd8952905b.sourceSha256 = "0603663612875bd6a3e58e005d50427c1a2bccf4417a64d67ab707cd3be152b5")
#check (generated_ir_binding : DFTCert.StructuralRun_66fd8952905b.irSha256 = "66fd8952905b7c6924548abb9c5ba11d44b00f86a7ac5c6155c106e46d9afdc3")

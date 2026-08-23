import Testv2.StructuralV2

namespace DFTCert.StructuralRun_82fcf286f2b4

def sourceSha256 : String := "ed39b8bcb7da8f9148044b948c0f68c12f1467b75b3610424dc0b8d840449ec9"
def irSha256 : String := "82fcf286f2b44c3e8a87c9caeba1a76c4ecf2f89427357666f1e0f6df51b04c3"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_82fcf286f2b4

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_82fcf286f2b4.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_82fcf286f2b4.edges DFTCert.StructuralRun_82fcf286f2b4.messageDepth DFTCert.StructuralRun_82fcf286f2b4.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_82fcf286f2b4.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_82fcf286f2b4.sourceSha256 = "ed39b8bcb7da8f9148044b948c0f68c12f1467b75b3610424dc0b8d840449ec9" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_82fcf286f2b4.irSha256 = "82fcf286f2b44c3e8a87c9caeba1a76c4ecf2f89427357666f1e0f6df51b04c3" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_82fcf286f2b4.sourceSha256 = "ed39b8bcb7da8f9148044b948c0f68c12f1467b75b3610424dc0b8d840449ec9")
#check (generated_ir_binding : DFTCert.StructuralRun_82fcf286f2b4.irSha256 = "82fcf286f2b44c3e8a87c9caeba1a76c4ecf2f89427357666f1e0f6df51b04c3")

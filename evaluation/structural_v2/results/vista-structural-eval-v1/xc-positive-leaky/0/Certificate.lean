import Testv2.StructuralV2

namespace DFTCert.StructuralRun_d0ef546933e6

def sourceSha256 : String := "169ac1bc9f1cff28935b2d6da134ed6e41e3f13cdb18a092afdccf4748569bc9"
def irSha256 : String := "d0ef546933e6909e7f26ed0ab1d3a769018762d48b7b89d9cae2b30e31e92457"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_d0ef546933e6

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_d0ef546933e6.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_d0ef546933e6.edges DFTCert.StructuralRun_d0ef546933e6.messageDepth DFTCert.StructuralRun_d0ef546933e6.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_d0ef546933e6.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_d0ef546933e6.sourceSha256 = "169ac1bc9f1cff28935b2d6da134ed6e41e3f13cdb18a092afdccf4748569bc9" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_d0ef546933e6.irSha256 = "d0ef546933e6909e7f26ed0ab1d3a769018762d48b7b89d9cae2b30e31e92457" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_d0ef546933e6.sourceSha256 = "169ac1bc9f1cff28935b2d6da134ed6e41e3f13cdb18a092afdccf4748569bc9")
#check (generated_ir_binding : DFTCert.StructuralRun_d0ef546933e6.irSha256 = "d0ef546933e6909e7f26ed0ab1d3a769018762d48b7b89d9cae2b30e31e92457")

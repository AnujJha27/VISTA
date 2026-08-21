import Testv2.StructuralV2

namespace DFTCert.StructuralRun_8fc2adabafc9

def sourceSha256 : String := "60a1026d7dad213684f2eff5775b7cccd9ad894cca75bd3aa3bbcc59336f7fb8"
def irSha256 : String := "8fc2adabafc92f571f3fb9b2ee2e268b1530a7ff5652ec96302a442a9cfb9f20"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (3, 2), (1, 3), (2, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_8fc2adabafc9

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_8fc2adabafc9.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_8fc2adabafc9.edges DFTCert.StructuralRun_8fc2adabafc9.messageDepth DFTCert.StructuralRun_8fc2adabafc9.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_8fc2adabafc9.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_8fc2adabafc9.sourceSha256 = "60a1026d7dad213684f2eff5775b7cccd9ad894cca75bd3aa3bbcc59336f7fb8" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_8fc2adabafc9.irSha256 = "8fc2adabafc92f571f3fb9b2ee2e268b1530a7ff5652ec96302a442a9cfb9f20" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_8fc2adabafc9.sourceSha256 = "60a1026d7dad213684f2eff5775b7cccd9ad894cca75bd3aa3bbcc59336f7fb8")
#check (generated_ir_binding : DFTCert.StructuralRun_8fc2adabafc9.irSha256 = "8fc2adabafc92f571f3fb9b2ee2e268b1530a7ff5652ec96302a442a9cfb9f20")

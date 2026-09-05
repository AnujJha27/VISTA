import Testv2.StructuralV2

namespace DFTCert.StructuralRun_05993478df23

def sourceSha256 : String := "7d54a067333ccc16893a1856cefa338a14a941bd6ac36eb094c81dad04be06ad"
def irSha256 : String := "05993478df2306e0c1a53e95fe46673c879e3014d0b0a2df8b89e969041fd577"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_05993478df23

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_05993478df23.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_05993478df23.edges DFTCert.StructuralRun_05993478df23.messageDepth DFTCert.StructuralRun_05993478df23.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_05993478df23.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_05993478df23.sourceSha256 = "7d54a067333ccc16893a1856cefa338a14a941bd6ac36eb094c81dad04be06ad" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_05993478df23.irSha256 = "05993478df2306e0c1a53e95fe46673c879e3014d0b0a2df8b89e969041fd577" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_05993478df23.sourceSha256 = "7d54a067333ccc16893a1856cefa338a14a941bd6ac36eb094c81dad04be06ad")
#check (generated_ir_binding : DFTCert.StructuralRun_05993478df23.irSha256 = "05993478df2306e0c1a53e95fe46673c879e3014d0b0a2df8b89e969041fd577")

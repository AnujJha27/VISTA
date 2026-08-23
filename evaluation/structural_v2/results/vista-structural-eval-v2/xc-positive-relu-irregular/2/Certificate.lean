import Testv2.StructuralV2

namespace DFTCert.StructuralRun_e02313801017

def sourceSha256 : String := "3b8760a75752db2b5e6047ce4b3c116ecfa6a2a2165ca714a442ed5bcb6af051"
def irSha256 : String := "e02313801017f7fca2d05d00e5a9b16317666650b281f1ce6d97072f77797968"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (3, 2), (1, 3), (2, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_e02313801017

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_e02313801017.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_e02313801017.edges DFTCert.StructuralRun_e02313801017.messageDepth DFTCert.StructuralRun_e02313801017.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_e02313801017.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_e02313801017.sourceSha256 = "3b8760a75752db2b5e6047ce4b3c116ecfa6a2a2165ca714a442ed5bcb6af051" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_e02313801017.irSha256 = "e02313801017f7fca2d05d00e5a9b16317666650b281f1ce6d97072f77797968" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_e02313801017.sourceSha256 = "3b8760a75752db2b5e6047ce4b3c116ecfa6a2a2165ca714a442ed5bcb6af051")
#check (generated_ir_binding : DFTCert.StructuralRun_e02313801017.irSha256 = "e02313801017f7fca2d05d00e5a9b16317666650b281f1ce6d97072f77797968")

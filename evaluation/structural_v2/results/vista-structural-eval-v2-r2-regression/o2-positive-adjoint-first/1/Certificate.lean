import Testv2.StructuralV2

namespace DFTCert.StructuralRun_eba9c308a717

def sourceSha256 : String := "cfe30b33a78c0163dbeaca8c171f324fb61757ea7e0d479e0eddcb07f4c322e6"
def irSha256 : String := "eba9c308a717cb0ab8d38dde53e3327e567657a4f48d61e785ba261f45563b55"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_eba9c308a717

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_eba9c308a717.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_eba9c308a717.edges DFTCert.StructuralRun_eba9c308a717.messageDepth DFTCert.StructuralRun_eba9c308a717.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_eba9c308a717.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_eba9c308a717.sourceSha256 = "cfe30b33a78c0163dbeaca8c171f324fb61757ea7e0d479e0eddcb07f4c322e6" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_eba9c308a717.irSha256 = "eba9c308a717cb0ab8d38dde53e3327e567657a4f48d61e785ba261f45563b55" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_eba9c308a717.sourceSha256 = "cfe30b33a78c0163dbeaca8c171f324fb61757ea7e0d479e0eddcb07f4c322e6")
#check (generated_ir_binding : DFTCert.StructuralRun_eba9c308a717.irSha256 = "eba9c308a717cb0ab8d38dde53e3327e567657a4f48d61e785ba261f45563b55")

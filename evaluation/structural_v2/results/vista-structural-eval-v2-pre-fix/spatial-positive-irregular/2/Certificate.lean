import Testv2.StructuralV2

namespace DFTCert.StructuralRun_a1ddcfbcef76

def sourceSha256 : String := "5f6b0693188d2548327695ab837130af1fbae2159ccc7be7887f8e3f31ad4281"
def irSha256 : String := "a1ddcfbcef760c79cc8ddf440bde852dc19b66b7bbc13e3f63a4b5b73e749b82"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (3, 2), (1, 3), (2, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_a1ddcfbcef76

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_a1ddcfbcef76.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_a1ddcfbcef76.edges DFTCert.StructuralRun_a1ddcfbcef76.messageDepth DFTCert.StructuralRun_a1ddcfbcef76.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_a1ddcfbcef76.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_a1ddcfbcef76.sourceSha256 = "5f6b0693188d2548327695ab837130af1fbae2159ccc7be7887f8e3f31ad4281" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_a1ddcfbcef76.irSha256 = "a1ddcfbcef760c79cc8ddf440bde852dc19b66b7bbc13e3f63a4b5b73e749b82" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_a1ddcfbcef76.sourceSha256 = "5f6b0693188d2548327695ab837130af1fbae2159ccc7be7887f8e3f31ad4281")
#check (generated_ir_binding : DFTCert.StructuralRun_a1ddcfbcef76.irSha256 = "a1ddcfbcef760c79cc8ddf440bde852dc19b66b7bbc13e3f63a4b5b73e749b82")

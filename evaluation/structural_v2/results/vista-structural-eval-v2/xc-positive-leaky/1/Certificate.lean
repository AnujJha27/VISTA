import Testv2.StructuralV2

namespace DFTCert.StructuralRun_86e2947f9298

def sourceSha256 : String := "240e7aa2003a984bc6feaec1620213e0710f09417eec97dd2b10bf179c20ae96"
def irSha256 : String := "86e2947f92982b7f366e290bbd1b1971163dfe02458e1e78a82e9f96bf45ab8b"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_86e2947f9298

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_86e2947f9298.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_86e2947f9298.edges DFTCert.StructuralRun_86e2947f9298.messageDepth DFTCert.StructuralRun_86e2947f9298.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_86e2947f9298.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_86e2947f9298.sourceSha256 = "240e7aa2003a984bc6feaec1620213e0710f09417eec97dd2b10bf179c20ae96" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_86e2947f9298.irSha256 = "86e2947f92982b7f366e290bbd1b1971163dfe02458e1e78a82e9f96bf45ab8b" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_86e2947f9298.sourceSha256 = "240e7aa2003a984bc6feaec1620213e0710f09417eec97dd2b10bf179c20ae96")
#check (generated_ir_binding : DFTCert.StructuralRun_86e2947f9298.irSha256 = "86e2947f92982b7f366e290bbd1b1971163dfe02458e1e78a82e9f96bf45ab8b")

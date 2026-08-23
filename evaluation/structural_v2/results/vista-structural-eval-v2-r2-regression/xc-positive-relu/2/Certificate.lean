import Testv2.StructuralV2

namespace DFTCert.StructuralRun_a99a3b9ef065

def sourceSha256 : String := "4282136351dfc0a5365b4d3c043f7f040bc11cc9d9adbf6c9a6973a5b0f851a7"
def irSha256 : String := "a99a3b9ef065827b9098cea4f37e6504412acad2c89b4320b91b308efef5dcdb"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_a99a3b9ef065

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_a99a3b9ef065.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_a99a3b9ef065.edges DFTCert.StructuralRun_a99a3b9ef065.messageDepth DFTCert.StructuralRun_a99a3b9ef065.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_a99a3b9ef065.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_a99a3b9ef065.sourceSha256 = "4282136351dfc0a5365b4d3c043f7f040bc11cc9d9adbf6c9a6973a5b0f851a7" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_a99a3b9ef065.irSha256 = "a99a3b9ef065827b9098cea4f37e6504412acad2c89b4320b91b308efef5dcdb" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_a99a3b9ef065.sourceSha256 = "4282136351dfc0a5365b4d3c043f7f040bc11cc9d9adbf6c9a6973a5b0f851a7")
#check (generated_ir_binding : DFTCert.StructuralRun_a99a3b9ef065.irSha256 = "a99a3b9ef065827b9098cea4f37e6504412acad2c89b4320b91b308efef5dcdb")

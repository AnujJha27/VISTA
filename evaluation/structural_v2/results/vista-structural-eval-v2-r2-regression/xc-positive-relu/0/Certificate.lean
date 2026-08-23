import Testv2.StructuralV2

namespace DFTCert.StructuralRun_62816f9b8977

def sourceSha256 : String := "4ed83e37d73214d3e0e53a0878d988bd7c30fab30da98a23485da9ea913b4502"
def irSha256 : String := "62816f9b8977ef8af17d88b6de7d15a3a8602d585c32d6b039c36f1b689261da"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_62816f9b8977

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_62816f9b8977.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_62816f9b8977.edges DFTCert.StructuralRun_62816f9b8977.messageDepth DFTCert.StructuralRun_62816f9b8977.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_62816f9b8977.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_62816f9b8977.sourceSha256 = "4ed83e37d73214d3e0e53a0878d988bd7c30fab30da98a23485da9ea913b4502" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_62816f9b8977.irSha256 = "62816f9b8977ef8af17d88b6de7d15a3a8602d585c32d6b039c36f1b689261da" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_62816f9b8977.sourceSha256 = "4ed83e37d73214d3e0e53a0878d988bd7c30fab30da98a23485da9ea913b4502")
#check (generated_ir_binding : DFTCert.StructuralRun_62816f9b8977.irSha256 = "62816f9b8977ef8af17d88b6de7d15a3a8602d585c32d6b039c36f1b689261da")

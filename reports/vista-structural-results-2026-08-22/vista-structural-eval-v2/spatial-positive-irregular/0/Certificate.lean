import Testv2.StructuralV2

namespace DFTCert.StructuralRun_579d98479fdc

def sourceSha256 : String := "af1d52d6cbc3354a0457dbe1067df1e09e34a3b42068c7dba4dc3f50cbe2fec2"
def irSha256 : String := "579d98479fdcfc5f0a5c1429f53acea7012c6ab8dbed80e7bc236ed0a25b3e3c"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (3, 2), (1, 3), (2, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_579d98479fdc

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_579d98479fdc.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_579d98479fdc.edges DFTCert.StructuralRun_579d98479fdc.messageDepth DFTCert.StructuralRun_579d98479fdc.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_579d98479fdc.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_579d98479fdc.sourceSha256 = "af1d52d6cbc3354a0457dbe1067df1e09e34a3b42068c7dba4dc3f50cbe2fec2" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_579d98479fdc.irSha256 = "579d98479fdcfc5f0a5c1429f53acea7012c6ab8dbed80e7bc236ed0a25b3e3c" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_579d98479fdc.sourceSha256 = "af1d52d6cbc3354a0457dbe1067df1e09e34a3b42068c7dba4dc3f50cbe2fec2")
#check (generated_ir_binding : DFTCert.StructuralRun_579d98479fdc.irSha256 = "579d98479fdcfc5f0a5c1429f53acea7012c6ab8dbed80e7bc236ed0a25b3e3c")

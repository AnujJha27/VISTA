import Testv2.StructuralV2

namespace DFTCert.StructuralRun_e86ccc98928f

def sourceSha256 : String := "061b94e4107d3a9a3bf16870e114a75f7cd34728cd922a1196ce3f64a276ed22"
def irSha256 : String := "e86ccc98928fd1375f7807a547e9889e160b1897c15886f618478175953e096a"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_e86ccc98928f

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_e86ccc98928f.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_e86ccc98928f.edges DFTCert.StructuralRun_e86ccc98928f.messageDepth DFTCert.StructuralRun_e86ccc98928f.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_e86ccc98928f.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_e86ccc98928f.sourceSha256 = "061b94e4107d3a9a3bf16870e114a75f7cd34728cd922a1196ce3f64a276ed22" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_e86ccc98928f.irSha256 = "e86ccc98928fd1375f7807a547e9889e160b1897c15886f618478175953e096a" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_e86ccc98928f.sourceSha256 = "061b94e4107d3a9a3bf16870e114a75f7cd34728cd922a1196ce3f64a276ed22")
#check (generated_ir_binding : DFTCert.StructuralRun_e86ccc98928f.irSha256 = "e86ccc98928fd1375f7807a547e9889e160b1897c15886f618478175953e096a")

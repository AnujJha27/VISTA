import Testv2.StructuralV2

namespace DFTCert.StructuralRun_979e15eb79ce

def sourceSha256 : String := "4dae9c45f82c4898129fc019aeb2395f39c72f90579bd95ae107413e3926298c"
def irSha256 : String := "979e15eb79ceacba2279adfaae1645ce481ad6b78d1a859ddd7625b85403092c"
def edges : List (Nat × Nat) := [(3, 0), (0, 1), (1, 2), (2, 3)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .zero

end DFTCert.StructuralRun_979e15eb79ce

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_979e15eb79ce.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_979e15eb79ce.edges DFTCert.StructuralRun_979e15eb79ce.messageDepth DFTCert.StructuralRun_979e15eb79ce.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_979e15eb79ce.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_979e15eb79ce.sourceSha256 = "4dae9c45f82c4898129fc019aeb2395f39c72f90579bd95ae107413e3926298c" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_979e15eb79ce.irSha256 = "979e15eb79ceacba2279adfaae1645ce481ad6b78d1a859ddd7625b85403092c" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_979e15eb79ce.sourceSha256 = "4dae9c45f82c4898129fc019aeb2395f39c72f90579bd95ae107413e3926298c")
#check (generated_ir_binding : DFTCert.StructuralRun_979e15eb79ce.irSha256 = "979e15eb79ceacba2279adfaae1645ce481ad6b78d1a859ddd7625b85403092c")

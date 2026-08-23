import Testv2.StructuralV2

namespace DFTCert.StructuralRun_6338d248f0ef

def sourceSha256 : String := "c0bd96eaf05ed3afce982c7ae020950924735a5e2e320612ad00672043000b23"
def irSha256 : String := "6338d248f0ef8c33027663a58146256f2aa83d1257e15decff35c9c406aa5626"
def edges : List (Nat × Nat) := [(5, 0), (0, 1), (1, 2), (2, 3), (3, 4), (4, 5)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_6338d248f0ef

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_6338d248f0ef.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_6338d248f0ef.edges DFTCert.StructuralRun_6338d248f0ef.messageDepth DFTCert.StructuralRun_6338d248f0ef.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_6338d248f0ef.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_6338d248f0ef.sourceSha256 = "c0bd96eaf05ed3afce982c7ae020950924735a5e2e320612ad00672043000b23" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_6338d248f0ef.irSha256 = "6338d248f0ef8c33027663a58146256f2aa83d1257e15decff35c9c406aa5626" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_6338d248f0ef.sourceSha256 = "c0bd96eaf05ed3afce982c7ae020950924735a5e2e320612ad00672043000b23")
#check (generated_ir_binding : DFTCert.StructuralRun_6338d248f0ef.irSha256 = "6338d248f0ef8c33027663a58146256f2aa83d1257e15decff35c9c406aa5626")

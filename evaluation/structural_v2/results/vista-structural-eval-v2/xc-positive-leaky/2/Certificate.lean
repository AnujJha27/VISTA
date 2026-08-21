import Testv2.StructuralV2

namespace DFTCert.StructuralRun_b43123b32346

def sourceSha256 : String := "f893c9b8d3d326ca9977d7476ce27d228862f51316547c56a23acdde61275b3a"
def irSha256 : String := "b43123b32346276bbf5f15b4f1c0e87a776576393a93609dae9a7ca57d220e11"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_b43123b32346

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_b43123b32346.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_b43123b32346.edges DFTCert.StructuralRun_b43123b32346.messageDepth DFTCert.StructuralRun_b43123b32346.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_b43123b32346.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_b43123b32346.sourceSha256 = "f893c9b8d3d326ca9977d7476ce27d228862f51316547c56a23acdde61275b3a" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_b43123b32346.irSha256 = "b43123b32346276bbf5f15b4f1c0e87a776576393a93609dae9a7ca57d220e11" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_b43123b32346.sourceSha256 = "f893c9b8d3d326ca9977d7476ce27d228862f51316547c56a23acdde61275b3a")
#check (generated_ir_binding : DFTCert.StructuralRun_b43123b32346.irSha256 = "b43123b32346276bbf5f15b4f1c0e87a776576393a93609dae9a7ca57d220e11")

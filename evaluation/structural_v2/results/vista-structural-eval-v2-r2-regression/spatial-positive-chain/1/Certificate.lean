import Testv2.StructuralV2

namespace DFTCert.StructuralRun_1dbf637fb245

def sourceSha256 : String := "f7690444c682a7a4f67a6a461e481277740f91068d9fe428ca370fc42ed5cc0f"
def irSha256 : String := "1dbf637fb245a730444e91a8ec31a22f85387044db4e9ea96aa16e7b2bf2fd49"
def edges : List (Nat × Nat) := [(0, 1), (1, 2), (2, 3)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 3)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_1dbf637fb245

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_1dbf637fb245.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_1dbf637fb245.edges DFTCert.StructuralRun_1dbf637fb245.messageDepth DFTCert.StructuralRun_1dbf637fb245.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_1dbf637fb245.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_1dbf637fb245.sourceSha256 = "f7690444c682a7a4f67a6a461e481277740f91068d9fe428ca370fc42ed5cc0f" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_1dbf637fb245.irSha256 = "1dbf637fb245a730444e91a8ec31a22f85387044db4e9ea96aa16e7b2bf2fd49" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_1dbf637fb245.sourceSha256 = "f7690444c682a7a4f67a6a461e481277740f91068d9fe428ca370fc42ed5cc0f")
#check (generated_ir_binding : DFTCert.StructuralRun_1dbf637fb245.irSha256 = "1dbf637fb245a730444e91a8ec31a22f85387044db4e9ea96aa16e7b2bf2fd49")

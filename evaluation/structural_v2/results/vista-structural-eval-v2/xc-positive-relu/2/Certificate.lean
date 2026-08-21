import Testv2.StructuralV2

namespace DFTCert.StructuralRun_7a5fb6fe8ff1

def sourceSha256 : String := "3a4a5a8cdc9c2dd7af91e71e2752fefd2620541c2c04d4503f739b8d184e6cdf"
def irSha256 : String := "7a5fb6fe8ff1aafd1b60bf9492a9a27882a9f40ec3799ea03921938954433280"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_7a5fb6fe8ff1

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_7a5fb6fe8ff1.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_7a5fb6fe8ff1.edges DFTCert.StructuralRun_7a5fb6fe8ff1.messageDepth DFTCert.StructuralRun_7a5fb6fe8ff1.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_7a5fb6fe8ff1.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_7a5fb6fe8ff1.sourceSha256 = "3a4a5a8cdc9c2dd7af91e71e2752fefd2620541c2c04d4503f739b8d184e6cdf" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_7a5fb6fe8ff1.irSha256 = "7a5fb6fe8ff1aafd1b60bf9492a9a27882a9f40ec3799ea03921938954433280" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_7a5fb6fe8ff1.sourceSha256 = "3a4a5a8cdc9c2dd7af91e71e2752fefd2620541c2c04d4503f739b8d184e6cdf")
#check (generated_ir_binding : DFTCert.StructuralRun_7a5fb6fe8ff1.irSha256 = "7a5fb6fe8ff1aafd1b60bf9492a9a27882a9f40ec3799ea03921938954433280")

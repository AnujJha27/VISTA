import Testv2.StructuralV2

namespace DFTCert.StructuralRun_040dc27ef489

def sourceSha256 : String := "21f8dbe6d9dfc71832fdc3bc05272eead06d51f1c86efaf0b788fbb706d1612f"
def irSha256 : String := "040dc27ef4895ebf202cecbef2d2cddefa9547386280fb0bf8c9ff4d3f185786"
def edges : List (Nat × Nat) := [(3, 0), (0, 1), (1, 2), (2, 3)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .identity

end DFTCert.StructuralRun_040dc27ef489

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_040dc27ef489.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_040dc27ef489.edges DFTCert.StructuralRun_040dc27ef489.messageDepth DFTCert.StructuralRun_040dc27ef489.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_040dc27ef489.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_040dc27ef489.sourceSha256 = "21f8dbe6d9dfc71832fdc3bc05272eead06d51f1c86efaf0b788fbb706d1612f" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_040dc27ef489.irSha256 = "040dc27ef4895ebf202cecbef2d2cddefa9547386280fb0bf8c9ff4d3f185786" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_040dc27ef489.sourceSha256 = "21f8dbe6d9dfc71832fdc3bc05272eead06d51f1c86efaf0b788fbb706d1612f")
#check (generated_ir_binding : DFTCert.StructuralRun_040dc27ef489.irSha256 = "040dc27ef4895ebf202cecbef2d2cddefa9547386280fb0bf8c9ff4d3f185786")

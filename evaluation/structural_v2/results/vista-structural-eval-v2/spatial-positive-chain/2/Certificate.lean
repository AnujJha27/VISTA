import Testv2.StructuralV2

namespace DFTCert.StructuralRun_396851b8e7a8

def sourceSha256 : String := "06a24b80cbaab1588bfbd0c4550821eb319fa9e8706db4bcd3c9d94419704e8f"
def irSha256 : String := "396851b8e7a880fe78c2d5a16887fe892bc08140e020e2a831b5cdf15c3778ce"
def edges : List (Nat × Nat) := [(0, 1), (1, 2), (2, 3)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 3)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_396851b8e7a8

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_396851b8e7a8.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_396851b8e7a8.edges DFTCert.StructuralRun_396851b8e7a8.messageDepth DFTCert.StructuralRun_396851b8e7a8.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_396851b8e7a8.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_396851b8e7a8.sourceSha256 = "06a24b80cbaab1588bfbd0c4550821eb319fa9e8706db4bcd3c9d94419704e8f" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_396851b8e7a8.irSha256 = "396851b8e7a880fe78c2d5a16887fe892bc08140e020e2a831b5cdf15c3778ce" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_396851b8e7a8.sourceSha256 = "06a24b80cbaab1588bfbd0c4550821eb319fa9e8706db4bcd3c9d94419704e8f")
#check (generated_ir_binding : DFTCert.StructuralRun_396851b8e7a8.irSha256 = "396851b8e7a880fe78c2d5a16887fe892bc08140e020e2a831b5cdf15c3778ce")

import Testv2.StructuralV2

namespace DFTCert.StructuralRun_2e5dc8ad86ed

def sourceSha256 : String := "2b13460072538929f17615ae2261aa32ec6c27e24c9c3f34bdf74d5afa4aba07"
def irSha256 : String := "2e5dc8ad86ed3307dd78d8536c29eb936588d5e74bc40da94a430e3711286f3c"
def edges : List (Nat × Nat) := [(3, 0), (0, 1), (1, 2), (2, 3)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .identity

end DFTCert.StructuralRun_2e5dc8ad86ed

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_2e5dc8ad86ed.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_2e5dc8ad86ed.edges DFTCert.StructuralRun_2e5dc8ad86ed.messageDepth DFTCert.StructuralRun_2e5dc8ad86ed.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_2e5dc8ad86ed.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_2e5dc8ad86ed.sourceSha256 = "2b13460072538929f17615ae2261aa32ec6c27e24c9c3f34bdf74d5afa4aba07" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_2e5dc8ad86ed.irSha256 = "2e5dc8ad86ed3307dd78d8536c29eb936588d5e74bc40da94a430e3711286f3c" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_2e5dc8ad86ed.sourceSha256 = "2b13460072538929f17615ae2261aa32ec6c27e24c9c3f34bdf74d5afa4aba07")
#check (generated_ir_binding : DFTCert.StructuralRun_2e5dc8ad86ed.irSha256 = "2e5dc8ad86ed3307dd78d8536c29eb936588d5e74bc40da94a430e3711286f3c")

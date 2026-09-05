import Testv2.StructuralV2

namespace DFTCert.StructuralRun_fe075055849d

def sourceSha256 : String := "67833304a686bdbf470d79aff8d8542547321e243323aa387ca6762603766204"
def irSha256 : String := "fe075055849d851357b3ac7bd42b9efe79745fdddfb12738ba5f0b64c6fde337"
def edges : List (Nat × Nat) := [(3, 0), (0, 1), (1, 2), (2, 3)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .identity

end DFTCert.StructuralRun_fe075055849d

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_fe075055849d.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_fe075055849d.edges DFTCert.StructuralRun_fe075055849d.messageDepth DFTCert.StructuralRun_fe075055849d.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_fe075055849d.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_fe075055849d.sourceSha256 = "67833304a686bdbf470d79aff8d8542547321e243323aa387ca6762603766204" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_fe075055849d.irSha256 = "fe075055849d851357b3ac7bd42b9efe79745fdddfb12738ba5f0b64c6fde337" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_fe075055849d.sourceSha256 = "67833304a686bdbf470d79aff8d8542547321e243323aa387ca6762603766204")
#check (generated_ir_binding : DFTCert.StructuralRun_fe075055849d.irSha256 = "fe075055849d851357b3ac7bd42b9efe79745fdddfb12738ba5f0b64c6fde337")

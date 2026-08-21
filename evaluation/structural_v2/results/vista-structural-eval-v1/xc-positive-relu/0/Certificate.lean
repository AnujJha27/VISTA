import Testv2.StructuralV2

namespace DFTCert.StructuralRun_731e127df910

def sourceSha256 : String := "22d44cdc14e57c808dbeba2d9a244be8681c861afc8302e5e19ec5008a1aa257"
def irSha256 : String := "731e127df910a2b79b1308b0fec6f939b2f99d147a4c9f0bba05eb59b0d8f708"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_731e127df910

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_731e127df910.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_731e127df910.edges DFTCert.StructuralRun_731e127df910.messageDepth DFTCert.StructuralRun_731e127df910.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_731e127df910.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_731e127df910.sourceSha256 = "22d44cdc14e57c808dbeba2d9a244be8681c861afc8302e5e19ec5008a1aa257" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_731e127df910.irSha256 = "731e127df910a2b79b1308b0fec6f939b2f99d147a4c9f0bba05eb59b0d8f708" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_731e127df910.sourceSha256 = "22d44cdc14e57c808dbeba2d9a244be8681c861afc8302e5e19ec5008a1aa257")
#check (generated_ir_binding : DFTCert.StructuralRun_731e127df910.irSha256 = "731e127df910a2b79b1308b0fec6f939b2f99d147a4c9f0bba05eb59b0d8f708")

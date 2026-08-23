import Testv2.StructuralV2

namespace DFTCert.StructuralRun_ac0cf0d016ca

def sourceSha256 : String := "d468309986704b4042dc43ee73a44353b764f21ae3bc170e0f5dbefae7ac0291"
def irSha256 : String := "ac0cf0d016cad330548caf97e08d21a04b0c5f8f891d5d5cc62bb3fe08cb0b18"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 3)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_ac0cf0d016ca

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_ac0cf0d016ca.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_ac0cf0d016ca.edges DFTCert.StructuralRun_ac0cf0d016ca.messageDepth DFTCert.StructuralRun_ac0cf0d016ca.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_ac0cf0d016ca.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_ac0cf0d016ca.sourceSha256 = "d468309986704b4042dc43ee73a44353b764f21ae3bc170e0f5dbefae7ac0291" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_ac0cf0d016ca.irSha256 = "ac0cf0d016cad330548caf97e08d21a04b0c5f8f891d5d5cc62bb3fe08cb0b18" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_ac0cf0d016ca.sourceSha256 = "d468309986704b4042dc43ee73a44353b764f21ae3bc170e0f5dbefae7ac0291")
#check (generated_ir_binding : DFTCert.StructuralRun_ac0cf0d016ca.irSha256 = "ac0cf0d016cad330548caf97e08d21a04b0c5f8f891d5d5cc62bb3fe08cb0b18")

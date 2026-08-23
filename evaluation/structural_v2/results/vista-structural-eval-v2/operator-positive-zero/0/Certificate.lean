import Testv2.StructuralV2

namespace DFTCert.StructuralRun_a7a7d8fe1e12

def sourceSha256 : String := "3b4b372ec9ee60cbfe796153aa0d8954f267f7462569f65728665386802ebf4e"
def irSha256 : String := "a7a7d8fe1e12661c69d842ca0b65fcb6fcc045383ba5e7afc3c2cff38ca0b58c"
def edges : List (Nat × Nat) := [(3, 0), (0, 1), (1, 2), (2, 3)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .zero

end DFTCert.StructuralRun_a7a7d8fe1e12

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_a7a7d8fe1e12.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_a7a7d8fe1e12.edges DFTCert.StructuralRun_a7a7d8fe1e12.messageDepth DFTCert.StructuralRun_a7a7d8fe1e12.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_a7a7d8fe1e12.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_a7a7d8fe1e12.sourceSha256 = "3b4b372ec9ee60cbfe796153aa0d8954f267f7462569f65728665386802ebf4e" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_a7a7d8fe1e12.irSha256 = "a7a7d8fe1e12661c69d842ca0b65fcb6fcc045383ba5e7afc3c2cff38ca0b58c" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_a7a7d8fe1e12.sourceSha256 = "3b4b372ec9ee60cbfe796153aa0d8954f267f7462569f65728665386802ebf4e")
#check (generated_ir_binding : DFTCert.StructuralRun_a7a7d8fe1e12.irSha256 = "a7a7d8fe1e12661c69d842ca0b65fcb6fcc045383ba5e7afc3c2cff38ca0b58c")

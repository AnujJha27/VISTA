import Testv2.StructuralV2

namespace DFTCert.StructuralRun_543c016ba944

def sourceSha256 : String := "3be8c9add6852030f5fcae23c83454012a34ac45def13db246ba11ac9d71fa46"
def irSha256 : String := "543c016ba944e70baaedcb4a85e4bd0bff7e7a5c73d8d28c06da09aebf4d417a"
def edges : List (Nat × Nat) := [(3, 0), (0, 1), (1, 2), (2, 3)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .zero

end DFTCert.StructuralRun_543c016ba944

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_543c016ba944.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_543c016ba944.edges DFTCert.StructuralRun_543c016ba944.messageDepth DFTCert.StructuralRun_543c016ba944.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_543c016ba944.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_543c016ba944.sourceSha256 = "3be8c9add6852030f5fcae23c83454012a34ac45def13db246ba11ac9d71fa46" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_543c016ba944.irSha256 = "543c016ba944e70baaedcb4a85e4bd0bff7e7a5c73d8d28c06da09aebf4d417a" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_543c016ba944.sourceSha256 = "3be8c9add6852030f5fcae23c83454012a34ac45def13db246ba11ac9d71fa46")
#check (generated_ir_binding : DFTCert.StructuralRun_543c016ba944.irSha256 = "543c016ba944e70baaedcb4a85e4bd0bff7e7a5c73d8d28c06da09aebf4d417a")

import Testv2.StructuralV2

namespace DFTCert.StructuralRun_0ee714300bec

def sourceSha256 : String := "333108d421999ecd24248a64fd9a55e4f21d7b78ecdb3521a680e1450ff55720"
def irSha256 : String := "0ee714300bec616b55a88696e331cdf3a1e14bb753d8dd620d1b85398ad1b8ba"
def edges : List (Nat × Nat) := [(3, 0), (0, 1), (1, 2), (2, 3)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .zero

end DFTCert.StructuralRun_0ee714300bec

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_0ee714300bec.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_0ee714300bec.edges DFTCert.StructuralRun_0ee714300bec.messageDepth DFTCert.StructuralRun_0ee714300bec.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_0ee714300bec.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_0ee714300bec.sourceSha256 = "333108d421999ecd24248a64fd9a55e4f21d7b78ecdb3521a680e1450ff55720" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_0ee714300bec.irSha256 = "0ee714300bec616b55a88696e331cdf3a1e14bb753d8dd620d1b85398ad1b8ba" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_0ee714300bec.sourceSha256 = "333108d421999ecd24248a64fd9a55e4f21d7b78ecdb3521a680e1450ff55720")
#check (generated_ir_binding : DFTCert.StructuralRun_0ee714300bec.irSha256 = "0ee714300bec616b55a88696e331cdf3a1e14bb753d8dd620d1b85398ad1b8ba")

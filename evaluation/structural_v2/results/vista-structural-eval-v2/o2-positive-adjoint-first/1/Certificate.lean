import Testv2.StructuralV2

namespace DFTCert.StructuralRun_96dd12fe7cc4

def sourceSha256 : String := "fb0f7db49770420befee74236e0d35f2a839e4fb5b1245f8ca0c72aae3a51e8a"
def irSha256 : String := "96dd12fe7cc4dca0bdf5a1b4fe39a2b039dbbba1bc9f28453a48981af1f80d1e"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_96dd12fe7cc4

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_96dd12fe7cc4.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_96dd12fe7cc4.edges DFTCert.StructuralRun_96dd12fe7cc4.messageDepth DFTCert.StructuralRun_96dd12fe7cc4.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_96dd12fe7cc4.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_96dd12fe7cc4.sourceSha256 = "fb0f7db49770420befee74236e0d35f2a839e4fb5b1245f8ca0c72aae3a51e8a" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_96dd12fe7cc4.irSha256 = "96dd12fe7cc4dca0bdf5a1b4fe39a2b039dbbba1bc9f28453a48981af1f80d1e" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_96dd12fe7cc4.sourceSha256 = "fb0f7db49770420befee74236e0d35f2a839e4fb5b1245f8ca0c72aae3a51e8a")
#check (generated_ir_binding : DFTCert.StructuralRun_96dd12fe7cc4.irSha256 = "96dd12fe7cc4dca0bdf5a1b4fe39a2b039dbbba1bc9f28453a48981af1f80d1e")

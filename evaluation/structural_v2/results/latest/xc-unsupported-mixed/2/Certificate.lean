import Testv2.StructuralV2

namespace DFTCert.StructuralRun_2c17e693721a

def sourceSha256 : String := "e53ce18d4fb2299a7a944b7cc4219fe37bf78c492d8e8eb9c85d5c72cf822a5f"
def irSha256 : String := "2c17e693721ace780c4eef7424037e9c2720eb386cf3ce8c19eecb78add79d7e"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_2c17e693721a

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_2c17e693721a.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_2c17e693721a.edges DFTCert.StructuralRun_2c17e693721a.messageDepth DFTCert.StructuralRun_2c17e693721a.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_2c17e693721a.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_2c17e693721a.sourceSha256 = "e53ce18d4fb2299a7a944b7cc4219fe37bf78c492d8e8eb9c85d5c72cf822a5f" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_2c17e693721a.irSha256 = "2c17e693721ace780c4eef7424037e9c2720eb386cf3ce8c19eecb78add79d7e" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_2c17e693721a.sourceSha256 = "e53ce18d4fb2299a7a944b7cc4219fe37bf78c492d8e8eb9c85d5c72cf822a5f")
#check (generated_ir_binding : DFTCert.StructuralRun_2c17e693721a.irSha256 = "2c17e693721ace780c4eef7424037e9c2720eb386cf3ce8c19eecb78add79d7e")

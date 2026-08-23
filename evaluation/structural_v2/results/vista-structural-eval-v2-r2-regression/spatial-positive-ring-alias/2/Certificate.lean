import Testv2.StructuralV2

namespace DFTCert.StructuralRun_a8cc4cca59dc

def sourceSha256 : String := "10ed8e22f263dc84e9bf6287a85be52aae9d03ec796e7560a8175f78982d9807"
def irSha256 : String := "a8cc4cca59dc94275da0d156589e6c25be15b13fc5edf683165c8d293fdd4994"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 3)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_a8cc4cca59dc

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_a8cc4cca59dc.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_a8cc4cca59dc.edges DFTCert.StructuralRun_a8cc4cca59dc.messageDepth DFTCert.StructuralRun_a8cc4cca59dc.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_a8cc4cca59dc.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_a8cc4cca59dc.sourceSha256 = "10ed8e22f263dc84e9bf6287a85be52aae9d03ec796e7560a8175f78982d9807" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_a8cc4cca59dc.irSha256 = "a8cc4cca59dc94275da0d156589e6c25be15b13fc5edf683165c8d293fdd4994" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_a8cc4cca59dc.sourceSha256 = "10ed8e22f263dc84e9bf6287a85be52aae9d03ec796e7560a8175f78982d9807")
#check (generated_ir_binding : DFTCert.StructuralRun_a8cc4cca59dc.irSha256 = "a8cc4cca59dc94275da0d156589e6c25be15b13fc5edf683165c8d293fdd4994")

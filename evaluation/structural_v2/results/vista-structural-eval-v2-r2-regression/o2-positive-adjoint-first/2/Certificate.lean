import Testv2.StructuralV2

namespace DFTCert.StructuralRun_59a7eb721b5a

def sourceSha256 : String := "174f9b3f0bddfcda1ab2557670452bbd71895a1abe09b20402bbc22e939e7b43"
def irSha256 : String := "59a7eb721b5a67be2cf7e79f13c00eb46cb24a6df0bf30880ad7ff0d383a1f5b"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_59a7eb721b5a

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_59a7eb721b5a.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_59a7eb721b5a.edges DFTCert.StructuralRun_59a7eb721b5a.messageDepth DFTCert.StructuralRun_59a7eb721b5a.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_59a7eb721b5a.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_59a7eb721b5a.sourceSha256 = "174f9b3f0bddfcda1ab2557670452bbd71895a1abe09b20402bbc22e939e7b43" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_59a7eb721b5a.irSha256 = "59a7eb721b5a67be2cf7e79f13c00eb46cb24a6df0bf30880ad7ff0d383a1f5b" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_59a7eb721b5a.sourceSha256 = "174f9b3f0bddfcda1ab2557670452bbd71895a1abe09b20402bbc22e939e7b43")
#check (generated_ir_binding : DFTCert.StructuralRun_59a7eb721b5a.irSha256 = "59a7eb721b5a67be2cf7e79f13c00eb46cb24a6df0bf30880ad7ff0d383a1f5b")

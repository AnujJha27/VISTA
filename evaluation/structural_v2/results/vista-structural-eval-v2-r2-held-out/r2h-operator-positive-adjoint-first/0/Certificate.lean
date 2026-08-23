import Testv2.StructuralV2

namespace DFTCert.StructuralRun_ee0cdb457ad6

def sourceSha256 : String := "3127d85b707d5fdc13783e067e0403a18f75ee1d903841d8587f79be4a4b1a40"
def irSha256 : String := "ee0cdb457ad6512c8912ef5acb7fb020cd5effb1edb420780793f8a51d8b7a4c"
def edges : List (Nat × Nat) := [(5, 0), (0, 1), (1, 2), (2, 3), (3, 4), (4, 5)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_ee0cdb457ad6

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_ee0cdb457ad6.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_ee0cdb457ad6.edges DFTCert.StructuralRun_ee0cdb457ad6.messageDepth DFTCert.StructuralRun_ee0cdb457ad6.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_ee0cdb457ad6.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_ee0cdb457ad6.sourceSha256 = "3127d85b707d5fdc13783e067e0403a18f75ee1d903841d8587f79be4a4b1a40" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_ee0cdb457ad6.irSha256 = "ee0cdb457ad6512c8912ef5acb7fb020cd5effb1edb420780793f8a51d8b7a4c" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_ee0cdb457ad6.sourceSha256 = "3127d85b707d5fdc13783e067e0403a18f75ee1d903841d8587f79be4a4b1a40")
#check (generated_ir_binding : DFTCert.StructuralRun_ee0cdb457ad6.irSha256 = "ee0cdb457ad6512c8912ef5acb7fb020cd5effb1edb420780793f8a51d8b7a4c")

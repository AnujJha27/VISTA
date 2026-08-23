import Testv2.StructuralV2

namespace DFTCert.StructuralRun_39ac27e4d72e

def sourceSha256 : String := "bde911d4d391c37c0f9a4d3d39af22847868ddf77921611a0cf934b0eec30de4"
def irSha256 : String := "39ac27e4d72e737092850769d0a2cda947ef3c134022532c43a62e86f73d69e4"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_39ac27e4d72e

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_39ac27e4d72e.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_39ac27e4d72e.edges DFTCert.StructuralRun_39ac27e4d72e.messageDepth DFTCert.StructuralRun_39ac27e4d72e.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_39ac27e4d72e.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_39ac27e4d72e.sourceSha256 = "bde911d4d391c37c0f9a4d3d39af22847868ddf77921611a0cf934b0eec30de4" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_39ac27e4d72e.irSha256 = "39ac27e4d72e737092850769d0a2cda947ef3c134022532c43a62e86f73d69e4" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_39ac27e4d72e.sourceSha256 = "bde911d4d391c37c0f9a4d3d39af22847868ddf77921611a0cf934b0eec30de4")
#check (generated_ir_binding : DFTCert.StructuralRun_39ac27e4d72e.irSha256 = "39ac27e4d72e737092850769d0a2cda947ef3c134022532c43a62e86f73d69e4")

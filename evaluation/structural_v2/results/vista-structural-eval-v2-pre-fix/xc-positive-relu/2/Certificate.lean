import Testv2.StructuralV2

namespace DFTCert.StructuralRun_d3922f908a28

def sourceSha256 : String := "8dd997b58b1e6c7b590db45f439c744aa76eae3659241e5a8bf30d0a031f5004"
def irSha256 : String := "d3922f908a2824cbc5c7a78f69ec6d3dbbb4a5917bc075026c4c4e3b63891f09"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_d3922f908a28

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_d3922f908a28.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_d3922f908a28.edges DFTCert.StructuralRun_d3922f908a28.messageDepth DFTCert.StructuralRun_d3922f908a28.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_d3922f908a28.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_d3922f908a28.sourceSha256 = "8dd997b58b1e6c7b590db45f439c744aa76eae3659241e5a8bf30d0a031f5004" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_d3922f908a28.irSha256 = "d3922f908a2824cbc5c7a78f69ec6d3dbbb4a5917bc075026c4c4e3b63891f09" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_d3922f908a28.sourceSha256 = "8dd997b58b1e6c7b590db45f439c744aa76eae3659241e5a8bf30d0a031f5004")
#check (generated_ir_binding : DFTCert.StructuralRun_d3922f908a28.irSha256 = "d3922f908a2824cbc5c7a78f69ec6d3dbbb4a5917bc075026c4c4e3b63891f09")

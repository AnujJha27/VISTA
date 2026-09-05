import Testv2.StructuralV2

namespace DFTCert.StructuralRun_974b0fda62d6

def sourceSha256 : String := "121e96ec782803488e7982d1970db5f52f979f6ed006b16b33ae1d825b54f3fb"
def irSha256 : String := "974b0fda62d645c41bd04ba749ab107857230e3bbfdf8220abed8e1797c703c4"
def edges : List (Nat × Nat) := [(0, 1), (1, 2), (2, 3)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 3)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_974b0fda62d6

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_974b0fda62d6.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_974b0fda62d6.edges DFTCert.StructuralRun_974b0fda62d6.messageDepth DFTCert.StructuralRun_974b0fda62d6.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_974b0fda62d6.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_974b0fda62d6.sourceSha256 = "121e96ec782803488e7982d1970db5f52f979f6ed006b16b33ae1d825b54f3fb" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_974b0fda62d6.irSha256 = "974b0fda62d645c41bd04ba749ab107857230e3bbfdf8220abed8e1797c703c4" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_974b0fda62d6.sourceSha256 = "121e96ec782803488e7982d1970db5f52f979f6ed006b16b33ae1d825b54f3fb")
#check (generated_ir_binding : DFTCert.StructuralRun_974b0fda62d6.irSha256 = "974b0fda62d645c41bd04ba749ab107857230e3bbfdf8220abed8e1797c703c4")

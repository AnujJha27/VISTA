import Testv2.StructuralV2

namespace DFTCert.StructuralRun_1be54b7d3833

def sourceSha256 : String := "58faeb876d0ee1ca901eb1d58232a1dcccbc77ca5df952c8871ff882f5659b7b"
def irSha256 : String := "1be54b7d3833598bc4b129851f9c872ec01de79eb3ebcf386727e8956dd94da6"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_1be54b7d3833

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_1be54b7d3833.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_1be54b7d3833.edges DFTCert.StructuralRun_1be54b7d3833.messageDepth DFTCert.StructuralRun_1be54b7d3833.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_1be54b7d3833.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_1be54b7d3833.sourceSha256 = "58faeb876d0ee1ca901eb1d58232a1dcccbc77ca5df952c8871ff882f5659b7b" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_1be54b7d3833.irSha256 = "1be54b7d3833598bc4b129851f9c872ec01de79eb3ebcf386727e8956dd94da6" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_1be54b7d3833.sourceSha256 = "58faeb876d0ee1ca901eb1d58232a1dcccbc77ca5df952c8871ff882f5659b7b")
#check (generated_ir_binding : DFTCert.StructuralRun_1be54b7d3833.irSha256 = "1be54b7d3833598bc4b129851f9c872ec01de79eb3ebcf386727e8956dd94da6")

import Testv2.StructuralV2

namespace DFTCert.StructuralRun_979b5e2522cc

def sourceSha256 : String := "07127e46c4f19b8b4747450ca0ee633a99b5d06e272dd1589d1289a797253230"
def irSha256 : String := "979b5e2522ccb5adbc85727ed3464d68a6781890d711010702d14c3102bae625"
def edges : List (Nat × Nat) := [(3, 0), (0, 1), (1, 2), (2, 3)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .identity

end DFTCert.StructuralRun_979b5e2522cc

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_979b5e2522cc.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_979b5e2522cc.edges DFTCert.StructuralRun_979b5e2522cc.messageDepth DFTCert.StructuralRun_979b5e2522cc.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_979b5e2522cc.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_979b5e2522cc.sourceSha256 = "07127e46c4f19b8b4747450ca0ee633a99b5d06e272dd1589d1289a797253230" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_979b5e2522cc.irSha256 = "979b5e2522ccb5adbc85727ed3464d68a6781890d711010702d14c3102bae625" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_979b5e2522cc.sourceSha256 = "07127e46c4f19b8b4747450ca0ee633a99b5d06e272dd1589d1289a797253230")
#check (generated_ir_binding : DFTCert.StructuralRun_979b5e2522cc.irSha256 = "979b5e2522ccb5adbc85727ed3464d68a6781890d711010702d14c3102bae625")

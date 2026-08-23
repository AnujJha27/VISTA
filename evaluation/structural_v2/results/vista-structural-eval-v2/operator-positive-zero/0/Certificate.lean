import Testv2.StructuralV2

namespace DFTCert.StructuralRun_c6863fa9f03e

def sourceSha256 : String := "65104f83370706f1ef1faa02ca65f98fddf5f1ebb4c1b44662a43498ca9c9cc5"
def irSha256 : String := "c6863fa9f03e827e1f520b456248261c6890c9bd86a1f88f3333790d6fe0ceee"
def edges : List (Nat × Nat) := [(3, 0), (0, 1), (1, 2), (2, 3)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .zero

end DFTCert.StructuralRun_c6863fa9f03e

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_c6863fa9f03e.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_c6863fa9f03e.edges DFTCert.StructuralRun_c6863fa9f03e.messageDepth DFTCert.StructuralRun_c6863fa9f03e.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_c6863fa9f03e.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_c6863fa9f03e.sourceSha256 = "65104f83370706f1ef1faa02ca65f98fddf5f1ebb4c1b44662a43498ca9c9cc5" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_c6863fa9f03e.irSha256 = "c6863fa9f03e827e1f520b456248261c6890c9bd86a1f88f3333790d6fe0ceee" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_c6863fa9f03e.sourceSha256 = "65104f83370706f1ef1faa02ca65f98fddf5f1ebb4c1b44662a43498ca9c9cc5")
#check (generated_ir_binding : DFTCert.StructuralRun_c6863fa9f03e.irSha256 = "c6863fa9f03e827e1f520b456248261c6890c9bd86a1f88f3333790d6fe0ceee")

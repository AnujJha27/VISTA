import Testv2.StructuralV2

namespace DFTCert.StructuralRun_98d963805dec

def sourceSha256 : String := "09771905136e7fdbaa6cbf3459fe1090df8def42e2a6e486600dc9d2204bab7e"
def irSha256 : String := "98d963805decb9d24a39cfead3c6e536b90f50239e548198b7628fc04f016f1b"
def edges : List (Nat × Nat) := [(4, 0), (0, 1), (1, 2), (2, 3), (3, 4)]
def messageDepth : Nat := 3
def requiredCouplings : List (Nat × Nat) := [(0, 2)]
def xcForm : Testv2.StructuralV2.XCForm := .hinge
def operatorForm : Testv2.StructuralV2.OperatorForm := .add (.parameter "base") (.adjoint (.parameter "base"))

end DFTCert.StructuralRun_98d963805dec

theorem generated_xc_structure : Testv2.StructuralV2.xcSupportsDiscontinuity DFTCert.StructuralRun_98d963805dec.xcForm = true := by decide

theorem generated_spatial_structure : Testv2.StructuralV2.allCovered DFTCert.StructuralRun_98d963805dec.edges DFTCert.StructuralRun_98d963805dec.messageDepth DFTCert.StructuralRun_98d963805dec.requiredCouplings = true := by decide

theorem generated_operator_structure : Testv2.StructuralV2.guaranteedSelfAdjoint DFTCert.StructuralRun_98d963805dec.operatorForm = true := by decide

theorem generated_source_binding : DFTCert.StructuralRun_98d963805dec.sourceSha256 = "09771905136e7fdbaa6cbf3459fe1090df8def42e2a6e486600dc9d2204bab7e" := rfl
theorem generated_ir_binding : DFTCert.StructuralRun_98d963805dec.irSha256 = "98d963805decb9d24a39cfead3c6e536b90f50239e548198b7628fc04f016f1b" := rfl

#check (generated_source_binding : DFTCert.StructuralRun_98d963805dec.sourceSha256 = "09771905136e7fdbaa6cbf3459fe1090df8def42e2a6e486600dc9d2204bab7e")
#check (generated_ir_binding : DFTCert.StructuralRun_98d963805dec.irSha256 = "98d963805decb9d24a39cfead3c6e536b90f50239e548198b7628fc04f016f1b")

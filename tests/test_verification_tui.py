"""`dftcert.verification.tui`'s pure rendering functions (spec section 15) --
no `curses`, so this runs anywhere, unlike `run_interactive` itself. Fixture
session is hand-built, not derived from a real Lean run: this only checks
rendering, not resolution semantics (that's `test_verification_session.py`).
"""
import unittest

from dftcert.verification.tui import node_detail_lines, render_target_tree

ENTRY = "Testv2.Requirements.ValidPretrainingArchitecture"


def _session():
    nodes = {
        f"{ENTRY}#0": {
            "kind": "data", "entrypoint": ENTRY, "binder_path": "0", "binder_name": "siteCount",
            "pretty_type": "siteCount = 3", "status": "artifact_grounded",
            "candidate_keys": ["site_count"], "chosen_candidate_key": "site_count",
        },
        f"{ENTRY}#1": {
            "kind": "data", "entrypoint": ENTRY, "binder_path": "1", "binder_name": "op",
            "pretty_type": "operator = symmetrized", "status": "artifact_grounded",
            "candidate_keys": ["operator_form"], "chosen_candidate_key": "operator_form",
        },
        f"{ENTRY}#2": {
            "kind": "premise", "entrypoint": ENTRY, "binder_path": "2", "binder_name": "hPhysical",
            "pretty_type": "TargetRequiresNonLocality", "status": "unresolved",
        },
    }
    return {
        "targets": [{"entrypoint": ENTRY, "root_node_ids": list(nodes)}],
        "nodes": nodes,
    }


class RenderTargetTreeTests(unittest.TestCase):
    def test_blocked_target_shows_blocked_header(self):
        tree = render_target_tree(_session(), ENTRY)
        self.assertIn(f"{ENTRY}     [BLOCKED]", tree)

    def test_ready_target_shows_ready_header_when_nothing_unresolved(self):
        session = _session()
        session["nodes"][f"{ENTRY}#2"]["status"] = "specified_assumption"
        tree = render_target_tree(session, ENTRY)
        self.assertIn(f"{ENTRY}     [READY]", tree)

    def test_each_node_shows_its_status_tag(self):
        tree = render_target_tree(_session(), ENTRY)
        self.assertIn("[ARTIFACT]", tree)
        self.assertIn("[UNRESOLVED]", tree)

    def test_unknown_entrypoint_does_not_crash(self):
        self.assertIn("no such target", render_target_tree(_session(), "Nope.Entrypoint"))


class NodeDetailLinesTests(unittest.TestCase):
    def test_unresolved_premise_offers_accept_assumption_action(self):
        lines = node_detail_lines(_session(), f"{ENTRY}#2")
        self.assertIn("  [a] accept as explicit external assumption", lines)
        self.assertIn("  no explicit assumption", lines)

    def test_resolved_data_node_shows_status_not_actions(self):
        lines = node_detail_lines(_session(), f"{ENTRY}#0")
        self.assertTrue(any("ARTIFACT" in line for line in lines))
        self.assertFalse(any("[a] accept" in line for line in lines))

    def test_unknown_node_does_not_crash(self):
        self.assertEqual(node_detail_lines(_session(), "nope"), ["no such node: nope"])


if __name__ == "__main__":
    unittest.main()

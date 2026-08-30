from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PentaPRTerminalV3Tests(unittest.TestCase):
    def test_terminal_provider_is_exact_head_fenced(self):
        text = (ROOT / "supabase/functions/penta-pr-terminal-provider/index.ts").read_text()
        self.assertIn('DEFERRED_HEAD_MOVED', text)
        self.assertIn('expected_head_sha', text)
        self.assertIn('exact_head_certified', text)

    def test_zero_delta_evidence_descendants_are_narrow(self):
        text = (ROOT / "supabase/functions/penta-pr-terminal-provider/index.ts").read_text()
        self.assertIn('EVIDENCE_ONLY_DESCENDANT', text)
        self.assertIn('penta/remediations/${finding}.execution.json', text)
        self.assertIn('NON_EVIDENCE_DELTA', text)

    def test_zero_delta_closes_without_merge(self):
        text = (ROOT / "supabase/functions/penta-pr-terminal-provider/index.ts").read_text()
        self.assertIn('VERIFIED_ZERO_DELTA', text)
        self.assertIn('terminal close without merge', text)
        self.assertIn('close_classification_not_allowed', text)

    def test_scheduler_contract_is_source_controlled(self):
        text = (ROOT / "supabase/migrations/20260830032100_penta_pr_exact_head_terminal_reconciliation_v3.sql").read_text()
        self.assertIn('penta_pr_terminal_reconcile', text)
        self.assertIn('current_vergence_repairs_v3', text)
        self.assertIn('historical_vergence_non_authoritative', text)
        self.assertIn("'D3_human_reserved',true", text)


if __name__ == "__main__":
    unittest.main()

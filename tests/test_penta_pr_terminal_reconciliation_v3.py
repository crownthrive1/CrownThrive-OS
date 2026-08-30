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

    def test_worker_does_not_mutate_zero_delta_branch(self):
        worker = (ROOT / "scripts/penta_remediation_worker_execute_native.py").read_text()
        workflow = (ROOT / ".github/workflows/penta-remediation-worker-execution.yml").read_text()
        self.assertIn('if bool(receipt.get("no_code_delta")):', worker)
        self.assertIn('return None', worker)
        self.assertIn('"penta:hold" in labels', worker)
        self.assertIn('penta_remediation_worker_execute_native.py', workflow)
        self.assertIn('GITHUB_TOKEN: ${{ github.token }}', workflow)

    def test_scheduler_contract_is_source_controlled(self):
        text = (ROOT / "supabase/migrations/20260830032100_penta_pr_exact_head_terminal_reconciliation_v3.sql").read_text()
        self.assertIn('penta_pr_terminal_reconcile', text)
        self.assertIn('current_vergence_repairs_v3', text)
        self.assertIn('historical_vergence_non_authoritative', text)
        self.assertIn("'D3_human_reserved',true", text)

    def test_retroactive_backfill_is_resumable_and_never_auto_merges(self):
        provider = (ROOT / "supabase/functions/penta-pr-terminal-provider/index.ts").read_text()
        migration = (ROOT / "supabase/migrations/20260830034200_penta_pr_retroactive_backfill_v3_2.sql").read_text()
        self.assertIn('backfillStep', provider)
        self.assertIn('state=all', provider)
        self.assertIn('retroactive_merge: false', provider)
        self.assertIn('Historical merges are never manufactured', provider)
        self.assertIn('penta_pr.retroactive_backfill_v3', migration)
        self.assertIn('for update of b skip locked', migration)
        self.assertIn("lease_until=now()+interval '90 seconds'", migration)

    def test_historical_truth_repairs_lifecycle_holes(self):
        migration = (ROOT / "supabase/migrations/20260830034200_penta_pr_retroactive_backfill_v3_2.sql").read_text()
        self.assertIn('insert into penta_pr.lifecycle', migration)
        self.assertIn('on conflict(repo,pr_number) do update', migration)
        self.assertIn("'retroactive_provider_truth',true", migration)
        self.assertIn('github_pr_truth_receipts_v2', migration)


if __name__ == "__main__":
    unittest.main()

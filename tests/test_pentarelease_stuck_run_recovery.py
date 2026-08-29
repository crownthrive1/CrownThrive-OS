from pathlib import Path
import json
import unittest


class PentaReleaseStuckRunRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = Path('.github/workflows/pentarelease-stuck-run-recovery.yml').read_text(encoding='utf-8')
        cls.marker = json.loads(Path('penta/recovery/pentarelease-run-33244352453.json').read_text(encoding='utf-8'))

    def test_recovery_targets_only_the_known_broken_run(self):
        self.assertEqual(self.marker['target_run_id'], 33244352453)
        self.assertEqual(self.marker['scope'], 'cancel_exact_run_only')
        self.assertTrue(self.marker['one_shot'])
        self.assertIn("TARGET_RUN_ID: '33244352453'", self.workflow)
        self.assertNotIn('actions/runs?status=', self.workflow)

    def test_recovery_is_idempotent_if_target_is_terminal(self):
        self.assertTrue(self.marker['idempotent_if_terminal'])
        self.assertIn('if [ "$STATUS" = "completed" ]; then', self.workflow)
        self.assertIn('idempotent no-op', self.workflow)

    def test_cancel_and_readback_are_provider_resilient(self):
        self.assertIn('gh_retry()', self.workflow)
        self.assertIn('gh api --method POST', self.workflow)
        self.assertIn('/cancel', self.workflow)
        self.assertIn('test "$terminal" = true', self.workflow)
        self.assertIn('Scope: one known pre-fix run only', self.workflow)


if __name__ == '__main__':
    unittest.main()

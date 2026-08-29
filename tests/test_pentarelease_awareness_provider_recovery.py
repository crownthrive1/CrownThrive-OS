from pathlib import Path
import unittest


class PentaReleaseAwarenessProviderRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = Path('.github/workflows/pentarelease-autonomous-awareness.yml').read_text(encoding='utf-8')

    def test_reruns_use_attempt_isolated_release_branches(self):
        self.assertIn('${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}', self.workflow)
        self.assertIn('Attempt identity is part of the release lane', self.workflow)

    def test_provider_reads_use_bounded_retry(self):
        self.assertIn('gh_retry()', self.workflow)
        self.assertIn('max_attempts=12', self.workflow)
        self.assertIn('gh_retry gh workflow run governed-merge-gate.yml', self.workflow)
        self.assertIn('STATE=$(gh_retry gh api', self.workflow)
        self.assertIn('gh_retry gh release upload', self.workflow)
        self.assertIn('READBACK=$(gh_retry gh release view', self.workflow)

    def test_governance_stays_fail_closed(self):
        self.assertIn('PentaRelease HOLD: governed merge gate did not pass', self.workflow)
        self.assertIn('test "$success" = true', self.workflow)
        self.assertIn('D3/breaking-authority changes remain HOLD for human governance', self.workflow)


if __name__ == '__main__':
    unittest.main()

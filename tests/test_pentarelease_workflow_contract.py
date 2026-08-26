import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "pentarelease-comprehensive-release-surface.yml"


class PentaReleaseWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_never_direct_pushes_protected_main(self):
        self.assertNotIn('git push origin "$HEAD_SHA":refs/heads/main', self.text)
        self.assertNotIn('git push origin HEAD:main', self.text)

    def test_provider_identity_gap_is_explicit_hold(self):
        self.assertIn("HOLD_PR_PROVIDER_IDENTITY", self.text)
        self.assertIn("HOLD_PR_MERGE_IDENTITY", self.text)

    def test_reconciliation_has_local_and_provider_preflight(self):
        self.assertIn("Determine reconciliation need", self.text)
        self.assertIn("local_ready=", self.text)
        self.assertIn("provider_ready=", self.text)
        self.assertIn("needs_sync=", self.text)

    def test_same_release_can_short_circuit(self):
        self.assertIn("ALREADY_SYNCHRONIZED", self.text)
        self.assertIn("steps.preflight.outputs.needs_sync == 'true'", self.text)

    def test_pending_branch_is_stable_per_release_and_base(self):
        self.assertIn('BRANCH="pentarelease/surface-${SAFE_TAG}-${BASE_SHA:0:12}"', self.text)
        self.assertIn('git ls-remote --heads origin "$BRANCH"', self.text)

    def test_pr_specific_gate_is_required_before_merge(self):
        self.assertIn("--event pull_request", self.text)
        self.assertIn('RUN_HEAD" = "$HEAD_SHA', self.text)
        self.assertIn('RUN_CONCLUSION" = "success', self.text)
        self.assertIn('gh pr merge "$PR_URL"', self.text)

    def test_release_payload_contract_is_complete(self):
        for name in (
            "PENTARELEASE_COMPREHENSIVE_RELEASE.md",
            "PENTARELEASE_RELEASE_RECORD.json",
            "PENTARELEASE_COSTS.json",
            "PENTARELEASE_CIE_SCORE.json",
            "PENTARELEASE_DATA_CATALOG.json",
            "PENTARELEASE_EVIDENCE.json",
            "PENTARELEASE_FAQ.md",
            "PENTARELEASE_CHANGELOG.md",
        ):
            self.assertIn(name, self.text)


if __name__ == "__main__":
    unittest.main()

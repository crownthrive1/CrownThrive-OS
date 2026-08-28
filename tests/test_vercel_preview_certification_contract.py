import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "vercel-preview-certification.yml"


class VercelPreviewCertificationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_default_audience_github_oidc_is_preserved(self):
        self.assertIn("ACTIONS_ID_TOKEN_REQUEST_URL", self.text)
        self.assertIn("ACTIONS_ID_TOKEN_REQUEST_TOKEN", self.text)
        self.assertIn("x-vercel-trusted-oidc-idp-token", self.text)
        self.assertNotIn("audience=", self.text)
        self.assertNotIn("actions/github-script", self.text)

    def test_exact_provider_deployment_is_read_back(self):
        self.assertIn('gh_json(f"/deployments/{deployment_id}")', self.text)
        self.assertIn('gh_json(f"/deployments/{deployment_id}/statuses?per_page=25")', self.text)
        self.assertIn("deployment SHA readback mismatch", self.text)
        self.assertIn("deployment ref readback mismatch", self.text)
        self.assertIn("deployment environment URL readback mismatch", self.text)

    def test_protected_preview_is_not_misclassified_as_provider_failure(self):
        self.assertIn("HOLD_TRUSTED_SOURCE", self.text)
        self.assertIn('certification_scope = "provider-deployment-only"', self.text)
        self.assertIn("provider_deployment_status", self.text)
        self.assertIn("application_probe_status", self.text)
        self.assertIn("Deployment Protection", self.text)

    def test_real_provider_or_runtime_failures_still_fail_closed(self):
        self.assertIn("provider_failures", self.text)
        self.assertIn("application_failures", self.text)
        self.assertIn("if failures:", self.text)
        self.assertIn("raise SystemExit(1)", self.text)

    def test_write_boundary_is_only_skipped_behind_verified_vercel_protection(self):
        self.assertIn("is_vercel_protection_wall", self.text)
        self.assertIn("x-vercel-id", self.text)
        self.assertIn('results["unauthorized_write"]', self.text)
        self.assertIn('"status": "NOT_EXECUTED"', self.text)
        self.assertIn("WRITE_GATED", self.text)


if __name__ == "__main__":
    unittest.main()

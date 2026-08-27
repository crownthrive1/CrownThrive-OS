import unittest
from pathlib import Path

from scripts import validate_security_governance as security


ROOT = Path(__file__).resolve().parents[1]
TRUSTED = (ROOT / ".github/workflows/penta-provider-control-plane.yml").read_text(
    encoding="utf-8"
)
CONTRACT = (ROOT / ".github/workflows/penta-provider-contract.yml").read_text(
    encoding="utf-8"
)


class ProviderWorkflowSecretBoundaryTests(unittest.TestCase):
    def test_repository_workflows_satisfy_secret_boundary(self):
        self.assertEqual(
            security.provider_workflow_boundary_errors(TRUSTED, CONTRACT),
            [],
        )

    def test_secret_reference_in_pull_request_contract_fails_closed(self):
        unsafe = CONTRACT.replace(
            "    timeout-minutes: 10",
            "    timeout-minutes: 10\n    env:\n      PROVIDER_TOKEN: ${{ secrets.UNIT_TEST_PROVIDER_TOKEN }}",
            1,
        )
        errors = security.provider_workflow_boundary_errors(TRUSTED, unsafe)
        self.assertIn(
            "provider contract workflow must not reference credentials or inherited secrets",
            errors,
        )

    def test_inherited_secrets_in_pull_request_contract_fail_closed(self):
        unsafe = CONTRACT.replace(
            "    timeout-minutes: 10",
            "    timeout-minutes: 10\n    secrets: inherit",
            1,
        )
        errors = security.provider_workflow_boundary_errors(TRUSTED, unsafe)
        self.assertIn(
            "provider contract workflow must not reference credentials or inherited secrets",
            errors,
        )

    def test_pull_request_event_on_trusted_workflow_fails_closed(self):
        unsafe = TRUSTED.replace("  push:\n", "  pull_request:\n  push:\n", 1)
        errors = security.provider_workflow_boundary_errors(unsafe, CONTRACT)
        self.assertIn(
            "trusted provider workflow must not accept pull-request events",
            errors,
        )

    def test_missing_exact_main_guard_fails_closed(self):
        unsafe = TRUSTED.replace(security.PROVIDER_TRUST_GUARD, "true", 1)
        errors = security.provider_workflow_boundary_errors(unsafe, CONTRACT)
        self.assertTrue(
            any("lacks exact-main repository guard" in error for error in errors),
            errors,
        )

    def test_persisted_pull_request_checkout_credentials_fail_closed(self):
        unsafe = CONTRACT.replace("          persist-credentials: false\n", "", 1)
        errors = security.provider_workflow_boundary_errors(TRUSTED, unsafe)
        self.assertIn(
            "every provider contract checkout must disable persisted credentials",
            errors,
        )

    def test_oidc_write_permission_in_pull_request_contract_fails_closed(self):
        unsafe = CONTRACT.replace("  contents: read", "  contents: read\n  id-token: write", 1)
        errors = security.provider_workflow_boundary_errors(TRUSTED, unsafe)
        self.assertIn("provider contract workflow must not mint OIDC tokens", errors)

    def test_error_tolerant_live_provider_probe_fails_closed(self):
        unsafe = TRUSTED.replace(
            "        id: certify\n",
            "        id: certify\n        continue-on-error: true\n",
            1,
        )
        errors = security.provider_workflow_boundary_errors(unsafe, CONTRACT)
        self.assertIn("provider live certification must not tolerate probe errors", errors)

    def test_missing_production_gate_hold_check_fails_closed(self):
        unsafe = TRUSTED.replace(
            "if gate.get('state') == 'HOLD' or not gate.get('eligible'):",
            "if False:",
            1,
        )
        errors = security.provider_workflow_boundary_errors(unsafe, CONTRACT)
        self.assertIn(
            "provider live certification missing fail-closed fragment \"if gate.get('state') == 'HOLD' or not gate.get('eligible'):\"",
            errors,
        )


if __name__ == "__main__":
    unittest.main()

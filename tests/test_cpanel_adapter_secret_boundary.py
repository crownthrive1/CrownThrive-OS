import unittest
import json
from pathlib import Path

from scripts import validate_security_governance as security


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = security.CPANEL_ADAPTER.read_text(encoding="utf-8")


class CpanelAdapterSecretBoundaryTests(unittest.TestCase):
    def test_repository_adapter_satisfies_public_secret_boundary(self):
        self.assertEqual(security.cpanel_adapter_boundary_errors(ADAPTER), [])

    def test_hard_coded_token_literal_fails_closed(self):
        unsafe = ADAPTER.replace(
            "const token = await runtimeSecret();",
            'const token = "unit-test-literal-must-not-ship";',
            1,
        )
        errors = security.cpanel_adapter_boundary_errors(unsafe)
        self.assertTrue(
            any("hard-codes a secret-like literal" in error for error in errors),
            errors,
        )

    def test_removing_locator_binding_fails_closed(self):
        unsafe = ADAPTER.replace(
            'const CPANEL_SECRET_NAME_ENV = "CPANEL_RUNTIME_SECRET_NAME";\n',
            "",
            1,
        )
        errors = security.cpanel_adapter_boundary_errors(unsafe)
        self.assertTrue(
            any("CPANEL_RUNTIME_SECRET_NAME" in error for error in errors),
            errors,
        )

    def test_raw_provider_error_reflection_fails_closed(self):
        unsafe = ADAPTER.replace(
            "provider_error_count: providerFieldCount(writeJson.errors),",
            "provider_errors: writeJson.errors,",
            1,
        )
        self.assertIn(
            "cPanel adapter must not return raw provider errors or messages",
            security.cpanel_adapter_boundary_errors(unsafe),
        )

    def test_provider_traffic_logging_fails_closed(self):
        unsafe = ADAPTER.replace(
            "const writeText = await writeResponse.text();",
            "const writeText = await writeResponse.text();\n    console.log(writeText);",
            1,
        )
        self.assertIn(
            "cPanel adapter must not log credential-bearing provider traffic",
            security.cpanel_adapter_boundary_errors(unsafe),
        )

    def test_terminal_error_capture_fails_closed(self):
        unsafe = ADAPTER.replace(
            "  } catch {\n    return jsonResponse({ ok: false, error: \"internal_adapter_error\" }, 500);",
            "  } catch (error) {\n    return jsonResponse({ ok: false, error: \"internal_adapter_error\" }, 500);",
            1,
        )
        errors = security.cpanel_adapter_boundary_errors(unsafe)
        self.assertIn(
            "cPanel adapter terminal error boundary must not capture throwable details",
            errors,
        )

    def test_public_incident_record_retains_major_release_hold(self):
        record = json.loads(security.CPANEL_EXPOSURE_RESPONSE.read_text(encoding="utf-8"))
        self.assertEqual(security.cpanel_exposure_response_errors(record), [])

    def test_public_incident_record_cannot_publish_sensitive_fields(self):
        record = json.loads(security.CPANEL_EXPOSURE_RESPONSE.read_text(encoding="utf-8"))
        record["incident"]["locator_fingerprint"] = "unit-test-forbidden-field"
        errors = security.cpanel_exposure_response_errors(record)
        self.assertTrue(any("forbidden sensitive key" in error for error in errors), errors)

    def test_public_incident_record_cannot_promote_release(self):
        record = json.loads(security.CPANEL_EXPOSURE_RESPONSE.read_text(encoding="utf-8"))
        record["release_predicate"]["current_state"] = "PASS"
        errors = security.cpanel_exposure_response_errors(record)
        self.assertIn("cPanel major-release predicate must remain HOLD", errors)


if __name__ == "__main__":
    unittest.main()

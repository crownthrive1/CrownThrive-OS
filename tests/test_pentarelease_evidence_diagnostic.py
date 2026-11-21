import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.pentarelease.evidence_failure_diagnostic import diagnostic, MAX_BYTES

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/pentarelease-release-intelligence-v3.yml"


class EvidenceDiagnosticTests(unittest.TestCase):
    def check_payload(self, payload, status="409"):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "body"
            path.write_bytes(payload)
            return diagnostic(path, status)

    def test_only_allowlisted_code_stage_and_status_are_exposed(self):
        result = self.check_payload(json.dumps({
            "error": "release_evidence_projection_rejected",
            "diagnostic_stage": "resolve_release_evidence_bundle",
            "diagnostic_code": "database_unique_conflict",
            "detail": "PRIVATE_DB_IDENTIFIER_AND_TENANT_VALUE",
            "user": "PRIVATE_USER",
        }).encode())
        self.assertEqual(result, {
            "status": "HOLD",
            "http_status": "409",
            "error_code": "release_evidence_projection_rejected",
            "diagnostic_stage": "resolve_release_evidence_bundle",
            "diagnostic_code": "database_unique_conflict",
        })
        self.assertNotIn("PRIVATE_", json.dumps(result))

    def test_legacy_provider_detail_is_classified_without_echo(self):
        cases = {
            'duplicate key value violates unique constraint "private_tenant_release_key" DETAIL: Key (tenant_id)=(PRIVATE_TENANT)': "database_unique_conflict",
            'insert or update violates foreign key constraint "private_fk"': "database_foreign_key_conflict",
            'permission denied for schema private_tenant': "database_permission_denied",
            'function penta_os20.private_resolver() does not exist': "database_contract_missing",
            'canceling statement due to statement timeout for tenant PRIVATE_TENANT': "database_timeout_or_lock",
            'could not serialize access due to concurrent update': "database_serialization_conflict",
            'invalid input syntax for type bigint: "PRIVATE_VALUE"': "database_value_rejected",
            "P0001: resolver raised an exception for PRIVATE_TENANT": "database_application_exception",
            "unexpected private provider failure": "unclassified_provider_error",
        }
        for detail, expected in cases.items():
            with self.subTest(expected=expected):
                result = self.check_payload(json.dumps({
                    "error": "release_evidence_projection_rejected",
                    "detail": detail,
                }).encode())
                self.assertEqual(result["diagnostic_code"], expected)
                self.assertEqual(result["diagnostic_stage"], "unavailable")
                self.assertNotIn("PRIVATE_", json.dumps(result))
                self.assertNotIn(detail, json.dumps(result))

    def test_database_application_exception_code_is_allowlisted_without_echo(self):
        result = self.check_payload(json.dumps({
            "error": "release_evidence_projection_rejected",
            "diagnostic_stage": "resolve_release_evidence_bundle",
            "diagnostic_code": "database_application_exception",
            "detail": "PRIVATE_TENANT_AND_PROVIDER_DETAIL",
        }).encode())
        self.assertEqual(result["diagnostic_code"], "database_application_exception")
        self.assertEqual(result["diagnostic_stage"], "resolve_release_evidence_bundle")
        self.assertNotIn("PRIVATE_", json.dumps(result))

    def test_untrusted_diagnostic_values_are_not_echoed(self):
        result = self.check_payload(json.dumps({
            "error": "release_evidence_projection_rejected",
            "diagnostic_stage": "PRIVATE_STAGE",
            "diagnostic_code": "PRIVATE_CODE",
            "detail": "PRIVATE_SECRET",
        }).encode())
        self.assertEqual(result["diagnostic_stage"], "unavailable")
        self.assertEqual(result["diagnostic_code"], "unclassified_provider_error")
        self.assertNotIn("PRIVATE_", json.dumps(result))

    def test_untrusted_malformed_and_oversized_inputs_are_not_echoed(self):
        for payload in (b'{"error":"PRIVATE_SECRET"}', b'{"error":[]}',
                        b'PRIVATE_SECRET', b'[]', b'null', b'x' * (MAX_BYTES + 1)):
            with self.subTest(payload=payload[:20]):
                self.assertEqual(self.check_payload(payload, "409\nPRIVATE_SECRET"), {
                    "status": "HOLD",
                    "http_status": "unavailable",
                    "error_code": "unavailable",
                    "diagnostic_stage": "unavailable",
                    "diagnostic_code": "unavailable",
                })

    def test_missing_file_is_safe(self):
        result = diagnostic("/nonexistent-evidence-fixture", "000")
        self.assertEqual(result["error_code"], "unavailable")
        self.assertEqual(result["diagnostic_stage"], "unavailable")
        self.assertEqual(result["diagnostic_code"], "unavailable")

    def test_workflow_preserves_curl_failure_and_does_not_log_body(self):
        text = WORKFLOW.read_text()
        block = text.split('          CURL_EXIT=0\n', 1)[1].split('          test "$(jq', 1)[0]
        self.assertNotIn('jq .', block)
        for exit_code in (22, 6):
            with self.subTest(exit_code=exit_code), tempfile.TemporaryDirectory() as directory:
                path = Path(directory)
                body = path / "body.json"
                body.write_text('{"error":"release_evidence_projection_rejected","detail":"PRIVATE_SECRET"}')
                script = 'set -euo pipefail\nCURL_EXIT=0\ncurl() { printf 409; return ' + str(exit_code) + '; }\n'
                script += block.replace('/tmp/pentarelease-source/PENTARELEASE_RUNTIME_EVIDENCE.json', str(body))
                script += '\necho UNREACHABLE_PUBLICATION\n'
                result = subprocess.run(['bash', '-c', script], cwd=ROOT,
                    env={"PATH": os.environ['PATH'], "OIDC_TOKEN":"PRIVATE_SECRET", "PENTARELEASE_EVIDENCE_ENDPOINT":"https://unused.invalid"},
                    capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, exit_code, result.stderr)
                self.assertNotIn('PRIVATE_SECRET', result.stdout + result.stderr)
                self.assertNotIn('UNREACHABLE_PUBLICATION', result.stdout)
                self.assertEqual(json.loads(result.stdout)['status'], 'HOLD')


if __name__ == "__main__":
    unittest.main()

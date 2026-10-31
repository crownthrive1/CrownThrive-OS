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

    def test_only_allowlisted_code_and_status_are_exposed(self):
        result = self.check_payload(json.dumps({
            "error": "release_evidence_projection_rejected",
            "detail": "PRIVATE_DB_IDENTIFIER_AND_TOKEN", "user": "PRIVATE_USER",
        }).encode())
        self.assertEqual(result, {"status": "HOLD", "http_status": "409", "error_code": "release_evidence_projection_rejected"})

    def test_untrusted_malformed_and_oversized_inputs_are_not_echoed(self):
        for payload in (b'{"error":"PRIVATE_SECRET"}', b'{"error":[]}',
                        b'PRIVATE_SECRET', b'[]', b'null', b'x' * (MAX_BYTES + 1)):
            with self.subTest(payload=payload[:20]):
                self.assertEqual(self.check_payload(payload, "409\nPRIVATE_SECRET"), {
                    "status": "HOLD", "http_status": "unavailable", "error_code": "unavailable",
                })

    def test_missing_file_is_safe(self):
        self.assertEqual(diagnostic("/nonexistent-evidence-fixture", "000")["error_code"], "unavailable")

    def test_workflow_preserves_curl_failure_and_does_not_log_body(self):
        text = WORKFLOW.read_text()
        block = text.split('          CURL_EXIT=0\n', 1)[1].split('          test "$(jq', 1)[0]
        self.assertNotIn('jq .', block)
        # Execute the actual workflow failure handler with an inert curl stub.
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

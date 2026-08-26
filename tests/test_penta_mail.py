import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("penta_mail", ROOT / "runtime" / "penta_mail.py")
pm = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = pm
SPEC.loader.exec_module(pm)


class FakeAdapter:
    provider_id = "resend"
    sends = 0

    def domain_read(self):
        return {"schema": pm.EVIDENCE_SCHEMA, "provider": "resend", "operation": "domain_read", "result": "PASS", "readback": True, "http_status": 200}

    def send(self, envelope, authorization):
        envelope.validate()
        authorization.validate_for(envelope)
        type(self).sends += 1
        return {"provider": "resend", "provider_message_id": "msg-123", "http_status": 200, "accepted": True, "accepted_at": pm.now()}

    def readback(self, message_id):
        return {
            "schema": pm.EVIDENCE_SCHEMA,
            "provider": "resend",
            "operation": "email_send",
            "result": "PASS",
            "readback": True,
            "http_status": 200,
            "provider_message_id": message_id,
            "provider_event": "delivered",
            "normalized_state": "delivered",
            "observed_at": pm.now(),
        }


class PentaMailTests(unittest.TestCase):
    def envelope(self):
        return pm.build_envelope(
            origin_penta="penta.status",
            purpose="owner_execution_report",
            classification="internal",
            recipient="owner@example.com",
            sender_identity="CrownThrive PentaMail <system@example.com>",
            subject="Penta execution report",
            body_text="All evidence-backed checks are included.",
            correlation_id="run-20260826-001",
            authority_ref="founder-directive-20260826-pentamail-test",
            authority_class="D1",
            priority="high",
        )

    def auth(self):
        return pm.AuthorizationContext(
            authorized=True,
            authorized_by="founder",
            authority_ref="founder-directive-20260826-pentamail-test",
            authority_class="D1",
        )

    def test_envelope_validates(self):
        self.envelope().validate()

    def test_header_injection_fails_closed(self):
        with self.assertRaises(pm.PentaMailError):
            pm.build_envelope(
                origin_penta="penta.status", purpose="report", classification="internal",
                recipient="owner@example.com\nBcc: attacker@example.com", sender_identity="system@example.com",
                subject="report", body_text="safe", correlation_id="c1", authority_ref="a1", authority_class="D1",
            )

    def test_d0_cannot_send(self):
        with self.assertRaises(pm.PentaMailError):
            pm.build_envelope(
                origin_penta="penta.status", purpose="report", classification="internal",
                recipient="owner@example.com", sender_identity="system@example.com", subject="report", body_text="safe",
                correlation_id="c1", authority_ref="a1", authority_class="D0",
            )

    def test_authority_ref_must_match(self):
        with self.assertRaises(pm.PentaMailError):
            pm.AuthorizationContext(True, "founder", "other-ref", "D1").validate_for(self.envelope())

    def test_secret_like_body_fails_closed(self):
        with self.assertRaises(pm.PentaMailError):
            pm.build_envelope(
                origin_penta="penta.status", purpose="report", classification="internal",
                recipient="owner@example.com", sender_identity="system@example.com", subject="report",
                body_text="API_KEY=abcdefghijk12345", correlation_id="c1", authority_ref="a1", authority_class="D1",
            )

    def test_certification_send_and_readback(self):
        FakeAdapter.sends = 0
        with tempfile.TemporaryDirectory() as td:
            receipt = pm.certification_send(
                envelope=self.envelope(), authorization=self.auth(), state_dir=Path(td), adapter=FakeAdapter(),
            )
            self.assertEqual(receipt["lifecycle_state"], "delivered")
            self.assertEqual(receipt["provider_message_id"], "msg-123")
            self.assertEqual(FakeAdapter.sends, 1)
            self.assertTrue(all(e["readback"] for e in receipt["live_evidence"]))

    def test_idempotent_replay_does_not_resend(self):
        FakeAdapter.sends = 0
        with tempfile.TemporaryDirectory() as td:
            state = Path(td)
            first = pm.certification_send(envelope=self.envelope(), authorization=self.auth(), state_dir=state, adapter=FakeAdapter())
            second = pm.certification_send(envelope=self.envelope(), authorization=self.auth(), state_dir=state, adapter=FakeAdapter())
            self.assertEqual(first["provider_message_id"], second["provider_message_id"])
            self.assertFalse(first["idempotent_replay"])
            self.assertTrue(second["idempotent_replay"])
            self.assertEqual(FakeAdapter.sends, 1)


if __name__ == "__main__":
    unittest.main()

import base64
import json
import sys
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

import penta_mail as pm
from penta_mail_mailgun import MailgunAdapter


class FakeResponse:
    def __init__(self, status, payload):
        self.status = status
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, _limit=-1):
        return self.payload


class RecordingOpener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, timeout=None):
        self.requests.append((request, timeout))
        if not self.responses:
            raise AssertionError("unexpected HTTP request")
        status, payload = self.responses.pop(0)
        return FakeResponse(status, payload)


class MailgunAdapterTests(unittest.TestCase):
    def adapter(self, responses, **kwargs):
        opener = RecordingOpener(responses)
        adapter = MailgunAdapter(
            api_key="key-test-not-real",
            domain="relay.crownthrive.com",
            opener=opener,
            sleeper=lambda _seconds: None,
            poll_interval=0,
            **kwargs,
        )
        return adapter, opener

    @staticmethod
    def envelope():
        return pm.build_envelope(
            origin_penta="penta.status",
            purpose="mailgun_transport_certification",
            classification="internal",
            recipient="jones.usmc.kj@gmail.com",
            sender_identity="CrownThrive PentaMail <postmaster@relay.crownthrive.com>",
            subject="Mailgun certification test",
            body_text="Governed transport validation only.",
            correlation_id="mailgun-test-1",
            authority_ref="test-mailgun-d1",
            authority_class="D1",
            idempotency_key="mailgun-test-idempotency",
        )

    @staticmethod
    def authorization():
        return pm.AuthorizationContext(
            authorized=True,
            authorized_by="unit-test",
            authority_ref="test-mailgun-d1",
            authority_class="D1",
        )

    def test_domain_read_exact_match_and_basic_api_auth(self):
        adapter, opener = self.adapter([(200, {"domain": {"name": "relay.crownthrive.com"}})])
        evidence = adapter.domain_read()
        self.assertEqual(evidence["result"], "PASS")
        request, _timeout = opener.requests[0]
        self.assertEqual(request.full_url, "https://api.mailgun.net/v4/domains/relay.crownthrive.com")
        expected = "Basic " + base64.b64encode(b"api:key-test-not-real").decode()
        self.assertEqual(request.get_header("Authorization"), expected)

    def test_send_uses_domain_endpoint_and_returns_exact_id(self):
        message_id = "<20260826.mailgun.test@relay.crownthrive.com>"
        adapter, opener = self.adapter([(200, {"id": message_id, "message": "Queued. Thank you."})])
        receipt = adapter.send(self.envelope(), self.authorization())
        self.assertEqual(receipt["provider_message_id"], message_id)
        request, _timeout = opener.requests[0]
        self.assertEqual(request.full_url, "https://api.mailgun.net/v3/relay.crownthrive.com/messages")
        self.assertIn(b'name="subject"', request.data)
        self.assertIn(b"Mailgun certification test", request.data)
        self.assertNotIn(b"key-test-not-real", request.data)

    def test_event_readback_requires_exact_same_message_id(self):
        wanted = "<wanted@relay.crownthrive.com>"
        adapter, opener = self.adapter(
            [(200, {"items": [{"event": "delivered", "message": {"headers": {"message-id": "<other@relay.crownthrive.com>"}}}]})],
            poll_attempts=1,
        )
        evidence = adapter.readback(wanted)
        self.assertEqual(evidence["result"], "FAIL")
        self.assertFalse(evidence["readback"])
        self.assertIn("message-id=%3Cwanted%40relay.crownthrive.com%3E", opener.requests[0][0].full_url)

    def test_accepted_is_write_verified_transport_but_not_server_delivery(self):
        wanted = "<accepted@relay.crownthrive.com>"
        adapter, _ = self.adapter(
            [(200, {"items": [{"event": "accepted", "message": {"headers": {"message-id": wanted}}}]})],
            poll_attempts=1,
        )
        evidence = adapter.readback(wanted)
        self.assertEqual(evidence["result"], "PASS")
        self.assertTrue(evidence["readback"])
        self.assertTrue(evidence["provider_accepted"])
        self.assertFalse(evidence["recipient_server_accepted"])
        self.assertEqual(evidence["normalized_state"], "accepted")

    def test_delivered_records_recipient_server_acceptance(self):
        wanted = "<delivered@relay.crownthrive.com>"
        adapter, _ = self.adapter(
            [(200, {"items": [{"event": "delivered", "message": {"headers": {"message-id": wanted}}}]})],
            poll_attempts=1,
        )
        evidence = adapter.readback(wanted)
        self.assertEqual(evidence["result"], "PASS")
        self.assertTrue(evidence["recipient_server_accepted"])
        self.assertEqual(evidence["normalized_state"], "delivered")

    def test_failed_event_never_certifies_email_send(self):
        wanted = "<failed@relay.crownthrive.com>"
        adapter, _ = self.adapter(
            [(200, {"items": [{"event": "failed", "message": {"headers": {"message-id": wanted}}}]})],
            poll_attempts=1,
        )
        evidence = adapter.readback(wanted)
        self.assertEqual(evidence["result"], "FAIL")
        self.assertTrue(evidence["readback"])
        self.assertEqual(evidence["normalized_state"], "failed")

    def test_existing_pentamail_certification_send_works_with_mailgun(self):
        message_id = "<governed@relay.crownthrive.com>"
        adapter, _ = self.adapter(
            [
                (200, {"domain": {"name": "relay.crownthrive.com"}}),
                (200, {"id": message_id, "message": "Queued. Thank you."}),
                (200, {"items": [{"event": "accepted", "message": {"headers": {"message-id": message_id}}}]}),
            ],
            poll_attempts=1,
        )
        with tempfile.TemporaryDirectory() as td:
            receipt = pm.certification_send(
                envelope=self.envelope(),
                authorization=self.authorization(),
                state_dir=Path(td),
                adapter=adapter,
            )
        self.assertEqual(receipt["provider"], "mailgun")
        self.assertEqual(receipt["provider_message_id"], message_id)
        self.assertEqual(receipt["lifecycle_state"], "accepted")
        self.assertTrue(all(item["readback"] for item in receipt["live_evidence"]))
        serialized = json.dumps(receipt)
        self.assertNotIn("key-test-not-real", serialized)

    def test_base_url_is_fail_closed_to_mailgun_origins(self):
        with self.assertRaises(pm.PentaMailError):
            MailgunAdapter(api_key="key-test-not-real", domain="relay.crownthrive.com", base_url="https://evil.example")


if __name__ == "__main__":
    unittest.main()

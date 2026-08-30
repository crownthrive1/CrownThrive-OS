import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("penta_mail", ROOT / "runtime" / "penta_mail.py")
pm = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = pm
SPEC.loader.exec_module(pm)


class FakeHttpResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, _limit):
        return json.dumps(self.payload).encode("utf-8")


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

    def readback(self, message_id, envelope):
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
            "body_binding_verified": True,
            "provider_binding_channel": "resend_tags",
            "provider_binding_tags_returned": True,
            "correlation_binding_verified": True,
            "idempotency_binding_verified": True,
            "body_hash_binding_verified": True,
            "provider_returned_headers_exposed": False,
            "provider_returned_headers_consistent": True,
            "custom_header_readback_state": "NOT_EXPOSED_BY_RESEND_RETRIEVE_API",
            "exact_content_binding_verified": True,
            "observed_at": pm.now(),
        }


class MessageIdOnlyAdapter(FakeAdapter):
    def readback(self, message_id, envelope):
        evidence = super().readback(message_id, envelope)
        for field in (
            "body_binding_verified",
            "correlation_binding_verified",
            "idempotency_binding_verified",
            "body_hash_binding_verified",
            "exact_content_binding_verified",
        ):
            evidence.pop(field, None)
        return evidence


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
            self.assertEqual(receipt["verification_binding"]["correlation_id"], self.envelope().correlation_id)
            self.assertRegex(receipt["verification_binding"]["recipient_sha256"], r"^[a-f0-9]{64}$")
            self.assertEqual(
                receipt["verification_binding"]["body_sha256"],
                pm.stable_hash(self.envelope().body_text),
            )
            self.assertTrue(receipt["verification_binding"]["provider_tag_binding_verified"])
            self.assertEqual(
                receipt["verification_binding"]["custom_header_readback_state"],
                "NOT_EXPOSED_BY_RESEND_RETRIEVE_API",
            )
            report = pm.owner_report(receipt)
            self.assertIn("Provider body binding: PASS", report)
            self.assertIn("Provider correlation-tag binding: PASS", report)
            self.assertIn("Exact provider readback: PASS", report)

    def test_resend_send_uses_provider_idempotency_header_and_binding_tags(self):
        envelope = self.envelope()
        adapter = pm.ResendAdapter(api_key="test-only-key")
        with mock.patch.object(
            pm,
            "open_no_redirect",
            return_value=FakeHttpResponse({"id": "msg-123"}, status=201),
        ) as urlopen:
            result = adapter.send(envelope, self.auth())
        self.assertEqual(result["provider_message_id"], "msg-123")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header("Idempotency-key"), envelope.idempotency_key)
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["headers"][pm.IDEMPOTENCY_HEADER], envelope.idempotency_key)
        self.assertEqual(
            {tag["name"]: tag["value"] for tag in payload["tags"]},
            {
                pm.CORRELATION_TAG: pm.stable_hash(envelope.correlation_id),
                pm.IDEMPOTENCY_TAG: pm.stable_hash(envelope.idempotency_key),
                pm.BODY_TAG: pm.stable_hash(envelope.body_text),
            },
        )

    def test_resend_message_ids_are_strict_and_readback_path_is_encoded(self):
        envelope = self.envelope()
        adapter = pm.ResendAdapter(api_key="test-only-key")
        with mock.patch.object(
            pm,
            "open_no_redirect",
            return_value=FakeHttpResponse({"id": "../capture"}, status=201),
        ):
            with self.assertRaisesRegex(pm.PentaMailError, "valid stable message id"):
                adapter.send(envelope, self.auth())

        tags = [
            {"name": pm.CORRELATION_TAG, "value": pm.stable_hash(envelope.correlation_id)},
            {"name": pm.IDEMPOTENCY_TAG, "value": pm.stable_hash(envelope.idempotency_key)},
            {"name": pm.BODY_TAG, "value": pm.stable_hash(envelope.body_text)},
        ]
        payload = {
            "id": "msg:123",
            "last_event": "delivered",
            "to": [envelope.recipient],
            "from": envelope.sender_identity,
            "subject": envelope.subject,
            "text": envelope.body_text,
            "tags": tags,
        }
        with mock.patch.object(adapter, "_request", return_value=(200, payload)) as request:
            evidence = adapter.readback("msg:123", envelope)
        self.assertEqual(evidence["result"], "PASS")
        self.assertEqual(request.call_args.args[1], "/emails/msg%3A123")

        with mock.patch.object(adapter, "_request") as request:
            with self.assertRaisesRegex(pm.PentaMailError, "valid stable message id"):
                adapter.readback("../capture", envelope)
        request.assert_not_called()

    def test_resend_readback_binds_body_and_provider_returned_tags(self):
        envelope = self.envelope()
        payload = {
            "id": "msg-123",
            "last_event": "delivered",
            "to": [envelope.recipient],
            "from": envelope.sender_identity,
            "subject": envelope.subject,
            "text": envelope.body_text,
            "tags": [
                {"name": pm.CORRELATION_TAG, "value": pm.stable_hash(envelope.correlation_id)},
                {"name": pm.IDEMPOTENCY_TAG, "value": pm.stable_hash(envelope.idempotency_key)},
                {"name": pm.BODY_TAG, "value": pm.stable_hash(envelope.body_text)},
            ],
        }
        adapter = pm.ResendAdapter(api_key="test-only-key")
        with mock.patch.object(adapter, "_request", return_value=(200, payload)):
            evidence = adapter.readback("msg-123", envelope)
        self.assertEqual(evidence["result"], "PASS")
        self.assertTrue(evidence["body_binding_verified"])
        self.assertTrue(evidence["correlation_binding_verified"])
        self.assertTrue(evidence["idempotency_binding_verified"])
        self.assertEqual(
            evidence["custom_header_readback_state"],
            "NOT_EXPOSED_BY_RESEND_RETRIEVE_API",
        )

    def test_resend_readback_rejects_substituted_body_wrong_tags_or_wrong_returned_headers(self):
        envelope = self.envelope()
        correct_tags = [
            {"name": pm.CORRELATION_TAG, "value": pm.stable_hash(envelope.correlation_id)},
            {"name": pm.IDEMPOTENCY_TAG, "value": pm.stable_hash(envelope.idempotency_key)},
            {"name": pm.BODY_TAG, "value": pm.stable_hash(envelope.body_text)},
        ]
        base = {
            "id": "msg-123",
            "last_event": "delivered",
            "to": [envelope.recipient],
            "from": envelope.sender_identity,
            "subject": envelope.subject,
            "text": envelope.body_text,
            "tags": correct_tags,
        }
        cases = {
            "substituted-body": {**base, "text": "Substituted report."},
            "wrong-correlation-tag": {
                **base,
                "tags": [
                    {"name": pm.CORRELATION_TAG, "value": "0" * 64},
                    *correct_tags[1:],
                ],
            },
            "missing-tags": {key: value for key, value in base.items() if key != "tags"},
            "wrong-returned-headers": {
                **base,
                "headers": {
                    pm.CORRELATION_HEADER: "wrong-correlation",
                    pm.IDEMPOTENCY_HEADER: "wrong-idempotency",
                },
            },
        }
        adapter = pm.ResendAdapter(api_key="test-only-key")
        for label, payload in cases.items():
            with self.subTest(label=label), mock.patch.object(
                adapter, "_request", return_value=(200, payload)
            ):
                evidence = adapter.readback("msg-123", envelope)
            self.assertEqual(evidence["result"], "FAIL")
            self.assertFalse(evidence["readback"])

    def test_resend_http_error_does_not_echo_provider_response_content(self):
        leaked_values = (
            "owner-private@example.com",
            "sender-private@example.com",
            "confidential report body",
        )
        provider_body = json.dumps(
            {"to": leaked_values[0], "from": leaked_values[1], "message": leaked_values[2]}
        ).encode("utf-8")
        error = urllib.error.HTTPError(
            "https://api.resend.com/emails",
            422,
            "untrusted reason with confidential report body",
            {},
            io.BytesIO(provider_body),
        )
        adapter = pm.ResendAdapter(api_key="test-only-key")
        with mock.patch.object(pm, "open_no_redirect", side_effect=error):
            with self.assertRaises(pm.PentaMailError) as raised:
                adapter._request("POST", "/emails", {"text": leaked_values[2]})
        message = str(raised.exception)
        self.assertEqual(message, f"resend HTTP 422: {pm.HTTPStatus(422).phrase}")
        for leaked in leaked_values:
            self.assertNotIn(leaked, message)

    def test_resend_redirect_is_rejected_without_following_location(self):
        handler = pm.NoRedirectHandler()
        request = pm.urllib.request.Request(
            "https://api.resend.com/emails",
            headers={"Authorization": "Bearer test-only-key"},
        )
        redirected = handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {"Location": "https://attacker.invalid/capture"},
            "https://attacker.invalid/capture",
        )
        self.assertIsNone(redirected)

        error = urllib.error.HTTPError(
            request.full_url,
            302,
            "Found",
            {"Location": "https://attacker.invalid/capture"},
            io.BytesIO(b"redirect"),
        )
        adapter = pm.ResendAdapter(api_key="test-only-key")
        with mock.patch.object(pm, "open_no_redirect", side_effect=error) as opener:
            with self.assertRaisesRegex(pm.PentaMailError, r"resend HTTP 302: Found"):
                adapter._request("GET", "/domains")
        self.assertEqual(opener.call_count, 1)

    def test_live_cli_send_is_not_exposed_without_authority_receipt_verifier(self):
        argv = [
            "penta_mail.py",
            "live-certify-send",
            "--recipient",
            "owner@example.com",
        ]
        with mock.patch.object(sys, "argv", argv), mock.patch.object(
            pm, "certification_send"
        ) as certification_send, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                pm._cli()
        self.assertEqual(raised.exception.code, 2)
        certification_send.assert_not_called()

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

    def test_idempotent_replay_rejects_a_different_envelope(self):
        FakeAdapter.sends = 0
        original = self.envelope()
        changed = pm.dataclasses.replace(
            original,
            body_text="A substituted report must not inherit the old receipt.",
            requested_at=pm.now(),
        )
        with tempfile.TemporaryDirectory() as td:
            state = Path(td)
            pm.certification_send(
                envelope=original,
                authorization=self.auth(),
                state_dir=state,
                adapter=FakeAdapter(),
            )
            with self.assertRaisesRegex(
                pm.PentaMailError,
                "prior receipt is bound to a different envelope",
            ):
                pm.certification_send(
                    envelope=changed,
                    authorization=self.auth(),
                    state_dir=state,
                    adapter=FakeAdapter(),
                )
        self.assertEqual(FakeAdapter.sends, 1)

    def test_message_id_only_readback_cannot_generate_exact_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(
                pm.PentaMailError, "provider content/tag binding failed"
            ):
                pm.certification_send(
                    envelope=self.envelope(),
                    authorization=self.auth(),
                    state_dir=Path(td),
                    adapter=MessageIdOnlyAdapter(),
                )


if __name__ == "__main__":
    unittest.main()

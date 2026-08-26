import hashlib
import hmac
import importlib.util
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "penta_mailgun_security", ROOT / "runtime" / "penta_mailgun_security.py"
)
mg = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mg
SPEC.loader.exec_module(mg)


class MailgunWebhookSecurityTests(unittest.TestCase):
    KEY = "unit-test-mailgun-signing-key-2026"
    TOKEN = "e0b5477167110d68991efc6b9f89f0a11066af27834600e123"
    NOW = 1_770_920_900

    def signature(self, timestamp, token=None):
        token = token or self.TOKEN
        return hmac.new(
            self.KEY.encode(),
            f"{timestamp}{token}".encode(),
            hashlib.sha256,
        ).hexdigest()

    def payload(self, timestamp=None):
        timestamp = timestamp or self.NOW
        return {
            "token": self.TOKEN,
            "timestamp": str(timestamp),
            "signature": self.signature(timestamp),
        }

    def test_exact_timestamp_token_hmac_contract_passes(self):
        result = mg.verify_mailgun_webhook(
            self.payload(),
            signing_key=self.KEY,
            received_at=self.NOW,
            replay_cache=mg.TokenReplayCache(),
        )
        self.assertTrue(result["verified"])
        self.assertEqual(result["provider"], "mailgun")
        self.assertEqual(result["operation"], "webhook_verify")
        self.assertEqual(result["signature_source"], "signature")
        self.assertNotIn(self.TOKEN, str(result))
        self.assertNotIn(self.KEY, str(result))

    def test_wrong_signature_fails_closed(self):
        payload = self.payload()
        payload["signature"] = "0" * 64
        with self.assertRaises(mg.MailgunWebhookError):
            mg.verify_mailgun_webhook(payload, signing_key=self.KEY, received_at=self.NOW)

    def test_parent_signature_supported_for_subaccount_events(self):
        payload = self.payload()
        payload["parent-signature"] = payload["signature"]
        payload["signature"] = "0" * 64
        result = mg.verify_mailgun_webhook(payload, signing_key=self.KEY, received_at=self.NOW)
        self.assertEqual(result["signature_source"], "parent-signature")

    def test_replay_token_is_rejected(self):
        cache = mg.TokenReplayCache()
        payload = self.payload()
        mg.verify_mailgun_webhook(
            payload, signing_key=self.KEY, received_at=self.NOW, replay_cache=cache
        )
        with self.assertRaisesRegex(mg.MailgunWebhookError, "replayed"):
            mg.verify_mailgun_webhook(
                payload, signing_key=self.KEY, received_at=self.NOW + 1, replay_cache=cache
            )

    def test_stale_timestamp_is_rejected(self):
        timestamp = self.NOW - mg.DEFAULT_MAX_AGE_SECONDS - 1
        with self.assertRaisesRegex(mg.MailgunWebhookError, "stale"):
            mg.verify_mailgun_webhook(
                self.payload(timestamp), signing_key=self.KEY, received_at=self.NOW
            )

    def test_timestamp_window_can_be_disabled(self):
        timestamp = self.NOW - (7 * mg.DEFAULT_MAX_AGE_SECONDS)
        result = mg.verify_mailgun_webhook(
            self.payload(timestamp),
            signing_key=self.KEY,
            received_at=self.NOW,
            max_age_seconds=None,
        )
        self.assertTrue(result["verified"])
        self.assertFalse(result["freshness_checked"])

    def test_future_timestamp_is_rejected(self):
        timestamp = self.NOW + mg.DEFAULT_FUTURE_SKEW_SECONDS + 1
        with self.assertRaisesRegex(mg.MailgunWebhookError, "future"):
            mg.verify_mailgun_webhook(
                self.payload(timestamp), signing_key=self.KEY, received_at=self.NOW
            )

    def test_missing_key_fails_closed(self):
        old = os.environ.pop(mg.ENV_ALIAS, None)
        try:
            with self.assertRaisesRegex(mg.MailgunWebhookError, "not bound"):
                mg.MailgunWebhookVerifier()
        finally:
            if old is not None:
                os.environ[mg.ENV_ALIAS] = old

    def test_environment_alias_is_supported(self):
        old = os.environ.get(mg.ENV_ALIAS)
        os.environ[mg.ENV_ALIAS] = self.KEY
        try:
            result = mg.verify_mailgun_webhook(self.payload(), received_at=self.NOW)
            self.assertTrue(result["verified"])
        finally:
            if old is None:
                os.environ.pop(mg.ENV_ALIAS, None)
            else:
                os.environ[mg.ENV_ALIAS] = old

    def test_signature_encoding_is_strict(self):
        payload = self.payload()
        payload["signature"] = "not-hex"
        with self.assertRaisesRegex(mg.MailgunWebhookError, "encoding"):
            mg.verify_mailgun_webhook(payload, signing_key=self.KEY, received_at=self.NOW)


if __name__ == "__main__":
    unittest.main()

import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "data/penta/stripe-institutional-webhooks.v1.json"
INVENTORY_SQL = ROOT / "supabase/migrations/20260829021800_stripe_webhook_safe_provider_inventory_v1.sql"
FABRIC_SQL = ROOT / "supabase/migrations/20260829021900_stripe_institutional_webhook_fabric_v1.sql"


class StripeInstitutionalWebhookContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        cls.inventory_sql = INVENTORY_SQL.read_text(encoding="utf-8")
        cls.fabric_sql = FABRIC_SQL.read_text(encoding="utf-8")

    def test_exact_two_production_lanes(self):
        lanes = {lane["lane_key"]: lane for lane in self.contract["lanes"]}
        self.assertEqual(set(lanes), {"thrivetickets", "sermon-toolkit"})
        self.assertTrue(all(lane["state"] == "production" for lane in lanes.values()))

    def test_signature_and_dedupe_are_mandatory(self):
        receiver = self.contract["receiver"]
        self.assertTrue(receiver["stripe_signature_required"])
        self.assertEqual(receiver["signature_tolerance_seconds"], 300)
        self.assertEqual(receiver["dedupe_key"], ["lane_key", "stripe_event_id"])
        self.assertFalse(receiver["raw_event_persisted"])
        self.assertFalse(receiver["raw_event_returned"])
        self.assertIn("unique(lane_key,stripe_event_id)", self.fabric_sql)
        self.assertIn("signature_verification_required boolean not null default true", self.fabric_sql)

    def test_canary_does_not_manufacture_payment_evidence(self):
        evidence = self.contract["evidence"]
        self.assertTrue(evidence["canary_is_not_real_payment_evidence"])
        self.assertTrue(evidence["real_provider_event_receipt_required_for_delivery_certification"])
        self.assertIn("crownthrive.webhook.canary", self.fabric_sql)
        self.assertIn("canary_noop", self.fabric_sql)

    def test_authority_is_fail_closed(self):
        authority = self.contract["authority"]
        self.assertFalse(authority["money_movement"])
        self.assertFalse(authority["entitlement_grant_from_unprocessed_receipt"])
        self.assertFalse(authority["d3_bypass"])
        self.assertFalse(authority["provider_secret_projection"])
        self.assertTrue(authority["fulfillment_requires_registered_downstream_handler"])

    def test_provider_inventory_never_projects_keys(self):
        self.assertIn("raw_credentials_exposed", self.inventory_sql)
        self.assertIn("key_fingerprint", self.inventory_sql)
        self.assertNotIn("select name,decrypted_secret into", self.inventory_sql.lower())

    def test_resolved_p0s_are_permanent_against_stale_evidence(self):
        permanence = self.contract["permanence"]
        self.assertFalse(permanence["stale_endpoint_evidence_may_reopen_resolved_p0"])
        self.assertTrue(permanence["newer_provider_or_signed_canary_failure_may_open_regression"])
        self.assertIn("register_permanent_repair_v1", self.fabric_sql)


if __name__ == "__main__":
    unittest.main()

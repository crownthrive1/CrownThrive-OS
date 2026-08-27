from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECEIPT_PATH = ROOT / "developers/manifests/pentamailer-mailgun-deployment-receipt.v1.json"
REGISTRY_PATH = ROOT / "docs/versioning/VERSION_REGISTRY.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PentaMailgunDeploymentReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        cls.epoch_sql = (
            ROOT
            / "supabase/migrations/20260827011146_pentamail_receipt_epoch_anchor_hardening.sql"
        ).read_text(encoding="utf-8")
        cls.role_sql = (
            ROOT
            / "supabase/migrations/20260827011347_pentamail_service_role_assertion_hardening.sql"
        ).read_text(encoding="utf-8")
        cls.readback_sql = (
            ROOT
            / "supabase/migrations/20260827011427_pentamail_readback_probe_ordering.sql"
        ).read_text(encoding="utf-8")
        cls.post_receipt_index_sql = (
            ROOT
            / "supabase/migrations/20260827013000_pentamail_receipt_epoch_anchor_fk_index.sql"
        ).read_text(encoding="utf-8")
        cls.workflow = (
            ROOT / ".github/workflows/pentamailer-mailgun-delivery-resilience.yml"
        ).read_text(encoding="utf-8")

    def test_receipt_is_explicit_provider_hold_without_send_or_delivery_claim(self):
        self.assertEqual(
            self.receipt["schema"],
            "ct.pentamailer.mailgun-deployment-receipt.v1",
        )
        readback = self.receipt["live_readback"]
        self.assertEqual(readback["route_state"], "PROVIDER_HOLD")
        self.assertEqual(readback["mailgun_enabled_readback"], "PENDING_AFTER_HOLD_BOUNDARY")
        self.assertEqual(readback["provider_attempt_starts"], 0)
        self.assertEqual(readback["provider_attempt_outcomes"], 0)
        self.assertEqual(readback["global_rate_reservations"], 0)
        self.assertEqual(readback["held_outbox_attempts"], 0)
        claims = "\n".join(self.receipt["claims_boundary"])
        self.assertIn("not authenticated Mailgun evidence", claims)
        self.assertIn("not recipient delivery", claims)
        self.assertNotIn("delivery confirmed", claims.lower())

    def test_deployed_source_receipt_binds_exact_repository_bytes(self):
        deployments = self.receipt["edge_deployments"]
        for deployment_id in (
            "mailgun_relay_control",
            "penta_mail",
            "crownthrive_os_v2_runtime",
        ):
            deployment = deployments[deployment_id]
            source = ROOT / deployment["repository_source"]
            self.assertEqual(sha256(source), deployment["repository_source_sha256"])
        runtime = deployments["crownthrive_os_v2_runtime"]
        self.assertEqual(
            sha256(ROOT / "supabase/functions/crownthrive-os-v2-runtime/deno.json"),
            runtime["import_map_source_sha256"],
        )
        self.assertEqual(
            deployments["mailgun_relay_control"]["live_provider_call_readback"],
            "INTENTIONALLY_ABSENT_DURING_HOLD",
        )

    def test_registry_component_is_unique_and_retains_active_provider_hold(self):
        components = [
            item
            for item in self.registry["components"]
            if item.get("component_id")
            == "ct.pentamailer.mailgun-delivery-resilience"
        ]
        self.assertEqual(len(components), 1)
        component = components[0]
        self.assertEqual(component["version"], "1.0.0")
        self.assertEqual(component["lifecycle_state"], "active_provider_hold")
        self.assertEqual(
            component["evidence_ref"],
            "developers/manifests/pentamailer-mailgun-deployment-receipt.v1.json",
        )
        self.assertIn("no Mailgun enablement or recipient delivery is inferred", component["production_scope"])

    def test_receipt_epoch_is_current_head_anchored_and_append_only(self):
        for fragment in (
            "penta_mail_receipt_epoch_anchor_fk_v1",
            "penta_mail_receipt_epoch_anchor_validation_v1",
            "PENTAMAIL_RECEIPT_EPOCH_ANCHOR_NOT_CURRENT_HEAD",
            "PENTAMAIL_RECEIPT_EPOCH_OBSERVATION_MISMATCH",
            "penta_mail_assert_service_role_v1()",
            "revoke insert, update, delete, truncate",
        ):
            self.assertIn(fragment, self.epoch_sql)

    def test_security_definer_checks_invoker_not_owner(self):
        self.assertIn("session_user not in ('postgres','service_role')", self.role_sql)
        self.assertNotIn("current_user not in", self.role_sql)
        self.assertIn("request.jwt.claim.role", self.role_sql)
        self.assertIn("from public, anon, authenticated", self.role_sql)

    def test_out_of_order_readback_cannot_reopen_provider_route(self):
        for fragment in (
            "last_readback_probe_started_at",
            "PENTAMAIL_INVALID_READBACK_PROBE_START",
            "mail.provider_readback_ignored_out_of_order",
            "penta_mail_record_mailgun_readback_v3",
            "ignored_out_of_order",
            "revoke execute on function public.penta_mail_record_mailgun_readback_v2",
        ):
            self.assertIn(fragment, self.readback_sql)

    def test_receipt_security_readback_retains_privacy_and_mutation_denials(self):
        security = self.receipt["security_readback"]
        self.assertFalse(security["private_recipient_in_public_source"])
        self.assertFalse(security["raw_provider_body_retained"])
        self.assertFalse(security["service_role_direct_provider_control_update"])
        self.assertFalse(security["service_role_direct_trigger_probation_update"])
        self.assertFalse(security["service_role_direct_outbox_update"])
        self.assertFalse(security["service_role_direct_receipt_epoch_insert"])
        self.assertTrue(security["governed_accept_rpc_execute"])
        self.assertTrue(security["ordered_readback_rpc_execute"])

    def test_post_receipt_fk_index_is_gated_but_not_claimed_deployed(self):
        path = "supabase/migrations/20260827013000_pentamail_receipt_epoch_anchor_fk_index.sql"
        self.assertEqual(self.workflow.count(f"- '{path}'"), 2)
        self.assertIn(
            "create index if not exists penta_mail_receipt_epoch_anchor_idx",
            self.post_receipt_index_sql,
        )
        self.assertIn("starts_after_receipt_id", self.post_receipt_index_sql)
        self.assertIn("starts_after_chain_sha256", self.post_receipt_index_sql)
        deployed_names = {
            item["name"] for item in self.receipt["database_migrations"]
        }
        self.assertNotIn("pentamail_receipt_epoch_anchor_fk_index", deployed_names)
        self.assertEqual(self.receipt["live_readback"]["route_state"], "PROVIDER_HOLD")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20260901121000_penta_help_independent_gate_review_nodes_v1.sql"
ROLLBACK = ROOT / "supabase/rollback/20260901121000_penta_help_independent_gate_review_nodes_v1_rollback.sql"


class PentaHelpIndependentGateReviewNodesContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.migration = MIGRATION.read_text(encoding="utf-8")
        cls.rollback = ROLLBACK.read_text(encoding="utf-8")

    def test_review_node_ids_obey_pentas_v2_address_contract(self) -> None:
        node_ids = re.findall(r"'((?:ct[.]penta[.])[a-z0-9._-]+)'", self.migration)
        expected = {"ct.penta.security", "ct.penta.chlom-review", "ct.penta.cie-review"}
        self.assertTrue(expected.issubset(set(node_ids)))
        for node_id in expected:
            self.assertRegex(node_id, r"^ct[.]penta[.][a-z0-9][a-z0-9._-]{2,160}$")
        self.assertNotIn("ct.chlom.authority", self.migration)
        self.assertNotIn("ct.cie.review", self.migration)

    def test_nodes_are_transport_addresses_not_new_sovereign_authorities(self) -> None:
        self.assertIn("'transport_only',true", self.migration)
        self.assertIn("'disposition_authority',false", self.migration)
        self.assertIn("'authority_created',false", self.migration)
        self.assertIn("'d3_human_reserved',true", self.migration)
        forbidden = (
            "provider_write=true",
            "credential_change=true",
            "money_movement=true",
            "rights_grant=true",
            "vote_effect=true",
            "quorum_effect=true",
            "d3_execution=true",
            "LICENSE_GRANTED",
            "PASS_CERTIFIED",
            "PASS_SECURITY",
        )
        for token in forbidden:
            self.assertNotIn(token, self.migration)

    def test_preflight_verifies_signed_packet_exact_subject_and_exact_head(self) -> None:
        self.assertIn("pentas.verify_packet_v2(p_packet_id)", self.migration)
        self.assertIn("HOLD_PACKET_VERIFICATION_FAILED", self.migration)
        self.assertIn("HOLD_EXACT_SUBJECT_MISMATCH", self.migration)
        self.assertIn("HOLD_EXACT_HEAD_MISMATCH", self.migration)
        self.assertIn("HOLD_INDEPENDENT_OWNER_TARGET_MISMATCH", self.migration)
        self.assertIn("HOLD_ORIGINATOR_INDEPENDENCE_UNPROVEN", self.migration)
        self.assertIn("READY_FOR_INDEPENDENT_REVIEW", self.migration)

    def test_ready_state_is_explicitly_not_a_gate_disposition(self) -> None:
        self.assertIn("'gate_disposition_created',false", self.migration)
        self.assertIn("'independent_review_required',true", self.migration)
        self.assertIn("READY_FOR_INDEPENDENT_REVIEW is transport readiness only", self.migration)

    def test_node_registration_never_overwrites_existing_native_nodes(self) -> None:
        self.assertGreaterEqual(self.migration.count("where not exists(select 1 from pentas.nodes_v2"), 3)
        self.assertNotIn("on conflict(node_id) do update", self.migration.lower())

    def test_preflight_is_service_role_only(self) -> None:
        self.assertIn("raise exception 'service_role_required'", self.migration)
        self.assertIn("revoke all on function public.penta_help_independent_gate_review_preflight_v1", self.migration)
        self.assertIn("grant execute on function public.penta_help_independent_gate_review_preflight_v1", self.migration)

    def test_rollback_is_collision_safe_and_preserves_used_node_lineage(self) -> None:
        self.assertIn("exists(select 1 from pentas.deliveries_v2", self.rollback)
        self.assertIn("lifecycle_state='retired'", self.rollback)
        self.assertIn("RETIRED_WITH_PRESERVED_DELIVERY_LINEAGE", self.rollback)
        self.assertIn("delete from pentas.nodes_v2", self.rollback)
        self.assertIn("drop function if exists public.penta_help_independent_gate_review_preflight_v1", self.rollback)
        self.assertNotIn("delete from penta_help.requests_v1", self.rollback)


if __name__ == "__main__":
    unittest.main()

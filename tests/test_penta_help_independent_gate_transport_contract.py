from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20260901111500_penta_help_independent_gate_transport_v1.sql"
ROLLBACK = ROOT / "supabase/rollback/20260901111500_penta_help_independent_gate_transport_v1_rollback.sql"
CERTIFIER_ISOLATION = ROOT / "supabase/migrations/20260901125500_penta_help_independent_gate_certifier_transport_isolation_v1.sql"
CERTIFIER_ISOLATION_ROLLBACK = ROOT / "supabase/rollback/20260901125500_penta_help_independent_gate_certifier_transport_isolation_v1_rollback.sql"


class PentaHelpIndependentGateTransportContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.migration = MIGRATION.read_text(encoding="utf-8")
        cls.rollback = ROLLBACK.read_text(encoding="utf-8")
        cls.certifier_isolation = CERTIFIER_ISOLATION.read_text(encoding="utf-8")
        cls.certifier_isolation_rollback = CERTIFIER_ISOLATION_ROLLBACK.read_text(encoding="utf-8")

    def test_transport_is_bound_to_independent_gate_requests(self) -> None:
        self.assertIn("q.blocker_class='independent_gate'", self.migration)
        self.assertIn("q.risk_class in ('D0','D1','D2')", self.migration)
        self.assertIn("institutional.independent-gate.review.request", self.migration)

    def test_transport_never_creates_a_gate_disposition(self) -> None:
        forbidden = (
            "PASS_CERTIFIED",
            "PASS_SECURITY",
            "LICENSE_GRANTED",
            "provider_write=true",
            "credential_change=true",
            "money_movement=true",
            "rights_grant=true",
            "vote_effect=true",
            "quorum_effect=true",
            "d3_execution=true",
        )
        for token in forbidden:
            self.assertNotIn(token, self.migration)
        self.assertIn("'transport_only',true", self.migration)
        self.assertIn("'authority_created',false", self.migration)

    def test_missing_authority_nodes_remain_explicit_holds(self) -> None:
        self.assertIn("HOLD_TARGET_NODE_UNREGISTERED", self.migration)
        self.assertIn("HOLD_TARGET_NODE_UNHEALTHY", self.migration)
        self.assertIn("'ct.penta.security'", self.migration)
        self.assertIn("'ct.penta.chlom-review'", self.migration)
        self.assertIn("'ct.penta.cie-review'", self.migration)

    def test_every_concrete_owner_target_obeys_pentas_v2_node_id_contract(self) -> None:
        targets = (
            "ct.penta.certify",
            "ct.penta.security",
            "ct.penta.chlom-review",
            "ct.penta.cie-review",
        )
        for target in targets:
            self.assertIn(f"then '{target}'", self.migration)
            self.assertRegex(target, r"^ct[.]penta[.][a-z0-9][a-z0-9._-]{2,160}$")
        self.assertNotIn("ct.chlom.authority", self.migration)
        self.assertNotIn("ct.cie.review", self.migration)

    def test_current_pentacertifier_node_is_supported_without_inheriting_authority(self) -> None:
        self.assertIn("'ct.penta.certify'", self.migration)
        self.assertIn("destination retains independent authority", self.migration)
        self.assertIn("PentaHelp/PentaLiaison/PentaCensus", self.migration)

    def test_dispatch_receipts_are_append_only_and_service_role_only(self) -> None:
        self.assertIn("PENTA_HELP_INDEPENDENT_GATE_DISPATCH_APPEND_ONLY", self.migration)
        self.assertIn("before update or delete", self.migration)
        self.assertIn("force row level security", self.migration)
        self.assertIn("grant select on penta_help.independent_gate_dispatches_v1 to service_role", self.migration)
        self.assertIn("grant execute on function public.penta_help_dispatch_independent_gates_v1(integer) to service_role", self.migration)

    def test_transport_requires_dail_readback(self) -> None:
        self.assertIn("public.chlom_append_dail_event", self.migration)
        self.assertIn("DAIL_GATE_TRANSPORT_READBACK_FAILED", self.migration)
        self.assertIn("dail_event_hash", self.migration)

    def test_rollback_removes_only_additive_transport_objects(self) -> None:
        self.assertIn("drop function if exists public.penta_help_dispatch_independent_gates_v1", self.rollback)
        self.assertIn("drop table if exists penta_help.independent_gate_dispatches_v1", self.rollback)
        self.assertNotIn("drop table if exists penta_help.requests_v1", self.rollback)
        self.assertNotIn("drop table if exists penta_help.liaison_threads_v1", self.rollback)

    def test_exact_gate_certifier_transport_is_isolated_from_generic_certifier_node(self) -> None:
        self.assertIn("ct.penta.certify-review", self.certifier_isolation)
        self.assertIn("generic_factory_dispatch_allowed',false", self.certifier_isolation)
        self.assertIn("terminal_ack_from_transport',false", self.certifier_isolation)
        self.assertIn("independent_owner_execution_required',true", self.certifier_isolation)
        self.assertIn("then ''ct.penta.certify-review''", self.certifier_isolation)
        self.assertIn("then ''ct.penta.certify''", self.certifier_isolation)
        self.assertIn("PENTA_HELP_CERTIFIER_TRANSPORT_REWRITE_READBACK_FAILED", self.certifier_isolation)
        self.assertIn("PENTA_HELP_CERTIFIER_PREFLIGHT_REWRITE_READBACK_FAILED", self.certifier_isolation)

    def test_certifier_isolation_does_not_manufacture_independent_disposition(self) -> None:
        forbidden = (
            "PASS_CERTIFIED",
            "PASS_SECURITY",
            "LICENSE_GRANTED",
            "provider_write=true",
            "credential_change=true",
            "money_movement=true",
            "rights_grant=true",
            "vote_effect=true",
            "quorum_effect=true",
            "d3_execution=true",
        )
        for token in forbidden:
            self.assertNotIn(token, self.certifier_isolation)
        self.assertIn("'transport_only',true", self.certifier_isolation)
        self.assertIn("'disposition_authority',false", self.certifier_isolation)
        self.assertIn("'authority_created',false", self.certifier_isolation)

    def test_certifier_isolation_preserves_canonical_certifier_identity(self) -> None:
        self.assertIn("does not replace or", self.certifier_isolation)
        self.assertIn("mutate the canonical `ct.penta.certify` node", self.certifier_isolation)
        self.assertIn("'canonical_owner','penta.certify'", self.certifier_isolation)
        self.assertNotIn("delete from pentas.nodes_v2 where node_id='ct.penta.certify'", self.certifier_isolation.lower())

    def test_certifier_isolation_rollback_is_lineage_safe(self) -> None:
        self.assertIn("independent_gate_dispatches_v1", self.certifier_isolation_rollback)
        self.assertIn("pentas.deliveries_v2", self.certifier_isolation_rollback)
        self.assertIn("ROLLBACK_REQUIRES_FORWARD_SUPERSESSION_CERTIFIER_REVIEW_LINEAGE_PRESENT", self.certifier_isolation_rollback)
        self.assertIn("node_id='ct.penta.certify-review'", self.certifier_isolation_rollback)
        self.assertIn("then ''ct.penta.certify''", self.certifier_isolation_rollback)
        self.assertNotIn("delete from penta_help.requests_v1", self.certifier_isolation_rollback.lower())


if __name__ == "__main__":
    unittest.main()

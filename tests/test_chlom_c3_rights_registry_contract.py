from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20260901104500_chlom_c3_rights_registry_v1.sql"
ROLLBACK = ROOT / "supabase/rollback/20260901104500_chlom_c3_rights_registry_v1_rollback.sql"


class CHLOMC3RightsRegistryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = MIGRATION.read_text(encoding="utf-8")
        cls.rollback = ROLLBACK.read_text(encoding="utf-8")

    def test_builds_claim_and_decision_history(self) -> None:
        self.assertIn("create table if not exists chlom_runtime.rights_claims_v1", self.sql)
        self.assertIn("create table if not exists chlom_runtime.rights_claim_decisions_v1", self.sql)
        self.assertIn("ownership','administration','representation", self.sql)
        self.assertIn("rights_object_key", self.sql)
        self.assertIn("territories text[]", self.sql)
        self.assertIn("media_scopes text[]", self.sql)
        self.assertIn("use_scopes text[]", self.sql)
        self.assertIn("restrictions jsonb", self.sql)
        self.assertIn("evidence_refs jsonb", self.sql)

    def test_history_is_immutable(self) -> None:
        self.assertIn("CHLOM_RIGHTS_HISTORY_IMMUTABLE", self.sql)
        self.assertIn("before update or delete on chlom_runtime.rights_claims_v1", self.sql)
        self.assertIn("before update or delete on chlom_runtime.rights_claim_decisions_v1", self.sql)
        self.assertIn("on delete restrict", self.sql)

    def test_originator_cannot_self_verify(self) -> None:
        self.assertIn("CHLOM_RIGHTS_SELF_VERIFICATION_DENIED", self.sql)
        self.assertIn("v_verifier=c.asserted_by or v_verifier=c.claimant_ref", self.sql)

    def test_conflicting_claims_fail_closed(self) -> None:
        self.assertIn("CONFLICTING_VERIFIED_CLAIM", self.sql)
        self.assertIn("v_effective:='hold'", self.sql)
        self.assertIn("HOLD_CONFLICT", self.sql)
        self.assertIn("a.claim_role=b.claim_role", self.sql)
        self.assertIn("a.claimant_ref<>b.claimant_ref", self.sql)
        self.assertIn("territories &&", self.sql)
        self.assertIn("media_scopes &&", self.sql)
        self.assertIn("use_scopes &&", self.sql)

    def test_query_never_becomes_a_rights_grant(self) -> None:
        self.assertIn("VERIFIED_CLAIMS_NOT_GRANT", self.sql)
        self.assertIn("QUERY_IS_EVIDENCE_STATUS_NOT_RIGHTS_OR_LICENSE_GRANT", self.sql)
        self.assertIn("EVIDENCE_CLAIM_NOT_RIGHTS_GRANT", self.sql)
        self.assertIn("INDEPENDENT_CLAIM_DISPOSITION_NOT_RIGHTS_GRANT", self.sql)
        forbidden = (
            "LICENSE_GRANTED",
            "RIGHTS_GRANTED",
            "provider_write=true",
            "vote_effect=true",
            "quorum_effect=true",
            "money_movement=true",
        )
        for token in forbidden:
            self.assertNotIn(token, self.sql)

    def test_material_events_use_canonical_dail_append(self) -> None:
        self.assertIn("chlom_runtime.append_dail_event", self.sql)
        self.assertIn("chlom.rights.claim.asserted", self.sql)
        self.assertIn("chlom.rights.claim.disposition", self.sql)
        self.assertIn("dail_event_hash", self.sql)

    def test_tables_are_not_directly_writable_by_service_role(self) -> None:
        self.assertIn(
            "revoke all on table chlom_runtime.rights_claims_v1 from public,anon,authenticated,service_role",
            self.sql,
        )
        self.assertIn(
            "revoke all on table chlom_runtime.rights_claim_decisions_v1 from public,anon,authenticated,service_role",
            self.sql,
        )
        self.assertIn("grant select on table chlom_runtime.rights_claims_v1 to service_role", self.sql)
        self.assertIn("grant select on table chlom_runtime.rights_claim_decisions_v1 to service_role", self.sql)
        self.assertIn("grant execute on function chlom_runtime.assert_rights_claim_v1", self.sql)
        self.assertIn("grant execute on function chlom_runtime.record_rights_claim_decision_v1", self.sql)

    def test_evidence_digests_and_refs_are_required(self) -> None:
        self.assertIn("CHLOM_RIGHTS_EVIDENCE_REQUIRED", self.sql)
        self.assertIn("CHLOM_RIGHTS_EVIDENCE_DIGEST_REQUIRED", self.sql)
        self.assertIn("CHLOM_RIGHTS_DECISION_EVIDENCE_REQUIRED", self.sql)
        self.assertIn("CHLOM_RIGHTS_DECISION_DIGEST_REQUIRED", self.sql)
        self.assertIn("jsonb_array_length(evidence_refs)>0", self.sql)

    def test_rollback_refuses_to_erase_real_history(self) -> None:
        self.assertIn("CHLOM_C3_ROLLBACK_BLOCKED_RIGHTS_HISTORY_EXISTS", self.rollback)
        self.assertIn("CHLOM_C3_ROLLBACK_BLOCKED_DECISION_HISTORY_EXISTS", self.rollback)
        self.assertIn("drop table if exists chlom_runtime.rights_claim_decisions_v1", self.rollback)
        self.assertIn("drop table if exists chlom_runtime.rights_claims_v1", self.rollback)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260907211000_penta_assignment_security_review_adapter_v1.sql"
SQL_TEST = ROOT / "tests" / "security" / "penta_assignment_security_review_adapter_v1.sql"


class PentaSecurityAssignmentPolicyIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.migration = MIGRATION.read_text(encoding="utf-8")
        cls.sql_test = SQL_TEST.read_text(encoding="utf-8")

    def test_policy_selection_binds_complete_identity_tuple(self) -> None:
        required = (
            "p.policy_key=v_policy_key",
            "p.policy_version='1.0.0'",
            "p.system_family='SECURITY_TRUST'",
            "p.provider_system='github'",
            "p.resource_type='migration_source'",
            "p.resource_id='assignment-migration:'||v_version",
            "p.repository=a.source_repo",
            "p.state='active'",
            "p.authority_effect='none'",
        )
        for clause in required:
            with self.subTest(clause=clause):
                self.assertIn(clause, self.migration)

    def test_policy_selection_requires_exactly_one_row_and_fails_closed(self) -> None:
        self.assertIn("if v_policy_count<>1 then", self.migration)
        self.assertIn("select * into strict v_policy", self.migration)
        self.assertIn("when no_data_found or too_many_rows then", self.migration)
        self.assertIn("SOURCE_POLICY_IDENTITY_AMBIGUOUS:", self.migration)
        self.assertNotIn("order by p.created_at desc", self.migration)
        self.assertNotIn("limit 1", self.migration.lower())

    def test_sql_acceptance_covers_policy_identity_and_ambiguity(self) -> None:
        required = (
            "p.policy_version=''1.0.0''",
            "p.system_family=''SECURITY_TRUST''",
            "p.provider_system=''github''",
            "p.resource_type=''migration_source''",
            "v_policy_count<>1",
            "too_many_rows",
            "limit 1",
        )
        for clause in required:
            with self.subTest(clause=clause):
                self.assertIn(clause, self.sql_test)

    def test_security_adapter_remains_authority_neutral(self) -> None:
        self.assertIn("'independent_certification',false", self.migration)
        self.assertIn("'release_authorized',false", self.migration)
        self.assertIn("'authority_created',false", self.migration)


if __name__ == "__main__":
    unittest.main()

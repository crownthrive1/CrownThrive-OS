from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260907211000_penta_assignment_security_review_adapter_v1.sql"
FINAL_MIGRATION = ROOT / "supabase" / "migrations" / "20260907225700_penta_assignment_manifest_content_binding_v1.sql"
SQL_TEST = ROOT / "tests" / "security" / "penta_assignment_security_review_adapter_v1.sql"


class PentaSecurityAssignmentPolicyIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.migration = MIGRATION.read_text(encoding="utf-8")
        cls.final_migration = FINAL_MIGRATION.read_text(encoding="utf-8")
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

    def test_policy_selection_binds_complete_policy_content(self) -> None:
        required = (
            "p.source_path=v_expected_policy.source_path",
            "p.required_literals=v_expected_policy.required_literals",
            "p.forbidden_literals=v_expected_policy.forbidden_literals",
            "p.max_source_bytes=v_expected_policy.max_source_bytes",
            "v_policy_content_count<>1",
            "SOURCE_POLICY_CONTENT_MISMATCH:",
            "SOURCE_POLICY_CONTENT_CHANGED_DURING_SELECTION:",
        )
        for clause in required:
            with self.subTest(clause=clause):
                self.assertIn(clause, self.migration)

        for version in ("20260831093500", "20260831135000", "20260831143500", "20260831154500"):
            with self.subTest(version=version):
                self.assertIn(version, self.migration)

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

    def test_sql_acceptance_reads_back_four_canonical_policy_rows(self) -> None:
        required = (
            "v_policy_row_matches<>4",
            "p.policy_key='ct.penta.security.assignment-migration.'||e.version||'.v1'",
            "p.source_path=e.source_path",
            "p.required_literals=e.required_literals",
            "p.forbidden_literals=e.forbidden_literals",
            "p.max_source_bytes=e.max_source_bytes",
        )
        for clause in required:
            with self.subTest(clause=clause):
                self.assertIn(clause, self.sql_test)

        for version in ("20260831093500", "20260831135000", "20260831143500", "20260831154500"):
            with self.subTest(version=version):
                self.assertIn(version, self.sql_test)

    def test_effective_search_path_and_schema_create_acl_are_verified(self) -> None:
        sql = "".join(self.sql_test.lower().split())
        required = (
            "p.prosecdef",
            "p.proconfig",
            "search_path=pg_catalog,penta_security,integration_control",
            "aclexplode",
            "acl.grantee=0",
            "acl.privilege_type='create'",
            "has_schema_privilege('anon','penta_security','create')",
            "has_schema_privilege('authenticated','penta_security','create')",
            "has_schema_privilege('service_role','penta_security','create')",
            "has_schema_privilege('anon','integration_control','create')",
            "has_schema_privilege('authenticated','integration_control','create')",
            "has_schema_privilege('service_role','integration_control','create')",
        )
        for clause in required:
            with self.subTest(clause=clause):
                self.assertIn(clause, sql)

        final_migration = "".join(self.final_migration.lower().split())
        self.assertIn(
            "setsearch_pathto'pg_catalog','penta_security','integration_control'",
            final_migration,
        )

    def test_security_adapter_remains_authority_neutral(self) -> None:
        self.assertIn("'independent_certification',false", self.migration)
        self.assertIn("'release_authorized',false", self.migration)
        self.assertIn("'authority_created',false", self.migration)


if __name__ == "__main__":
    unittest.main()

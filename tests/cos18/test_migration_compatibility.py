from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "supabase/migrations/20260904000099_cos_1_8_jsonb_object_length_compat.sql"
KERNEL = ROOT / "supabase/migrations/20260904000100_cos_1_8_constitutional_kernel.sql"


class MigrationCompatibilityTests(unittest.TestCase):
    def test_01_helper_precedes_kernel(self) -> None:
        self.assertLess(HELPER.name, KERNEL.name)

    def test_02_helper_uses_supported_primitive(self) -> None:
        sql = HELPER.read_text(encoding="utf-8")
        self.assertIn("pg_catalog.jsonb_object_keys(p_object)", sql)
        self.assertIn("immutable", sql.lower())
        self.assertIn("strict", sql.lower())
        self.assertIn("set search_path = pg_catalog", sql.lower())

    def test_03_helper_is_not_end_user_callable(self) -> None:
        sql = HELPER.read_text(encoding="utf-8").lower()
        self.assertIn(
            "revoke all on function public.jsonb_object_length(jsonb) from public, anon, authenticated",
            sql,
        )
        self.assertIn(
            "grant execute on function public.jsonb_object_length(jsonb) to service_role",
            sql,
        )

    def test_04_kernel_dependency_is_supplied(self) -> None:
        helper_sql = HELPER.read_text(encoding="utf-8")
        kernel_sql = KERNEL.read_text(encoding="utf-8")
        self.assertIn(
            "create or replace function public.jsonb_object_length(p_object jsonb)",
            helper_sql.lower(),
        )
        self.assertIn("jsonb_object_length(domains) = 13", kernel_sql)


if __name__ == "__main__":
    unittest.main()

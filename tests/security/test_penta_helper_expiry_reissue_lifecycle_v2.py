from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "supabase/migrations/20260903143000_penta_helper_expiry_reissue_lifecycle_v2.sql"
ROLLBACK = ROOT / "supabase/rollback/20260903143000_penta_helper_expiry_reissue_lifecycle_v2_rollback.sql"


class PentaHelperExpiryReissueLifecycleV2Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = MIGRATION.read_text(encoding="utf-8").lower()
        cls.rollback = ROLLBACK.read_text(encoding="utf-8").lower()

    def test_expiry_reaper_is_bounded_concurrency_safe(self):
        self.assertIn("penta_helper_reap_expired_requests_v1", self.sql)
        self.assertIn("for update skip locked", self.sql)
        self.assertIn("limit v_limit", self.sql)
        self.assertIn("expires_at <= clock_timestamp()", self.sql)
        self.assertIn("lease_expires_at is null or lease_expires_at <= clock_timestamp()", self.sql)
        self.assertIn("state='expired'", self.sql)

    def test_reaper_is_bound_into_helper_reconcile(self):
        self.assertIn("v_expiry:=public.penta_helper_reap_expired_requests_v1(100)", self.sql)
        self.assertIn("'expiry',v_expiry", self.sql)

    def test_expired_request_cannot_be_routed_until_reissued(self):
        self.assertIn("penta_help_request_not_routeable", self.sql)
        self.assertIn("r.state in ('resolved','retired','expired')", self.sql)
        self.assertIn("r.expires_at <= clock_timestamp()", self.sql)

    def test_same_liaison_transport_reopens_after_valid_reissue(self):
        self.assertIn("on conflict(request_id,destination_kind,destination_ref) do update set", self.sql)
        self.assertIn("state='routed'", self.sql)
        self.assertIn("resolved_at=null", self.sql.replace(" ", ""))
        self.assertIn("expires_at=excluded.expires_at", self.sql)
        self.assertIn("ttyl_at=excluded.ttyl_at", self.sql)

    def test_acl_is_least_privilege(self):
        for signature in (
            "public.penta_helper_reap_expired_requests_v1(integer)",
            "public.penta_liaison_route_v1(uuid,text,text,text,jsonb)",
            "public.penta_helper_reconcile_v1()",
        ):
            self.assertIn(f"revoke all on function {signature} from public, anon, authenticated", self.sql)
            self.assertIn(f"grant execute on function {signature} to service_role", self.sql)

    def test_no_semantic_or_authority_manufacture(self):
        self.assertNotIn("semantic_result_created',true", self.sql)
        self.assertNotIn("authority_created',true", self.sql)
        self.assertNotIn("state','pass", self.sql)
        self.assertNotIn("state','certified", self.sql)

    def test_rollback_is_fail_closed_and_preserves_function_identity(self):
        self.assertIn("penta_help_expiry_reaper_disabled_by_rollback", self.rollback)
        self.assertIn("create or replace function public.penta_helper_reap_expired_requests_v1", self.rollback)
        self.assertIn("create or replace function public.penta_liaison_route_v1", self.rollback)
        self.assertIn("create or replace function public.penta_helper_reconcile_v1", self.rollback)
        self.assertNotIn("drop function", self.rollback)


if __name__ == "__main__":
    unittest.main()

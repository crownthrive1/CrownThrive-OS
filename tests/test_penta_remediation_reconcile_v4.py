from pathlib import Path
import unittest


class PentaRemediationReconcileV4Tests(unittest.TestCase):
    def test_post_surgery_success_can_use_last_success_at(self) -> None:
        sql = Path(
            "supabase/migrations/20260829192000_penta_remediation_reconcile_post_surgery_success_v4.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("last_success_at", sql)
        self.assertIn("latest_started_at", sql)
        self.assertIn("v_no_code_delta := not", sql)
        self.assertIn("verified_repaired", sql)
        self.assertIn("ct.penta.pm.assignment-execution.v4", sql)


if __name__ == "__main__":
    unittest.main()

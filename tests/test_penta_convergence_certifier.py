from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "runtime" / "penta_convergence_certifier.py"
spec = importlib.util.spec_from_file_location("penta_convergence_certifier_test", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class PentaConvergenceCertifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = module.certify(ROOT)

    def test_invokes_complete_registered_family(self):
        family = self.evidence["family"]
        self.assertGreater(family["member_count"], 0)
        self.assertEqual(family["member_count"], family["invocation_count"])
        keys = [item["machine_key"] for item in self.evidence["invocations"]]
        self.assertEqual(len(keys), len(set(keys)))

    def test_preserves_held_members_without_promotion(self):
        family = self.evidence["family"]
        self.assertEqual(
            family["member_count"],
            family["eligible_count"] + family["held_count"],
        )
        for invocation in self.evidence["invocations"]:
            if invocation["disposition"] == "hold_preserved":
                self.assertFalse(invocation["effective_execution_eligible"])

    def test_critical_control_plane_contract_passes(self):
        checks = self.evidence["critical_checks"]
        self.assertTrue(checks["family_status_production"])
        self.assertTrue(checks["family_fail_closed"])
        self.assertTrue(checks["full_member_census_invoked"])
        self.assertTrue(checks["runtime_member_census_matches"])
        self.assertTrue(checks["provider_control_plane_present"])
        self.assertTrue(checks["provider_contract_clean"])
        self.assertTrue(checks["pentamail_registered"])
        self.assertTrue(checks["resend_registered"])
        self.assertEqual(self.evidence["disposition"], "PASS")

    def test_evidence_is_hash_bound(self):
        self.assertRegex(self.evidence["evidence_sha256"], r"^[0-9a-f]{64}$")
        self.assertGreater(self.evidence["observability"]["log_event_count"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from penta_gate import scan_repository
from penta_heal import build_heal_packet


class PentaGateHealTests(unittest.TestCase):
    def make_repo(self, test_source: str):
        temp = tempfile.TemporaryDirectory()
        root = pathlib.Path(temp.name)
        (root / "tests").mkdir()
        (root / ".github" / "workflows").mkdir(parents=True)
        (root / "tests" / "test_sample.py").write_text(test_source, encoding="utf-8")
        (root / ".github" / "workflows" / "ci.yml").write_text(
            "run: python -m unittest discover -s tests -v\n", encoding="utf-8"
        )
        return temp, root

    def test_clean_unittest_contract_passes(self):
        temp, root = self.make_repo("import unittest\n\nclass T(unittest.TestCase):\n    pass\n")
        with temp:
            report = scan_repository(root)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["findings"], [])
        self.assertGreaterEqual(report["unittest_discovery_refs"], 1)

    def test_missing_unconditional_test_dependency_fails_closed(self):
        temp, root = self.make_repo("import definitely_missing_penta_dependency_xyz\n")
        with temp:
            report = scan_repository(root)
        self.assertEqual(report["status"], "HOLD")
        self.assertEqual(report["findings"][0]["code"], "missing_test_import")
        self.assertEqual(report["findings"][0]["severity"], "BLOCK")

    def test_optional_dependency_inside_try_is_not_misclassified(self):
        temp, root = self.make_repo(
            "try:\n    import definitely_missing_penta_dependency_xyz\nexcept ImportError:\n    pass\n"
        )
        with temp:
            report = scan_repository(root)
        self.assertEqual(report["status"], "PASS")

    def test_heal_packet_routes_through_independent_authorities(self):
        gate = {
            "status": "HOLD",
            "receipt_sha256": "a" * 64,
            "findings": [{
                "code": "missing_test_import",
                "path": "tests/test_x.py",
                "module": "pytest",
                "detail": "unavailable",
                "repair_class": "repair_workflow",
            }],
        }
        packet = build_heal_packet(gate)
        self.assertEqual(packet["repair_count"], 1)
        self.assertTrue(packet["exact_head_test_required"])
        self.assertTrue(packet["independent_certification_required"])
        self.assertFalse(packet["self_certification_authorized"])
        self.assertFalse(packet["production_promotion_authorized"])
        plan = packet["repairs"][0]
        self.assertEqual(plan["status"], "READY")
        self.assertEqual(plan["handler"], "repair_workflow")
        self.assertTrue(plan["rollback"])
        self.assertTrue(plan["fallback"])

    def test_repository_itself_is_pentagate_clean(self):
        report = scan_repository(ROOT)
        self.assertEqual(report["status"], "PASS", report["findings"])


if __name__ == "__main__":
    unittest.main()

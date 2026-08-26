import tempfile
import unittest
from pathlib import Path

from penta.runtime.resilience import (
    PentaHoneyPot,
    PentaLiency,
    PentaRed,
    PentaRollback,
    PentaSnapshot,
    PolicyViolation,
    RangeLease,
    RangePolicy,
    penta_status_adapter,
    tree_evidence,
)


class PentaResilienceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "os"
        self.root.mkdir()
        (self.root / "app.txt").write_text("stable\n", encoding="utf-8")
        (self.root / "config").mkdir()
        (self.root / "config" / "service.json").write_text('{"enabled":true}\n', encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_red_cannot_target_source_tree(self):
        policy = RangePolicy()
        fake = RangeLease("range-fake", str(self.root), "x", 0, 9999999999, "hash")
        with self.assertRaises(PolicyViolation):
            PentaRed(policy).execute(fake, "config_tamper")

    def test_honeypot_drill_restores_clone_and_preserves_source(self):
        before = tree_evidence(self.root)[1]
        report = PentaHoneyPot().run(self.root)
        after = tree_evidence(self.root)[1]
        self.assertEqual(before, after)
        self.assertTrue(report.source_unchanged)
        self.assertTrue(report.clone_restored)
        self.assertEqual(len(report.events), 5)
        self.assertTrue(all(d.contained and d.restored for d in report.detections))
        self.assertTrue(report.digest)
        status = penta_status_adapter(report)
        self.assertEqual(status["overall_state"], "verified")

    def test_snapshot_and_rollback_restore_content(self):
        snapshotter = PentaSnapshot()
        manifest = snapshotter.create(self.root)
        (self.root / "app.txt").write_text("bad\n", encoding="utf-8")
        result = PentaRollback(snapshotter).restore(
            manifest,
            self.root,
            approved_change_id="CHG-123",
            health_check=lambda p: (p / "app.txt").read_text() == "stable\n",
        )
        self.assertTrue(result.restored)
        self.assertTrue(result.health_ok)
        self.assertEqual((self.root / "app.txt").read_text(), "stable\n")

    def test_liency_plan_and_apply(self):
        report = PentaHoneyPot().run(self.root, ["config_tamper", "secret_canary"])
        liency = PentaLiency()
        plan = liency.plan(report)
        self.assertEqual(len(plan.actions), 2)
        result = liency.apply(plan, self.root, approved_change_id="CHG-456", health_check=lambda _: True)
        self.assertTrue(result["applied"])
        controls = list((self.root / ".penta-hardening" / "controls").glob("*.json"))
        self.assertEqual(len(controls), 2)

    def test_failed_health_gate_auto_rolls_back(self):
        before = tree_evidence(self.root)[1]
        report = PentaHoneyPot().run(self.root, ["integrity_tamper"])
        liency = PentaLiency()
        plan = liency.plan(report)
        result = liency.apply(plan, self.root, approved_change_id="CHG-789", health_check=lambda _: False)
        self.assertFalse(result["applied"])
        self.assertIsNotNone(result["rollback"])
        self.assertEqual(tree_evidence(self.root)[1], before)


if __name__ == "__main__":
    unittest.main()

from dataclasses import replace
import tempfile
import time
import unittest
from pathlib import Path

from penta.runtime.resilience import (
    AttackEvent,
    PentaBlue,
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
        self.honeypot = PentaHoneyPot()

    def tearDown(self):
        self.tmp.cleanup()

    def test_red_cannot_target_source_tree(self):
        policy = RangePolicy()
        fake = RangeLease("range-fake", str(self.root), "x", 0, 9999999999, "hash")
        with self.assertRaises(PolicyViolation):
            PentaRed(policy).execute(fake, "config_tamper")

    def test_honeypot_drill_restores_clone_and_preserves_source(self):
        before = tree_evidence(self.root)[1]
        report = self.honeypot.run(self.root)
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
        report = self.honeypot.run(self.root, ["config_tamper", "secret_canary"])
        liency = PentaLiency(report_verifier=self.honeypot.verify_report)
        plan = liency.plan(report)
        self.assertEqual(len(plan.actions), 2)
        result = liency.apply(plan, self.root, approved_change_id="CHG-456", health_check=lambda _: True)
        self.assertTrue(result["applied"])
        controls = list((self.root / ".penta-hardening" / "controls").glob("*.json"))
        self.assertEqual(len(controls), 2)

    def test_failed_health_gate_auto_rolls_back(self):
        before = tree_evidence(self.root)[1]
        report = self.honeypot.run(self.root, ["integrity_tamper"])
        liency = PentaLiency(report_verifier=self.honeypot.verify_report)
        plan = liency.plan(report)
        result = liency.apply(plan, self.root, approved_change_id="CHG-789", health_check=lambda _: False)
        self.assertFalse(result["applied"])
        self.assertIsNotNone(result["rollback"])
        self.assertEqual(tree_evidence(self.root)[1], before)

    def test_liency_rejects_forged_and_failed_drill_evidence(self):
        report = self.honeypot.run(self.root, ["config_tamper"])
        liency = PentaLiency(report_verifier=self.honeypot.verify_report)

        with self.assertRaises(PolicyViolation):
            liency.plan(replace(report, digest="f" * 64))

        failed_restore = replace(report, clone_restored=False, digest="").with_digest()
        with self.assertRaises(PolicyViolation):
            liency.plan(failed_restore)

        failed_detection = replace(report.detections[0], restored=False)
        inconsistent = replace(report, detections=(failed_detection,), digest="").with_digest()
        with self.assertRaises(PolicyViolation):
            liency.plan(inconsistent)

    def test_apply_rejects_unissued_and_path_traversal_plans(self):
        report = self.honeypot.run(self.root, ["config_tamper"])
        liency = PentaLiency(report_verifier=self.honeypot.verify_report)
        plan = liency.plan(report)
        forged = replace(plan, plan_id="plan-00000000000000", digest="").with_digest()
        with self.assertRaises(PolicyViolation):
            liency.apply(forged, self.root, approved_change_id="CHG-FORGED")

        class TraversalLiency(PentaLiency):
            CONTROL_MAP = {
                "config_tamper": ("../../../ESCAPED", "require_signed_config_changes", True),
            }

        traversal = TraversalLiency(report_verifier=self.honeypot.verify_report)
        traversal_plan = traversal.plan(report)
        escaped = self.root.parent / "escaped.json"
        with self.assertRaises(PolicyViolation):
            traversal.apply(traversal_plan, self.root, approved_change_id="CHG-TRAVERSAL")
        self.assertFalse(escaped.exists())

    def test_apply_binds_change_plan_and_exact_target(self):
        report = self.honeypot.run(self.root, ["secret_canary"])
        liency = PentaLiency(report_verifier=self.honeypot.verify_report)
        plan = liency.plan(report)
        other = self.root.parent / "other"
        other.mkdir()
        (other / "app.txt").write_text("other\n", encoding="utf-8")

        with self.assertRaises(PolicyViolation):
            liency.apply(plan, other, approved_change_id="CHG-WRONG-TARGET")
        with self.assertRaises(PolicyViolation):
            liency.apply(plan, self.root, approved_change_id="anything-goes")

        (self.root / "app.txt").write_text("drifted\n", encoding="utf-8")
        with self.assertRaises(PolicyViolation):
            liency.apply(plan, self.root, approved_change_id="CHG-STALE-PLAN")
        self.assertFalse((self.root / ".penta-hardening").exists())

    def test_rollback_binds_snapshot_provenance_and_exact_target(self):
        snapshotter = PentaSnapshot()
        manifest = snapshotter.create(self.root)
        other = self.root.parent / "other-rollback"
        other.mkdir()
        (other / "app.txt").write_text("other\n", encoding="utf-8")

        with self.assertRaises(PolicyViolation):
            PentaRollback(snapshotter).restore(
                manifest,
                other,
                approved_change_id="CHG-WRONG-ROLLBACK",
                health_check=lambda _: True,
            )
        self.assertEqual((other / "app.txt").read_text(encoding="utf-8"), "other\n")

        forged = replace(manifest, tree_sha256="0" * 64, manifest_sha256="").with_digest()
        with self.assertRaises(PolicyViolation):
            PentaRollback(snapshotter).restore(
                forged,
                self.root,
                approved_change_id="CHG-FORGED-SNAPSHOT",
                health_check=lambda _: True,
            )

    def test_blue_containment_rejects_traversal_and_symlink_escape(self):
        lab = self.root / "lab"
        lab.mkdir()
        (lab / "config.json").write_text('{"mode":"normal"}\n', encoding="utf-8")
        snapshotter = PentaSnapshot()
        baseline = snapshotter.create(self.root)
        blue = PentaBlue(snapshotter)
        outside = self.root.parent / "outside"
        outside.mkdir()
        outside_config = outside / "config.json"
        outside_config.write_text("outside-safe\n", encoding="utf-8")

        traversal = AttackEvent(
            event_id="red-traversal",
            scenario="config_tamper",
            path="../outside/config.json",
            action="simulated-local-tamper",
            timestamp=time.time(),
            severity=PentaRed.SCENARIOS["config_tamper"][2],
        )
        with self.assertRaises(PolicyViolation):
            blue.inspect_and_contain(self.root, baseline, [traversal])
        self.assertEqual(outside_config.read_text(encoding="utf-8"), "outside-safe\n")

        (lab / "config.json").unlink()
        lab.rmdir()
        lab.symlink_to(outside, target_is_directory=True)
        valid_shape = replace(traversal, event_id="red-symlink", path="lab/config.json")
        with self.assertRaises(PolicyViolation):
            blue.inspect_and_contain(self.root, baseline, [valid_shape])
        self.assertEqual(outside_config.read_text(encoding="utf-8"), "outside-safe\n")

    def test_honeypot_rejects_duplicate_scenarios(self):
        with self.assertRaises(PolicyViolation):
            PentaHoneyPot().run(self.root, ["config_tamper", "config_tamper"])


if __name__ == "__main__":
    unittest.main()

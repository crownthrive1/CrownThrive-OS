import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "developers/manifests/system-convergence-cutoff-receipt.v1.json"
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class SystemConvergenceCutoffReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))

    def test_all_audited_instances_have_a_disposition(self):
        scope = self.receipt["scope"]
        counts = self.receipt["disposition_counts"]
        self.assertEqual(
            scope["total_audited_source_instances"],
            scope["preserved_worktree_source_instances"]
            + scope["provider_main_pr_556_pre_cutoff_source_instances"]
            + scope["production_promotion_wave3_source_instances"],
        )
        self.assertEqual(
            scope["total_audited_source_instances"],
            counts["byte_identical_in_canonical"]
            + counts["semantically_integrated_or_superseded"]
            + counts["intentional_or_post_cutoff_hold"],
        )
        self.assertEqual(counts["unmanaged_missing"], 0)

    def test_pre_cutoff_provider_main_is_bound_and_reconciled(self):
        authority = self.receipt["source_authorities"]
        moving = self.receipt["moving_main_reconciliation"]
        self.assertEqual(
            authority["support_provider_main_pr_556_merge_commit"],
            "beea4383b3e47ce30f884be8d37aabb4c9f413a6",
        )
        self.assertTrue(moving["pre_cutoff"])
        self.assertTrue(moving["provider_main_is_integration_parent"])
        self.assertEqual(moving["provider_main_changed_paths"], 80)
        self.assertEqual(moving["tip_identical_overlaps"], 48)
        self.assertEqual(moving["true_conflicts"], 25)
        self.assertEqual(moving["unmanaged_missing_after_resolution"], 0)

    def test_every_hold_is_exactly_enumerated_and_digest_bound(self):
        artifacts = [
            artifact
            for group in self.receipt["held_source_instances"]
            for artifact in group["artifacts"]
        ]
        self.assertEqual(len(artifacts), 15)
        self.assertEqual(
            len(artifacts),
            self.receipt["disposition_counts"]["intentional_or_post_cutoff_hold"],
        )
        paths = [artifact["path"] for artifact in artifacts]
        self.assertEqual(len(paths), len(set(paths)))
        for artifact in artifacts:
            self.assertRegex(artifact["sha256"], SHA256)

    def test_unsafe_candidate_pack_is_not_integrated(self):
        groups = {
            group["group"]: group for group in self.receipt["held_source_instances"]
        }
        candidate = groups["repository_candidate_sync_pack"]
        self.assertEqual(candidate["disposition"], "SECURITY_HOLD_SUPERSEDE")
        self.assertEqual(
            candidate["canonical_effect"], "HOLD_SUPERSEDED_NOT_INTEGRATED"
        )
        self.assertEqual(len(candidate["artifacts"]), 5)

    def test_major_release_remains_fail_closed(self):
        release = self.receipt["release_boundary"]
        self.assertEqual(self.receipt["institutional_phase"], 3)
        self.assertEqual(release["target_tag"], "v4.0.0.0")
        self.assertEqual(release["status"], "HOLD")
        self.assertEqual(release["penta_os_status"], "built_unreleased")
        for key in (
            "provider_effect_performed",
            "release_request_created",
            "major_release_terms_assigned",
            "frozen_head_created",
            "human_d3_approval_recorded",
            "protected_merge_receipt_present",
            "provider_tag_readback_present",
        ):
            self.assertFalse(release[key], key)
        self.assertEqual(
            release["prior_invalid_candidate"]["disposition"],
            "ABANDONED_INVALID_LINEAGE_CANDIDATE",
        )
        self.assertTrue(release["prior_invalid_candidate"]["preserve"])
        self.assertFalse(release["prior_invalid_candidate"]["reuse"])


if __name__ == "__main__":
    unittest.main()

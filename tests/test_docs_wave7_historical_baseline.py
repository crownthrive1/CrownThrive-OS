from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from unittest import mock

from scripts import execute_docs_rebuild_quad_lane_batch as quad_lane
from scripts import substantive_rebuild_current_snapshot as current_snapshot

ROOT = Path(__file__).resolve().parents[1]
RECEIPT_DIGESTS = (
    (
        "developers/manifests/docs-rebuild-quad-lane-batch-001.v1.json",
        "execution_sha256",
        "3f5aaf22204148a961b59a50cafd7cc32bb048cdaf8b8ce8b19ec3b6c10f624a",
    ),
    (
        "developers/manifests/docs-wave7-adluxe-substantive-gate-001.v1.json",
        "gate_sha256",
        "a31c3eec30d2d1e45b3ebfd7890b0f4584b7465e8b44797061d30c31dedfe1a3",
    ),
    (
        "developers/manifests/docs-wave7-adluxe-substantive-gate-002.v1.json",
        "gate_sha256",
        "6ad2e29bf4412e37d4b6ce873ab4a38425bfaa36156f81d94a80515f391e0679",
    ),
    (
        "developers/manifests/docs-rebuild-quad-lane-batch-002.v1.json",
        "execution_sha256",
        "68b37afe3b41f83040b6b349d97b1036f7ba36ee809c02ef9a0a7308bc561441",
    ),
    (
        "developers/manifests/docs-rebuild-quad-lane-batch-003.v1.json",
        "execution_sha256",
        "fc69af9604f118809095de6af32cebbbcb25a320dc9c708e3cca2101d1620549",
    ),
    (
        "developers/manifests/docs-wave7-melanin-magic-substantive-gate-003.v1.json",
        "gate_sha256",
        "6104d57c4c99a741e4c3ef8ebf7e074862b403d6edd7e8289f90ea47369b817e",
    ),
    (
        "developers/manifests/docs-rebuild-quad-lane-batch-004.v1.json",
        "execution_sha256",
        "fb4f2747ff0dc98c0f679815c459969c6745dfe9137c06774ae3062c87306d8a",
    ),
    (
        "developers/manifests/docs-wave7-substantive-gate-004.v1.json",
        "gate_sha256",
        "c9bcad7aa82e75c5dd9b7730f1488d5143f46c91f103eef5c415b5910f039310",
    ),
)


class Wave7HistoricalBaselineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.snapshot = current_snapshot.load_snapshot()

    def test_reconstructs_immutable_61_from_current_57_plus_four_remaps(self) -> None:
        prior = quad_lane.prior_ids()
        current = {
            inventory_id
            for wave in self.snapshot["current_waves"].values()
            for inventory_id in wave["selected_inventory_ids"]
        }
        remap = {
            record["inventory_id"]
            for record in self.snapshot["historical_wave_1_current_remap_required"]
        }

        self.assertEqual(len(current), 57)
        self.assertEqual(
            remap,
            {"HC-0072", "HC-0073", "HC-0074", "HC-0211"},
        )
        self.assertFalse(current & remap)
        self.assertEqual(prior, current | remap)
        self.assertEqual(len(prior), 61)

    def test_fails_closed_on_current_count_drift(self) -> None:
        drifted = copy.deepcopy(self.snapshot)
        drifted["current_waves"]["6"]["selected_inventory_ids"].pop()
        drifted_without_sha = {
            key: value for key, value in drifted.items() if key != "snapshot_sha256"
        }
        drifted["snapshot_sha256"] = current_snapshot.canonical_sha(drifted_without_sha)

        with mock.patch.object(quad_lane.current_snapshot, "load_snapshot", return_value=drifted):
            with self.assertRaisesRegex(ValueError, "count drift"):
                quad_lane.prior_ids()

    def test_fails_closed_on_remap_state_drift(self) -> None:
        drifted = copy.deepcopy(self.snapshot)
        drifted["historical_wave_1_current_remap_required"][0][
            "current_semantic_state"
        ] = "selected"
        drifted_without_sha = {
            key: value for key, value in drifted.items() if key != "snapshot_sha256"
        }
        drifted["snapshot_sha256"] = current_snapshot.canonical_sha(drifted_without_sha)

        with mock.patch.object(quad_lane.current_snapshot, "load_snapshot", return_value=drifted):
            with self.assertRaisesRegex(ValueError, "current semantic remap state drift"):
                quad_lane.prior_ids()

    def test_fails_closed_on_snapshot_digest_drift(self) -> None:
        drifted = copy.deepcopy(self.snapshot)
        drifted["snapshot_sha256"] = "0" * 64

        with mock.patch.object(quad_lane.current_snapshot, "load_snapshot", return_value=drifted):
            with self.assertRaisesRegex(ValueError, "snapshot digest drift"):
                quad_lane.prior_ids()

    def test_immutable_historical_receipt_digests(self) -> None:
        for receipt_path, digest_key, expected_digest in RECEIPT_DIGESTS:
            with self.subTest(receipt=receipt_path):
                receipt = json.loads((ROOT / receipt_path).read_text(encoding="utf-8"))
                self.assertEqual(receipt[digest_key], expected_digest)


if __name__ == "__main__":
    unittest.main()

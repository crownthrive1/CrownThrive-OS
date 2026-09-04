from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = (
    ROOT
    / "data"
    / "penta"
    / "source-custody"
    / "stripe-os-runtime-repair.20260901.v1.json"
)
MIGRATIONS = ROOT / "supabase" / "migrations"
HISTORICAL_CRON_PATH = (
    MIGRATIONS / "20260901015101_pentagreen_stripe_autowire_v1.sql"
)
HARD_CODED_CRON_146 = re.compile(
    r"cron\.unschedule\s*\(\s*jobid\s*\)\s+from\s+cron\.job\s+"
    r"where\s+jobid\s*=\s*146\b",
    re.IGNORECASE,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class StripeRuntimeSourceCustodyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_manifest_fails_closed_on_replay_and_main_merge(self) -> None:
        data = self.manifest
        self.assertEqual(
            data["record_id"],
            "ct.source-custody.stripe-os-runtime-repair.20260901.v1",
        )
        self.assertFalse(data["production_history_rewritten"])
        self.assertFalse(data["replay_attempted"])
        self.assertFalse(data["raw_secrets_in_source"])
        self.assertFalse(data["authority_created"])

        debt = data["replay_debt"]
        self.assertFalse(debt["source_history_self_contained"])
        self.assertFalse(debt["fresh_clone_replayable"])
        self.assertFalse(debt["clone_ready_claim_allowed"])
        self.assertEqual(debt["current_state"], "BLOCKED")
        self.assertEqual(debt["main_merge_gate"], "BLOCK")
        self.assertGreaterEqual(len(debt["unblock_requires"]), 5)

    def test_runtime_readback_preserves_paused_zero_ready_truth(self) -> None:
        readback = self.manifest["runtime_readback"]
        self.assertEqual(
            readback["state"],
            "RUNTIME_REPAIRED_FACTORY_PAUSED_GOVERNED_GATES",
        )
        self.assertFalse(readback["factory_clock_active"])
        self.assertEqual(readback["live_clock_rows"], 0)
        self.assertEqual(readback["factory_ready_candidates"], 0)
        self.assertEqual(readback["provider_adapter_api_roles"], [])
        self.assertTrue(readback["money_movement_separately_gated"])

    def test_original_provider_history_fingerprints_and_gaps_are_exact(self) -> None:
        expected = {
            "20260901021427": (
                "stripe_runtime_adapter_commerce_binder_v1",
                "88629070f15a9ab0baff33b8165a573b598ad0a9c70635723b9a489ec5328757",
                "DIVERGENT_FROM_PROVIDER_STATEMENT",
            ),
            "20260901021754": (
                "stripe_secondary_runtime_reactivation_v2",
                "9b3c3dd68fd2de2abe5e07cec42680ba8b1c3d377242cd734c9921db478aa1ba",
                "MISSING_EXACT_SOURCE",
            ),
            "20260901022028": (
                "pentagreen_stripe_clock_topology_supersession_v1",
                "6d810b5386bd53abeeaf594312cb4e09a6df035d42395e3647b796c1803aa3d8",
                "MISSING_EXACT_SOURCE",
            ),
            "20260901022200": (
                "stripe_secondary_runtime_lane_canonicalization_v3",
                "a9da1f16b009ecf72df2ce72167a8e8a00b748fe9591608e72e189f7536dac78",
                "MISSING_EXACT_SOURCE",
            ),
            "20260901022658": (
                "stripe_os_runtime_topology_convergence_v1",
                "4adb2ea90d35bb048edb90f401e948f3c26bccc5e0f2520be5973914a70e6781",
                "MISSING_EXACT_SOURCE_NON_EXACT_PROJECTION_PRESENT",
            ),
        }
        actual = {
            row["provider_version"]: (
                row["name"],
                row["provider_statement_sha256"],
                row["source_custody_state"],
            )
            for row in self.manifest["original_provider_history"]
        }
        self.assertEqual(actual, expected)

        divergent = self.manifest["original_provider_history"][0]
        divergent_path = ROOT / divergent["repository_path"]
        self.assertEqual(sha256(divergent_path), divergent["repository_file_sha256"])
        self.assertNotEqual(
            divergent["provider_statement_sha256"],
            divergent["repository_file_sha256"],
        )

    def test_repair_files_are_bound_to_exact_provider_versions(self) -> None:
        repairs = {
            row["provider_version"]: row for row in self.manifest["repair_lineage"]
        }
        self.assertEqual(
            set(repairs),
            {
                "20260901024135",
                "20260901024551",
                "20260901025133",
                "20260901025747",
            },
        )
        for version, row in repairs.items():
            path = ROOT / row["repository_path"]
            self.assertTrue(path.is_file(), version)
            self.assertEqual(sha256(path), row["repository_file_sha256"], version)
            self.assertTrue(path.name.startswith(f"{version}_"), version)

        for version in (
            "20260901024135",
            "20260901024551",
            "20260901025133",
            "20260901025747",
        ):
            row = repairs[version]
            self.assertEqual(
                row["repository_file_sha256"],
                row["provider_statement_sha256"],
                version,
            )
            self.assertEqual(
                row["source_custody_state"], "EXACT_PROVIDER_STATEMENT_CAPTURE"
            )

    def test_hard_coded_cron_146_is_declared_and_not_repeated(self) -> None:
        offenders = []
        for path in MIGRATIONS.glob("*.sql"):
            if HARD_CODED_CRON_146.search(path.read_text(encoding="utf-8")):
                offenders.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(
            offenders,
            [HISTORICAL_CRON_PATH.relative_to(ROOT).as_posix()],
        )

        hazards = self.manifest["replay_debt"]["known_static_hazards"]
        self.assertEqual(len(hazards), 1)
        hazard = hazards[0]
        self.assertEqual(hazard["path"], offenders[0])
        self.assertEqual(hazard["replay_disposition"], "BLOCK")
        self.assertFalse(hazard["historical_source_edit_allowed"])

        for repair in self.manifest["repair_lineage"]:
            repair_text = (ROOT / repair["repository_path"]).read_text(encoding="utf-8")
            self.assertIsNone(
                HARD_CODED_CRON_146.search(repair_text), repair["provider_version"]
            )

    def test_manifest_contains_no_stripe_secret_material(self) -> None:
        serialized = json.dumps(self.manifest, sort_keys=True)
        for token_prefix in ("sk_live_", "rk_live_", "whsec_", "sk_test_", "rk_test_"):
            self.assertNotIn(token_prefix, serialized)


if __name__ == "__main__":
    unittest.main()

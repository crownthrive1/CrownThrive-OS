from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import penta_gap_closure as gap


class PentaGapClosureAdvisoryStaleTests(unittest.TestCase):
    def test_removed_registered_alias_is_advisory_not_blocking(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        manifest_path = root / gap.REGISTRY
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "owner": "crownthrive_os_convergence",
                    "category_policy": {
                        "historical_alias_evidence": "historical",
                        "current_record_contextual_reference": "current",
                    },
                    "dispositions": {
                        "historical_alias_evidence": [],
                        "current_record_contextual_reference": [
                            {
                                "path": "removed.yml",
                                "retired_alias_hits": 1,
                                "stale_current_claim_hits": 0,
                            }
                        ],
                    },
                }
            ),
            encoding="utf-8",
        )
        summary, status = gap.scan(root)
        self.assertEqual(status, 0)
        self.assertEqual(summary["counts"]["STALE_REGISTRATION"], 1)
        self.assertEqual(summary["blocking_findings"], 0)
        self.assertEqual(summary["stale_registration_policy"], "ADVISORY_CLEANUP")

    def test_new_unregistered_alias_still_blocks(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        retired_phase = "Phase " + "2.99"
        (root / "unexpected.mdx").write_text(
            f"This current record unexpectedly refers to {retired_phase}.",
            encoding="utf-8",
        )
        manifest_path = root / gap.REGISTRY
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "owner": "crownthrive_os_convergence",
                    "category_policy": {
                        "historical_alias_evidence": "historical",
                        "current_record_contextual_reference": "current",
                    },
                    "dispositions": {
                        "historical_alias_evidence": [],
                        "current_record_contextual_reference": [],
                    },
                }
            ),
            encoding="utf-8",
        )
        summary, status = gap.scan(root)
        self.assertEqual(status, 2)
        self.assertEqual(summary["counts"]["REVIEW_CONTEXT"], 1)


if __name__ == "__main__":
    unittest.main()

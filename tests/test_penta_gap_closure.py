from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import penta_gap_closure as gap


class PentaGapClosureTests(unittest.TestCase):
    def make_root(self, category: str, content: str, *, aliases: int, stale: int) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        target = root / "record.mdx"
        target.write_text(content, encoding="utf-8")
        manifest_path = root / gap.REGISTRY
        manifest_path.parent.mkdir(parents=True)
        categories = {
            "historical_alias_evidence": [],
            "current_record_contextual_reference": [],
        }
        categories[category].append(
            {
                "path": "record.mdx",
                "retired_alias_hits": aliases,
                "stale_current_claim_hits": stale,
            }
        )
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "owner": "crownthrive_os_convergence",
                    "category_policy": {key: key for key in categories},
                    "dispositions": categories,
                }
            ),
            encoding="utf-8",
        )
        return root

    def test_exact_registered_context_passes(self) -> None:
        root = self.make_root(
            "current_record_contextual_reference",
            "This record explains why Phase 2.99 is a retired historical alias.",
            aliases=1,
            stale=0,
        )
        summary, status = gap.scan(root)
        self.assertEqual(status, 0)
        self.assertEqual(summary["findings"], [])

    def test_alias_count_drift_blocks(self) -> None:
        root = self.make_root(
            "current_record_contextual_reference",
            "Phase 2.99 is referenced once.",
            aliases=1,
            stale=0,
        )
        (root / "record.mdx").write_text(
            "Phase 2.99 is referenced once, then Phase 2.99 is referenced again.",
            encoding="utf-8",
        )
        summary, status = gap.scan(root)
        self.assertEqual(status, 2)
        self.assertEqual(summary["counts"]["REVIEW_CONTEXT"], 1)

    def test_stale_current_claim_in_active_record_blocks(self) -> None:
        root = self.make_root(
            "current_record_contextual_reference",
            "Current institutional phase remains Phase 2.99.",
            aliases=1,
            stale=1,
        )
        summary, status = gap.scan(root)
        self.assertEqual(status, 2)
        self.assertEqual(summary["counts"]["REPAIR_REQUIRED"], 1)

    def test_retired_phase_metadata_in_active_record_blocks(self) -> None:
        root = self.make_root(
            "current_record_contextual_reference",
            "**Phase:** 2.99\n",
            aliases=1,
            stale=1,
        )
        summary, status = gap.scan(root)
        self.assertEqual(status, 2)
        self.assertEqual(summary["counts"]["REPAIR_REQUIRED"], 1)

    def test_retired_phase_gate_language_in_active_record_blocks(self) -> None:
        root = self.make_root(
            "current_record_contextual_reference",
            "The gate evaluates Phase 2.99 after every material continuation.",
            aliases=1,
            stale=1,
        )
        summary, status = gap.scan(root)
        self.assertEqual(status, 2)
        self.assertEqual(summary["counts"]["REPAIR_REQUIRED"], 1)

    def test_historical_record_must_keep_historical_overlay(self) -> None:
        root = self.make_root(
            "historical_alias_evidence",
            "Phase 2.99 source snapshot.",
            aliases=1,
            stale=0,
        )
        summary, status = gap.scan(root)
        self.assertEqual(status, 2)
        self.assertEqual(summary["counts"]["REPAIR_REQUIRED"], 1)

    def test_generated_v2_orientation_does_not_manufacture_alias_hits(self) -> None:
        quality = gap.pentadocs_quality
        retired_phase = "Phase " + "2.99"
        profile = quality.PageProfile(
            route="record",
            path="record.mdx",
            navigation_context=(),
            primary_audience="historical",
            page_type="historical_record",
            content_state="historical",
            orientation_component="Warning",
            role_links=(
                "/start-here/current-operational-state",
                "/knowledge/source-authority-hierarchy",
            ),
        )
        orientation = quality.orientation_block(
            profile,
            f"{retired_phase} source",
            f"{retired_phase} evidence.",
        )
        content = f"""---
title: "{retired_phase} source"
description: "{retired_phase} evidence."
standard_version: "1.0.0"
primary_audience: "historical"
page_type: "historical_record"
content_state: "historical"
---

{orientation}

## Preserved body

{retired_phase} source snapshot.
"""
        root = self.make_root(
            "historical_alias_evidence",
            content,
            aliases=3,
            stale=0,
        )
        summary, status = gap.scan(root)
        self.assertEqual(status, 0)
        self.assertEqual(summary["findings"], [])

    def test_custom_v2_keeps_custom_prose_but_strips_generated_supplement(self) -> None:
        quality = gap.pentadocs_quality
        retired_phase = "Phase " + "2.99"
        profile = quality.PageProfile(
            route="record",
            path="record.mdx",
            navigation_context=(),
            primary_audience="historical",
            page_type="historical_record",
            content_state="historical",
            orientation_component="Warning",
            role_links=(
                "/start-here/current-operational-state",
                "/knowledge/source-authority-hierarchy",
            ),
        )
        generated = quality.orientation_block(
            profile,
            f"{retired_phase} source",
            f"{retired_phase} evidence.",
        )
        custom = generated.replace(
            "  **Audience:** governance reviewers and researchers (`historical`).",
            "  **Audience:** archive reviewers. Custom lineage prose remains.",
            1,
        )
        content = f"""---
title: "{retired_phase} source"
description: "{retired_phase} evidence."
standard_version: "1.0.0"
primary_audience: "historical"
page_type: "historical_record"
content_state: "historical"
---

{custom}

{retired_phase} source snapshot.
"""
        normalized = gap.substantive_wave1.normalize_pentadocs_envelope(content)
        self.assertIn("Custom lineage prose remains", normalized)
        self.assertNotIn("**This page:**", normalized)
        root = self.make_root(
            "historical_alias_evidence",
            content,
            aliases=3,
            stale=0,
        )
        summary, status = gap.scan(root)
        self.assertEqual(status, 0)
        self.assertEqual(summary["findings"], [])

    def test_recovered_evidence_is_explicit_historical_context(self) -> None:
        retired_phase = "Phase " + "2.99"
        root = self.make_root(
            "historical_alias_evidence",
            f"Recovered requirements from {retired_phase}; not current authority.",
            aliases=1,
            stale=0,
        )
        summary, status = gap.scan(root)
        self.assertEqual(status, 0)
        self.assertEqual(summary["findings"], [])


if __name__ == "__main__":
    unittest.main()

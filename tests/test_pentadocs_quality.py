from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from scripts import build_substantive_rebuild_wave1 as substantive_wave1
from scripts import build_substantive_rebuild_wave2 as substantive_wave2
from scripts import build_substantive_rebuild_wave3 as substantive_wave3
from scripts import build_substantive_rebuild_wave4 as substantive_wave4
from scripts import build_substantive_rebuild_wave5 as substantive_wave5
from scripts import build_substantive_rebuild_wave6 as substantive_wave6
from scripts import pentadocs_quality as quality


class PentaDocsQualityTests(unittest.TestCase):
    def make_root(self, *, include_index: bool = False) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        routes: list[object] = [
            {
                "group": "Developer Platform",
                "pages": ["developers/example"],
            },
            {
                "group": "Changelog and Decisions",
                "pages": ["changelog/example-event"],
            },
            {
                "group": "Compatibility",
                "pages": ["legacy-route"],
            },
        ]
        if include_index:
            routes.insert(0, {"group": "Start Here", "pages": ["index"]})
        docs = {
            "navigation": {
                "tabs": [
                    {
                        "tab": "CrownThrive OS",
                        "pages": routes,
                    }
                ]
            },
            "redirects": [
                {
                    "source": "/legacy-route",
                    "destination": "/developers/example",
                    "permanent": True,
                }
            ],
        }
        (root / "docs.json").write_text(json.dumps(docs), encoding="utf-8")
        unlisted_path = root / quality.UNLISTED_DISPOSITIONS_PATH
        unlisted_path.parent.mkdir(parents=True)
        unlisted_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "dispositions": {
                        category: []
                        for category in sorted(quality.UNLISTED_DISPOSITION_CATEGORIES)
                    },
                }
            ),
            encoding="utf-8",
        )
        (root / "developers").mkdir(exist_ok=True)
        (root / "developers/example.mdx").write_text(
            """---
title: "Example Developer Guide"
description: "A public-safe fixture for developer documentation."
---

# Example Developer Guide

<CardGroup cols={2}>
  <Card title="One" href="/developers/example">One</Card>
</CardGroup>

```md
# Fenced example remains an H1 example
<CardGroup cols={4}>
```
""",
            encoding="utf-8",
        )
        (root / "changelog").mkdir()
        (root / "changelog/example-event.mdx").write_text(
            """---
title: "Example Historical Event"
description: "A dated fixture that requires an authority boundary."
---

# Example Historical Event

This fixture preserves a dated event without asserting current state.
""",
            encoding="utf-8",
        )
        (root / "legacy-route.mdx").write_text(
            """---
title: "Legacy Route"
description: "Compatibility route for a canonical developer page."
deprecated: true
noindex: true
---

# Legacy Route

Continue to [the canonical page](/developers/example).
""",
            encoding="utf-8",
        )
        if include_index:
            (root / "index.mdx").write_text(
                """---
title: "Fixture Home"
description: "A fixture homepage with a compatibility body H1."
---

# Fixture Home

Homepage body.
""",
                encoding="utf-8",
            )
        fixture_targets = {
            target
            for candidates in tuple(quality.ROLE_LINKS.values())
            + (quality.UNRESOLVED_GOVERNING_LINKS,)
            for _label, target in candidates
        }
        for target in fixture_targets:
            target_path = root / f"{target.strip('/')}.mdx"
            if target_path.is_file():
                continue
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text("Fixture link target.\n", encoding="utf-8")
        return root

    def test_apply_is_idempotent_and_fence_aware(self) -> None:
        root = self.make_root()

        first = quality.apply_repository(root)
        errors, stats = quality.validate_repository(root)
        self.assertEqual(errors, [])
        self.assertEqual(stats["navigation_pages"], 3)
        self.assertEqual(stats["standard_pages"], 3)
        self.assertGreater(first["changed_files"], 0)

        developer = (root / "developers/example.mdx").read_text(encoding="utf-8")
        self.assertIn('standard_version: "1.0.0"', developer)
        self.assertIn('primary_audience: "developer"', developer)
        self.assertIn(quality.ORIENTATION_MARKER, developer)
        self.assertIn("<Columns cols={2}>", developer)
        self.assertIn("## Example Developer Guide", developer)
        self.assertIn("# Fenced example remains an H1 example", developer)
        self.assertIn("<CardGroup cols={4}>", developer)

        snapshot = {
            path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
            for path in root.rglob("*")
            if path.is_file()
        }
        second = quality.apply_repository(root)
        self.assertEqual(second["changed_files"], 0)
        self.assertEqual(
            snapshot,
            {
                path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
                for path in root.rglob("*")
                if path.is_file()
            },
        )

    def test_missing_metadata_and_relative_link_fail(self) -> None:
        root = self.make_root()
        quality.apply_repository(root)
        path = root / "developers/example.mdx"
        text = path.read_text(encoding="utf-8")
        text = text.replace('primary_audience: "developer"\n', "", 1)
        text += "\n[Relative link](../other-page)\n[Protocol-relative link](//example.test/path)\n"
        path.write_text(text, encoding="utf-8")

        errors, _stats = quality.validate_repository(root)
        joined = "\n".join(errors)
        self.assertIn("missing frontmatter field primary_audience", joined)
        self.assertIn("internal link must be root-relative", joined)
        self.assertIn("protocol-relative link is not allowed", joined)

    def test_tailored_v1_orientation_is_registered_and_preserved_as_custom_v2(self) -> None:
        root = self.make_root()
        path = root / "developers/example.mdx"
        text = path.read_text(encoding="utf-8")
        parsed = quality.split_frontmatter(text)
        assert parsed is not None
        tailored = f"""{quality.LEGACY_ORIENTATION_MARKER}
<Info>
  **Audience:** SDK maintainers and integration reviewers. Use the [API standard](/technology/api-integration-standards) and [release workflow](/workflows/product-release).
</Info>"""
        path.write_text(
            f"---\n{parsed[0]}\n---\n\n{tailored}\n\n{parsed[1]}",
            encoding="utf-8",
        )

        quality.apply_repository(root)

        errors, _stats = quality.validate_repository(root)
        self.assertEqual(errors, [])
        updated = path.read_text(encoding="utf-8")
        self.assertIn("SDK maintainers and integration reviewers", updated)
        self.assertIn(quality.ORIENTATION_MARKER, updated)
        self.assertIn("**This page:**", updated)
        self.assertIn("**Documentation state:**", updated)
        manifest = json.loads((root / quality.PROFILE_PATH).read_text(encoding="utf-8"))
        record = next(item for item in manifest["profiles"] if item["route"] == "developers/example")
        self.assertEqual(record["orientation_mode"], quality.ORIENTATION_MODE_CUSTOM)
        normalized = substantive_wave1.normalize_pentadocs_envelope(updated)
        self.assertIn("SDK maintainers and integration reviewers", normalized)
        self.assertNotIn("**This page:**", normalized)
        self.assertNotIn("**Documentation state:**", normalized)
        self.assertNotIn("**Unresolved reason:**", normalized)

    def test_live_h1_and_cardgroup_fail_but_fenced_examples_do_not(self) -> None:
        root = self.make_root()
        quality.apply_repository(root)
        path = root / "developers/example.mdx"
        text = path.read_text(encoding="utf-8")
        text += "\n# Live H1\n\n<CardGroup cols={2}>\n</CardGroup>\n"
        path.write_text(text, encoding="utf-8")

        errors, _stats = quality.validate_repository(root)
        joined = "\n".join(errors)
        self.assertIn("body H1 remains outside fenced code", joined)
        self.assertIn("deprecated CardGroup remains outside a fenced example", joined)

    def test_historical_page_requires_warning_and_boundary(self) -> None:
        root = self.make_root()
        quality.apply_repository(root)
        path = root / "changelog/example-event.mdx"
        text = path.read_text(encoding="utf-8").replace(
            quality.HISTORICAL_BOUNDARY,
            "a dated record",
            1,
        )
        path.write_text(text, encoding="utf-8")

        errors, _stats = quality.validate_repository(root)
        self.assertIn(
            "historical or superseded page lacks explicit non-current authority boundary",
            "\n".join(errors),
        )

    def test_typed_redirect_is_exempt_but_fail_closed(self) -> None:
        root = self.make_root()
        quality.apply_repository(root)
        redirect = root / "legacy-route.mdx"
        text = redirect.read_text(encoding="utf-8")
        self.assertNotIn(quality.ORIENTATION_MARKER, text)
        self.assertIn("# Legacy Route", text)

        text = text.replace("deprecated: true\n", "", 1)
        redirect.write_text(text, encoding="utf-8")
        errors, _stats = quality.validate_repository(root)
        self.assertIn("typed redirect must set deprecated: true", "\n".join(errors))

    def test_unlisted_typed_redirect_source_remains_governed(self) -> None:
        root = self.make_root()
        quality.apply_repository(root)
        docs_path = root / "docs.json"
        docs = json.loads(docs_path.read_text(encoding="utf-8"))
        groups = docs["navigation"]["tabs"][0]["pages"]
        docs["navigation"]["tabs"][0]["pages"] = [
            group for group in groups if group.get("group") != "Compatibility"
        ]
        docs_path.write_text(json.dumps(docs), encoding="utf-8")
        disposition_path = root / quality.UNLISTED_DISPOSITIONS_PATH
        dispositions = json.loads(disposition_path.read_text(encoding="utf-8"))
        dispositions["dispositions"]["operational_reference_direct_link"].append(
            "legacy-route.mdx"
        )
        disposition_path.write_text(json.dumps(dispositions), encoding="utf-8")
        quality.apply_repository(root)

        errors, stats = quality.validate_repository(root)
        self.assertEqual(errors, [])
        self.assertEqual(stats["navigation_pages"], 2)
        self.assertEqual(stats["governed_unlisted_pages"], 1)
        self.assertEqual(stats["governed_pages"], 3)
        self.assertEqual(stats["redirect_pages"], 1)

        redirect = root / "legacy-route.mdx"
        text = redirect.read_text(encoding="utf-8").replace(
            'content_state: "superseded"',
            'content_state: "unresolved"',
            1,
        )
        redirect.write_text(text, encoding="utf-8")
        errors, _stats = quality.validate_repository(root)
        self.assertIn(
            "typed redirect must set content_state: superseded",
            "\n".join(errors),
        )

    def test_governed_unlisted_historical_evidence_is_profiled(self) -> None:
        root = self.make_root()
        historical = root / "evidence/example-build.mdx"
        historical.parent.mkdir()
        historical.write_text(
            """---
title: "Example build evidence"
description: "A dated build-evidence fixture."
---

# Example build evidence

This fixture is retained to reproduce a dated build result.
""",
            encoding="utf-8",
        )
        disposition_path = root / quality.UNLISTED_DISPOSITIONS_PATH
        dispositions = json.loads(disposition_path.read_text(encoding="utf-8"))
        dispositions["dispositions"]["generated_build_evidence"].append(
            "evidence/example-build.mdx"
        )
        disposition_path.write_text(json.dumps(dispositions), encoding="utf-8")

        receipt = quality.apply_repository(root)
        errors, stats = quality.validate_repository(root)
        self.assertEqual(errors, [])
        self.assertEqual(receipt["navigation_pages"], 3)
        self.assertEqual(receipt["governed_unlisted_pages"], 1)
        self.assertEqual(stats["governed_pages"], 4)
        text = historical.read_text(encoding="utf-8")
        self.assertIn('primary_audience: "historical"', text)
        self.assertIn('page_type: "historical_record"', text)
        self.assertIn('content_state: "historical"', text)
        self.assertIn("<Warning>", text)
        self.assertIn(quality.HISTORICAL_BOUNDARY, text)
        manifest = json.loads((root / quality.PROFILE_PATH).read_text(encoding="utf-8"))
        self.assertEqual(manifest["navigation_page_count"], 3)
        self.assertEqual(manifest["governed_unlisted_page_count"], 1)
        self.assertEqual(manifest["governed_page_count"], 4)
        record = next(
            profile
            for profile in manifest["profiles"]
            if profile["route"] == "evidence/example-build"
        )
        self.assertEqual(record["governance_scope"], "governed_unlisted")
        self.assertEqual(record["disposition"], "generated_build_evidence")

    def test_index_body_h1_is_demoted_with_other_standard_pages(self) -> None:
        root = self.make_root(include_index=True)
        quality.apply_repository(root)
        index = (root / "index.mdx").read_text(encoding="utf-8")
        self.assertIn("## Fixture Home", index)
        self.assertNotIn("\n# Fixture Home", index)
        errors, _stats = quality.validate_repository(root)
        self.assertEqual(errors, [])

    def test_representative_route_audiences_are_deterministic(self) -> None:
        cases = {
            "commerce/rails": "operator",
            "platforms/example-registry": "executive",
            "revenue/acquisition-and-distribution": "executive",
            "governance/model": "executive",
            "doctrine/convergent-ecosystem": "executive",
            "ecosystem/map": "executive",
            "portfolio/operating-rhythm": "executive",
            "knowledge/source-authority-hierarchy": "operator",
            "standards/evidence-claims-and-proof-standard": "operator",
            "automation/command-structure": "operator",
            "workflows/product-release": "operator",
            "runbooks/production-deployment-and-rollback": "operator",
            "support/support-operating-model": "rights_support",
            "developers/overview": "developer",
            "technology/api-integration-standards": "developer",
            "chlom/rights-ledger-and-evidence": "rights_support",
            "chlom/compliance-as-code": "rights_support",
            "chlom/fingerprint-ids": "developer",
            "chlom/pentafabric": "executive",
            "start-here/orientation": "public",
            "about/kavonte-jones-sr": "public",
            "corridors/media-culture": "public",
        }
        for route, expected in cases.items():
            with self.subTest(route=route):
                self.assertEqual(
                    quality.infer_audience(route, (), "reference"),
                    expected,
                )
        self.assertEqual(
            quality.infer_audience("changelog/example", (), "changelog"),
            "historical",
        )

    def test_profile_manifest_drift_fails(self) -> None:
        root = self.make_root()
        quality.apply_repository(root)
        path = root / quality.PROFILE_PATH
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["navigation_page_count"] = 999
        path.write_text(json.dumps(manifest), encoding="utf-8")

        errors, _stats = quality.validate_repository(root)
        self.assertIn("navigation_page_count=999", "\n".join(errors))

    def test_v2_escaping_hash_drift_and_unicode_normalization(self) -> None:
        profile = quality.PageProfile(
            route="developers/example",
            path="developers/example.mdx",
            navigation_context=("Developers",),
            primary_audience="developer",
            page_type="developer",
            content_state="current_with_holds",
            orientation_component="Note",
            role_links=("/developers/overview", "/technology/api-integration-standards"),
        )
        links = quality.link_records_for_profile(profile)
        hostile = "A & <Danger> {/* x */} \\ ` * _ [x](y) ! | # $ ~\nnext"
        rendered = quality.orientation_block(profile, hostile, hostile, links)
        self.assertNotIn("<Danger>", rendered)
        self.assertNotIn("{/* x */}", rendered)
        for entity in (
            "&amp;",
            "&lt;",
            "&#123;",
            "&#92;",
            "&#96;",
            "&#42;",
            "&#95;",
            "&#91;",
            "&#40;",
            "&#33;",
            "&#124;",
            "&#35;",
            "&#36;",
            "&#126;",
        ):
            self.assertIn(entity, rendered)

        base = quality.orientation_input_sha256(profile, "Cafe\u0301", "  Fixture\ntext  ", links)
        self.assertEqual(
            base,
            quality.orientation_input_sha256(profile, "Café", "Fixture text", links),
        )
        variants = (
            (replace(profile, primary_audience="operator"), "Café", "Fixture text", links),
            (replace(profile, page_type="reference"), "Café", "Fixture text", links),
            (replace(profile, content_state="candidate"), "Café", "Fixture text", links),
            (profile, "Different", "Fixture text", links),
            (profile, "Café", "Different", links),
            (profile, "Café", "Fixture text", tuple(reversed(links))),
        )
        for variant_profile, title, description, variant_links in variants:
            with self.subTest(title=title, description=description, profile=variant_profile):
                self.assertNotEqual(
                    base,
                    quality.orientation_input_sha256(
                        variant_profile,
                        title,
                        description,
                        variant_links,
                    ),
                )

    def test_managed_hash_drift_updates_only_envelope_and_remains_idempotent(self) -> None:
        root = self.make_root()
        quality.apply_repository(root)
        path = root / "developers/example.mdx"
        before = path.read_text(encoding="utf-8")
        before_tail = before.split(quality.ORIENTATION_END_MARKER, 1)[1]
        manifest = json.loads((root / quality.PROFILE_PATH).read_text(encoding="utf-8"))
        before_hash = next(
            item["orientation_input_sha256"]
            for item in manifest["profiles"]
            if item["route"] == "developers/example"
        )

        path.write_text(
            before.replace('title: "Example Developer Guide"', 'title: "Renamed Developer Guide"', 1),
            encoding="utf-8",
        )
        errors, _stats = quality.validate_repository(root)
        self.assertIn("managed v2 audience orientation drifted", "\n".join(errors))
        first = quality.apply_repository(root)
        self.assertIn("developers/example.mdx", first["changed_paths"])
        after = path.read_text(encoding="utf-8")
        self.assertEqual(before_tail, after.split(quality.ORIENTATION_END_MARKER, 1)[1])
        manifest = json.loads((root / quality.PROFILE_PATH).read_text(encoding="utf-8"))
        after_hash = next(
            item["orientation_input_sha256"]
            for item in manifest["profiles"]
            if item["route"] == "developers/example"
        )
        self.assertNotEqual(before_hash, after_hash)
        self.assertEqual(quality.apply_repository(root)["changed_files"], 0)

    def test_managed_human_edit_requires_custom_override(self) -> None:
        root = self.make_root()
        quality.apply_repository(root)
        path = root / "developers/example.mdx"
        text = path.read_text(encoding="utf-8").replace(
            "builders and integrators",
            "manually edited audience",
            1,
        )
        path.write_text(text, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "edited without a custom profile override"):
            quality.apply_repository(root)

    def test_self_link_fallback_and_zero_orientation_metrics(self) -> None:
        root = self.make_root()
        values = {
            "title": "Start",
            "description": "Start fixture.",
            "primary_audience": "public",
            "page_type": "orientation",
            "content_state": "current",
        }
        profile = quality.profile_for_page(
            "start-here/orientation",
            (),
            values,
            {},
            root=root,
        )
        self.assertEqual(len(profile.role_links), 2)
        self.assertNotIn("/start-here/orientation", profile.role_links)

        quality.apply_repository(root)
        errors, stats = quality.validate_repository(root)
        self.assertEqual(errors, [])
        self.assertEqual(stats["page_specific_orientation_rate"], 1.0)
        self.assertEqual(stats["generic_v1_orientation_pages"], 0)
        self.assertEqual(stats["orientation_self_link_pages"], 0)
        self.assertEqual(stats["orientation_input_collision_groups"], 0)
        self.assertEqual(stats["orientation_render_collision_groups"], 0)
        manifest = json.loads((root / quality.PROFILE_PATH).read_text(encoding="utf-8"))
        self.assertEqual(manifest["orientation_metrics"]["page_specific_orientation_rate"], 1.0)
        self.assertEqual(manifest["orientation_metrics"]["generic_v1_page_count"], 0)
        self.assertEqual(manifest["orientation_metrics"]["self_link_page_count"], 0)
        self.assertEqual(manifest["orientation_metrics"]["invalid_link_page_count"], 0)

    def test_orientation_collisions_fail_closed(self) -> None:
        root = self.make_root()
        docs_path = root / "docs.json"
        docs = json.loads(docs_path.read_text(encoding="utf-8"))
        docs["navigation"]["tabs"][0]["pages"][0]["pages"].append(
            "developers/example-copy"
        )
        docs_path.write_text(json.dumps(docs), encoding="utf-8")
        source = (root / "developers/example.mdx").read_text(encoding="utf-8")
        (root / "developers/example-copy.mdx").write_text(source, encoding="utf-8")

        quality.apply_repository(root)
        errors, stats = quality.validate_repository(root)
        self.assertIn("orientation input hashes collide", "\n".join(errors))
        self.assertIn("rendered orientations collide", "\n".join(errors))
        self.assertEqual(stats["orientation_input_collision_groups"], 1)
        self.assertEqual(stats["orientation_render_collision_groups"], 1)

    def test_unresolved_contradiction_requires_structured_explanation(self) -> None:
        root = self.make_root()
        quality.apply_repository(root)
        path = root / "developers/example.mdx"
        text = path.read_text(encoding="utf-8")
        text = text.replace(
            f"  **Review trigger:** {quality.UNRESOLVED_REVIEW_TRIGGER}.\n\n",
            "",
            1,
        )
        text = text.replace(
            quality.UNRESOLVED_EVIDENCE,
            "any available note",
            1,
        )
        text += "\n## Current authority\n\nCanonical fixture wording.\n"
        path.write_text(text, encoding="utf-8")
        errors, _stats = quality.validate_repository(root)
        self.assertIn(
            "without a structured page-authority explanation",
            "\n".join(errors),
        )
        self.assertIn("lacks governed Evidence needed text", "\n".join(errors))

    def test_structural_preflight_prevents_partial_migration(self) -> None:
        root = self.make_root()
        before = (root / "developers/example.mdx").read_text(encoding="utf-8")
        broken = root / "evidence/broken.mdx"
        broken.parent.mkdir()
        broken.write_text("---\ntitle: \"Broken evidence\"\n---\n\n# Broken\n", encoding="utf-8")
        disposition_path = root / quality.UNLISTED_DISPOSITIONS_PATH
        dispositions = json.loads(disposition_path.read_text(encoding="utf-8"))
        dispositions["dispositions"]["generated_build_evidence"].append(
            "evidence/broken.mdx"
        )
        disposition_path.write_text(json.dumps(dispositions), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "missing source-derived frontmatter fields"):
            quality.apply_repository(root)
        self.assertEqual(
            before,
            (root / "developers/example.mdx").read_text(encoding="utf-8"),
        )

    def test_six_repaired_sources_have_parseable_title_and_description(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        paths = (
            "chlom/insights/inside-chlom-architecture-for-support-technical.mdx",
            "security/chlom-wallet-continuity-penta-v2-threat-model.mdx",
            "changelog/phase-2-99-execution-builder-agent-2026-08-23.mdx",
            "chlom/architecture-overview.mdx",
            "chlom/core-four-framework.mdx",
            "chlom/fingerprint-ids.mdx",
        )
        for relative in paths:
            with self.subTest(path=relative):
                text = (repository / relative).read_text(encoding="utf-8")
                parsed = quality.split_frontmatter(text)
                self.assertIsNotNone(parsed)
                assert parsed is not None
                values = quality.parse_frontmatter(parsed[0]).values
                self.assertTrue(values.get("title"))
                self.assertTrue(values.get("description"))
                self.assertGreater(len(text.splitlines()), 3)

    def test_unlisted_profile_override_defaults_are_conservative(self) -> None:
        cases = {
            "developers/runbooks/chlom-agentic-foundry-production-activation": (
                "operator", "runbook", "unresolved"
            ),
            "commerce/thriveevergreen-production-fabric": (
                "historical", "historical_record", "superseded"
            ),
            "security/chlom-wallet-continuity-penta-v2-threat-model": (
                "developer", "policy", "unresolved"
            ),
            "chlom/insights/inside-chlom-architecture-for-support-technical": (
                "rights_support", "support", "unresolved"
            ),
        }
        values = {"title": "Fixture", "description": "Fixture description."}
        for route, expected in cases.items():
            with self.subTest(route=route):
                profile = quality.profile_for_page(
                    route,
                    (),
                    values,
                    {},
                    "operational_reference_direct_link",
                )
                self.assertEqual(
                    (profile.primary_audience, profile.page_type, profile.content_state),
                    expected,
                )


class PentaDocsLegacyQualityCompatibilityTests(unittest.TestCase):
    def generated_text(self) -> tuple[str, str]:
        profile = quality.PageProfile(
            route="developers/example",
            path="developers/example.mdx",
            navigation_context=("Developers",),
            primary_audience="developer",
            page_type="developer",
            content_state="unresolved",
            orientation_component="Note",
            role_links=("/developers/overview", "/technology/api-integration-standards"),
        )
        content = "## Example\n\n[Body source](/knowledge/source-authority-hierarchy).\n"
        text = (
            "---\n"
            'title: "Example"\n'
            'description: "Fixture"\n'
            'standard_version: "1.0.0"\n'
            'primary_audience: "developer"\n'
            'page_type: "developer"\n'
            'content_state: "unresolved"\n'
            "---\n\n"
            f"{quality.orientation_block_v1(profile)}\n\n"
            f"{content}"
        )
        expected = (
            "---\n"
            'title: "Example"\n'
            'description: "Fixture"\n'
            "---\n\n"
            f"{content}"
        )
        return text, expected

    def test_generated_envelope_is_removed_idempotently(self) -> None:
        text, expected = self.generated_text()
        normalized = substantive_wave1.normalize_pentadocs_envelope(text)
        self.assertEqual(normalized, expected)
        self.assertEqual(
            substantive_wave1.normalize_pentadocs_envelope(normalized),
            normalized,
        )
        self.assertIn("## Example", normalized)

    def test_managed_v2_envelope_is_removed_but_tail_is_preserved(self) -> None:
        profile = quality.PageProfile(
            route="developers/example",
            path="developers/example.mdx",
            navigation_context=("Developers",),
            primary_audience="developer",
            page_type="developer",
            content_state="current_with_holds",
            orientation_component="Note",
            role_links=("/developers/overview", "/technology/api-integration-standards"),
        )
        content = "## Example\n\n[Body source](/knowledge/source-authority-hierarchy).\n"
        frontmatter = (
            'title: "Example"\n'
            'description: "Fixture"\n'
            'standard_version: "1.0.0"\n'
            'primary_audience: "developer"\n'
            'page_type: "developer"\n'
            'content_state: "current_with_holds"'
        )
        text = (
            f"---\n{frontmatter}\n---\n\n"
            f"{quality.orientation_block(profile, 'Example', 'Fixture')}\n\n"
            f"{content}"
        )
        expected = (
            "---\n"
            'title: "Example"\n'
            'description: "Fixture"\n'
            "---\n\n"
            f"{content}"
        )
        normalized = substantive_wave1.normalize_pentadocs_envelope(text)
        self.assertEqual(normalized, expected)
        self.assertEqual(
            substantive_wave1.normalize_pentadocs_envelope(normalized),
            normalized,
        )

        edited = text.replace("builders and integrators", "custom integration readers", 1)
        self.assertIn(
            quality.ORIENTATION_MARKER,
            substantive_wave1.normalize_pentadocs_envelope(edited),
        )

    def test_custom_orientation_callout_is_preserved(self) -> None:
        text, _expected = self.generated_text()
        generated = quality.orientation_block_v1(
            quality.PageProfile(
                route="developers/example",
                path="developers/example.mdx",
                navigation_context=(),
                primary_audience="developer",
                page_type="developer",
                content_state="unresolved",
                orientation_component="Note",
                role_links=("/developers/overview", "/technology/api-integration-standards"),
            )
        )
        custom = """{/* pentadocs:audience-orientation:v1 */}
<Info>
  **Audience:** integration reviewers. Use the [release workflow](/workflows/product-release) and [API standard](/technology/api-integration-standards).
</Info>"""
        text = text.replace(generated, custom, 1)
        normalized = substantive_wave1.normalize_pentadocs_envelope(text)
        self.assertIn(custom, normalized)
        for key in substantive_wave1.PENTADOCS_PROFILE_FIELDS:
            self.assertNotIn(f"{key}:", normalized)

    def test_route_quality_excludes_generated_role_links(self) -> None:
        text, expected = self.generated_text()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / "example.mdx").write_text(text, encoding="utf-8")
        with mock.patch.object(substantive_wave1, "ROOT", root):
            result = substantive_wave1.route_quality("/example")

        self.assertEqual(
            result["quality_algorithm"],
            substantive_wave1.ROUTE_QUALITY_ALGORITHM,
        )
        self.assertEqual(result["internal_link_count"], 1)
        self.assertEqual(result["body_characters"], len(expected))
        self.assertEqual(
            result["sha256"],
            hashlib.sha256(expected.encode("utf-8")).hexdigest(),
        )

    def test_historical_profile_cannot_qualify_as_current_successor(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        body = "Current-source-looking body. " * 80
        (root / "historical.mdx").write_text(
            """---
title: "Historical fixture"
description: "A preserved lineage page."
standard_version: "1.0.0"
primary_audience: "historical"
page_type: "historical_record"
content_state: "superseded"
---

{/* pentadocs:audience-orientation:v1 */}
<Warning>
  **Audience:** lineage reviewers. Use the [first record](/knowledge/source-register) and [second record](/knowledge/source-authority-hierarchy).
</Warning>

## Preserved body

"""
            + body,
            encoding="utf-8",
        )
        policy = {
            "canonical_anchor_routes": ["/historical"],
            "minimum_anchor_body_characters": 100,
            "minimum_anchor_internal_links": 2,
        }
        row = {"target_routes": ["/historical"]}
        with mock.patch.object(substantive_wave1, "ROOT", root):
            anchor, checked = substantive_wave1.choose_anchor(row, policy)

        self.assertIsNone(anchor)
        self.assertEqual(len(checked), 1)
        self.assertFalse(checked[0]["editorial_current_successor_eligible"])
        self.assertEqual(
            checked[0]["editorial_eligibility_reasons"],
            ["primary_audience_historical", "content_state_superseded"],
        )

    def test_state_lane_precedence_defers_before_broad_anchor_scan(self) -> None:
        base_row = {
            "inventory_id": "HC-STATE-LANE",
            "article_id": "ct.hc.state-lane",
            "legacy_section": "CHLOM",
            "legacy_subcategory": "Contracts",
            "legacy_title": "Machine contract continuity",
            "priority": "P0",
            "disposition_candidate": "merged_into_current_successor",
            "current_state_candidate": "machine_contract_reconciliation",
            "target_routes": ["/chlom/registry-model"],
            "missing_target_routes": [],
            "flags": ["specialist_review_required"],
            "candidate_cohort": "fixture",
        }
        wave1_policy = substantive_wave1.load_json(substantive_wave1.POLICY_PATH)
        with mock.patch.object(substantive_wave1, "choose_anchor") as generic_scan:
            state, record = substantive_wave1.classify(base_row, wave1_policy)
        self.assertEqual(state, "held")
        self.assertIn(
            "deferred_to_wave_2_machine_contract_state_lane",
            record["hold_reasons"],
        )
        self.assertEqual(record["anchor_quality_checked"], [])
        self.assertEqual(
            record["source_specialist_review_flags"],
            ["specialist_review_required"],
        )
        generic_scan.assert_not_called()

        identity_row = {
            **base_row,
            "current_state_candidate": "identity_trust_reconciliation",
            "legacy_title": "Identity trust continuity",
        }
        wave2_policy = substantive_wave2.load_json(substantive_wave2.POLICY_PATH)
        with mock.patch.object(substantive_wave2, "choose_anchor") as broad_scan:
            state, record = substantive_wave2.classify(identity_row, wave2_policy, set())
        self.assertEqual(state, "held")
        self.assertIn(
            "deferred_to_wave_3_identity_evidence_state_lane",
            record["hold_reasons"],
        )
        self.assertEqual(record["anchor_quality_checked"], [])
        broad_scan.assert_not_called()

        machine_row = {
            **base_row,
            "target_routes": [
                "/chlom/registry-model",
                "/chlom/ecosystem-integrations",
            ],
        }
        qualified = {
            "editorial_current_successor_eligible": True,
            "body_characters": 9000,
            "internal_link_count": 9,
            "route": "/chlom/ecosystem-integrations",
        }
        with mock.patch.object(
            substantive_wave2.wave1,
            "route_quality",
            return_value=qualified,
        ) as quality_scan:
            anchor, checked = substantive_wave2.choose_anchor(machine_row, wave2_policy)
        self.assertEqual(anchor, "/chlom/ecosystem-integrations")
        self.assertEqual(checked, [qualified])
        quality_scan.assert_called_once_with("/chlom/ecosystem-integrations")

    def test_semantic_state_lanes_produce_current_wave_counts(self) -> None:
        results = [
            substantive_wave1.build(),
            substantive_wave2.build(),
            substantive_wave3.build(),
            substantive_wave4.build(),
            substantive_wave5.build(),
            substantive_wave6.build(),
        ]
        self.assertEqual([result["selected_count"] for result in results], [12, 19, 17, 5, 1, 3])
        self.assertEqual(
            results[0]["hold_reason_counts"]["deferred_to_wave_2_machine_contract_state_lane"],
            19,
        )
        self.assertEqual(
            results[0]["hold_reason_counts"]["deferred_to_wave_3_identity_evidence_state_lane"],
            17,
        )
        self.assertEqual(
            results[1]["hold_reason_counts"]["deferred_to_wave_3_identity_evidence_state_lane"],
            17,
        )

    def test_structural_gate_is_fence_aware_and_allows_leaf_components(self) -> None:
        body = """## Overview

<Columns cols={2}>
<Card title="One">
### Detail
</Card>
</Columns>

<Icon icon="check" />
<Badge>Current</Badge>
<Color value="#fff" />
<Tree.File name="fixture.mdx" />

```mdx
<Columns>
#### A skipped example heading
```
"""
        errors, facts = quality.validate_mdx_structure(body)
        self.assertEqual(errors, [])
        self.assertEqual(facts["unclosed_fences"], 0)
        self.assertEqual(facts["heading_level_skips"], 0)
        self.assertEqual(facts["component_balance_errors"], 0)
        self.assertEqual(facts["known_component_tags_checked"], 4)

    def test_structural_gate_reports_unclosed_fence_heading_skip_and_component_crossing(self) -> None:
        body = """## Overview
#### Skipped detail

<Columns cols={2}>
<Card title="One">
</Columns>
</Card>

```mdx
unterminated example
"""
        errors, facts = quality.validate_mdx_structure(body)
        self.assertTrue(any("code fence is not closed" in error for error in errors))
        self.assertTrue(any("heading level skips from H2 to H4" in error for error in errors))
        self.assertTrue(any("crosses <Card>" in error for error in errors))
        self.assertEqual(facts["unclosed_fences"], 1)
        self.assertEqual(facts["heading_level_skips"], 1)
        self.assertGreater(facts["component_balance_errors"], 0)

    def test_image_accessibility_gate_and_media_human_review_diagnostic(self) -> None:
        valid = f"""## Media

![Architecture overview](/assets/architecture.png)

{quality.DECORATIVE_IMAGE_MARKER}
![](/assets/divider.png)

<Image src="/assets/decorative.png" alt="" role="presentation" />
<img src="/assets/chart.png" alt="Quarterly values by category" />

```mdx
![](/assets/example-only.png)
<Image src="/assets/example-only.png" />
```

<Video src="/assets/overview.mp4" />
"""
        errors, facts = quality.validate_image_accessibility(valid)
        self.assertEqual(errors, [])
        self.assertEqual(facts["markdown_images"], 2)
        self.assertEqual(facts["jsx_images"], 2)
        self.assertEqual(facts["media_human_review_occurrences"], 1)

        invalid = """## Media

![](/assets/no-alt.png)
<Image src="/assets/missing-alt.png" />
<img src="/assets/empty-alt.png" alt="" />
"""
        errors, facts = quality.validate_image_accessibility(invalid)
        self.assertEqual(len(errors), 3)
        self.assertEqual(facts["markdown_images"], 1)
        self.assertEqual(facts["jsx_images"], 2)

    def test_custom_orientation_cannot_count_a_redirect_source_as_governing_link(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / "current.mdx").write_text("---\ntitle: Current\n---\n", encoding="utf-8")
        (root / "legacy.mdx").write_text("---\ntitle: Legacy\n---\n", encoding="utf-8")
        (root / "governing.mdx").write_text(
            "---\ntitle: Governing\n---\n", encoding="utf-8"
        )
        block = (
            "[Legacy route](/legacy) and [governing source](/governing)"
        )
        valid, self_links, invalid = quality.valid_orientation_link_records(
            root,
            "current",
            block,
            {"legacy"},
        )
        self.assertEqual(valid, (("governing source", "/governing"),))
        self.assertEqual(self_links, ())
        self.assertEqual(invalid, ("/legacy",))


if __name__ == "__main__":
    unittest.main()
